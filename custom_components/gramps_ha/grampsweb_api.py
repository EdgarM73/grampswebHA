"""API client for Gramps Web."""

import logging
from datetime import datetime, date
import requests
import hashlib
import os

_LOGGER = logging.getLogger(__name__)


class GrampsWebAPI:
    """Class to interact with Gramps Web API."""

    def __init__(
        self,
        url: str,
        username: str = None,
        password: str = None,
        hass_config_path: str = None,
    ):
        """Initialize the API client."""
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

    def _get(self, endpoint: str, params: dict = None):
        """Make a GET request to the API."""
        if not self.token and self.username:
            self._authenticate()

        try:
            url = f"{self.url}/api/{endpoint}"
            _LOGGER.debug("GET request to: %s", url)

            response = self._session.get(
                url,
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            _LOGGER.debug("Response status: %s", response.status_code)
            return response.json()
        except Exception as err:
            _LOGGER.error("API request to %s failed: %s", endpoint, err, exc_info=True)
            raise

    def _resolve_event_handle(self, event_ref: dict) -> str | None:
        """Resolve an event handle from different possible keys."""
        if not event_ref:
            return None

        # Gramps may provide the event reference under different keys
        handle = None
        for key in ("ref", "handle", "hlink"):
            candidate = event_ref.get(key)
            if candidate:
                handle = candidate
                break

        if not handle or not isinstance(handle, str):
            return None

        # If the handle looks like a URL/path, keep only the last segment
        if "/" in handle:
            handle = handle.rstrip("/").split("/")[-1]

        return handle

    async def get_event_types(self) -> list[dict]:
        """Fetch all available event types from Gramps Web."""
        try:
            _LOGGER.info("Fetching all event types from Gramps Web...")

            # Try to fetch event types
            # Gramps Web API endpoint for event types
            event_types = self._get("event_types")

            if isinstance(event_types, list):
                _LOGGER.info("Found %s event types", len(event_types))
                for et in event_types:
                    _LOGGER.info("  - %s", et)
                return event_types
            elif isinstance(event_types, dict):
                # Sometimes returns dict with 'types' key
                types_list = event_types.get("types", event_types.get("results", []))
                _LOGGER.info("Found %s event types", len(types_list))
                for et in types_list:
                    _LOGGER.info("  - %s", et)
                return types_list

            _LOGGER.warning(
                "Unexpected event types response format: %s", type(event_types)
            )
            return []

        except Exception as err:
            _LOGGER.error("Failed to fetch event types: %s", err)
            return []

    async def get_all_events(self) -> list[dict]:
        """Fetch all events (not just birthdays) from Gramps Web."""
        try:
            _LOGGER.info("Fetching all events from Gramps Web...")

            events = self._get("events")

            if isinstance(events, dict):
                results = events.get("results", [])
                _LOGGER.info("Found %s events", len(results))
                return results
            elif isinstance(events, list):
                _LOGGER.info("Found %s events", len(events))
                return events

            return []

        except Exception as err:
            _LOGGER.error("Failed to fetch events: %s", err)
            return []

        return handle

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

            # Ensure all are integers
            try:
                vals = [int(v) for v in vals]
            except Exception:
                return None

            # Try combinations with a plausible year (>= 100)
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
                return date(year, month, day)

            return None
        except Exception:
            return None

    def _ensure_person_events(self, person: dict) -> dict:
        """Ensure a person dict has event_ref_list by refetching details if needed."""
        try:
            event_ref_list = person.get("event_ref_list", []) or []
            birth_ref_index = person.get("birth_ref_index", -1)

            # If we already have events and a birth ref index, keep as is
            if event_ref_list:
                return person

            handle = person.get("handle")
            if not handle:
                return person

            try:
                detailed = self._get(f"people/{handle}")
                # Only update the minimal fields we care about
                if detailed:
                    person["event_ref_list"] = detailed.get(
                        "event_ref_list", event_ref_list
                    )
                    person["birth_ref_index"] = detailed.get(
                        "birth_ref_index", birth_ref_index
                    )
                    person["death_ref_index"] = detailed.get(
                        "death_ref_index", person.get("death_ref_index", -1)
                    )
            except Exception as err:
                _LOGGER.debug("Could not fetch detailed person %s: %s", handle, err)

            return person
        except Exception:
            return person

    def get_people(self):
        """Get all people from Gramps Web."""
        _LOGGER.debug("Fetching people from %s", self.url)
        try:
            result = self._get("people/")
            _LOGGER.debug("API response type: %s", type(result))
            return result
        except Exception as err:
            _LOGGER.error("Failed to get people: %s", err, exc_info=True)
            raise

    def get_birthdays(self, limit: int = 50):
        """Get upcoming birthdays from Gramps Web."""
        try:
            _LOGGER.info("Fetching birthdays from Gramps Web API")

            # Get all people
            try:
                all_people = self.get_people()
                _LOGGER.info(
                    "Fetched %s people from Gramps Web",
                    len(all_people) if isinstance(all_people, list) else "unknown",
                )
            except Exception as people_err:
                _LOGGER.error("Failed to fetch people: %s", people_err, exc_info=True)
                return []

            if not all_people:
                _LOGGER.warning("No people data returned from Gramps Web")
                return []

            # Diagnostics: check sample people (first 5) for events
            _LOGGER.info("Running diagnostics on first 5 people...")
            for idx, person in enumerate(all_people[:5]):
                name = self._get_person_name(person)
                handle = person.get("handle")
                _LOGGER.info(
                    "Person %s (%s): event_ref_list=%s, birth_ref_index=%s",
                    idx + 1,
                    name,
                    len(person.get("event_ref_list", [])),
                    person.get("birth_ref_index", -1),
                )

                # Try fetching detailed info
                if handle:
                    try:
                        detailed = self._get(f"people/{handle}")
                        detailed_events = detailed.get("event_ref_list", [])
                        _LOGGER.info(
                            "  -> After detail fetch: event_ref_list=%s, birth_ref_index=%s",
                            len(detailed_events),
                            detailed.get("birth_ref_index", -1),
                        )
                        if detailed_events:
                            _LOGGER.info("  -> First event ref: %s", detailed_events[0])
                    except Exception as diag_err:
                        _LOGGER.warning("  -> Could not fetch details: %s", diag_err)

            # Filter to only include people with a birth date
            _LOGGER.info("Filtering %s people for birth dates...", len(all_people))
            people_data = []
            for idx, person in enumerate(all_people):
                if idx % 50 == 0:
                    _LOGGER.debug("Processed %s/%s people...", idx, len(all_people))
                person = self._ensure_person_events(person)
                if self._has_birth_date(person):
                    people_data.append(person)
            _LOGGER.info(
                "Filtered to %s people with birth dates (from %s total)",
                len(people_data),
                len(all_people),
            )

            if not people_data:
                _LOGGER.warning("No people with birth dates found")
                return []

            birthdays = []
            people_with_birth = 0
            living_people = 0
            deceased_people = 0

            today = date.today()
            current_year = today.year

            # Sample first person for debugging
            if people_data:
                sample = people_data[0]
                _LOGGER.debug("Sample person data: %s", sample)
                _LOGGER.debug(
                    "Sample birth_ref_index: %s", sample.get("birth_ref_index")
                )
                _LOGGER.debug(
                    "Sample event_ref_list length: %s",
                    len(sample.get("event_ref_list", [])),
                )
                if sample.get("event_ref_list"):
                    _LOGGER.debug(
                        "Sample first event: %s", sample.get("event_ref_list")[0]
                    )

            # Search for specific person: Erdal Akkaya
            for p in people_data:
                pname = self._get_person_name(p)
                if "erdal" in pname.lower() and "akkaya" in pname.lower():
                    _LOGGER.info("Found Erdal Akkaya:")
                    _LOGGER.info("  Full data: %s", p)
                    _LOGGER.info("  birth_ref_index: %s", p.get("birth_ref_index"))
                    _LOGGER.info("  death_ref_index: %s", p.get("death_ref_index"))
                    _LOGGER.info("  event_ref_list: %s", p.get("event_ref_list"))
                    break

            for person in people_data:
                # Get name
                name = self._get_person_name(person)

                # Get birth event
                birth_date = self._extract_birth_date(person)
                if not birth_date:
                    # Should not happen since we pre-filtered, but handle it
                    continue

                people_with_birth += 1

                # Check if person is still alive
                is_alive = self._is_person_alive(person)

                if is_alive:
                    living_people += 1
                else:
                    deceased_people += 1
                    _LOGGER.debug("Skipping deceased person: %s", name)
                    continue

                # Calculate next birthday (pass person data for image)
                next_birthday_info = self._calculate_next_birthday(
                    birth_date, name, person
                )

                if next_birthday_info:
                    birthdays.append(next_birthday_info)

            _LOGGER.info(
                "Summary - Total with birth date: %s, Living: %s, Deceased: %s",
                people_with_birth,
                living_people,
                deceased_people,
            )
            _LOGGER.info("Found %s birthdays from living people", len(birthdays))

            # Sort by days until birthday
            birthdays.sort(key=lambda x: x["days_until"])

            return birthdays[:limit]

        except Exception as err:
            _LOGGER.error("Failed to fetch birthdays: %s", err, exc_info=True)
            return []

    def _has_birth_date(self, person: dict) -> bool:
        """Check if person has a birth date set."""
        try:
            person = self._ensure_person_events(person)
            # Check birth_ref_index
            birth_ref_index = person.get("birth_ref_index", -1)
            event_ref_list = person.get("event_ref_list", [])

            # If birth_ref_index is valid, we have a birth date
            if birth_ref_index >= 0 and birth_ref_index < len(event_ref_list):
                event_handle = self._resolve_event_handle(
                    event_ref_list[birth_ref_index]
                )
                if event_handle:
                    parsed = self._fetch_event_date(event_handle)
                    if parsed:
                        return True

            # Otherwise, check if there's a birth event in the list
            for event_ref in event_ref_list:
                event_handle = self._resolve_event_handle(event_ref)
                if not event_handle:
                    continue
                try:
                    parsed = self._fetch_event_date(event_handle)
                    if parsed:
                        return True
                except Exception:
                    continue

            return False

        except Exception as err:
            _LOGGER.debug("Error checking birth date: %s", err)
            return False

    def _extract_birth_date(self, person: dict):
        """Extract birth date from person data."""
        try:
            person = self._ensure_person_events(person)
            birth_ref_index = person.get("birth_ref_index", -1)
            event_ref_list = person.get("event_ref_list", [])

            # If birth_ref_index is valid, try that reference first
            if birth_ref_index >= 0 and birth_ref_index < len(event_ref_list):
                event_handle = self._resolve_event_handle(
                    event_ref_list[birth_ref_index]
                )
                if event_handle:
                    parsed = self._fetch_event_date(event_handle, require_birth=True)
                    if parsed:
                        return parsed

            # Otherwise, scan all events for a birth event
            for event_ref in event_ref_list:
                event_handle = self._resolve_event_handle(event_ref)
                if not event_handle:
                    continue
                try:
                    parsed = self._fetch_event_date(event_handle, require_birth=True)
                    if parsed:
                        return parsed
                except Exception as event_err:
                    _LOGGER.debug(
                        "Could not fetch event %s: %s", event_handle, event_err
                    )
                    continue

            return None

        except Exception as err:
            _LOGGER.debug("Could not extract birth date: %s", err)
            return None

    def _fetch_event_date(self, event_handle: str, require_birth: bool = False):
        """Fetch and parse an event date, optionally requiring a birth event."""
        try:
            if not event_handle:
                return None

            # Clean up handle if it's a path-like string
            handle = event_handle
            if "/" in handle:
                handle = handle.rstrip("/").split("/")[-1]

            event_data = self._get(f"events/{handle}")

            if require_birth:
                event_type = event_data.get("type", {})
                type_string = (
                    event_type.get("string", "")
                    if isinstance(event_type, dict)
                    else str(event_type)
                )
                if "birth" not in type_string.lower():
                    return None

            date_info = event_data.get("date", {})
            parsed = self._parse_dateval(date_info.get("dateval", []))
            if parsed:
                _LOGGER.debug("Parsed event date: %s", parsed)
                return parsed

            return None
        except Exception as err:
            _LOGGER.debug("Could not fetch event date: %s", err)
            return None

    def _is_person_alive(self, person: dict) -> bool:
        """Check if person is still alive (no death date)."""
        try:
            # Check death_ref_index
            death_ref_index = person.get("death_ref_index", -1)

            if death_ref_index == -1:
                # No death event, person is alive
                return True

            # Person has a death event, they are deceased
            _LOGGER.debug("Person has death_ref_index: %s", death_ref_index)
            return False

        except Exception as err:
            _LOGGER.debug("Could not determine if person is alive: %s", err)
            # If we can't determine, assume person is alive
            return True

    def _parse_gramps_date(self, date_str: str):
        """Parse Gramps date format to Python date."""
        try:
            # Gramps can have various date formats
            # Common format: "1990-01-15" or "15 Jan 1990"
            if "-" in date_str and len(date_str) == 10:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            # Add more parsing logic as needed
            return None
        except Exception:
            return None

    def _get_person_name(self, person: dict):
        """Get person's display name."""
        try:
            primary_name = person.get("primary_name", {})
            first_name = primary_name.get("first_name", "")

            # Get surname from surname_list
            surname_list = primary_name.get("surname_list", [])
            surname = ""
            if surname_list:
                surname = surname_list[0].get("surname", "")

            full_name = f"{first_name} {surname}".strip()
            return full_name if full_name else "Unknown"
        except Exception:
            return "Unknown"

    def _get_person_image_url(self, person: dict) -> str | None:
        """Get the URL for a person's profile image."""
        try:
            # Get person handle
            person_handle = person.get("handle", "")
            if not person_handle:
                _LOGGER.debug("No person handle found")
                return None

            # Check media_list for images
            media_list = person.get("media_list", [])
            if not media_list:
                _LOGGER.debug("No media_list for person %s", person_handle)
                return None

            # Get first media reference
            media_ref = media_list[0]
            media_handle = None

            # Extract media handle from various possible keys
            for key in ("ref", "handle", "hlink"):
                candidate = media_ref.get(key)
                if candidate:
                    media_handle = candidate
                    break

            if not media_handle:
                _LOGGER.debug("Could not extract media handle from: %s", media_ref)
                return None

            # Clean handle if it's a path
            if "/" in media_handle:
                media_handle = media_handle.rstrip("/").split("/")[-1]

            # Construct thumbnail URL
            thumbnail_url = f"{self.url}/api/media/{media_handle}/thumbnail/200"

            # Download and save image locally
            if self.hass_config_path:
                return self._download_image(thumbnail_url, person_handle, media_handle)

            # Fallback to remote URL
            _LOGGER.debug("Image URL for person: %s", thumbnail_url)
            return thumbnail_url

        except Exception as err:
            _LOGGER.debug("Could not get person image: %s", err)
            return None

    def _download_image(
        self, image_url: str, person_handle: str, media_handle: str
    ) -> str | None:
        """Download image and return local path."""
        try:
            # Create filename from handles
            filename_hash = hashlib.md5(
                f"{person_handle}_{media_handle}".encode()
            ).hexdigest()
            filename = f"{filename_hash}.jpg"
            filepath = os.path.join(self.images_dir, filename)

            # Check if already downloaded
            if os.path.exists(filepath):
                _LOGGER.debug("Image already cached: %s", filepath)
                return f"/local/gramps/{filename}"

            # Download image
            _LOGGER.debug("Downloading image from: %s", image_url)
            response = self._session.get(image_url, timeout=10)
            response.raise_for_status()

            # Save to file
            with open(filepath, "wb") as f:
                f.write(response.content)

            _LOGGER.info("Downloaded image to: %s", filepath)
            return f"/local/gramps/{filename}"

        except Exception as err:
            _LOGGER.warning("Failed to download image: %s", err)
            return image_url  # Fallback to remote URL

    def _calculate_next_birthday(
        self, birth_date: date, name: str, person: dict = None
    ):
        """Calculate next birthday occurrence."""
        try:
            today = date.today()
            current_year = today.year

            # Calculate this year's birthday
            this_year_birthday = birth_date.replace(year=current_year)

            # If birthday already passed this year, use next year
            if this_year_birthday < today:
                next_birthday = birth_date.replace(year=current_year + 1)
            else:
                next_birthday = this_year_birthday

            days_until = (next_birthday - today).days
            age = next_birthday.year - birth_date.year

            # Get image URL if person data is provided
            image_url = None
            if person:
                image_url = self._get_person_image_url(person)

            result = {
                "person_name": name,
                "birth_date": birth_date.isoformat(),
                "next_birthday": next_birthday.isoformat(),
                "age": age,
                "days_until": days_until,
            }

            if image_url:
                result["image_url"] = image_url

            return result

        except Exception as err:
            _LOGGER.debug("Could not calculate birthday for %s: %s", name, err)
            return None

    def get_deathdays(self, limit: int = 50):
        """Get upcoming deathdays/memorial dates from Gramps Web."""
        try:
            _LOGGER.info("Fetching deathdays from Gramps Web API")

            all_people = self.get_people()
            if not isinstance(all_people, list):
                _LOGGER.warning(
                    "Unexpected response type for people: %s", type(all_people)
                )
                return []

            _LOGGER.info("Checking %s people for death dates...", len(all_people))

            # Diagnostics: check sample people (first 5) for death events
            _LOGGER.info("Running diagnostics on first 5 people for death events...")
            for idx, person in enumerate(all_people[:5]):
                name = self._get_person_name(person)
                death_ref_index = person.get("death_ref_index", -1)
                event_ref_list = person.get("event_ref_list", [])
                _LOGGER.info(
                    "Person %s (%s): death_ref_index=%s, event_ref_list length=%s",
                    idx + 1,
                    name,
                    death_ref_index,
                    len(event_ref_list),
                )

                # Log all events to see their types
                if event_ref_list:
                    for event_idx, event_ref in enumerate(event_ref_list):
                        event_handle = (
                            event_ref.get("ref")
                            or event_ref.get("handle")
                            or event_ref.get("hlink")
                        )
                        if event_handle:
                            try:
                                event = self._get_event(event_handle)
                                if event:
                                    event_type = event.get("type", {})
                                    type_string = (
                                        event_type.get("string", "")
                                        if isinstance(event_type, dict)
                                        else str(event_type)
                                    )
                                    _LOGGER.info(
                                        "  Event %s: type=%s, has date=%s",
                                        event_idx,
                                        type_string,
                                        "date" in event,
                                    )
                            except Exception as e:
                                _LOGGER.debug(
                                    "Could not fetch event %s: %s", event_handle, e
                                )

            deathdays = []
            candidates = 0
            no_death_ref = 0
            failed_calculation = 0

            for idx, person in enumerate(all_people):
                if idx % 50 == 0:
                    _LOGGER.debug(
                        "Processed %s/%s people for deathdays...", idx, len(all_people)
                    )

                self._ensure_person_events(person)

                if self._has_death_date(person):
                    candidates += 1
                    deathday = self._calculate_next_deathday(person)
                    if deathday:
                        deathdays.append(deathday)
                    else:
                        failed_calculation += 1
                else:
                    no_death_ref += 1

            # Sort by days until deathday
            deathdays.sort(key=lambda x: x.get("days_until", 999))

            _LOGGER.info(
                "Deathdays result: %s total people, %s without death_ref_index, %s candidates with death dates, %s failed calculation, %s entries after success%s",
                len(all_people),
                no_death_ref,
                candidates,
                failed_calculation,
                len(deathdays),
                f" | first: {deathdays[0]}" if deathdays else "",
            )

            # Return limited list
            return deathdays[:limit]

        except Exception as err:
            _LOGGER.error("Failed to get deathdays: %s", err, exc_info=True)
            return []

    def get_anniversaries(self, limit: int = 50):
        """Get upcoming anniversaries from Gramps Web."""
        try:
            _LOGGER.info("Fetching anniversaries from Gramps Web API")

            all_people = self.get_people()
            if not isinstance(all_people, list):
                _LOGGER.warning(
                    "Unexpected response type for people: %s", type(all_people)
                )
                return []

            # First pass: collect all anniversaries with event handles
            anniversaries_with_events = {}  # key: (marriage_date, event_handle)
            person_by_handle = {}  # key: person_handle, value: person_name
            marriage_events = 0

            for person in all_people:
                self._ensure_person_events(person)
                person_handle = person.get("handle", "")
                person_name = self._get_person_name(person)
                person_by_handle[person_handle] = person_name

                # Look for marriage events
                marriage_dates = self._get_marriage_dates(person)
                marriage_events += len(marriage_dates)
                for spouse_name, marriage_date, event_handle in marriage_dates:
                    key = (str(marriage_date), event_handle)
                    
                    if key not in anniversaries_with_events:
                        anniversaries_with_events[key] = {
                            "person_names": set(),
                            "marriage_date": marriage_date,
                            "event_handle": event_handle,
                            "spouse_name": spouse_name,
                        }
                    
                    anniversaries_with_events[key]["person_names"].add(person_name)

            # Second pass: create anniversary entries and find partners
            anniversaries = []
            seen_events = set()
            
            for (date_str, event_handle), data in anniversaries_with_events.items():
                # Skip if we already processed this event
                if event_handle in seen_events:
                    continue
                seen_events.add(event_handle)
                
                # Get the list of people for this event
                person_names = sorted(data["person_names"])
                marriage_date = data["marriage_date"]
                
                # Create anniversary entry
                if len(person_names) >= 2:
                    # We have both partners, combine them
                    combined_name = " & ".join(person_names[:2])
                else:
                    # We only have one person, use the spouse name if available
                    combined_name = f"{person_names[0]}"
                    if data["spouse_name"]:
                        combined_name = f"{person_names[0]} & {data['spouse_name']}"
                
                anniversary = self._calculate_anniversary(
                    combined_name.split(" & ")[0],
                    combined_name.split(" & ")[1] if " & " in combined_name else data["spouse_name"] or "Unknown",
                    marriage_date
                )
                if anniversary:
                    # Update the person_name to the combined version
                    anniversary["person_name"] = combined_name
                    anniversaries.append(anniversary)

            # Sort by days until anniversary
            anniversaries.sort(key=lambda x: x.get("days_until", 999))

            _LOGGER.info(
                "Anniversaries result: %s marriage events, %s entries after deduplication%s",
                marriage_events,
                len(anniversaries),
                f" | first: {anniversaries[0]}" if anniversaries else "",
            )

            # Return limited list
            return anniversaries[:limit]

        except Exception as err:
            _LOGGER.error("Failed to get anniversaries: %s", err, exc_info=True)
            return []

    def _has_death_date(self, person: dict) -> bool:
        """Check if person has a death date."""
        try:
            person_name = self._get_person_name(person)
            death_ref_index = person.get("death_ref_index", -1)

            if death_ref_index < 0:
                _LOGGER.debug(
                    "Person %s: no death_ref_index (value: %s)",
                    person_name,
                    death_ref_index,
                )
                return False

            event_ref_list = person.get("event_ref_list", [])
            if death_ref_index >= len(event_ref_list):
                _LOGGER.debug(
                    "Person %s: death_ref_index %s out of range (event_ref_list length: %s)",
                    person_name,
                    death_ref_index,
                    len(event_ref_list),
                )
                return False

            death_ref = event_ref_list[death_ref_index]
            handle = (
                death_ref.get("ref")
                or death_ref.get("handle")
                or death_ref.get("hlink")
            )

            if not handle:
                _LOGGER.debug("Person %s: no handle in death_ref", person_name)
                return False

            event = self._get_event(handle)
            if not event:
                _LOGGER.debug(
                    "Person %s: could not fetch event with handle %s",
                    person_name,
                    handle,
                )
                return False

            # Verify this is actually a Death event
            event_type = event.get("type", {})
            type_string = (
                event_type.get("string", "")
                if isinstance(event_type, dict)
                else str(event_type)
            )
            if "death" not in type_string.lower():
                _LOGGER.debug(
                    "Person %s: event type is '%s', not Death", person_name, type_string
                )
                return False

            dateval = event.get("date", {})
            raw_dateval = None
            if isinstance(dateval, dict):
                raw_dateval = (
                    dateval.get("dateval") or dateval.get("val") or dateval.get("start")
                )
            else:
                raw_dateval = dateval

            parsed = self._parse_dateval(raw_dateval)

            if not parsed:
                _LOGGER.debug(
                    "Person %s: could not parse death date from %s (raw=%s)",
                    person_name,
                    dateval,
                    raw_dateval,
                )
                return False

            _LOGGER.debug(
                "Person %s: has death date %s (event type: %s)",
                person_name,
                parsed,
                type_string,
            )
            return bool(parsed)

        except Exception as err:
            _LOGGER.debug(
                "Error checking death date for %s: %s",
                person.get("handle", "unknown"),
                err,
            )
            return False

    def _get_marriage_dates(self, person: dict) -> list:
        """Get all marriage dates from person and family events.
        
        Returns list of tuples: (spouse_name_or_none, marriage_date, event_handle)
        where event_handle is used to find the partner later.
        """
        marriage_dates = []
        try:
            person_handle = person.get("handle", "")
            event_ref_list = person.get("event_ref_list", [])
            families = person.get("family_list", [])

            # Collect possible spouse handles from families
            # family_list contains STRINGS (handles), not dictionaries!
            spouse_handles = set()
            for family_handle_or_ref in families:
                # If it's a dict, extract handle; if it's a string, use directly
                if isinstance(family_handle_or_ref, dict):
                    family_handle = (
                        family_handle_or_ref.get("ref")
                        or family_handle_or_ref.get("handle")
                        or family_handle_or_ref.get("hlink")
                    )
                else:
                    # It's a string (the handle directly)
                    family_handle = family_handle_or_ref

                if not family_handle:
                    continue

                family = self._get_family(family_handle)
                if not family:
                    continue

                for parent_rel in family.get("parent_rel_list", []):
                    spouse_handle = parent_rel.get("ref") or parent_rel.get("handle")
                    if spouse_handle and spouse_handle != person_handle:
                        spouse_handles.add(spouse_handle)

                # Process marriage events attached to the family
                for event_ref in family.get("event_ref_list", []):
                    ev_handle = (
                        event_ref.get("ref")
                        or event_ref.get("handle")
                        or event_ref.get("hlink")
                    )
                    if not ev_handle:
                        continue
                    event = self._get_event(ev_handle)
                    if not event:
                        continue

                    event_type = event.get("type", {})
                    type_string = (
                        event_type.get("string", "")
                        if isinstance(event_type, dict)
                        else str(event_type)
                    )
                    if "marriage" not in type_string.lower() and "engagement" not in type_string.lower():
                        continue

                    dateval = event.get("date", {})
                    raw_dateval = None
                    if isinstance(dateval, dict):
                        raw_dateval = (
                            dateval.get("dateval")
                            or dateval.get("val")
                            or dateval.get("start")
                        )
                    else:
                        raw_dateval = dateval

                    parsed_dateval = self._parse_dateval(raw_dateval)
                    if not parsed_dateval:
                        continue

                    for spouse_handle in spouse_handles or [None]:
                        spouse_name = None
                        if spouse_handle:
                            try:
                                spouse_person = self._get(f"people/{spouse_handle}")
                                if spouse_person:
                                    spouse_name = self._get_person_name(spouse_person)
                            except Exception:
                                spouse_name = None
                        marriage_dates.append((spouse_name, parsed_dateval, ev_handle))

            # Also process any marriage events directly attached to the person
            for event_ref in event_ref_list:
                # event_ref_list should contain dicts with .get() method
                if not isinstance(event_ref, dict):
                    continue

                event_handle = (
                    event_ref.get("ref")
                    or event_ref.get("handle")
                    or event_ref.get("hlink")
                )
                if not event_handle:
                    continue

                event = self._get_event(event_handle)
                if not event:
                    continue

                event_type = event.get("type", {})
                type_string = (
                    event_type.get("string", "")
                    if isinstance(event_type, dict)
                    else str(event_type)
                )
                if "marriage" not in type_string.lower() and "engagement" not in type_string.lower():
                    continue

                dateval = event.get("date", {})
                raw_dateval = None
                if isinstance(dateval, dict):
                    raw_dateval = (
                        dateval.get("dateval")
                        or dateval.get("val")
                        or dateval.get("start")
                    )
                else:
                    raw_dateval = dateval

                parsed_dateval = self._parse_dateval(raw_dateval)
                if not parsed_dateval:
                    continue

                # If we know spouses, emit one entry per spouse; otherwise None
                if spouse_handles:
                    for spouse_handle in spouse_handles:
                        spouse_name = None
                        try:
                            spouse_person = self._get(f"people/{spouse_handle}")
                            if spouse_person:
                                spouse_name = self._get_person_name(spouse_person)
                        except Exception:
                            spouse_name = None
                        marriage_dates.append((spouse_name, parsed_dateval, event_handle))
                else:
                    # Return None for spouse_name to signal we need to find the partner
                    marriage_dates.append((None, parsed_dateval, event_handle))

            return marriage_dates

        except Exception as err:
            _LOGGER.debug("Error getting marriage dates: %s", err)
            return []

    def _get_event(self, handle: str):
        """Get event details from API."""
        try:
            if not handle:
                return None
            event = self._get(f"events/{handle}")
            if event:
                _LOGGER.debug(
                    "Fetched event %s: type=%s", handle, event.get("type", {})
                )
            return event
        except Exception as err:
            _LOGGER.debug("Could not fetch event %s: %s", handle, err)
            return None

    def _get_family(self, handle: str):
        """Get family details from API."""
        try:
            return self._get(f"families/{handle}")
        except Exception:
            return None

    def _calculate_next_deathday(self, person: dict) -> dict | None:
        """Calculate next deathday for a person."""
        try:
            death_ref_index = person.get("death_ref_index", -1)
            if death_ref_index < 0:
                return None

            event_ref_list = person.get("event_ref_list", [])
            if death_ref_index >= len(event_ref_list):
                return None

            death_ref = event_ref_list[death_ref_index]
            handle = (
                death_ref.get("ref")
                or death_ref.get("handle")
                or death_ref.get("hlink")
            )

            event = self._get_event(handle)
            if not event:
                return None

            # Verify this is actually a Death event
            event_type = event.get("type", {})
            type_string = (
                event_type.get("string", "")
                if isinstance(event_type, dict)
                else str(event_type)
            )
            if "death" not in type_string.lower():
                name = self._get_person_name(person)
                _LOGGER.debug(
                    "Person %s: death_ref_index points to non-Death event type: %s",
                    name,
                    type_string,
                )
                return None

            dateval = event.get("date", {})
            raw_dateval = None
            if isinstance(dateval, dict):
                raw_dateval = (
                    dateval.get("dateval") or dateval.get("val") or dateval.get("start")
                )
            else:
                raw_dateval = dateval

            death_date = self._parse_dateval(raw_dateval)

            if not death_date:
                return None

            today = date.today()
            next_deathday = death_date.replace(year=today.year)

            if next_deathday < today:
                next_deathday = next_deathday.replace(year=today.year + 1)

            days_until = (next_deathday - today).days

            name = self._get_person_name(person)
            years_ago = today.year - death_date.year

            return {
                "person_name": name,
                "death_date": death_date.isoformat(),
                "next_deathday": next_deathday.isoformat(),
                "years_ago": years_ago,
                "days_until": days_until,
            }

        except Exception as err:
            _LOGGER.debug("Could not calculate deathday: %s", err)
            return None

    def _calculate_anniversary(
        self, person1_name: str, person2_name: str, dateval
    ) -> dict | None:
        """Calculate next anniversary for a couple."""
        try:
            # dateval can already be a date object (from _get_marriage_dates)
            # or it can be a dict/list that needs parsing
            if isinstance(dateval, date):
                marriage_date = dateval
            else:
                marriage_date = self._parse_dateval(dateval)

            if not marriage_date:
                return None

            today = date.today()
            next_anniversary = marriage_date.replace(year=today.year)

            if next_anniversary < today:
                next_anniversary = next_anniversary.replace(year=today.year + 1)

            days_until = (next_anniversary - today).days
            years_together = today.year - marriage_date.year

            # Build person_name string
            if person2_name and person2_name != "Unknown":
                person_name_str = f"{person1_name} & {person2_name}"
            else:
                person_name_str = person1_name

            return {
                "person_name": person_name_str,
                "marriage_date": marriage_date.isoformat(),
                "next_anniversary": next_anniversary.isoformat(),
                "years_together": years_together,
                "days_until": days_until,
            }

        except Exception as err:
            _LOGGER.debug("Could not calculate anniversary: %s", err)
            return None
