"""Birthday / deathday / anniversary lists, date helpers and milestone labels."""

from __future__ import annotations

from datetime import date

import pytest

from helpers import FakeServer, ev, family, person


def names(items):
    return [i["person_name"] for i in items]


# ------------------------------------------------------------------ date helpers


@pytest.mark.parametrize(
    "original, today, expected",
    [
        (date(1990, 10, 13), date(2026, 10, 13), date(2026, 10, 13)),  # today counts
        (date(1990, 10, 12), date(2026, 10, 13), date(2027, 10, 12)),  # already passed
        (date(2000, 2, 29), date(2026, 10, 13), date(2027, 2, 28)),  # leap day, normal year
        (date(2000, 2, 29), date(2027, 2, 28), date(2027, 2, 28)),
        (date(2000, 2, 29), date(2027, 3, 1), date(2028, 2, 29)),  # next year is a leap year
        (date(2000, 2, 29), date(2028, 2, 29), date(2028, 2, 29)),
        (date(1999, 12, 31), date(2026, 12, 31), date(2026, 12, 31)),
        (date(1999, 1, 1), date(2026, 12, 31), date(2027, 1, 1)),  # across New Year
    ],
)
def test_next_occurrence(api_module, original, today, expected):
    assert api_module.GrampsWebAPI._next_occurrence(original, today) == expected


def test_date_in_year_handles_feb_29(api_module):
    f = api_module.GrampsWebAPI._date_in_year
    assert f(date(2000, 2, 29), 2027) == date(2027, 2, 28)
    assert f(date(2000, 2, 29), 2028) == date(2028, 2, 29)
    assert f(date(1990, 5, 5), 2030) == date(2030, 5, 5)


@pytest.mark.parametrize(
    "value, expected",
    [
        ([13, 10, 1990, False], date(1990, 10, 13)),  # Gramps: day, month, year
        ({"val": [13, 10, 1990, False]}, date(1990, 10, 13)),
        ({"start": [1, 1, 2000, False]}, date(2000, 1, 1)),
        ([0, 0, 1990, False], None),  # year only
        ([0, 10, 1990, False], None),  # no day
        ([31, 2, 1990, False], None),  # impossible date
        ([13, 10], None),
        ("1990-10-13", None),
        (None, None),
        (["a", "b", "c"], None),
    ],
)
def test_parse_dateval(api, value, expected):
    assert api._parse_dateval(value) == expected


# ------------------------------------------------------------------- milestones


@pytest.mark.parametrize(
    "kind, years, lang, expected",
    [
        ("birthday", 18, "de", "18. Geburtstag"),
        ("birthday", 50, "de", "50. Geburtstag"),
        ("birthday", 10, "de", "10. Geburtstag"),
        ("birthday", 50, "en", "50th birthday"),
        ("birthday", 50, "de-DE", "50. Geburtstag"),
        ("birthday", 50, "DE", "50. Geburtstag"),
        ("birthday", 50, "fr", "50th birthday"),
        ("birthday", 25, "de", None),
        ("birthday", 17, "de", None),
        ("birthday", 0, "de", None),
        ("birthday", -10, "de", None),
        ("birthday", None, "de", None),
        ("anniversary", 25, "de", "Silberhochzeit (25)"),
        ("anniversary", 30, "de", "Perlenhochzeit (30)"),
        ("anniversary", 40, "de", "Rubinhochzeit (40)"),
        ("anniversary", 50, "de", "Goldene Hochzeit (50)"),
        ("anniversary", 60, "de", "Diamantene Hochzeit (60)"),
        ("anniversary", 65, "de", "Eiserne Hochzeit (65)"),
        ("anniversary", 70, "de", "Gnadenhochzeit (70)"),
        ("anniversary", 5, "de", "5. Hochzeitstag"),
        ("anniversary", 35, "de", "35. Hochzeitstag"),
        ("anniversary", 25, "en", "Silver wedding anniversary (25)"),
        ("anniversary", 35, "en", "35th wedding anniversary"),
        ("anniversary", 24, "de", None),
        ("deathday", 20, "de", "20. Todestag"),
        ("deathday", 20, "en", "20th death anniversary"),
        ("deathday", 15, "de", None),
        ("unknown", 20, "de", None),
    ],
)
def test_milestone_label(api_module, kind, years, lang, expected):
    assert api_module.milestone_label(kind, years, lang) == expected


# ---------------------------------------------------------------------- birthdays


def test_birthdays_sorted_and_limited_to_living_people_with_a_date(api):
    result = api.get_birthdays()
    assert names(result) == [
        "Dora Muster",  # today
        "Anna Muster",  # in 5 days
        "Bob Muster",  # 2027-02-28
        "Eva Beispiel",
        "Max Muster",
    ]
    # Carl and Gina are dead, Frank has no birth date
    assert not {"Carl Beispiel", "Frank Muster", "Gina Beispiel"} & set(names(result))


def test_birthday_fields(api):
    by_name = {b["person_name"]: b for b in api.get_birthdays()}

    dora = by_name["Dora Muster"]
    assert dora["birth_date"] == "1990-10-13"
    assert dora["next_birthday"] == "2026-10-13"
    assert dora["age"] == 36
    assert dora["days_until"] == 0
    assert dora["person_handle"] == "dora"
    assert "milestone" not in dora

    anna = by_name["Anna Muster"]
    assert anna["next_birthday"] == "2026-10-18"
    assert anna["age"] == 50  # the age she is turning, not the current one
    assert anna["days_until"] == 5
    assert anna["milestone"] == "50. Geburtstag"


def test_leap_day_birthday_in_a_normal_year(api):
    bob = next(b for b in api.get_birthdays() if b["person_name"] == "Bob Muster")
    assert bob["birth_date"] == "2000-02-29"
    assert bob["next_birthday"] == "2027-02-28"
    assert bob["age"] == 27


def test_birthday_limit(api):
    assert names(api.get_birthdays(limit=2)) == ["Dora Muster", "Anna Muster"]
    assert api.get_birthdays(limit=0) == []


def test_birthday_uses_birth_event_not_the_first_dated_event(make_api):
    """Regression: the old code accepted any event when birth_ref_index was missing."""
    people = [person("p", "Pia", "Probe", ["e_res", "e_birth"], birth=1)]
    events = [ev("e_res", "Residence", 1, 1, 2000), ev("e_birth", "Birth", 5, 5, 1980)]
    result = make_api(FakeServer(people, events, [])).get_birthdays()
    assert result[0]["birth_date"] == "1980-05-05"


def test_birth_found_by_scanning_when_the_index_is_missing(make_api):
    people = [person("p", "Pia", "Probe", ["e_res", "e_birth"], birth=-1)]
    events = [ev("e_res", "Residence", 1, 1, 2000), ev("e_birth", "Birth", 5, 5, 1980)]
    result = make_api(FakeServer(people, events, [])).get_birthdays()
    assert result[0]["birth_date"] == "1980-05-05"


def test_person_without_events_is_skipped_without_error(make_api):
    people = [person("p", "Pia", "Probe", [])]
    assert make_api(FakeServer(people, [], [])).get_birthdays() == []


def test_missing_event_reference_is_ignored(make_api):
    people = [person("p", "Pia", "Probe", ["does_not_exist"], birth=0)]
    assert make_api(FakeServer(people, [], [])).get_birthdays() == []


def test_name_fallbacks(api):
    assert api._get_person_name({}) == "Unknown"
    assert api._get_person_name({"primary_name": {"first_name": "Only"}}) == "Only"
    assert api._get_person_name({"primary_name": {"surname_list": [{"surname": "Last"}]}}) == "Last"


# ---------------------------------------------------------------------- deathdays


def test_deathdays(api):
    result = api.get_deathdays()
    assert names(result) == ["Carl Beispiel"]  # Gina's death has no date
    carl = result[0]
    assert carl["death_date"] == "2006-10-20"
    assert carl["next_deathday"] == "2026-10-20"
    assert carl["years_ago"] == 20
    assert carl["days_until"] == 7
    assert carl["milestone"] == "20. Todestag"
    assert carl["person_handle"] == "carl"


def test_death_index_pointing_to_a_non_death_event_is_ignored(make_api):
    people = [person("p", "Pia", "Probe", ["e_burial"], death=0)]
    events = [ev("e_burial", "Burial", 1, 1, 2000)]
    assert make_api(FakeServer(people, events, [])).get_deathdays() == []


def test_death_event_found_without_index(make_api):
    people = [person("p", "Pia", "Probe", ["e_death"], death=0)]
    events = [ev("e_death", "Death", 2, 3, 1999)]
    result = make_api(FakeServer(people, events, [])).get_deathdays()
    assert result[0]["death_date"] == "1999-03-02"


# ------------------------------------------------------------------ anniversaries


def test_anniversaries(api):
    result = api.get_anniversaries()
    # the divorce, the undated marriage and the family without partners add nothing
    assert names(result) == ["Carl Beispiel & Eva Beispiel", "Bob Muster & Dora Muster"]


def test_silver_wedding(api):
    silver = api.get_anniversaries()[0]
    assert silver["marriage_date"] == "2001-10-15"
    assert silver["next_anniversary"] == "2026-10-15"
    assert silver["days_until"] == 2
    assert silver["years_together"] == 25
    assert silver["milestone"] == "Silberhochzeit (25)"
    assert silver["family_handle"] == "f1"


def test_engagement_counts_as_an_anniversary(api):
    engagement = next(a for a in api.get_anniversaries() if a["family_handle"] == "f2")
    assert engagement["marriage_date"] == "2015-03-10"
    assert engagement["next_anniversary"] == "2027-03-10"


def test_deceased_flag_per_partner(api):
    silver = api.get_anniversaries()[0]
    assert silver["person1_deceased"] is True  # father Carl
    assert silver["person2_deceased"] is False  # mother Eva


def test_anniversary_limit(api):
    assert len(api.get_anniversaries(limit=1)) == 1


def test_event_shared_by_two_families_is_listed_once(make_api):
    people = [person("a", "A", "X"), person("b", "B", "X"), person("c", "C", "X")]
    events = [ev("m", "Marriage", 1, 1, 2000)]
    families = [family("f1", "a", "b", ["m"]), family("f2", "a", "c", ["m"])]
    assert len(make_api(FakeServer(people, events, families)).get_anniversaries()) == 1


def test_family_with_unknown_partners_is_skipped(make_api):
    events = [ev("m", "Marriage", 1, 1, 2000)]
    families = [family("f1", "ghost1", "ghost2", ["m"]), family("f2", None, None, ["m"])]
    assert make_api(FakeServer([], events, families)).get_anniversaries() == []


def test_single_parent_family(make_api):
    people = [person("a", "Ann", "Alone")]
    events = [ev("m", "Marriage", 1, 1, 2000)]
    families = [family("f1", "a", None, ["m"])]
    assert names(make_api(FakeServer(people, events, families)).get_anniversaries()) == ["Ann Alone"]
