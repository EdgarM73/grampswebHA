#!/usr/bin/env python3
"""Test date format for all sensors."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'gramps_ha'))

from grampsweb_api import GrampsWebAPI

# Initialize API
api = GrampsWebAPI(
    url="http://homeassistant:5000",
    username="erdal",
    password="1_Linux?"
)

try:
    print("=" * 80)
    print("BIRTHDAYS (first 3)")
    print("=" * 80)
    birthdays = api.get_birthdays(limit=3)
    for idx, bd in enumerate(birthdays[:3]):
        print(f"{idx+1}. {bd['person_name']} - Birth: {bd['birth_date']}, Next: {bd['next_birthday']}")
    
    print("\n" + "=" * 80)
    print("DEATHDAYS (first 3)")
    print("=" * 80)
    deathdays = api.get_deathdays(limit=3)
    for idx, dd in enumerate(deathdays[:3]):
        print(f"{idx+1}. {dd['person_name']} - Death: {dd['death_date']}, Next: {dd['next_deathday']}")
    
    print("\n" + "=" * 80)
    print("ANNIVERSARIES (first 3)")
    print("=" * 80)
    anniversaries = api.get_anniversaries(limit=3)
    for idx, ann in enumerate(anniversaries[:3]):
        print(f"{idx+1}. {ann['person_name']} - Marriage: {ann['marriage_date']}, Next: {ann['next_anniversary']}")

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
