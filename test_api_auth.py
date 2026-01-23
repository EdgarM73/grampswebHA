"""Test Gramps Web API with auth and list first 10 people."""
import requests

URL = "http://homeassistant:5000"
USERNAME = "erdal"
PASSWORD = "1_Linux?"

def main():
    print(f"Authenticating against {URL} ...")
    tok = requests.post(
        f"{URL}/api/token/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    print("Auth status:", tok.status_code)
    if tok.status_code != 200:
        print(tok.text)
        return
    token = tok.json().get("access_token")
    if not token:
        print("No access_token in response")
        return

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{URL}/api/people/", headers=headers, timeout=10)
    print("People status:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        return

    people = r.json()
    print(f"Total people: {len(people)}\n")
    print("First 10 people:")
    for i, p in enumerate(people[:10]):
        name = p.get("primary_name", {})
        first = name.get("first_name", "")
        surns = name.get("surname_list", [])
        surname = surns[0].get("surname", "") if surns else ""
        death_idx = p.get("death_ref_index", -1)
        events = len(p.get("event_ref_list", []))
        print(f"{i+1}. {first} {surname} | death_ref_index={death_idx} | events={events}")

    all_deceased = sum(1 for p in people if p.get("death_ref_index", -1) >= 0)
    print(f"\nDeceased (death_ref_index >= 0): {all_deceased} of {len(people)}")

if __name__ == "__main__":
    main()
