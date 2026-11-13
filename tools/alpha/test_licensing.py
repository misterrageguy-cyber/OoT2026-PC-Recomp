"""Developer test of the alpha licensing (cases A-I of the alpha plan) against a running local server.

    python tools/alpha/test_licensing.py --server http://127.0.0.1:8443 --code <valid code> --expired-code <code>

PC B is simulated by another hardware hash. Prints one PASS/FAIL line per case; never prints the codes.
"""
import argparse
import datetime
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'launcher'))
import license as lic  # noqa: E402

PUB = (HERE / 'licensing-server/keys/public.hex').read_text().strip()


def activate(server, code, hw, build=lic.BUILD_ID):
    req = urllib.request.Request(server + '/api/v1/activate', method='POST', headers={'Content-Type': 'application/json'},
                                 data=json.dumps(dict(activation_code=code, hardware_id=hw, build_id=build)).encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', required=True)
    ap.add_argument('--code', required=True)
    ap.add_argument('--expired-code', required=True)
    a = ap.parse_args()
    hw_a = lic.hardware_id()
    hw_b = hashlib.sha256(b'another pc').hexdigest()
    res = []

    def case(name, ok, detail=''):
        res.append(ok)
        print(f'{"PASS" if ok else "FAIL"}  {name}  {detail}')

    try:   # A: no license -> the launcher shows activation; check() on nothing fails
        lic.check('', PUB, hw_a)
        case('A no license blocks', False)
    except lic.LicenseError as e:
        case('A no license blocks', True, str(e))
    s, b = activate(a.server, 'WRONG-WRONG-WRONG-WRONG-WRONG', hw_a)
    case('B invalid code rejected', s == 403 and 'license' not in b, b.get('error', ''))
    s, b = activate(a.server, a.code, hw_a)
    ok = s == 200 and lic.check(b['license'], PUB, hw_a)['tester_id']
    case('C valid code on PC A', bool(ok), f'tester {ok}')
    good = b['license']
    s, b = activate(a.server, a.code, hw_a)
    case('D same code again on PC A', s == 200 and 'license' in b)
    s, b = activate(a.server, a.code, hw_b)
    case('E same code on PC B rejected', s == 403, b.get('error', ''))
    try:
        lic.check(good, PUB, hw_b)
        case('F license.dat copied to PC B', False)
    except lic.LicenseError as e:
        case('F license.dat copied to PC B', 'another PC' in str(e), str(e))
    doc = json.loads(good)
    doc['payload'] = doc['payload'].replace('"expires_at":"', '"expires_at":"2099')[:len(doc['payload']) + 4]
    try:
        lic.check(json.dumps(doc), PUB, hw_a)
        case('G modified license rejected', False)
    except lic.LicenseError as e:
        case('G modified license rejected', 'signature' in str(e), str(e))
    # H: offline start = check() alone, no network involved
    case('H valid license verifies offline', lic.check(good, PUB, hw_a)['hardware_id'] == hw_a)
    s, b = activate(a.server, a.expired_code, hw_a)
    later = datetime.datetime(2026, 11, 21, 1, tzinfo=datetime.timezone.utc)
    try:
        lic.check(good, PUB, hw_a, now=later)
        exp_ok = False
    except lic.LicenseError:
        exp_ok = True
    case('I expired code / license refused', s == 403 and exp_ok, b.get('error', ''))
    print(f'{sum(res)}/{len(res)} passed')
    return 0 if all(res) else 1


if __name__ == '__main__':
    sys.exit(main())
