"""Test script for caching and scan interval features."""
import sys
import time
from datetime import datetime, timedelta
sys.path.insert(0, '/home/erdal/grampswebHA/custom_components/gramps_ha')

from grampsweb_api import GrampsWebAPI

# Configuration
url = "http://mataradzija.akkaya.info"
username = "ha"
password = "proofx73"

def test_caching():
    """Test API caching functionality."""
    print("=" * 80)
    print("TEST: API CACHING")
    print("=" * 80)
    
    api = GrampsWebAPI(url=url, username=username, password=password)
    
    # First call - should fetch from API
    print("\n1. First call to get_birthdays() - should fetch from API...")
    start = datetime.now()
    result1 = api.get_birthdays(limit=5)
    elapsed1 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed1:.2f}s")
    print(f"   Results: {len(result1)} birthdays")
    
    # Second call - should use cache
    print("\n2. Second call to get_birthdays() - should use CACHE...")
    start = datetime.now()
    result2 = api.get_birthdays(limit=5)
    elapsed2 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed2:.2f}s")
    print(f"   Results: {len(result2)} birthdays")
    
    # Check if results are identical
    if result1 == result2:
        print("   ✓ Results are identical (cached)")
    else:
        print("   ✗ Results differ (cache may not be working)")
    
    # Time difference check
    if elapsed2 < elapsed1 / 2:
        print(f"   ✓ Second call was significantly faster ({elapsed2:.2f}s vs {elapsed1:.2f}s)")
    else:
        print(f"   ⚠ Second call not significantly faster")
    
    # Test deathdays caching
    print("\n3. First call to get_deathdays() - should fetch from API...")
    start = datetime.now()
    result3 = api.get_deathdays(limit=5)
    elapsed3 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed3:.2f}s")
    print(f"   Results: {len(result3)} deathdays")
    
    print("\n4. Second call to get_deathdays() - should use CACHE...")
    start = datetime.now()
    result4 = api.get_deathdays(limit=5)
    elapsed4 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed4:.2f}s")
    print(f"   Results: {len(result4)} deathdays")
    
    if result3 == result4:
        print("   ✓ Results are identical (cached)")
    
    # Test anniversaries caching
    print("\n5. First call to get_anniversaries() - should fetch from API...")
    start = datetime.now()
    result5 = api.get_anniversaries(limit=5)
    elapsed5 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed5:.2f}s")
    print(f"   Results: {len(result5)} anniversaries")
    
    print("\n6. Second call to get_anniversaries() - should use CACHE...")
    start = datetime.now()
    result6 = api.get_anniversaries(limit=5)
    elapsed6 = (datetime.now() - start).total_seconds()
    print(f"   Time: {elapsed6:.2f}s")
    print(f"   Results: {len(result6)} anniversaries")
    
    if result5 == result6:
        print("   ✓ Results are identical (cached)")
    
    # Check cache status
    print("\n" + "=" * 80)
    print("CACHE STATUS:")
    print("=" * 80)
    print(f"People cache valid: {api._is_cache_valid('people')}")
    print(f"Birthdays cache valid: {api._is_cache_valid('birthdays')}")
    print(f"Deathdays cache valid: {api._is_cache_valid('deathdays')}")
    print(f"Anniversaries cache valid: {api._is_cache_valid('anniversaries')}")
    print(f"Cache TTL: {api._cache_ttl_seconds} seconds")
    
    return True

def test_scan_interval_config():
    """Test scan interval configuration."""
    print("\n" + "=" * 80)
    print("TEST: SCAN INTERVAL CONFIGURATION")
    print("=" * 80)
    
    from const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    
    print(f"\nScan Interval Constant: CONF_SCAN_INTERVAL = '{CONF_SCAN_INTERVAL}'")
    print(f"Default Scan Interval: DEFAULT_SCAN_INTERVAL = {DEFAULT_SCAN_INTERVAL} hours")
    print(f"That equals: {DEFAULT_SCAN_INTERVAL / 24} days")
    
    # Expected values
    if CONF_SCAN_INTERVAL == "scan_interval":
        print("✓ CONF_SCAN_INTERVAL has correct value")
    else:
        print("✗ CONF_SCAN_INTERVAL has incorrect value")
    
    if DEFAULT_SCAN_INTERVAL == 168:  # 7 days
        print("✓ DEFAULT_SCAN_INTERVAL is 7 days (168 hours)")
    else:
        print("✗ DEFAULT_SCAN_INTERVAL is not 7 days")
    
    return True

if __name__ == "__main__":
    try:
        print("\n")
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║  GRAMPS HA - CACHING & SCAN INTERVAL TEST                                      ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        
        test_scan_interval_config()
        test_caching()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
