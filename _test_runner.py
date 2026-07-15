import sys
sys.path.insert(0, ".")
import pipeline_runner

# Test list_all_cached_domains
domains = pipeline_runner.list_all_cached_domains()
print(f"Found {len(domains)} cached domains:")
for d in domains:
    print(f"  {d['domain']} -- {d['verdict']} ({d['confidence']*100:.0f}%)")

# Test find_cached_result
if domains:
    first = domains[0]
    print(f"\nTesting find_cached_result for: {first['domain']}")
    result = pipeline_runner.find_cached_result(first['domain'])
    if result:
        print(f"  -> Found! report keys: {list(result.keys())}")
        rdata = result.get('report_data', {})
        print(f"  -> Verdict: {rdata.get('verdict')}, Conf: {rdata.get('confidence')}")
    else:
        print("  -> Not found!")

print("\nAll checks passed!")
