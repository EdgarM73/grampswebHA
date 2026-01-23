"""Test Gramps Web API to check death_ref_index values."""
import requests

# Adjust the URL/port here if needed
url = "http://homeassistant:5000"

try:
    print("Fetching people from Gramps Web API...")
    response = requests.get(f"{url}/api/people/", timeout=10)
    
    if response.status_code != 200:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)
        exit(1)
    
    people = response.json()
    print(f"Total people: {len(people)}\n")
    
    # Check first 10 people
    print("First 10 people:")
    print("-" * 80)
    
    deceased_count = 0
    
    for idx, person in enumerate(people[:10]):
        name_data = person.get("primary_name", {})
        first = name_data.get("first_name", "")
        surname_list = name_data.get("surname_list", [])
        surname = surname_list[0].get("surname", "") if surname_list else ""
        full_name = f"{first} {surname}".strip()
        
        death_idx = person.get("death_ref_index", -1)
        events = person.get("event_ref_list", [])
        
        print(f"{idx+1}. {full_name}")
        print(f"   death_ref_index: {death_idx}")
        print(f"   event_ref_list length: {len(events)}")
        
        if death_idx >= 0:
            deceased_count += 1
            print(f"   ✓ Has death event reference")
            
            # Try to fetch the event
            if death_idx < len(events):
                event_ref = events[death_idx]
                handle = event_ref.get("ref") or event_ref.get("handle") or event_ref.get("hlink")
                
                if handle:
                    if "/" in handle:
                        handle = handle.rstrip("/").split("/")[-1]
                    
                    try:
                        event_resp = requests.get(f"{url}/api/events/{handle}", timeout=10)
                        if event_resp.status_code == 200:
                            event = event_resp.json()
                            event_type = event.get("type", {})
                            type_string = event_type.get("string", "") if isinstance(event_type, dict) else str(event_type)
                            date_info = event.get("date", {})
                            
                            print(f"   Event type: {type_string}")
                            print(f"   Date info: {date_info}")
                    except Exception as e:
                        print(f"   Could not fetch event: {e}")
        
        print()
    
    print(f"\nSummary: {deceased_count} out of 10 have death_ref_index >= 0")
    
    # Count all deceased
    all_deceased = sum(1 for p in people if p.get("death_ref_index", -1) >= 0)
    print(f"Total deceased in database: {all_deceased} out of {len(people)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
