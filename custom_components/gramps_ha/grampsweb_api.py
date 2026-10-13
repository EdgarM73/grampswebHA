"""API client for Gramps Web.

Performance note: all data is loaded in bulk (people, events, families) with a
handful of paginated requests and joined locally. The old implementation issued
several HTTP requests *per person*, which made a refresh take minutes on larger
trees.
"""

import calendar
import hashlib
import logging
import os
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta

import requests

_LOGGER = logging.getLogger(__name__)

PAGE_SIZE = 1000

PERSON_KEYS = (
    "handle,primary_name,gender,event_ref_list,birth_ref_index,death_ref_index,"
    "family_list,media_list"
)
EVENT_KEYS = "handle,type,date,description"
RELATION_TTL_SECONDS = 7 * 24 * 3600
RELATION_RETRY_SECONDS = 3600

EVENT_TYPES_DE = {
    "birth": "Geburt",
    "death": "Tod",
    "marriage": "Heirat",
    "engagement": "Verlobung",
    "divorce": "Scheidung",
    "baptism": "Taufe",
    "christening": "Taufe",
    "burial": "Beerdigung",
    "cremation": "Einäscherung",
    "residence": "Wohnort",
    "occupation": "Beruf",
    "emigration": "Auswanderung",
    "immigration": "Einwanderung",
    "census": "Volkszählung",
    "graduation": "Abschluss",
    "education": "Ausbildung",
    "retirement": "Ruhestand",
}
FAMILY_KEYS = "handle,father_handle,mother_handle,event_ref_list"


ANNIVERSARY_NAMES = {
    "de": {
        25: "Silberhochzeit",
        30: "Perlenhochzeit",
        40: "Rubinhochzeit",
        50: "Goldene Hochzeit",
        60: "Diamantene Hochzeit",
        65: "Eiserne Hochzeit",
        70: "Gnadenhochzeit",
    },
    "en": {
        25: "Silver wedding anniversary",
        30: "Pearl wedding anniversary",
        40: "Ruby wedding anniversary",
        50: "Golden wedding anniversary",
        60: "Diamond wedding anniversary",
        65: "Sapphire wedding anniversary",
        70: "Platinum wedding anniversary",
    },
}


def milestone_label(kind: str, years: int, lang: str = "de") -> str | None:
    """Return a label if `years` is a round number for this kind of date.

    Birthdays: every 10th and the 18th. Anniversaries: every 5th year.
    Deathdays: every 10th year.
    """
    if years is None or years <= 0:
        return None
    de = str(lang).lower().startswith("de")
    if kind == "birthday" and (years % 10 == 0 or years == 18):
        return f"{years}. Geburtstag" if de else f"{years}th birthday"
    if kind == "anniversary" and years % 5 == 0:
        names = ANNIVERSARY_NAMES["de" if de else "en"]
        special = names.get(years)
        if special:
            return f"{special} ({years})"
        return f"{years}. Hochzeitstag" if de else f"{years}th wedding anniversary"
    if kind == "deathday" and years % 10 == 0:
        return f"{years}. Todestag" if de else f"{years}th death anniversary"
    return None


class GrampsWebAPI:
    """Class to interact with Gramps Web API."""

    def __init__(
        self,
        url: str,
        username: str = None,
        password: str = None,
        hass_config_path: str = None,
        language: str = "de",
    ):
        """Initialize the API client."""
        self.language = language or "de"
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token = None
        self._session = requests.Session()
        self.hass_config_path = hass_config_path

        # Create images directory
        if self.hass_config_path:
            self.images_dir = os.path.join(self.hass_config_path, "www", "gramps")
            os.makedirs(self.images_dir, exist_ok=True)

        # Bulk snapshot of the tree (people/events/families), shared by all
        # get_* methods so a coordinator refresh loads the database only once.
        self._snapshot = None
        self._snapshot_timestamp = None
        self._snapshot_loaded_at = None
        self._snapshot_lock = threading.Lock()
        # handle -> (expires_at, relationship string or None)
        self._relation_cache = {}
        self._cache_ttl_seconds = 3600  # Cache for 1 hour

    # ------------------------------------------------------------------ HTTP

    def _authenticate(self):
        """Authenticate with the Gramps Web API."""
        if not self.username or not self.password:
            return True

        try:
            response = self._session.post(
                f"{self.url}/api/token/",
                json={
                    "username": self.username,
                    "password": self.password,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("access_token")

            if self.token:
                self._session.headers.update({"Authorization": f"Bearer {self.token}"})
            return True
        except Exception as err:
            _LOGGER.warning("Failed to authenticate with Gramps Web: %s", err)
            return False

    def _get(self, endpoint: str, params: dict = None, quiet: bool = False):
        """Make a GET request to the API."""
        if not self.token and self.username:
            self._authenticate()

        try:
            url = f"{self.url}/api/{endpoint}"
            _LOGGER.debug("GET request to: %s", url)

            response = self._session.get(url, params=params, timeout=60)
            if response.status_code == 401 and self.username:
                # Token expired: re-authenticate once and retry
                self.token = None
                if self._authenticate():
                    response = self._session.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as err:
            if quiet:
                _LOGGER.debug("API request to %s failed: %s", endpoint, err)
            else:
                _LOGGER.error(
                    "API request to %s failed: %s", endpoint, err, exc_info=True
                )
            raise

    def _get_all(self, endpoint: str, keys: str) -> list[dict]:
        """Fetch every object of a collection using paginated, key-limited requests."""
        results: list[dict] = []
        page = 1
        use_keys = True
        while True:
            params = {"page": page, "pagesize": PAGE_SIZE}
            if use_keys:
                params["keys"] = keys
            try:
                chunk = self._get(endpoint, params)
            except requests.HTTPError:
                if use_keys and page == 1:
                    # Older servers may not support `keys`: retry without it
                    use_keys = False
                    continue
                raise
            if not isinstance(chunk, list):
                chunk = chunk.get("results", []) if isinstance(chunk, dict) else []
            results.extend(chunk)
            if len(chunk) < PAGE_SIZE:
                return results
            page += 1

    # -------------------------------------------------------------- snapshot

    def _load_snapshot(self) -> dict:
        """Return the (cached) in-memory snapshot of people, events and families."""
        with self._snapshot_lock:
            if self._snapshot is not None and self._snapshot_timestamp is not None:
                age = (datetime.now() - self._snapshot_timestamp).total_seconds()
                if age < self._cache_ttl_seconds:
                    return self._snapshot

            _LOGGER.info("Loading Gramps Web data (bulk)")
            start = datetime.now()
            try:
                people = self._get_all("people/", PERSON_KEYS)
                events = self._get_all("events/", EVENT_KEYS)
                families = self._get_all("families/", FAMILY_KEYS)
            except Exception as err:
                if self._snapshot is not None:
                    # Server unreachable/token problem: keep showing the last
                    # known data instead of blanking the sensors.
                    _LOGGER.warning(
                        "Could not refresh Gramps Web data, using data from %s: %s",
                        self._snapshot_loaded_at,
                        err,
                    )
                    # Retry in ~5 minutes rather than on every call
                    self._snapshot_timestamp = datetime.now() - timedelta(
                        seconds=self._cache_ttl_seconds - 300
                    )
                    return self._snapshot
                raise

            try:
                # home person + object counts (best effort)
                metadata = self._get("metadata/", quiet=True) or {}
            except Exception:
                metadata = {}

            snapshot = {
                "metadata": metadata,
                "people": people,
                "events": {e["handle"]: e for e in events if e.get("handle")},
                "families": {f["handle"]: f for f in families if f.get("handle")},
                "people_by_handle": {p["handle"]: p for p in people if p.get("handle")},
            }
            self._snapshot = snapshot
            self._snapshot_timestamp = self._snapshot_loaded_at = datetime.now()
            _LOGGER.info(
                "Loaded %s people, %s events, %s families in %.1fs",
                len(people),
                len(events),
                len(families),
                (datetime.now() - start).total_seconds(),
            )
            return snapshot

    def invalidate_cache(self) -> None:
        """Force the next call to reload data from the server."""
        with self._snapshot_lock:
            self._snapshot_timestamp = None

    def get_people(self):
        """Get all people (bulk, cached)."""
        return self._load_snapshot()["people"]

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _ref_handle(ref) -> str | None:
        """Extract a handle from an event/media reference (dict) or plain handle."""
        if isinstance(ref, str):
            handle = ref
        elif isinstance(ref, dict):
            handle = ref.get("ref") or ref.get("handle") or ref.get("hlink")
        else:
            return None
        if not handle or not isinstance(handle, str):
            return None
        return handle.rstrip("/").split("/")[-1]

    @staticmethod
    def _event_type(event: dict) -> str:
        etype = event.get("type", {})
        string = etype.get("string", "") if isinstance(etype, dict) else str(etype)
        return string.lower()

    def _parse_dateval(self, dateval):
        """Convert Gramps date structures into a Python date using safe heuristics."""
        try:
            # Accept dict structures: {"val": [year, month, day]} or start/end
            if isinstance(dateval, dict):
                if "val" in dateval:
                    dateval = dateval.get("val")
                elif "start" in dateval:  # sometimes ranges
                    dateval = dateval.get("start")

            if not isinstance(dateval, (list, tuple)):
                return None

            # We only need the first three entries for day/month/year
            vals = list(dateval[:3])
            if len(vals) < 3:
                return None

            try:
                vals = [int(v) for v in vals]
            except Exception:
                return None

            combinations = [
                (2, 1, 0),  # dateval = [day, month, year]
                (0, 1, 2),  # dateval = [year, month, day]
                (0, 2, 1),  # dateval = [year, day, month]
            ]

            for y_idx, m_idx, d_idx in combinations:
                year, month, day = vals[y_idx], vals[m_idx], vals[d_idx]
                if year < 100:
                    continue
                if not (1 <= month <= 12 and 1 <= day <= 31):
                    continue
                try:
                    return date(year, month, day)
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def _event_date(self, event: dict | None):
        """Parsed date of an event dict, or None."""
        if not event:
            return None
        dateval = event.get("date", {})
        if isinstance(dateval, dict):
            raw = dateval.get("dateval") or dateval.get("val") or dateval.get("start")
        else:
            raw = dateval
        return self._parse_dateval(raw)

    def _person_event_date(self, person: dict, events: dict, kind: str, ref_key: str):
        """Date of the person's `kind` ("birth"/"death") event, or None."""
        refs = person.get("event_ref_list", []) or []
        idx = person.get(ref_key, -1)

        # Prefer the primary reference Gramps maintains for birth/death
        if isinstance(idx, int) and 0 <= idx < len(refs):
            event = events.get(self._ref_handle(refs[idx]))
            if event and kind in self._event_type(event):
                parsed = self._event_date(event)
                if parsed:
                    return parsed

        # Fall back to any matching event on the person
        for ref in refs:
            event = events.get(self._ref_handle(ref))
            if event and kind in self._event_type(event):
                parsed = self._event_date(event)
                if parsed:
                    return parsed
        return None

    @staticmethod
    def _date_in_year(original: date, year: int) -> date:
        """Same month/day in `year` (Feb 29 -> Feb 28 in non-leap years)."""
        day = original.day
        if original.month == 2 and day == 29 and not calendar.isleap(year):
            day = 28
        return date(year, original.month, day)

    @classmethod
    def _next_occurrence(cls, original: date, today: date) -> date:
        """Next date >= today with the same month/day."""
        candidate = cls._date_in_year(original, today.year)
        if candidate < today:
            candidate = cls._date_in_year(original, today.year + 1)
        return candidate

    def _get_person_name(self, person: dict):
        """Get person's display name."""
        try:
            primary_name = person.get("primary_name", {})
            first_name = primary_name.get("first_name", "")

            surname_list = primary_name.get("surname_list", [])
            surname = ""
            if surname_list:
                surname = surname_list[0].get("surname", "")

            full_name = f"{first_name} {surname}".strip()
            return full_name if full_name else "Unknown"
        except Exception:
            return "Unknown"

    def _get_person_image_url(
        self, person: dict, grayscale: bool = False
    ) -> str | None:
        """Get the URL for a person's profile image (optionally in grayscale)."""
        try:
            person_handle = person.get("handle", "")
            if not person_handle:
                return None

            media_list = person.get("media_list", [])
            if not media_list:
                return None

            media_handle = self._ref_handle(media_list[0])
            if not media_handle:
                return None

            thumbnail_url = f"{self.url}/api/media/{media_handle}/thumbnail/200"

            if self.hass_config_path:
                return self._download_image(
                    thumbnail_url, person_handle, media_handle, grayscale
                )

            return thumbnail_url

        except Exception as err:
            _LOGGER.debug("Could not get person image: %s", err)
            return None

    def _download_image(
        self,
        image_url: str,
        person_handle: str,
        media_handle: str,
        grayscale: bool = False,
    ) -> str | None:
        """Download image and return local path (grayscale copy if requested)."""
        try:
            filename_hash = hashlib.md5(
                f"{person_handle}_{media_handle}".encode()
            ).hexdigest()
            filename = f"{filename_hash}.jpg"
            filepath = os.path.join(self.images_dir, filename)

            if not os.path.exists(filepath):
                response = self._session.get(image_url, timeout=10)
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(response.content)
                _LOGGER.info("Downloaded image to: %s", filepath)

            if not grayscale:
                return f"/local/gramps/{filename}"

            gray_name = f"{filename_hash}_gray.jpg"
            gray_path = os.path.join(self.images_dir, gray_name)
            if os.path.exists(gray_path):
                return f"/local/gramps/{gray_name}"

            try:
                from PIL import Image  # bundled with Home Assistant

                with Image.open(filepath) as img:
                    img.convert("L").save(gray_path, "JPEG", quality=85)
                return f"/local/gramps/{gray_name}"
            except Exception as gray_err:
                _LOGGER.warning(
                    "Could not create grayscale image, using color: %s", gray_err
                )
                return f"/local/gramps/{filename}"

        except Exception as err:
            _LOGGER.warning("Failed to download image: %s", err)
            return image_url  # Fallback to remote URL

    # -------------------------------------------------------------- birthdays

    def get_birthdays(self, limit: int = 50):
        """Get upcoming birthdays of living people."""
        try:
            snap = self._load_snapshot()
            events = snap["events"]
            today = date.today()

            entries = []
            for person in snap["people"]:
                # Deceased people have no birthday
                if person.get("death_ref_index", -1) != -1:
                    continue
                birth_date = self._person_event_date(
                    person, events, "birth", "birth_ref_index"
                )
                if not birth_date:
                    continue
                entries.append((self._next_occurrence(birth_date, today), birth_date, person))

            entries.sort(key=lambda e: e[0])

            # Only touch images for the entries we actually return
            result = []
            for next_birthday, birth_date, person in entries[:limit]:
                item = {
                    "person_name": self._get_person_name(person),
                    "birth_date": birth_date.isoformat(),
                    "next_birthday": next_birthday.isoformat(),
                    "age": next_birthday.year - birth_date.year,
                    "days_until": (next_birthday - today).days,
                }
                label = milestone_label("birthday", item["age"], self.language)
                if label:
                    item["milestone"] = label
                relationship = self._relationship(person.get("handle"))
                if relationship:
                    item["relationship"] = relationship
                image_url = self._get_person_image_url(person)
                if image_url:
                    item["image_url"] = image_url
                if person.get("handle"):
                    item["person_handle"] = person["handle"]
                result.append(item)

            _LOGGER.info("Birthdays: %s candidates, returning %s", len(entries), len(result))
            return result

        except Exception as err:
            _LOGGER.error("Failed to fetch birthdays: %s", err, exc_info=True)
            return []

    # -------------------------------------------------------------- deathdays

    def get_deathdays(self, limit: int = 50):
        """Get upcoming deathdays/memorial dates."""
        try:
            snap = self._load_snapshot()
            events = snap["events"]
            today = date.today()

            entries = []
            for person in snap["people"]:
                if person.get("death_ref_index", -1) < 0:
                    continue
                death_date = self._person_event_date(
                    person, events, "death", "death_ref_index"
                )
                if not death_date:
                    continue
                entries.append((self._next_occurrence(death_date, today), death_date, person))

            entries.sort(key=lambda e: e[0])

            result = []
            for next_deathday, death_date, person in entries[:limit]:
                item = {
                    "person_name": self._get_person_name(person),
                    "death_date": death_date.isoformat(),
                    "next_deathday": next_deathday.isoformat(),
                    "years_ago": today.year - death_date.year,
                    "days_until": (next_deathday - today).days,
                    "person_handle": person.get("handle"),
                }
                label = milestone_label(
                    "deathday", next_deathday.year - death_date.year, self.language
                )
                if label:
                    item["milestone"] = label
                relationship = self._relationship(person.get("handle"))
                if relationship:
                    item["relationship"] = relationship
                image_url = self._get_person_image_url(person)
                if image_url:
                    item["image_url"] = image_url
                result.append(item)

            _LOGGER.info("Deathdays: %s candidates, returning %s", len(entries), len(result))
            return result

        except Exception as err:
            _LOGGER.error("Failed to get deathdays: %s", err, exc_info=True)
            return []

    # ---------------------------------------------------------- anniversaries

    def get_anniversaries(self, limit: int = 50):
        """Get upcoming wedding/engagement anniversaries from family events."""
        try:
            snap = self._load_snapshot()
            events = snap["events"]
            people_by_handle = snap["people_by_handle"]
            today = date.today()

            entries = []
            seen_events = set()
            for family_handle, family in snap["families"].items():
                partners = [
                    people_by_handle[h]
                    for h in (family.get("father_handle"), family.get("mother_handle"))
                    if h and h in people_by_handle
                ]
                if not partners:
                    continue

                for ref in family.get("event_ref_list", []) or []:
                    ev_handle = self._ref_handle(ref)
                    event = events.get(ev_handle)
                    if not event or ev_handle in seen_events:
                        continue
                    etype = self._event_type(event)
                    if "marriage" not in etype and "engagement" not in etype:
                        continue
                    marriage_date = self._event_date(event)
                    if not marriage_date:
                        continue
                    seen_events.add(ev_handle)
                    entries.append(
                        (
                            self._next_occurrence(marriage_date, today),
                            marriage_date,
                            family_handle,
                            partners,
                        )
                    )

            entries.sort(key=lambda e: e[0])

            result = []
            for next_anniv, marriage_date, family_handle, partners in entries[:limit]:
                names = sorted(self._get_person_name(p) for p in partners)
                item = {
                    "person_name": " & ".join(names),
                    "marriage_date": marriage_date.isoformat(),
                    "next_anniversary": next_anniv.isoformat(),
                    "years_together": today.year - marriage_date.year,
                    "days_until": (next_anniv - today).days,
                    "family_handle": family_handle,
                }
                label = milestone_label(
                    "anniversary", next_anniv.year - marriage_date.year, self.language
                )
                if label:
                    item["milestone"] = label
                for idx, partner in enumerate(partners[:2], start=1):
                    deceased = partner.get("death_ref_index", -1) != -1
                    item[f"person{idx}_deceased"] = deceased
                    relationship = self._relationship(partner.get("handle"))
                    if relationship:
                        item[f"relationship_person{idx}"] = relationship
                    image = self._get_person_image_url(partner, grayscale=deceased)
                    if image:
                        item[f"image_url_person{idx}"] = image
                result.append(item)

            _LOGGER.info("Anniversaries: %s candidates, returning %s", len(entries), len(result))
            return result

        except Exception as err:
            _LOGGER.error("Failed to get anniversaries: %s", err, exc_info=True)
            return []

    # ------------------------------------------------- calendar / milestones

    def _snapshot_any_age(self) -> dict:
        """Existing snapshot regardless of age (loads it if there is none yet)."""
        snap = self._snapshot
        return snap if snap is not None else self._load_snapshot()

    def _date_sources(
        self, snap: dict, include_deaths: bool, include_anniversaries: bool
    ) -> list[dict]:
        """All recurring dates as dicts: kind, date, name."""
        events = snap["events"]
        sources = []

        for person in snap["people"]:
            name = self._get_person_name(person)
            if person.get("death_ref_index", -1) == -1:
                born = self._person_event_date(person, events, "birth", "birth_ref_index")
                if born:
                    sources.append({"kind": "birthday", "date": born, "name": name})
            elif include_deaths:
                died = self._person_event_date(person, events, "death", "death_ref_index")
                if died:
                    sources.append({"kind": "deathday", "date": died, "name": name})

        if include_anniversaries:
            people = snap["people_by_handle"]
            seen = set()
            for family in snap["families"].values():
                partners = [
                    people[h]
                    for h in (family.get("father_handle"), family.get("mother_handle"))
                    if h and h in people
                ]
                if not partners:
                    continue
                name = " & ".join(sorted(self._get_person_name(p) for p in partners))
                for ref in family.get("event_ref_list", []) or []:
                    ev_handle = self._ref_handle(ref)
                    event = events.get(ev_handle)
                    if not event or ev_handle in seen:
                        continue
                    etype = self._event_type(event)
                    if "marriage" not in etype and "engagement" not in etype:
                        continue
                    when = self._event_date(event)
                    if when:
                        seen.add(ev_handle)
                        sources.append({"kind": "anniversary", "date": when, "name": name})
        return sources

    def _summary(self, kind: str, name: str, years: int, label: str | None) -> str:
        """Short calendar title for one occurrence."""
        de = str(self.language).lower().startswith("de")
        if label:
            return f"\U0001F389 {name} \u2013 {label}"
        if kind == "birthday":
            return f"\U0001F382 {name} ({years})"
        if kind == "deathday":
            suffix = f"{years}. Todestag" if de else f"{years}th death anniversary"
            return f"\U0001F56F\uFE0F {name} ({suffix})"
        suffix = f"{years}. Hochzeitstag" if de else f"{years}th wedding anniversary"
        return f"\U0001F48D {name} ({suffix})"

    def get_calendar_events(
        self,
        start: date,
        end: date,
        include_deaths: bool = True,
        include_anniversaries: bool = True,
    ) -> list[dict]:
        """Every birthday/deathday/anniversary between `start` and `end` (inclusive)."""
        try:
            snap = self._snapshot_any_age()
            result = []
            for src in self._date_sources(snap, include_deaths, include_anniversaries):
                orig = src["date"]
                for year in range(start.year, end.year + 1):
                    when = self._date_in_year(orig, year)
                    years = year - orig.year
                    if years < 1 or not (start <= when <= end):
                        continue
                    label = milestone_label(src["kind"], years, self.language)
                    result.append(
                        {
                            "kind": src["kind"],
                            "date": when,
                            "name": src["name"],
                            "years": years,
                            "milestone": label,
                            "summary": self._summary(
                                src["kind"], src["name"], years, label
                            ),
                        }
                    )
            result.sort(key=lambda e: (e["date"], e["name"]))
            return result
        except Exception as err:
            _LOGGER.error("Failed to build calendar events: %s", err, exc_info=True)
            return []

    def get_milestones(
        self,
        days: int = 365,
        limit: int = 10,
        include_deaths: bool = True,
        include_anniversaries: bool = True,
    ) -> list[dict]:
        """Upcoming round birthdays/anniversaries within the next `days` days."""
        today = date.today()
        events = self.get_calendar_events(
            today,
            today + timedelta(days=days),
            include_deaths,
            include_anniversaries,
        )
        result = []
        for e in events:
            if not e["milestone"]:
                continue
            result.append(
                {
                    "kind": e["kind"],
                    "person_name": e["name"],
                    "date": e["date"].isoformat(),
                    "days_until": (e["date"] - today).days,
                    "years": e["years"],
                    "label": e["milestone"],
                }
            )
            if len(result) >= limit:
                break
        return result

    # ------------------------------------------------ relationship to home

    def _relationship(self, handle: str | None) -> str | None:
        """Relationship of `handle` to the Gramps home person (cached for a week).

        Uses the home person configured in Gramps (`default_person`); returns
        None if there is none, the person is the home person, or no
        relationship exists.
        """
        snap = self._snapshot or {}
        home = (snap.get("metadata") or {}).get("default_person")
        if not handle or not home or handle == home:
            return None

        cached = self._relation_cache.get(handle)
        now = time.time()
        if cached and cached[0] > now:
            return cached[1]

        lang = str(self.language).replace("_", "-").split("-")[0]
        try:
            data = self._get(
                f"relations/{home}/{handle}", {"locale": lang}, quiet=True
            )
            value = str(data.get("relationship_string") or "").strip() or None
            self._relation_cache[handle] = (now + RELATION_TTL_SECONDS, value)
            return value
        except Exception:
            # Don't hammer the server: retry later
            self._relation_cache[handle] = (now + RELATION_RETRY_SECONDS, None)
            return None

    # --------------------------------------------------------- on this day

    @staticmethod
    def _event_type_raw(event: dict) -> str:
        etype = event.get("type", {})
        return str(etype.get("string", "") if isinstance(etype, dict) else etype)

    def get_on_this_day(self, limit: int = 20, today: date | None = None) -> list[dict]:
        """Everything in the tree that happened on today's day and month."""
        try:
            snap = self._snapshot_any_age()
            today = today or date.today()
            de = str(self.language).lower().startswith("de")

            owners: dict[str, list[str]] = {}
            for person in snap["people"]:
                name = self._get_person_name(person)
                for ref in person.get("event_ref_list", []) or []:
                    owners.setdefault(self._ref_handle(ref), []).append(name)
            people = snap["people_by_handle"]
            for family in snap["families"].values():
                partners = [
                    self._get_person_name(people[h])
                    for h in (family.get("father_handle"), family.get("mother_handle"))
                    if h and h in people
                ]
                if not partners:
                    continue
                for ref in family.get("event_ref_list", []) or []:
                    owners.setdefault(self._ref_handle(ref), []).append(
                        " & ".join(sorted(partners))
                    )

            result = []
            for handle, event in snap["events"].items():
                when = self._event_date(event)
                if not when or self._date_in_year(when, today.year) != today:
                    continue
                years_ago = today.year - when.year
                if years_ago < 1:
                    continue
                raw_type = self._event_type_raw(event)
                type_label = (
                    EVENT_TYPES_DE.get(raw_type.lower(), raw_type) if de else raw_type
                )
                names = sorted(set(owners.get(handle, [])))
                ago = f"vor {years_ago} Jahren" if de else f"{years_ago} years ago"
                text = f"{when.year} ({ago}): {type_label}"
                if names:
                    text += " \u2013 " + ", ".join(names)
                result.append(
                    {
                        "year": when.year,
                        "years_ago": years_ago,
                        "type": type_label,
                        "people": names,
                        "description": event.get("description") or None,
                        "text": text,
                    }
                )
            result.sort(key=lambda e: (e["year"], e["text"]))
            return result[:limit]
        except Exception as err:
            _LOGGER.error("Failed to build 'on this day': %s", err, exc_info=True)
            return []

    # ----------------------------------------------------------- statistics

    def get_statistics(self) -> dict:
        """Counts and a few derived numbers about the whole tree."""
        try:
            snap = self._snapshot_any_age()
            events = snap["events"]
            counts = (snap.get("metadata") or {}).get("object_counts") or {}
            today = date.today()

            def age(born: date, ref: date) -> int:
                return ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))

            living = deceased = male = female = 0
            no_birth = no_photo = 0
            ages, spans = [], []
            oldest = None
            surnames: Counter = Counter()

            for person in snap["people"]:
                gender = person.get("gender")
                if gender == 1:
                    male += 1
                elif gender == 0:
                    female += 1
                if not person.get("media_list"):
                    no_photo += 1
                surname_list = (person.get("primary_name") or {}).get("surname_list") or []
                if surname_list and surname_list[0].get("surname"):
                    surnames[surname_list[0]["surname"]] += 1

                born = self._person_event_date(person, events, "birth", "birth_ref_index")
                if not born:
                    no_birth += 1
                if person.get("death_ref_index", -1) == -1:
                    living += 1
                    if born:
                        years = age(born, today)
                        # ignore obviously incomplete data (no death recorded)
                        if 0 <= years <= 110:
                            ages.append(years)
                            if oldest is None or years > oldest["age"]:
                                oldest = {
                                    "name": self._get_person_name(person),
                                    "age": years,
                                    "birth_date": born.isoformat(),
                                }
                else:
                    deceased += 1
                    died = self._person_event_date(
                        person, events, "death", "death_ref_index"
                    )
                    if born and died:
                        span = age(born, died)
                        if 0 <= span <= 120:
                            spans.append(span)

            def avg(values):
                return round(sum(values) / len(values), 1) if values else None

            return {
                "people": counts.get("people", len(snap["people"])),
                "families": counts.get("families", len(snap["families"])),
                "events": counts.get("events", len(events)),
                "places": counts.get("places"),
                "media": counts.get("media"),
                "sources": counts.get("sources"),
                "citations": counts.get("citations"),
                "repositories": counts.get("repositories"),
                "notes": counts.get("notes"),
                "tags": counts.get("tags"),
                "living": living,
                "deceased": deceased,
                "male": male,
                "female": female,
                "without_birth_date": no_birth,
                "without_photo": no_photo,
                "avg_age_living": avg(ages),
                "avg_lifespan": avg(spans),
                "oldest_living": oldest,
                "top_surnames": [
                    {"surname": n, "count": c} for n, c in surnames.most_common(5)
                ],
            }
        except Exception as err:
            _LOGGER.error("Failed to build statistics: %s", err, exc_info=True)
            return {}
