"""Direct Gramps Web API check for marriage events (no Home Assistant).
Outputs total people, marriage event count, and first 10 anniversaries.
"""
import requests

URL = "http://homeassistant:5000"
USERNAME = "erdal"
PASSWORD = "1_Linux?"


def extract_handle(ref):
    if not ref:
        return None
    if isinstance(ref, str):
        handle = ref
    elif isinstance(ref, dict):
        handle = ref.get("ref") or ref.get("handle") or ref.get("hlink")
    else:
        return None
    if not handle:
        return None
    if "/" in handle:
        handle = handle.rstrip("/").split("/")[-1]
    return handle


def parse_dateval(dateval):
    if isinstance(dateval, dict):
        dateval = dateval.get("dateval") or dateval.get("val") or dateval.get("start")
    if not isinstance(dateval, (list, tuple)):
        return None
    vals = list(dateval[:3])
    if len(vals) < 3:
        return None
    try:
        vals = [int(v) for v in vals]
    except Exception:
        return None
    combos = [
        (2, 1, 0),  # [day, month, year]
        (0, 1, 2),  # [year, month, day]
        (0, 2, 1),  # [year, day, month]
    ]
    for y_idx, m_idx, d_idx in combos:
        y, m, d = vals[y_idx], vals[m_idx], vals[d_idx]
        if y < 100:
            continue
        if not (1 <= m <= 12 and 1 <= d <= 31):
            continue
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def get_marriage_dates(person, get_event, get_family, get_person):
    marriage_dates = []
    person_handle = person.get("handle", "")
    event_ref_list = person.get("event_ref_list", []) or []
    families = person.get("family_list", []) or []

    spouse_handles = set()
    for family_ref in families:
        fam_handle = extract_handle(family_ref)
        if not fam_handle:
            continue
        family = get_family(fam_handle)
        if not family:
            continue
        for parent_rel in family.get("parent_rel_list", []) or []:
            sp = extract_handle(parent_rel)
            if sp and sp != person_handle:
                spouse_handles.add(sp)
        for event_ref in family.get("event_ref_list", []) or []:
            ev_handle = extract_handle(event_ref)
            if not ev_handle:
                continue
            ev = get_event(ev_handle)
            if not ev:
                continue
            etype = ev.get("type", {})
            tstr = etype.get("string", "") if isinstance(etype, dict) else str(etype)
            if "marriage" not in tstr.lower():
                continue
            parsed = parse_dateval(ev.get("date", {}))
            if not parsed:
                continue
            if spouse_handles:
                for sp in spouse_handles:
                    sp_name = get_person(sp)
                    marriage_dates.append((sp_name, parsed))
            else:
                marriage_dates.append(("Unknown", parsed))

    for event_ref in event_ref_list:
        ev_handle = extract_handle(event_ref)
        if not ev_handle:
            continue
        ev = get_event(ev_handle)
        if not ev:
            continue
        etype = ev.get("type", {})
        tstr = etype.get("string", "") if isinstance(etype, dict) else str(etype)
        if "marriage" not in tstr.lower():
            continue
        parsed = parse_dateval(ev.get("date", {}))
        if not parsed:
            continue
        if spouse_handles:
            for sp in spouse_handles:
                sp_name = get_person(sp)
                marriage_dates.append((sp_name, parsed))
        else:
            marriage_dates.append(("Unknown", parsed))

    return marriage_dates


def main():
    tok = requests.post(
        f"{URL}/api/token/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    tok.raise_for_status()
    token = tok.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    def get_event(handle):
        if "/" in handle:
            handle = handle.rstrip("/").split("/")[-1]
        return requests.get(f"{URL}/api/events/{handle}", headers=headers, timeout=10).json()

    def get_family(handle):
        if "/" in handle:
            handle = handle.rstrip("/").split("/")[-1]
        return requests.get(f"{URL}/api/families/{handle}", headers=headers, timeout=10).json()

    def get_person(handle):
        if "/" in handle:
            handle = handle.rstrip("/").split("/")[-1]
        p = requests.get(f"{URL}/api/people/{handle}", headers=headers, timeout=10).json()
        name = p.get("primary_name", {})
        first = name.get("first_name", "")
        surns = name.get("surname_list", [])
        surname = surns[0].get("surname", "") if surns else ""
        return f"{first} {surname}".strip() or "Unknown"

    people = requests.get(f"{URL}/api/people/", headers=headers, timeout=30).json()
    print(f"Total people: {len(people)}")

    all_marriages = []
    for person in people:
        person_name = get_person(person.get("handle", ""))
        marriages = get_marriage_dates(person, get_event, get_family, get_person)
        for spouse_name, date in marriages:
            all_marriages.append((person_name, spouse_name, date))

    print(f"Marriage entries found: {len(all_marriages)}")
    print("First 10 entries:")
    for entry in all_marriages[:10]:
        print(entry)


if __name__ == "__main__":
    main()
