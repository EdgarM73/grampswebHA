"""Builders and a fake Gramps Web server for the offline tests."""

from __future__ import annotations

import requests


def ev(handle: str, etype: str, day: int, month: int, year: int, description: str = "") -> dict:
    """An event as returned by /api/events/ (Gramps dateval is [day, month, year, slot])."""
    event = {
        "handle": handle,
        "type": {"string": etype},
        "date": {"dateval": [day, month, year, False]},
    }
    if description:
        event["description"] = description
    return event


def ev_no_date(handle: str, etype: str) -> dict:
    return {"handle": handle, "type": {"string": etype}, "date": {"dateval": [0, 0, 0, False]}}


def person(
    handle: str,
    first: str,
    surname: str,
    events: list[str] | None = None,
    birth: int = -1,
    death: int = -1,
    gender: int = 2,
    media: str | None = None,
) -> dict:
    """A person; `birth`/`death` are indexes into `events` (like Gramps' *_ref_index)."""
    data = {
        "handle": handle,
        "gender": gender,
        "primary_name": {"first_name": first, "surname_list": [{"surname": surname}]},
        "event_ref_list": [{"ref": h} for h in (events or [])],
        "birth_ref_index": birth,
        "death_ref_index": death,
        "media_list": [{"ref": media}] if media else [],
    }
    return data


def family(handle: str, father: str | None, mother: str | None, events: list[str]) -> dict:
    return {
        "handle": handle,
        "father_handle": father,
        "mother_handle": mother,
        "event_ref_list": [{"ref": h} for h in events],
    }


class FakeServer:
    """Stands in for GrampsWebAPI._get (the only place that talks to the network)."""

    def __init__(self, people, events, families, metadata=None, relations=None):
        self.data = {
            "people/": people,
            "events/": events,
            "families/": families,
            "metadata/": metadata if metadata is not None else {},
        }
        self.relations = relations or {}
        self.calls: list[tuple[str, dict | None]] = []
        self.fail = False  # raise on every request
        self.reject_keys = False  # emulate a server that does not know `keys`
        self.fail_relations = False

    def get(self, endpoint, params=None, quiet=False):
        self.calls.append((endpoint, params))
        if self.fail:
            raise requests.ConnectionError("server down")
        if endpoint.startswith("relations/"):
            if self.fail_relations:
                raise requests.HTTPError("404")
            return {"relationship_string": self.relations.get(endpoint.split("/")[-1], "")}
        if params and "keys" in params and self.reject_keys:
            raise requests.HTTPError("400 unknown parameter keys")
        rows = self.data[endpoint]
        if isinstance(rows, list) and params and "page" in params:
            size = params["pagesize"]
            start = (params["page"] - 1) * size
            return rows[start : start + size]
        return rows

    def count(self, prefix: str) -> int:
        return sum(1 for endpoint, _ in self.calls if endpoint.startswith(prefix))


class FakeResponse:
    def __init__(self, status=200, payload=None, content=b"", json_error=False):
        self.status_code = status
        self._payload = payload
        self.content = content
        self._json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        if self._json_error:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeSession:
    """Scripted requests.Session: responses are consumed in order per method."""

    def __init__(self, gets=None, posts=None):
        self.headers: dict = {}
        self._gets = list(gets or [])
        self._posts = list(posts or [])
        self.get_calls: list[tuple] = []
        self.post_calls: list[tuple] = []

    def get(self, url, params=None, timeout=None):
        self.get_calls.append((url, params, dict(self.headers)))
        return self._gets.pop(0) if len(self._gets) > 1 else self._gets[0]

    def post(self, url, json=None, timeout=None):
        self.post_calls.append((url, json))
        return self._posts.pop(0) if len(self._posts) > 1 else self._posts[0]
