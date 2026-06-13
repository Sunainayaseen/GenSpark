"""
Live QA smoke test for the customization engine — hits the RUNNING backend
(http://127.0.0.1:5000) over HTTP and demonstrates all four compatibility
verdicts plus defensive handling. Pure stdlib (no extra deps).

Run (with the backend up on port 5000):
    .venv\\Scripts\\python.exe qa_smoke.py
"""
import json
import urllib.request

BASE = 'http://127.0.0.1:5000/api'


def call(path, payload=None, method='POST'):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f'{BASE}{path}', data=data, method=method,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def find(options, slot, needle):
    for o in options.get(slot, []):
        if needle.lower() in o['name'].lower():
            return o['id']
    return None


def main():
    # 1. Recommend an AM5/DDR5 base build.
    _, rec = call('/recommend-build', {'purpose': 'Gaming', 'budget': '250000'})
    comps = rec.get('build_components') or []
    build = {c['slot']: c['component_id'] for c in comps}
    print(f'BASE build (score {rec.get("compatibility_score")}):',
          {k: v for k, v in build.items()})

    # Candidate IDs: filtered options (no incompatible parts) + unfiltered for the ❌ case.
    _, filt = call('/build-options', {'build': build})
    fo = filt['options']
    _, unfilt = call('/build-options', None, method='GET')
    uo = unfilt['options']

    ram32 = find(fo, 'ram', '32GB DDR5')
    ram64 = find(fo, 'ram', '64GB')
    gpu4090 = find(fo, 'gpu', 'RTX 4090')
    ram_ddr4 = find(uo, 'ram', 'DDR4')          # hidden by the filtered dropdown

    def verdict(slot, cid, label, purpose='Gaming'):
        _, j = call('/evaluate-customization',
                    {'purpose': purpose, 'budget': '250000', 'build': build,
                     'change': {'slot': slot, 'component_id': cid}, 'mode': 'beginner'})
        deps = ','.join(d['slot'] for d in j.get('dependent_changes', [])) or '-'
        print(f'  {label:42} -> {j.get("status_label"):32} Δ{j["budget"]["delta"]:>8} deps:{deps}')

    print('\n=== Four verdicts ===')
    if ram32:
        verdict('ram', ram32, '✅ RAM 16->32GB DDR5 (Gaming)')
    if ram64:
        # Same 64GB part: overkill for a light workload, fine for a heavy one.
        verdict('ram', ram64, '⚠️ RAM ->64GB DDR5 (Office workload)', purpose='Office')
    if gpu4090:
        verdict('gpu', gpu4090, '🔄 GPU ->RTX 4090 (PSU auto-upgrade)')
    if ram_ddr4:
        verdict('ram', ram_ddr4, '❌ DDR4 stick on AM5 board')

    print('\n=== Dropdown integrity (no incompatible parts) ===')
    ddr4_in_filtered = [o['name'] for o in fo['ram'] if 'DDR4' in o['name']]
    print(f'  DDR4 sticks offered on the AM5 board: {len(ddr4_in_filtered)} (expect 0)')

    print('\n=== Defensive handling ===')
    print('  missing component_id ->', call('/evaluate-customization',
          {'build': build, 'change': {'slot': 'ram'}})[0], '(expect 400)')
    print('  bad slot            ->', call('/evaluate-customization',
          {'build': build, 'change': {'slot': 'banana', 'component_id': ram32 or 1}})[0], '(expect 400)')
    print('  nonexistent part    ->', call('/evaluate-customization',
          {'build': build, 'change': {'slot': 'ram', 'component_id': 999999}})[0], '(expect 404)')


if __name__ == '__main__':
    main()
