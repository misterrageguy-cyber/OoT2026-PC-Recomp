"""Ocarina Reborn private alpha: activation server and admin commands. Never shipped to testers.

Standard library only (Python 3.11+), SQLite database, Ed25519 signatures (launcher/ed25519.py).

    python server.py init-keys                       # keys/signing.key (PRIVATE, never share) and keys/public.hex
    python server.py create-alpha-code --tester ALPHA-AMD-001 --build ocarina-reborn-alpha-001 --expires 2026-11-20
    python server.py list-alpha-codes
    python server.py revoke-alpha-code --tester ALPHA-AMD-001
    python server.py reset-hardware-binding --tester ALPHA-AMD-001
    python server.py serve --port 8443 --cert cert.pem --certkey key.pem      # HTTPS (or plain HTTP behind a TLS proxy)

POST /api/v1/activate  {"activation_code", "hardware_id", "build_id"}  ->  {"license": "<license.dat text>"} or
{"error": "..."}. The code is stored only as a SHA-256 hash. The first activation binds the code to the hardware hash;
the same PC may activate again, another PC is refused until an admin resets the binding. At most 10 attempts per IP
address per 10 minutes.
"""
import argparse
import datetime
import hashlib
import json
import secrets
import sqlite3
import ssl
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'launcher'))
import ed25519  # noqa: E402

DB = HERE / 'database' / 'alpha.sqlite3'
KEYS = HERE / 'keys'
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # no 0/O, 1/I


def db():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute('''create table if not exists codes(code_hash text primary key, tester_id text unique, build_id text,
                 expires_at text, enabled integer default 1, revoked integer default 0, hardware_id text,
                 activated_at text, created_at text)''')
    c.execute('create table if not exists log(at text, tester_id text, ip text, result text)')
    return c


def code_hash(code):
    return hashlib.sha256(code.strip().upper().replace(' ', '').encode()).hexdigest()


def signing_key():
    return bytes.fromhex((KEYS / 'signing.key').read_text().strip())


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def activate(req, ip):
    code, hw, build = req.get('activation_code', ''), req.get('hardware_id', ''), req.get('build_id', '')
    if not (isinstance(hw, str) and len(hw) == 64 and all(ch in '0123456789abcdef' for ch in hw)):
        return 400, {'error': 'Invalid request.'}
    c = db()
    row = c.execute('select tester_id, build_id, expires_at, enabled, revoked, hardware_id from codes where code_hash=?',
                    (code_hash(str(code)),)).fetchone()
    def done(status, body, tester='-'):
        c.execute('insert into log values(?,?,?,?)', (now_iso(), tester, ip, body.get('error', 'ok')))
        c.commit()
        c.close()
        return status, body
    if not row:
        return done(403, {'error': 'This alpha code is not valid.'})
    tester, b, expires, enabled, revoked, bound = row
    if not enabled or revoked:
        return done(403, {'error': 'This alpha code has been revoked.'}, tester)
    if b != build:
        return done(403, {'error': 'This alpha code is for another Ocarina Reborn build.'}, tester)
    if datetime.datetime.now(datetime.timezone.utc) > datetime.datetime.fromisoformat(expires.replace('Z', '+00:00')):
        return done(403, {'error': 'This alpha code has expired.'}, tester)
    if bound and bound != hw:
        return done(403, {'error': 'This alpha code is already activated on another PC.'}, tester)
    if not bound:
        c.execute('update codes set hardware_id=?, activated_at=? where tester_id=?', (hw, now_iso(), tester))
    payload = dict(license_version=1, license_id=str(uuid.uuid4()), tester_id=tester, hardware_id=hw, build_id=b,
                   issued_at=now_iso(), expires_at=expires)
    text = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    sig = ed25519.sign(signing_key(), text.encode('utf-8'))
    return done(200, {'license': json.dumps({'payload': text, 'signature': sig.hex()})}, tester)


class Limiter:
    def __init__(self, n=10, window=600):
        self.n, self.window, self.hits, self.lock = n, window, {}, threading.Lock()

    def allow(self, ip):
        t = time.monotonic()
        with self.lock:
            h = [x for x in self.hits.get(ip, []) if t - x < self.window]
            if len(h) >= self.n:
                self.hits[ip] = h
                return False
            self.hits[ip] = h + [t]
            return True


LIMIT = Limiter()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != '/api/v1/activate':
            return self._send(404, {'error': 'not found'})
        ip = self.client_address[0]
        if not LIMIT.allow(ip):
            return self._send(429, {'error': 'Too many attempts. Try again in a few minutes.'})
        try:
            n = int(self.headers.get('Content-Length', '0'))
            req = json.loads(self.rfile.read(min(n, 4096)))
            if not isinstance(req, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {'error': 'Invalid request.'})
        self._send(*activate(req, ip))

    def log_message(self, fmt, *args):   # no request bodies (codes) in the console
        sys.stderr.write('%s %s\n' % (self.client_address[0], fmt % args))


def main():
    ap = argparse.ArgumentParser(description='Ocarina Reborn alpha licensing')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init-keys')
    s = sub.add_parser('create-alpha-code')
    s.add_argument('--tester', required=True)
    s.add_argument('--build', default='ocarina-reborn-alpha-001')
    s.add_argument('--expires', required=True, help='YYYY-MM-DD (end of that day, UTC)')
    s = sub.add_parser('issue-license', help='offline activation: license.dat for the PC-ID of a tester')
    s.add_argument('--tester', required=True)
    s.add_argument('--pc-id', required=True, help='the 64-character PC-ID the launcher shows')
    s.add_argument('--build', default='ocarina-reborn-alpha-001')
    s.add_argument('--expires', required=True, help='YYYY-MM-DD (end of that day, UTC)')
    s.add_argument('--out', default=None, help='output file (default licenses/<tester>/license.dat)')
    sub.add_parser('list-alpha-codes')
    for name in ('revoke-alpha-code', 'reset-hardware-binding'):
        sub.add_parser(name).add_argument('--tester', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--host', default='0.0.0.0')
    s.add_argument('--port', type=int, default=8443)
    s.add_argument('--cert')
    s.add_argument('--certkey')
    a = ap.parse_args()
    if a.cmd == 'init-keys':
        KEYS.mkdir(exist_ok=True)
        if (KEYS / 'signing.key').exists():
            raise SystemExit('keys/signing.key exists; refusing to replace it (licenses already issued would break)')
        sk = secrets.token_bytes(32)
        (KEYS / 'signing.key').write_text(sk.hex())
        (KEYS / 'public.hex').write_text(ed25519.public_key(sk).hex())
        print('public key (goes into the launcher):', ed25519.public_key(sk).hex())
    elif a.cmd == 'create-alpha-code':
        code = '-'.join(''.join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(5))
        exp = datetime.date.fromisoformat(a.expires).isoformat() + 'T23:59:59Z'
        c = db()
        c.execute('insert into codes(code_hash, tester_id, build_id, expires_at, created_at) values(?,?,?,?,?)',
                  (code_hash(code), a.tester, a.build, exp, now_iso()))
        c.commit()
        print(f'{a.tester}: {code}   (shown once; only its hash is stored)')
    elif a.cmd == 'issue-license':
        hw = a.pc_id.strip().lower()
        if len(hw) != 64 or any(ch not in '0123456789abcdef' for ch in hw):
            raise SystemExit('the PC-ID must be the 64 hex characters the launcher shows')
        exp = datetime.date.fromisoformat(a.expires).isoformat() + 'T23:59:59Z'
        c = db()
        row = c.execute('select hardware_id, revoked from codes where tester_id=?', (a.tester,)).fetchone()
        if row and row[1]:
            raise SystemExit(f'{a.tester} is revoked')
        if row and row[0] and row[0] != hw:
            raise SystemExit(f'{a.tester} is already bound to another PC; run reset-hardware-binding first')
        if not row:   # an offline tester without a code: a random code hash keeps the table's one-PC rule
            c.execute('insert into codes(code_hash, tester_id, build_id, expires_at, created_at) values(?,?,?,?,?)',
                      (code_hash(secrets.token_hex(16)), a.tester, a.build, exp, now_iso()))
        c.execute('update codes set hardware_id=?, activated_at=?, expires_at=? where tester_id=?', (hw, now_iso(), exp, a.tester))
        c.commit()
        payload = dict(license_version=1, license_id=str(uuid.uuid4()), tester_id=a.tester, hardware_id=hw,
                       build_id=a.build, issued_at=now_iso(), expires_at=exp)
        text = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        out = Path(a.out) if a.out else HERE / 'licenses' / a.tester / 'license.dat'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'payload': text, 'signature': ed25519.sign(signing_key(), text.encode()).hex()}))
        print(f'{a.tester}: license written to {out} (send this file to the tester)')
    elif a.cmd == 'list-alpha-codes':
        for r in db().execute('select tester_id, build_id, expires_at, enabled, revoked, hardware_id, activated_at from codes'):
            print(f'{r[0]:20} {r[1]}  expires {r[2]}  {"REVOKED" if r[4] or not r[3] else "active"}  '
                  f'{"bound " + r[5][:12] + "… at " + r[6] if r[5] else "not activated"}')
    elif a.cmd == 'revoke-alpha-code':
        c = db()
        n = c.execute('update codes set revoked=1 where tester_id=?', (a.tester,)).rowcount
        c.commit()
        print('revoked' if n else 'no such tester')
    elif a.cmd == 'reset-hardware-binding':
        c = db()
        n = c.execute('update codes set hardware_id=null, activated_at=null where tester_id=?', (a.tester,)).rowcount
        c.commit()
        print('binding reset' if n else 'no such tester')
    elif a.cmd == 'serve':
        signing_key()
        httpd = ThreadingHTTPServer((a.host, a.port), Handler)
        if a.cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(a.cert, a.certkey)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        print(f'listening on {a.host}:{a.port} ({"HTTPS" if a.cert else "HTTP: put a TLS proxy in front"})')
        httpd.serve_forever()


if __name__ == '__main__':
    main()
