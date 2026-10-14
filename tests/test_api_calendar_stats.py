"""Calendar events, milestones, "on this day" and the tree statistics."""

from __future__ import annotations

from datetime import date

import pytest

from helpers import FakeServer, ev, person

TODAY = date(2026, 10, 13)


def flat(events):
    return [(e["date"].isoformat(), e["kind"], e["name"]) for e in events]


# ----------------------------------------------------------------- calendar events


def test_calendar_events_in_a_range(api):
    events = api.get_calendar_events(date(2026, 10, 13), date(2026, 10, 31))
    assert flat(events) == [
        ("2026-10-13", "birthday", "Dora Muster"),
        ("2026-10-15", "anniversary", "Carl Beispiel & Eva Beispiel"),
        ("2026-10-18", "birthday", "Anna Muster"),
        ("2026-10-20", "deathday", "Carl Beispiel"),
    ]


def test_calendar_summaries(api):
    summaries = [e["summary"] for e in api.get_calendar_events(date(2026, 10, 13), date(2026, 10, 31))]
    assert summaries == [
        "\U0001F382 Dora Muster (36)",
        "\U0001F389 Carl Beispiel & Eva Beispiel – Silberhochzeit (25)",
        "\U0001F389 Anna Muster – 50. Geburtstag",
        "\U0001F389 Carl Beispiel – 20. Todestag",
    ]


def test_calendar_summaries_in_english(make_api, frozen_today):
    api = make_api(language="en")
    summaries = [e["summary"] for e in api.get_calendar_events(date(2026, 10, 13), date(2026, 10, 18))]
    assert summaries == [
        "\U0001F382 Dora Muster (36)",
        "\U0001F389 Carl Beispiel & Eva Beispiel – Silver wedding anniversary (25)",
        "\U0001F389 Anna Muster – 50th birthday",
    ]


def test_plain_deathday_and_anniversary_summaries(api):
    deathday = api.get_calendar_events(date(2027, 10, 20), date(2027, 10, 20))[0]
    assert deathday["summary"] == "\U0001F56F️ Carl Beispiel (21. Todestag)"
    anniversary = api.get_calendar_events(date(2027, 10, 15), date(2027, 10, 15))[0]
    assert anniversary["summary"] == "\U0001F48D Carl Beispiel & Eva Beispiel (26. Hochzeitstag)"


def test_calendar_can_leave_out_deathdays_and_anniversaries(api):
    start, end = date(2026, 10, 13), date(2026, 10, 31)
    assert {e["kind"] for e in api.get_calendar_events(start, end, include_deaths=False)} == {"birthday", "anniversary"}
    assert {e["kind"] for e in api.get_calendar_events(start, end, include_anniversaries=False)} == {"birthday", "deathday"}
    assert {e["kind"] for e in api.get_calendar_events(start, end, False, False)} == {"birthday"}


def test_calendar_skips_the_year_of_birth_and_death(api):
    assert api.get_calendar_events(date(1990, 10, 13), date(1990, 10, 13)) == []  # Dora is born
    assert api.get_calendar_events(date(2006, 10, 20), date(2006, 10, 20)) == []  # Carl dies
    first = api.get_calendar_events(date(2007, 10, 20), date(2007, 10, 20))
    assert [(e["kind"], e["years"]) for e in first] == [("deathday", 1)]


def test_calendar_leap_day_birthday(api):
    bob = lambda s, e: [x for x in api.get_calendar_events(s, e) if x["name"] == "Bob Muster"]  # noqa: E731
    assert [(e["date"], e["years"]) for e in bob(date(2027, 2, 1), date(2027, 3, 31))] == [(date(2027, 2, 28), 27)]
    assert [(e["date"], e["years"]) for e in bob(date(2028, 2, 1), date(2028, 3, 31))] == [(date(2028, 2, 29), 28)]


def test_calendar_spanning_several_years(api):
    dora = [e for e in api.get_calendar_events(date(2026, 10, 1), date(2028, 12, 31)) if e["name"] == "Dora Muster"]
    assert [e["date"].year for e in dora] == [2026, 2027, 2028]
    assert [e["years"] for e in dora] == [36, 37, 38]


def test_calendar_range_edges_are_inclusive(api):
    assert len(api.get_calendar_events(date(2026, 10, 18), date(2026, 10, 18))) == 1
    assert api.get_calendar_events(date(2026, 10, 19), date(2026, 10, 19)) == []


def test_calendar_inverted_range_is_empty(api):
    assert api.get_calendar_events(date(2026, 12, 31), date(2026, 1, 1)) == []


# ---------------------------------------------------------------------- milestones


def test_milestones(api):
    result = api.get_milestones(days=400)
    assert result == [
        {"kind": "anniversary", "person_name": "Carl Beispiel & Eva Beispiel", "date": "2026-10-15",
         "days_until": 2, "years": 25, "label": "Silberhochzeit (25)"},
        {"kind": "birthday", "person_name": "Anna Muster", "date": "2026-10-18",
         "days_until": 5, "years": 50, "label": "50. Geburtstag"},
        {"kind": "deathday", "person_name": "Carl Beispiel", "date": "2026-10-20",
         "days_until": 7, "years": 20, "label": "20. Todestag"},
    ]


def test_milestones_respect_limit_and_window(api):
    assert len(api.get_milestones(days=400, limit=1)) == 1
    assert [m["days_until"] for m in api.get_milestones(days=5)] == [2, 5]
    assert api.get_milestones(days=1) == []


def test_milestones_respect_the_enabled_kinds(api):
    kinds = {m["kind"] for m in api.get_milestones(days=400, include_deaths=False, include_anniversaries=False)}
    assert kinds == {"birthday"}


# ------------------------------------------------------------------- on this day


def test_on_this_day(api):
    items = api.get_on_this_day(today=TODAY)
    assert [(i["year"], i["type"], i["people"]) for i in items] == [
        (1990, "Geburt", ["Dora Muster"]),
        (1999, "Wohnort", ["Dora Muster"]),
    ]
    assert items[0]["years_ago"] == 36
    assert items[0]["text"] == "1990 (vor 36 Jahren): Geburt – Dora Muster"
    assert items[1]["description"] == "Umzug nach Wien"
    assert items[0]["description"] is None


def test_on_this_day_in_english(make_api, frozen_today):
    items = make_api(language="en").get_on_this_day(today=TODAY)
    assert items[0]["text"] == "1990 (36 years ago): Birth – Dora Muster"
    assert items[1]["type"] == "Residence"


def test_on_this_day_includes_family_events(api):
    items = api.get_on_this_day(today=date(2026, 10, 15))
    assert [i["text"] for i in items] == ["2001 (vor 25 Jahren): Heirat – Carl Beispiel & Eva Beispiel"]
    divorce = api.get_on_this_day(today=date(2026, 1, 1))
    assert [(i["year"], i["type"]) for i in divorce] == [(1930, "Geburt"), (2010, "Scheidung")]
    assert divorce[1]["people"] == ["Carl Beispiel & Eva Beispiel"]


def test_on_this_day_leap_day_events(api):
    assert [i["year"] for i in api.get_on_this_day(today=date(2027, 2, 28))] == [2000]
    assert [i["year"] for i in api.get_on_this_day(today=date(2028, 2, 29))] == [2000]
    assert api.get_on_this_day(today=date(2028, 2, 28)) == []


def test_on_this_day_ignores_events_from_this_or_a_future_year(api):
    assert api.get_on_this_day(today=date(1990, 10, 13)) == []
    assert api.get_on_this_day(today=date(1989, 10, 13)) == []


def test_on_this_day_empty_and_limited(api):
    assert api.get_on_this_day(today=date(2026, 7, 7)) == []
    assert len(api.get_on_this_day(today=TODAY, limit=1)) == 1


def test_on_this_day_unknown_event_type_keeps_its_name(make_api):
    people = [person("p", "Pia", "Probe", ["e"])]
    events = [ev("e", "Custom Thing", 7, 7, 2000)]
    items = make_api(FakeServer(people, events, []), language="de").get_on_this_day(today=date(2026, 7, 7))
    assert items[0]["type"] == "Custom Thing"


def test_on_this_day_event_without_owner(make_api):
    events = [ev("e", "Birth", 7, 7, 2000)]
    items = make_api(FakeServer([], events, [])).get_on_this_day(today=date(2026, 7, 7))
    assert items[0]["people"] == []
    assert items[0]["text"] == "2000 (vor 26 Jahren): Geburt"


# ------------------------------------------------------------------------ statistics


def test_statistics(api):
    stats = api.get_statistics()
    assert stats["people"] == 8
    assert stats["families"] == 3
    assert stats["events"] == 13
    assert stats["places"] == 4
    assert stats["media"] == 2
    assert stats["sources"] == 1
    assert stats["notes"] == 5
    assert stats["citations"] == 0
    assert stats["living"] == 6
    assert stats["deceased"] == 2
    assert stats["male"] == 4
    assert stats["female"] == 4
    assert stats["without_birth_date"] == 2  # Frank and Gina
    assert stats["without_photo"] == 6
    assert stats["avg_age_living"] == 44.6  # 46, 49, 26, 36, 66
    assert stats["avg_lifespan"] == 76.0  # Carl: 1930-01-01 .. 2006-10-20
    assert stats["oldest_living"] == {"name": "Eva Beispiel", "age": 66, "birth_date": "1960-05-05"}
    assert stats["top_surnames"] == [{"surname": "Muster", "count": 5}, {"surname": "Beispiel", "count": 3}]
    assert stats["main_person"] == {"name": "Max Muster", "source": "gramps", "handle": "home"}


def test_statistics_age_is_the_current_age_not_the_next_one(api):
    stats = api.get_statistics()
    # Anna turns 50 in five days: she still counts as 49 today
    assert stats["avg_age_living"] == 44.6


def test_statistics_count_fallback_without_metadata(make_api, server):
    server.data["metadata/"] = {}
    stats = make_api().get_statistics()
    assert (stats["people"], stats["families"], stats["events"]) == (8, 3, 13)
    assert stats["places"] is None and stats["media"] is None


def test_statistics_of_an_empty_tree(make_api):
    stats = make_api(FakeServer([], [], [])).get_statistics()
    assert stats["people"] == 0
    assert stats["avg_age_living"] is None
    assert stats["avg_lifespan"] is None
    assert stats["oldest_living"] is None
    assert stats["top_surnames"] == []
    assert stats["main_person"] is None


def test_statistics_ignore_implausible_ages(make_api, frozen_today):
    """A person without a death entry who would be 150 must not skew the numbers."""
    people = [
        person("old", "Ur", "Alt", ["b"], birth=0),
        person("ok", "Neu", "Jung", ["c"], birth=0),
    ]
    events = [ev("b", "Birth", 1, 1, 1870), ev("c", "Birth", 1, 1, 2000)]
    stats = make_api(FakeServer(people, events, [])).get_statistics()
    assert stats["avg_age_living"] == 26.0
    assert stats["oldest_living"]["name"] == "Neu Jung"
    assert stats["living"] == 2  # still counted as living


@pytest.mark.parametrize("gender, key", [(0, "female"), (1, "male")])
def test_statistics_gender(make_api, gender, key):
    stats = make_api(FakeServer([person("p", "A", "B", gender=gender)], [], [])).get_statistics()
    assert stats[key] == 1
