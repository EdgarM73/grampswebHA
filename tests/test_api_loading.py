"""Bulk loading, pagination, caching, stale-data fallback and authentication."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pytest
import requests

from helpers import FakeResponse, FakeServer, FakeSession


def test_snapshot_uses_one_request_per_collection(make_api, server):
    api = make_api()
    api.get_birthdays()
    api.get_deathdays()
    api.get_anniversaries()
    api.get_calendar_events(date(2026, 10, 1), date(2026, 10, 1))
    api.get_statistics()
    assert server.count("people/") == 1
    assert server.count("events/") == 1
    assert server.count("families/") == 1
    assert server.count("metadata/") == 1


def test_no_per_person_requests(make_api, server):
    """Regression: the old client sent several requests per person and per event."""
    make_api().get_birthdays()
    endpoints = {endpoint for endpoint, _ in server.calls}
    assert not any(e.startswith(("people/", "events/")) and e not in ("people/", "events/") for e in endpoints)
    assert not any(e.startswith("families/") and e != "families/" for e in endpoints)


def test_requests_ask_only_for_needed_fields(make_api, server):
    make_api().get_birthdays()
    params = {endpoint: p for endpoint, p in server.calls if p and "keys" in p}
    assert "event_ref_list" in params["people/"]["keys"]
    assert "gender" in params["people/"]["keys"]
    assert params["events/"]["keys"] == "handle,type,date,description"
    assert "father_handle" in params["families/"]["keys"]


def test_pagination_collects_every_page(api_module, make_api, server, monkeypatch):
    monkeypatch.setattr(api_module, "PAGE_SIZE", 3)
    api = make_api()
    snapshot = api._load_snapshot()
    assert len(snapshot["people"]) == 8
    assert len(snapshot["events"]) == 13
    assert len(snapshot["families"]) == 3
    assert server.count("people/") == 3  # 3 + 3 + 2
    assert server.count("events/") == 5  # 3 + 3 + 3 + 3 + 1
    assert server.count("families/") == 2  # a full page needs one more (empty) request


def test_pagination_accepts_dict_responses(make_api):
    api = make_api()
    api._get = lambda endpoint, params=None, quiet=False: {"results": [{"handle": "x"}]}
    assert api._get_all("people/", "handle") == [{"handle": "x"}]


def test_falls_back_when_server_rejects_keys(make_api, server):
    server.reject_keys = True
    api = make_api()
    snapshot = api._load_snapshot()
    assert len(snapshot["people"]) == 8
    people_calls = [p for endpoint, p in server.calls if endpoint == "people/"]
    assert "keys" in people_calls[0] and "keys" not in people_calls[1]


def test_other_errors_are_not_swallowed_by_the_keys_fallback(make_api, server):
    server.fail = True
    with pytest.raises(requests.ConnectionError):
        make_api()._load_snapshot()


def test_metadata_failure_is_not_fatal(make_api, server):
    original = server.get

    def failing_metadata(endpoint, params=None, quiet=False):
        if endpoint == "metadata/":
            raise requests.HTTPError("403")
        return original(endpoint, params, quiet)

    api = make_api()
    api._get = failing_metadata
    snapshot = api._load_snapshot()
    assert snapshot["metadata"] == {}
    assert api.get_statistics()["people"] == 8  # falls back to counting the list


def test_snapshot_is_reused_until_ttl_expires(make_api, server):
    api = make_api()
    api._load_snapshot()
    api._load_snapshot()
    assert server.count("people/") == 1

    api._snapshot_timestamp = datetime.now() - timedelta(seconds=api._cache_ttl_seconds + 1)
    api._load_snapshot()
    assert server.count("people/") == 2


def test_invalidate_cache_forces_reload(make_api, server):
    api = make_api()
    api._load_snapshot()
    api.invalidate_cache()
    api._load_snapshot()
    assert server.count("people/") == 2


def test_calendar_style_calls_never_reload_an_expired_snapshot(make_api, server):
    """Calendar/milestone queries use whatever data is there instead of hitting the server."""
    api = make_api()
    api._load_snapshot()
    api._snapshot_timestamp = datetime.now() - timedelta(days=3)
    api.get_calendar_events(date(2026, 10, 1), date(2026, 10, 31))
    assert server.count("people/") == 1


def test_keeps_last_data_when_the_server_fails(make_api, server, caplog):
    api = make_api()
    before = [b["person_name"] for b in api.get_birthdays()]
    assert before

    api.invalidate_cache()
    server.fail = True
    with caplog.at_level(logging.WARNING):
        after = [b["person_name"] for b in api.get_birthdays()]
    assert after == before
    assert "Could not refresh Gramps Web data" in caplog.text

    # ...and does not retry on every call, only after a few minutes
    calls = len(server.calls)
    api.get_birthdays()
    assert len(server.calls) == calls


def test_failed_refresh_is_retried_after_five_minutes(make_api, server):
    api = make_api()
    api._load_snapshot()
    api.invalidate_cache()
    server.fail = True
    api._load_snapshot()
    attempts = server.count("people/")  # the failed attempt is a request too
    remaining = api._cache_ttl_seconds - (datetime.now() - api._snapshot_timestamp).total_seconds()
    assert 290 <= remaining <= 300

    server.fail = False
    api._snapshot_timestamp = datetime.now() - timedelta(seconds=api._cache_ttl_seconds - 1)
    api._load_snapshot()  # still inside the retry window: no new request
    assert server.count("people/") == attempts
    api._snapshot_timestamp = datetime.now() - timedelta(seconds=api._cache_ttl_seconds + 1)
    api._load_snapshot()
    assert server.count("people/") == attempts + 1


def test_first_load_failure_raises_but_lists_stay_empty(make_api, server):
    server.fail = True
    api = make_api()
    with pytest.raises(requests.ConnectionError):
        api._load_snapshot()
    assert api.get_birthdays() == []
    assert api.get_deathdays() == []
    assert api.get_anniversaries() == []
    assert api.get_calendar_events(date(2026, 1, 1), date(2026, 1, 1)) == []
    assert api.get_on_this_day() == []
    assert api.get_statistics() == {}


# --------------------------------------------------------------------- HTTP / auth


def make_http_api(api_module, session, **kwargs):
    api = api_module.GrampsWebAPI("http://gramps.test/", **kwargs)
    api._session = session
    return api


def test_url_trailing_slash_is_removed(api_module):
    assert api_module.GrampsWebAPI("http://gramps.test///").url == "http://gramps.test"


def test_get_authenticates_first_and_sends_the_token(api_module):
    session = FakeSession(
        gets=[FakeResponse(200, payload=[{"a": 1}])],
        posts=[FakeResponse(200, payload={"access_token": "T1"})],
    )
    api = make_http_api(api_module, session, username="u", password="p")
    assert api._get("people/", {"page": 1}) == [{"a": 1}]
    assert session.post_calls == [("http://gramps.test/api/token/", {"username": "u", "password": "p"})]
    url, params, headers = session.get_calls[0]
    assert url == "http://gramps.test/api/people/"
    assert params == {"page": 1}
    assert headers["Authorization"] == "Bearer T1"


def test_get_without_credentials_does_not_authenticate(api_module):
    session = FakeSession(gets=[FakeResponse(200, payload={})])
    api = make_http_api(api_module, session)
    api._get("metadata/")
    assert session.post_calls == []


def test_expired_token_is_renewed_once_and_the_request_retried(api_module):
    session = FakeSession(
        gets=[FakeResponse(401), FakeResponse(200, payload=["ok"])],
        posts=[FakeResponse(200, payload={"access_token": "T1"}), FakeResponse(200, payload={"access_token": "T2"})],
    )
    api = make_http_api(api_module, session, username="u", password="p")
    assert api._get("people/") == ["ok"]
    assert len(session.post_calls) == 2
    assert session.get_calls[1][2]["Authorization"] == "Bearer T2"
    assert api.token == "T2"


def test_a_second_401_is_an_error(api_module):
    session = FakeSession(gets=[FakeResponse(401)], posts=[FakeResponse(200, payload={"access_token": "T"})])
    api = make_http_api(api_module, session, username="u", password="p")
    with pytest.raises(requests.HTTPError):
        api._get("people/")


def test_failed_login_is_reported_not_raised(api_module, caplog):
    session = FakeSession(posts=[FakeResponse(405)], gets=[FakeResponse(200, payload=[])])
    api = make_http_api(api_module, session, username="u", password="p")
    with caplog.at_level(logging.WARNING):
        assert api._authenticate() is False
    assert "Failed to authenticate" in caplog.text


def test_non_json_answer_raises(api_module):
    """A proxy answering with an HTML page instead of Gramps Web (the 405 case)."""
    session = FakeSession(gets=[FakeResponse(200, json_error=True)])
    api = make_http_api(api_module, session)
    with pytest.raises(ValueError):
        api._get("people/")


def test_quiet_requests_do_not_log_errors(api_module, caplog):
    session = FakeSession(gets=[FakeResponse(404)])
    api = make_http_api(api_module, session)
    with caplog.at_level(logging.ERROR), pytest.raises(requests.HTTPError):
        api._get("relations/a/b", quiet=True)
    assert "failed" not in caplog.text
    with caplog.at_level(logging.ERROR), pytest.raises(requests.HTTPError):
        api._get("relations/a/b")
    assert "failed" in caplog.text


def test_server_fixture_is_isolated(server):
    assert isinstance(server, FakeServer)
    assert server.calls == []
