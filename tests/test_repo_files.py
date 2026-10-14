"""Checks on the files HACS and Home Assistant read, and a guard against leaked credentials."""

from __future__ import annotations

import json
import os
import re

import pytest

from conftest import PKG, ROOT


def load(path):
    # The \\?\ prefix lifts the 260 character limit when the checkout sits in a very deep Windows folder
    target = "\\\\?\\" + str(path.resolve()) if os.name == "nt" else path
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest():
    manifest = load(PKG / "manifest.json")
    assert manifest["domain"] == PKG.name == "gramps_ha"
    assert manifest["config_flow"] is True
    assert re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}", manifest["version"]), manifest["version"]
    assert any(r.startswith("requests") for r in manifest["requirements"])
    for key in ("name", "documentation", "issue_tracker", "codeowners", "iot_class"):
        assert manifest[key]
    assert "grampswebHA" in manifest["documentation"] and "grampswebHA" in manifest["issue_tracker"]


def test_hacs_json():
    hacs = load(ROOT / "hacs.json")
    assert hacs["name"]
    assert "homeassistant" in hacs


@pytest.mark.parametrize("path", sorted((PKG / "translations").glob("*.json")) + [PKG / "strings.json"], ids=lambda p: p.name)
def test_translations_are_valid_json(path):
    assert isinstance(load(path), dict)


def test_every_platform_file_exists():
    for module in ("sensor", "calendar", "binary_sensor", "config_flow", "const", "grampsweb_api"):
        assert (PKG / f"{module}.py").exists(), module


CREDENTIAL = re.compile(
    r"""(?i)(?<![A-Za-z_])(password|passwd|secret|api[_-]?key|token)["']?\s*[:=]\s*["'][^"'\s]{3,}["']"""
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".cfg", ".ini", ".code-workspace"}
SKIP_DIRS = {".git", "tests", "brands", "__pycache__", ".pytest_cache", "node_modules"}


def test_no_credentials_are_committed():
    """Several old helper scripts contained real logins; make sure nothing like that comes back."""
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if CREDENTIAL.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, "possible credentials in: " + ", ".join(offenders)


def test_credential_pattern_catches_the_old_style():
    assert CREDENTIAL.search('password = "hunter22"')
    assert CREDENTIAL.search('PASSWORD = "hunter22"')
    assert CREDENTIAL.search('"password": "hunter22"')
    assert not CREDENTIAL.search('CONF_PASSWORD = "password"')
    assert not CREDENTIAL.search("password = os.environ['X']")
