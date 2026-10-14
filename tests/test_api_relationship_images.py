"""Relationship to the main person, main-person lookup, and (grayscale) images."""

from __future__ import annotations

import hashlib
import io
import logging
import time
from pathlib import Path

import pytest

from helpers import FakeResponse, FakeServer, FakeSession, person

# ------------------------------------------------------------------ main person


def test_home_person_from_gramps_is_the_default(api):
    api._load_snapshot()
    assert api._main_person(api._snapshot) == ("home", "gramps")


def test_main_person_by_name(api):
    api.main_person_name = "Anna Muster"
    api._load_snapshot()
    assert api._main_person(api._snapshot) == ("anna", "name")


@pytest.mark.parametrize("name", ["anna muster", "  Anna   Muster ", "Muster Anna", "ANNA MUSTER"])
def test_main_person_name_matching_is_forgiving(api, name):
    api.main_person_name = name
    api._load_snapshot()
    assert api._main_person(api._snapshot)[0] == "anna"


def test_ambiguous_name_falls_back_to_the_home_person(make_api, server):
    server.data["people/"].append(person("anna2", "Anna", "Muster"))
    api = make_api()
    api.main_person_name = "Anna Muster"
    api._load_snapshot()
    assert api._main_person(api._snapshot) == ("home", "gramps")


def test_unknown_name_falls_back_to_the_home_person(api):
    api.main_person_name = "Nobody Here"
    api._load_snapshot()
    assert api._main_person(api._snapshot) == ("home", "gramps")


def test_no_name_and_no_home_person(make_api, server):
    server.data["metadata/"] = {}
    api = make_api()
    api._load_snapshot()
    assert api._main_person(api._snapshot) == (None, None)
    assert api._main_person_info(api._snapshot) is None
    assert api._relationship("anna") is None
    assert server.count("relations/") == 0


def test_main_person_lookup_happens_once_per_snapshot(api):
    api.main_person_name = "Anna Muster"
    snapshot = api._load_snapshot()
    api._main_person(snapshot)
    snapshot["people"].clear()  # a second lookup would now find nobody
    assert api._main_person(snapshot) == ("anna", "name")


def test_main_person_info(api):
    api.main_person_name = "Eva Beispiel"
    snapshot = api._load_snapshot()
    assert api._main_person_info(snapshot) == {"name": "Eva Beispiel", "source": "name", "handle": "eva"}


# ----------------------------------------------------------------- relationships


def test_relationship_is_asked_from_the_main_person(api, server):
    api.main_person_name = "Anna Muster"
    api._load_snapshot()
    assert api._relationship("carl") == "Großvater"
    endpoint, params = server.calls[-1]
    assert endpoint == "relations/anna/carl"
    assert params == {"locale": "de"}
    assert server.calls[-1][0] != "relations/home/carl"


def test_relationship_to_oneself_or_without_handle_needs_no_request(api, server):
    api._load_snapshot()
    assert api._relationship("home") is None
    assert api._relationship(None) is None
    assert api._relationship("") is None
    assert server.count("relations/") == 0


def test_relationship_is_cached(api, server):
    api._load_snapshot()
    assert api._relationship("anna") == "Schwester"
    assert api._relationship("anna") == "Schwester"
    assert server.count("relations/") == 1


def test_unrelated_people_have_no_relationship_and_are_cached_too(api, server):
    api._load_snapshot()
    assert api._relationship("dora") is None  # the server answers with ""
    assert api._relationship("dora") is None
    assert server.count("relations/") == 1


def test_relationship_cache_expires_after_a_week(api, server):
    api._load_snapshot()
    api._relationship("anna")
    expires, value = api._relation_cache["anna"]
    assert 6.9 * 86400 < expires - time.time() < 7.1 * 86400
    api._relation_cache["anna"] = (time.time() - 1, value)
    api._relationship("anna")
    assert server.count("relations/") == 2


def test_failed_relationship_requests_are_retried_after_an_hour(api, server):
    api._load_snapshot()
    server.fail_relations = True
    assert api._relationship("anna") is None
    assert api._relationship("anna") is None
    assert server.count("relations/") == 1  # no hammering
    expires, _ = api._relation_cache["anna"]
    assert 3500 < expires - time.time() < 3700
    server.fail_relations = False
    api._relation_cache["anna"] = (time.time() - 1, None)
    assert api._relationship("anna") == "Schwester"


@pytest.mark.parametrize("language, locale", [("de", "de"), ("en", "en"), ("de-DE", "de"), ("pt_BR", "pt")])
def test_relationship_locale(make_api, frozen_today, server, language, locale):
    api = make_api(language=language)
    api._load_snapshot()
    api._relationship("anna")
    assert server.calls[-1][1] == {"locale": locale}


def test_lists_only_look_up_the_returned_entries(api, server):
    api.get_birthdays(limit=2)  # Dora, Anna
    asked = {endpoint for endpoint, _ in server.calls if endpoint.startswith("relations/")}
    assert asked == {"relations/home/dora", "relations/home/anna"}


def test_relationship_is_part_of_the_list_entries(api):
    birthdays = {b["person_name"]: b for b in api.get_birthdays()}
    assert birthdays["Anna Muster"]["relationship"] == "Schwester"
    assert "relationship" not in birthdays["Dora Muster"]  # not related
    assert "relationship" not in birthdays["Max Muster"]  # that is the home person itself
    assert api.get_deathdays()[0]["relationship"] == "Großvater"
    silver = api.get_anniversaries()[0]
    assert silver["relationship_person1"] == "Großvater"
    assert silver["relationship_person2"] == "Mutter"


# ------------------------------------------------------------------------ images


def person_with_media(handle="anna", media="m_anna"):
    return {"handle": handle, "media_list": [{"ref": media}]}


def test_remote_thumbnail_url_without_a_config_path(api):
    assert api._get_person_image_url(person_with_media()) == "http://gramps.test/api/media/m_anna/thumbnail/200"


@pytest.mark.parametrize(
    "media_ref, handle",
    [({"ref": "h1"}, "h1"), ({"handle": "h2"}, "h2"), ({"hlink": "a/b/h3/"}, "h3"), ("h4", "h4")],
)
def test_media_reference_formats(api, media_ref, handle):
    url = api._get_person_image_url({"handle": "p", "media_list": [media_ref]})
    assert url.endswith(f"/api/media/{handle}/thumbnail/200")


@pytest.mark.parametrize("data", [{}, {"handle": "p"}, {"handle": "p", "media_list": []}, {"media_list": [{"ref": "m"}]}])
def test_no_image(api, data):
    assert api._get_person_image_url(data) is None


@pytest.fixture
def image_api(api_module, tmp_path):
    pil = pytest.importorskip("PIL.Image")
    buffer = io.BytesIO()
    pil.new("RGB", (20, 20), (200, 30, 30)).save(buffer, "JPEG")
    api = api_module.GrampsWebAPI("http://gramps.test", hass_config_path=str(tmp_path))
    api._session = FakeSession(gets=[FakeResponse(200, content=buffer.getvalue())])
    api.images = Path(api.images_dir)
    return api


def md5(person_handle, media_handle):
    return hashlib.md5(f"{person_handle}_{media_handle}".encode()).hexdigest()


def pixel(path):
    from PIL import Image

    with Image.open(path) as img:
        return img.convert("RGB").getpixel((5, 5))


def test_image_is_downloaded_once_and_served_from_local(image_api):
    name = md5("anna", "m_anna")
    assert image_api._get_person_image_url(person_with_media()) == f"/local/gramps/{name}.jpg"
    assert (image_api.images / f"{name}.jpg").exists()
    image_api._get_person_image_url(person_with_media())
    assert len(image_api._session.get_calls) == 1


def test_grayscale_copy(image_api):
    name = md5("anna", "m_anna")
    url = image_api._get_person_image_url(person_with_media(), grayscale=True)
    assert url == f"/local/gramps/{name}_gray.jpg"
    r, g, b = pixel(image_api.images / f"{name}_gray.jpg")
    assert r == g == b
    red, green, _ = pixel(image_api.images / f"{name}.jpg")
    assert red > 150 and green < 80  # the original keeps its colour


def test_grayscale_is_created_once(image_api):
    image_api._get_person_image_url(person_with_media(), grayscale=True)
    image_api._get_person_image_url(person_with_media(), grayscale=True)
    image_api._get_person_image_url(person_with_media())
    assert len(image_api._session.get_calls) == 1


def test_grayscale_failure_falls_back_to_colour(api_module, tmp_path, caplog):
    api = api_module.GrampsWebAPI("http://gramps.test", hass_config_path=str(tmp_path))
    api._session = FakeSession(gets=[FakeResponse(200, content=b"definitely not an image")])
    pytest.importorskip("PIL")
    with caplog.at_level(logging.WARNING):
        url = api._get_person_image_url(person_with_media(), grayscale=True)
    assert url == f"/local/gramps/{md5('anna', 'm_anna')}.jpg"
    assert "Could not create grayscale image" in caplog.text


def test_download_failure_returns_the_remote_url(api_module, tmp_path):
    api = api_module.GrampsWebAPI("http://gramps.test", hass_config_path=str(tmp_path))
    api._session = FakeSession(gets=[FakeResponse(500)])
    assert api._get_person_image_url(person_with_media()).endswith("/api/media/m_anna/thumbnail/200")


def test_deceased_partners_get_the_grayscale_image(api_module, tmp_path, server, frozen_today):
    pytest.importorskip("PIL")
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 30, 30)).save(buffer, "JPEG")
    api = api_module.GrampsWebAPI("http://gramps.test", hass_config_path=str(tmp_path))
    api._get = server.get
    api._session = FakeSession(gets=[FakeResponse(200, content=buffer.getvalue())])
    silver = api.get_anniversaries()[0]
    assert silver["person1_deceased"] is True
    assert silver["image_url_person1"].endswith("_gray.jpg")  # Carl, deceased
    assert "image_url_person2" not in silver  # Eva has no photo


def test_images_are_only_fetched_for_the_returned_entries(api_module, tmp_path, server, frozen_today):
    """Regression: thumbnails used to be downloaded for everybody before the limit was applied."""
    pytest.importorskip("PIL")
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buffer, "JPEG")
    api = api_module.GrampsWebAPI("http://gramps.test", hass_config_path=str(tmp_path))
    api._get = server.get
    api._session = FakeSession(gets=[FakeResponse(200, content=buffer.getvalue())])
    api.get_birthdays(limit=1)  # only Dora, who has no photo
    assert api._session.get_calls == []
    api.get_birthdays(limit=2)  # Anna has one
    assert len(api._session.get_calls) == 1


def test_fake_server_is_not_shared_between_tests(server):
    assert isinstance(server, FakeServer)
