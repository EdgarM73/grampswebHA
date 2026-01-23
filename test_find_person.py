"""Find person by name and inspect death event."""
import re
import requests
import pprint

URL = "http://homeassistant:5000"
USERNAME = "erdal"
PASSWORD = "1_Linux?"
TARGET_FIRST = "muhamed"
TARGET_SURNAME = "rustemovic"

def main():
    tok = requests.post(
        f"{URL}/api/token/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    tok.raise_for_status()
    token = tok.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    people = requests.get(f"{URL}/api/people/", headers=headers, timeout=20).json()

    matches = []
    for p in people:
        name = p.get("primary_name", {})
        first = name.get("first_name", "")
        surns = name.get("surname_list", [])
        surname = surns[0].get("surname", "") if surns else ""
        if re.search(TARGET_FIRST, first, re.I) or re.search(TARGET_SURNAME, surname, re.I):
            matches.append(p)

    print(f"Matches: {len(matches)}")
    pp = pprint.PrettyPrinter(indent=2, width=120)
    for p in matches:
        name = p.get("primary_name", {})
        first = name.get("first_name", "")
        surns = name.get("surname_list", [])
        surname = surns[0].get("surname", "") if surns else ""
        death_idx = p.get("death_ref_index", -1)
        events = p.get("event_ref_list", [])
        print(f"\nPerson: {first} {surname} | death_ref_index={death_idx} | events={len(events)}")
        
        if death_idx >= 0 and death_idx < len(events):
            evref = events[death_idx]
            handle = evref.get("ref") or evref.get("handle") or evref.get("hlink")
            if handle and "/" in handle:
                handle = handle.rstrip("/").split("/")[-1]
            if handle:
                ev = requests.get(f"{URL}/api/events/{handle}", headers=headers, timeout=10).json()
                etype = ev.get("type", {})
                tstr = etype.get("string", "") if isinstance(etype, dict) else str(etype)
                print(f"  Event type: {tstr}")
                print(f"  Event date: {ev.get('date', {})}")
                pp.pprint(ev)

if __name__ == "__main__":
    main()
