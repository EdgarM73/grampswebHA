"""Home Assistant side: entities, the coordinator and the owner lookup.

These need the `homeassistant` package; without it the whole module is skipped.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from conftest import ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "custom_components"))

import gramps_ha  # noqa: E402
from gramps_ha import binary_sensor, sensor  # noqa: E402
from gramps_ha import calendar as gramps_calendar  # noqa: E402
from gramps_ha.const import DEFAULT_SCAN_INTERVAL, DOMAIN  # noqa: E402

ENTRY_ID = "E1"


def run(coro):
    return asyncio.run(coro)


class FakeHass:
    """The few bits of `hass` the entities touch."""

    def __init__(self, data=None):
        self.data = data or {}
        self.fired = []
        self.bus = SimpleNamespace(async_fire=lambda name, payload: self.fired.append((name, payload)))

    async def async_add_executor_job(self, func, *args):
        return func(*args)


def entry(**data):
    return SimpleNamespace(entry_id=ENTRY_ID, data=data)


def coordinator(hass, data=None):
    return SimpleNamespace(hass=hass, data=data, last_update_success=True)


# ------------------------------------------------------------------ statistics


@pytest.fixture
def stats(api):
    return api.get_statistics()


def stat_sensor(hass, key):
    spec = next(s for s in sensor.STAT_SENSORS if s[0] == key)
    return sensor.GrampsWebStatSensor(coordinator(hass), entry(), *spec)


def test_stat_sensor_values(stats):
    hass = FakeHass({f"{DOMAIN}_stats": {ENTRY_ID: stats}})
    assert stat_sensor(hass, "people").native_value == 8
    assert stat_sensor(hass, "living").native_value == 6
    assert stat_sensor(hass, "avg_age_living").native_value == 44.6
    assert stat_sensor(hass, "avg_age_living").native_unit_of_measurement == "years"

    oldest = stat_sensor(hass, "oldest_living")
    assert oldest.native_value == 66
    assert oldest.extra_state_attributes == {"person_name": "Eva Beispiel", "birth_date": "1960-05-05"}

    surname = stat_sensor(hass, "top_surnames")
    assert surname.native_value == "Muster"
    assert surname.extra_state_attributes["top"][0] == {"surname": "Muster", "count": 5}

    main = stat_sensor(hass, "main_person")
    assert main.native_value == "Max Muster"
    assert main.extra_state_attributes == {"source": "gramps", "person_handle": "home"}


def test_stat_sensors_without_data_are_empty():
    hass = FakeHass({})
    for spec in sensor.STAT_SENSORS:
        s = sensor.GrampsWebStatSensor(coordinator(hass), entry(), *spec)
        assert s.native_value is None
        assert s.extra_state_attributes == {}


def test_stat_sensor_setup():
    keys = [spec[0] for spec in sensor.STAT_SENSORS]
    assert len(keys) == len(set(keys))
    disabled = {s[0] for s in sensor.STAT_SENSORS if not s[4]}
    assert disabled == {
        "sources", "citations", "repositories", "notes", "tags",
        "male", "female", "without_birth_date", "without_photo",
    }
    hass = FakeHass({})
    sensors = [sensor.GrampsWebStatSensor(coordinator(hass), entry(), *s) for s in sensor.STAT_SENSORS]
    assert len({s.unique_id for s in sensors}) == len(sensors)
    by_key = dict(zip(keys, sensors))
    assert by_key["people"].state_class == "measurement"
    assert by_key["top_surnames"].state_class is None
    assert by_key["main_person"].state_class is None
    assert by_key["notes"].entity_registry_enabled_default is False
    assert by_key["people"].entity_registry_enabled_default is True


# -------------------------------------------------- other sensors / binary sensors


def test_on_this_day_sensor():
    items = [{"text": "1990: A"}, {"text": "1999: B"}]
    hass = FakeHass({f"{DOMAIN}_on_this_day": {ENTRY_ID: items}})
    s = sensor.GrampsWebOnThisDaySensor(coordinator(hass), entry())
    assert s.native_value == 2
    assert s.extra_state_attributes == {"events": items, "text": "1990: A\n1999: B"}
    empty = sensor.GrampsWebOnThisDaySensor(coordinator(FakeHass({})), entry())
    assert empty.native_value == 0
    assert empty.extra_state_attributes["text"] == ""


def test_milestone_sensor(api):
    milestones = api.get_milestones(days=400)
    hass = FakeHass({f"{DOMAIN}_milestones": {ENTRY_ID: milestones}})
    s = sensor.GrampsWebNextMilestoneSensor(coordinator(hass), entry())
    assert s.native_value == "Carl Beispiel & Eva Beispiel: Silberhochzeit (25)"
    attrs = s.extra_state_attributes
    assert attrs["days_until"] == 2 and attrs["kind"] == "anniversary"
    assert len(attrs["upcoming"]) == 3

    none = sensor.GrampsWebNextMilestoneSensor(coordinator(FakeHass({})), entry())
    assert none.native_value is None
    assert none.extra_state_attributes == {"upcoming": []}


def test_relationship_sensors():
    hass = FakeHass({f"{DOMAIN}_deathdays": {ENTRY_ID: [{"relationship": "Onkel"}, {}]}})
    births = [{"relationship": "Tante"}, {"person_name": "x"}]
    birthday = sensor.GrampsWebNextBirthdayRelationshipSensor(coordinator(hass, births), entry(), 0)
    assert birthday.native_value == "Tante"
    assert sensor.GrampsWebNextBirthdayRelationshipSensor(coordinator(hass, births), entry(), 1).native_value is None
    assert sensor.GrampsWebNextBirthdayRelationshipSensor(coordinator(hass, births), entry(), 9).native_value is None
    assert sensor.GrampsWebNextBirthdayRelationshipSensor(coordinator(hass, None), entry(), 0).native_value is None
    death = sensor.GrampsWebNextDeathdayRelationshipSensor(coordinator(hass), entry(), 0)
    assert death.native_value == "Onkel"
    assert sensor.GrampsWebNextDeathdayRelationshipSensor(coordinator(hass), entry(), 1).native_value is None
    assert sensor.GrampsWebNextDeathdayRelationshipSensor(coordinator(hass), entry(), 5).native_value is None
    assert birthday.unique_id != death.unique_id


def test_birthday_sensor_exposes_the_relationship_attribute():
    data = [{"person_name": "A", "relationship": "Tante", "age": 5, "days_until": 1}]
    name = sensor.GrampsWebNextBirthdayNameSensor(coordinator(FakeHass({}), data), entry(), 0)
    assert name.extra_state_attributes["relationship"] == "Tante"


@pytest.mark.parametrize(
    "kind, key, data_key, enabled",
    [
        ("birthday", "next_birthday", None, True),
        ("deathday", "next_deathday", f"{DOMAIN}_deathdays", True),
        ("anniversary", "next_anniversary", f"{DOMAIN}_anniversaries", True),
    ],
)
def test_today_binary_sensors(kind, key, data_key, enabled):
    today = date.today().isoformat()
    items = [
        {key: today, "person_name": "Heute", "milestone": "50. Geburtstag"},
        {key: "1999-01-01", "person_name": "Nicht heute"},
        {key: today, "person_name": "Auch heute"},
    ]
    hass = FakeHass({data_key: {ENTRY_ID: items}} if data_key else {})
    s = binary_sensor.GrampsWebTodayBinarySensor(coordinator(hass, items), entry(), kind)
    assert s.is_on is True
    assert s.extra_state_attributes == {"count": 2, "names": ["Heute", "Auch heute"], "milestones": ["50. Geburtstag"]}

    nothing = binary_sensor.GrampsWebTodayBinarySensor(coordinator(FakeHass({}), []), entry(), kind)
    assert nothing.is_on is False
    assert nothing.extra_state_attributes["count"] == 0
    assert nothing.unique_id == f"{ENTRY_ID}_today_{kind}"


def test_binary_sensors_follow_the_enabled_kinds():
    added = []

    def setup(**data):
        added.clear()
        hass = FakeHass({DOMAIN: {ENTRY_ID: coordinator(FakeHass({}), [])}})
        run(binary_sensor.async_setup_entry(hass, entry(**data), lambda entities: added.extend(entities)))
        return [e._kind for e in added]

    assert setup() == ["birthday"]
    assert setup(show_deathdays=True) == ["birthday", "deathday"]
    assert setup(show_deathdays=True, show_anniversaries=True) == ["birthday", "deathday", "anniversary"]


# ---------------------------------------------------------------------- calendar


class FakeCalendarApi:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def get_calendar_events(self, start, end, deaths, anniversaries):
        self.calls.append((start, end, deaths, anniversaries))
        return self.items


def calendar_entity(items, **data):
    api = FakeCalendarApi(items)
    entity = gramps_calendar.GrampsWebCalendar(api, entry(**data))
    entity.hass = FakeHass()
    return entity, api


ITEMS = [
    {"date": date(2026, 10, 15), "summary": "S1", "milestone": "Silberhochzeit (25)"},
    {"date": date(2026, 10, 18), "summary": "S2", "milestone": None},
]


def test_calendar_events_are_all_day_events():
    entity, _ = calendar_entity(ITEMS)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    events = run(entity.async_get_events(entity.hass, start, start + timedelta(days=31)))
    assert [(e.start, e.end, e.summary, e.description) for e in events] == [
        (date(2026, 10, 15), date(2026, 10, 16), "S1", "Silberhochzeit (25)"),
        (date(2026, 10, 18), date(2026, 10, 19), "S2", None),
    ]


def test_calendar_range_end_is_exclusive():
    entity, api = calendar_entity(ITEMS)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    run(entity.async_get_events(entity.hass, start, datetime(2026, 11, 1, tzinfo=timezone.utc)))
    first, last = api.calls[0][0], api.calls[0][1]
    assert last - first == timedelta(days=30)  # Oct 1 .. Oct 31, not Nov 1


def test_calendar_empty_range():
    entity, api = calendar_entity(ITEMS)
    moment = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert run(entity.async_get_events(entity.hass, moment, moment)) == []
    assert api.calls == []


def test_calendar_passes_the_enabled_kinds():
    entity, api = calendar_entity(ITEMS, show_deathdays=True)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    run(entity.async_get_events(entity.hass, start, start + timedelta(days=2)))
    assert api.calls[0][2:] == (True, False)
    default, api2 = calendar_entity(ITEMS)
    run(default.async_get_events(default.hass, start, start + timedelta(days=2)))
    assert api2.calls[0][2:] == (False, False)


def test_calendar_state_is_the_next_event():
    entity, api = calendar_entity(ITEMS)
    assert entity.event is None
    run(entity.async_update())
    assert entity.event.summary == "S1"
    assert (api.calls[0][1] - api.calls[0][0]).days == 366
    empty, _ = calendar_entity([])
    run(empty.async_update())
    assert empty.event is None


# ---------------------------------------------------------- coordinator / owner


def make_coordinator(hass, data=None, **entry_data):
    c = object.__new__(gramps_ha.GrampsWebCoordinator)
    c.hass, c.data, c.entry = hass, data, entry(**entry_data)
    return c


def test_events_are_fired_for_todays_entries_only():
    today = date.today().isoformat()
    hass = FakeHass(
        {
            f"{DOMAIN}_deathdays": {ENTRY_ID: [{"next_deathday": today, "person_name": "D", "years_ago": 20, "milestone": "20. Todestag"}]},
            f"{DOMAIN}_anniversaries": {ENTRY_ID: [{"next_anniversary": "2001-01-01", "person_name": "X"}]},
        }
    )
    births = [
        {"next_birthday": today, "person_name": "B", "age": 50, "milestone": "50. Geburtstag"},
        {"next_birthday": "2001-01-01", "person_name": "Y", "age": 5},
    ]
    make_coordinator(hass, births).fire_today_events()
    assert hass.fired == [
        ("gramps_ha_event", {"entry_id": ENTRY_ID, "type": "birthday", "person_name": "B", "years": 50, "milestone": "50. Geburtstag"}),
        ("gramps_ha_event", {"entry_id": ENTRY_ID, "type": "deathday", "person_name": "D", "years": 20, "milestone": "20. Todestag"}),
    ]


def test_anniversary_event_uses_years_together():
    today = date.today().isoformat()
    hass = FakeHass({f"{DOMAIN}_anniversaries": {ENTRY_ID: [{"next_anniversary": today, "person_name": "P", "years_together": 25}]}})
    make_coordinator(hass, []).fire_today_events()
    assert hass.fired[0][1]["type"] == "anniversary" and hass.fired[0][1]["years"] == 25


def test_no_events_without_data():
    hass = FakeHass({})
    make_coordinator(hass, None).fire_today_events()
    assert hass.fired == []


class FakeUpdateApi:
    def __init__(self):
        self.calls = []

    def _rec(self, name, value):
        self.calls.append(name)
        return value

    def get_birthdays(self):
        return self._rec("birthdays", [{"next_birthday": "2999-01-01", "person_name": "B"}])

    def get_deathdays(self):
        return self._rec("deathdays", [{"person_name": "D"}])

    def get_anniversaries(self):
        return self._rec("anniversaries", [{"person_name": "A"}])

    def get_milestones(self, days, limit, deaths, anniversaries):
        return self._rec("milestones", [{"flags": (deaths, anniversaries)}])

    def get_on_this_day(self):
        return self._rec("on_this_day", [{"text": "t"}])

    def get_statistics(self):
        return self._rec("statistics", {"people": 1})


def update(**entry_data):
    hass = FakeHass()
    c = make_coordinator(hass, None, **entry_data)
    c.api = FakeUpdateApi()

    async def no_notifications(_data):
        return None

    c._check_notifications = no_notifications
    result = run(c._async_update_data())
    return hass, c, result


def test_update_stores_everything_for_the_sensors():
    hass, c, result = update(show_deathdays=True, show_anniversaries=True)
    assert result == [{"next_birthday": "2999-01-01", "person_name": "B"}]
    assert hass.data[f"{DOMAIN}_deathdays"][ENTRY_ID] == [{"person_name": "D"}]
    assert hass.data[f"{DOMAIN}_anniversaries"][ENTRY_ID] == [{"person_name": "A"}]
    assert hass.data[f"{DOMAIN}_milestones"][ENTRY_ID] == [{"flags": (True, True)}]
    assert hass.data[f"{DOMAIN}_on_this_day"][ENTRY_ID] == [{"text": "t"}]
    assert hass.data[f"{DOMAIN}_stats"][ENTRY_ID] == {"people": 1}


def test_update_skips_disabled_kinds():
    hass, c, _ = update()
    assert "deathdays" not in c.api.calls and "anniversaries" not in c.api.calls
    assert hass.data[f"{DOMAIN}_milestones"][ENTRY_ID] == [{"flags": (False, False)}]


def test_update_failure_becomes_update_failed():
    from homeassistant.helpers.update_coordinator import UpdateFailed

    hass = FakeHass()
    c = make_coordinator(hass, None)
    c.api = SimpleNamespace(get_birthdays=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(UpdateFailed):
        run(c._async_update_data())


@pytest.mark.parametrize(
    "today, tomorrow",
    [
        (date(2026, 1, 30), "2026-01-31"),
        (date(2026, 1, 31), "2026-02-01"),  # month end: the old code looked at the wrong day
        (date(2026, 2, 28), "2026-03-01"),
        (date(2028, 2, 28), "2028-02-29"),
        (date(2026, 12, 31), "2027-01-01"),  # year end
    ],
)
def test_birthday_notification_is_sent_the_day_before(monkeypatch, today, tomorrow):
    class Frozen(date):
        @classmethod
        def today(cls):
            return today

    created = []
    monkeypatch.setattr(gramps_ha, "date", Frozen)
    monkeypatch.setattr(gramps_ha.persistent_notification, "create", lambda hass, message, **kw: created.append((message, kw)))
    c = make_coordinator(FakeHass())
    run(c._check_notifications([{"person_name": "Anna", "next_birthday": tomorrow, "age": 30}, {"person_name": "Nope", "next_birthday": "2000-01-01", "age": 1}]))
    assert len(created) == 1
    assert "Anna" in created[0][0]
    assert created[0][1]["notification_id"] == "gramps_tomorrow_Anna"


def test_no_notifications_without_birthdays():
    run(make_coordinator(FakeHass())._check_notifications([]))
    run(make_coordinator(FakeHass())._check_notifications(None))


def user(uid, name, owner=False, active=True):
    return SimpleNamespace(id=uid, name=name, is_owner=owner, is_active=active)


def person_state(user_id, name):
    return SimpleNamespace(attributes={"user_id": user_id, "friendly_name": name}, name=name)


class OwnerHass:
    def __init__(self, users, persons, fail=False):
        async def get_users():
            if fail:
                raise RuntimeError("auth unavailable")
            return users

        self.auth = SimpleNamespace(async_get_users=get_users)
        self.states = SimpleNamespace(async_all=lambda domain: persons)


@pytest.mark.parametrize(
    "users, persons, expected",
    [
        ([user("a", "admin"), user("o", "Owner Login", owner=True)], [person_state("x", "Other"), person_state("o", "Erdal Akkaya")], "Erdal Akkaya"),
        ([user("o", "Owner Login", owner=True)], [person_state("x", "Other")], "Owner Login"),  # no person linked
        ([user("a", "admin")], [person_state("a", "Admin Person")], None),  # no owner
        ([user("o", "Gone", owner=True, active=False)], [], None),  # inactive owner
        ([], [], None),
    ],
)
def test_owner_person_name(users, persons, expected):
    assert run(gramps_ha._async_owner_person_name(OwnerHass(users, persons))) == expected


def test_owner_lookup_never_raises():
    assert run(gramps_ha._async_owner_person_name(OwnerHass([], [], fail=True))) is None


# ----------------------------------------------------------------- device lookup


def test_via_device_uses_the_new_registry_call(monkeypatch):
    class Registry:
        def async_get_device_by_identifier(self, identifier, entry_id):
            assert identifier == (DOMAIN, ENTRY_ID) and entry_id == ENTRY_ID
            return SimpleNamespace(id="parent")

    monkeypatch.setattr(sensor, "async_get_device_registry", lambda hass: Registry())
    assert sensor._via_device(None, entry()) == {"via_device_id": "parent"}


def test_via_device_on_older_home_assistant(monkeypatch):
    class Registry:
        def async_get_device(self, identifiers):
            assert identifiers == {(DOMAIN, ENTRY_ID)}
            return SimpleNamespace(id="old")

    monkeypatch.setattr(sensor, "async_get_device_registry", lambda hass: Registry())
    assert sensor._via_device(None, entry()) == {"via_device_id": "old"}


def test_via_device_without_a_parent(monkeypatch):
    class Registry:
        def async_get_device_by_identifier(self, identifier, entry_id):
            return None

    monkeypatch.setattr(sensor, "async_get_device_registry", lambda hass: Registry())
    assert sensor._via_device(None, entry()) == {}


def test_defaults():
    assert DEFAULT_SCAN_INTERVAL == 7 * 24
    assert gramps_ha.PLATFORMS and {p.value for p in gramps_ha.PLATFORMS} == {"sensor", "calendar", "binary_sensor"}
