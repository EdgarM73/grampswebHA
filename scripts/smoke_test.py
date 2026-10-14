"""Check a real Gramps Web server by hand (not part of the automated tests).

Usage (credentials come from the environment, never from this file):

    GRAMPS_URL=https://gramps.example.com GRAMPS_USER=name GRAMPS_PASSWORD=... \
        python scripts/smoke_test.py
"""

import importlib.util
import os
import pathlib
import sys
import time

API_FILE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "gramps_ha" / "grampsweb_api.py"


def main() -> int:
    url = os.environ.get("GRAMPS_URL")
    if not url:
        print("Set GRAMPS_URL (and GRAMPS_USER / GRAMPS_PASSWORD if the server needs a login).")
        return 2

    spec = importlib.util.spec_from_file_location("grampsweb_api", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    api = module.GrampsWebAPI(url, os.environ.get("GRAMPS_USER"), os.environ.get("GRAMPS_PASSWORD"))
    started = time.time()
    snapshot = api._load_snapshot()
    print(
        f"Loaded {len(snapshot['people'])} people, {len(snapshot['events'])} events, "
        f"{len(snapshot['families'])} families in {time.time() - started:.1f}s"
    )
    for name, getter in (
        ("birthdays", api.get_birthdays),
        ("deathdays", api.get_deathdays),
        ("anniversaries", api.get_anniversaries),
    ):
        items = getter(limit=3)
        print(f"\n{name}: {len(items)} shown")
        for item in items:
            print(f"  {item['person_name']} - in {item['days_until']} days")
    print("\nstatistics:", {k: v for k, v in api.get_statistics().items() if k in ("people", "living", "deceased")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
