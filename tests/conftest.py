"""Shared fixtures: the API module without Home Assistant, a fixed "today", a sample tree."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import date

import pytest

from helpers import FakeServer, ev, ev_no_date, family, person

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "gramps_ha"
TODAY = date(2026, 10, 13)


@pytest.fixture(scope="session")
def api_module():
    """grampsweb_api.py loaded on its own, so these tests do not need Home Assistant."""
    spec = importlib.util.spec_from_file_location("grampsweb_api_under_test", PKG / "grampsweb_api.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["grampsweb_api_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def frozen_today(api_module, monkeypatch):
    """Make date.today() inside the API module return TODAY (2026-10-13)."""

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(api_module, "date", FrozenDate)
    return TODAY


def sample_tree() -> FakeServer:
    """A small tree whose dates are chosen relative to TODAY = 2026-10-13.

    people (alive unless noted)
      home   Max Muster      born 1980-06-01, the Gramps home person
      anna   Anna Muster     born 1976-10-18   -> 50th birthday in 5 days
      bob    Bob Muster      born 2000-02-29   -> leap-day birthday
      dora   Dora Muster     born 1990-10-13   -> birthday today
      eva    Eva Beispiel    born 1960-05-05, married to carl
      carl   Carl Beispiel   born 1930-01-01, died 2006-10-20 (deceased)
      frank  Frank Muster    no birth date
      gina   Gina Beispiel   death event without a date
    families
      f1 carl + eva   Marriage 2001-10-15 (25th anniversary in 2 days), Divorce event ignored
      f2 bob + dora   Engagement 2015-03-10
      f3 anna + frank Marriage without a date (ignored)
    """
    events = [
        ev("e_home_b", "Birth", 1, 6, 1980),
        ev("e_anna_b", "Birth", 18, 10, 1976),
        ev("e_bob_b", "Birth", 29, 2, 2000),
        ev("e_dora_b", "Birth", 13, 10, 1990),
        ev("e_eva_b", "Birth", 5, 5, 1960),
        ev("e_carl_b", "Birth", 1, 1, 1930),
        ev("e_carl_d", "Death", 20, 10, 2006),
        ev_no_date("e_gina_d", "Death"),
        ev("e_f1_m", "Marriage", 15, 10, 2001),
        ev("e_f1_div", "Divorce", 1, 1, 2010),
        ev("e_f2_eng", "Engagement", 10, 3, 2015),
        ev_no_date("e_f3_m", "Marriage"),
        ev("e_resid", "Residence", 13, 10, 1999, description="Umzug nach Wien"),
    ]
    people = [
        person("home", "Max", "Muster", ["e_home_b"], birth=0, gender=1),
        person("anna", "Anna", "Muster", ["e_anna_b"], birth=0, gender=0, media="m_anna"),
        person("bob", "Bob", "Muster", ["e_bob_b"], birth=0, gender=1),
        person("dora", "Dora", "Muster", ["e_dora_b", "e_resid"], birth=0, gender=0),
        person("eva", "Eva", "Beispiel", ["e_eva_b"], birth=0, gender=0),
        person("carl", "Carl", "Beispiel", ["e_carl_b", "e_carl_d"], birth=0, death=1, gender=1, media="m_carl"),
        person("frank", "Frank", "Muster", [], gender=1),
        person("gina", "Gina", "Beispiel", ["e_gina_d"], death=0, gender=0),
    ]
    families = [
        family("f1", "carl", "eva", ["e_f1_m", "e_f1_div"]),
        family("f2", "bob", "dora", ["e_f2_eng"]),
        family("f3", "frank", "anna", ["e_f3_m"]),
    ]
    metadata = {
        "default_person": "home",
        "object_counts": {
            "people": 8, "families": 3, "events": 13, "places": 4, "media": 2,
            "sources": 1, "citations": 0, "repositories": 0, "notes": 5, "tags": 0,
        },
    }
    relations = {"anna": "Schwester", "carl": "Großvater", "eva": "Mutter"}
    return FakeServer(people, events, families, metadata, relations)


@pytest.fixture
def server():
    return sample_tree()


@pytest.fixture
def make_api(api_module, server):
    """Factory: an API client wired to the fake server (no network, no sleeping)."""

    def factory(srv=None, **kwargs):
        client = api_module.GrampsWebAPI("http://gramps.test", **kwargs)
        client._get = (srv or server).get
        return client

    return factory


@pytest.fixture
def api(make_api, frozen_today):
    return make_api()
