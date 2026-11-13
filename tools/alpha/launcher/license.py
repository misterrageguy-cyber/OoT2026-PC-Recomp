"""Ocarina Reborn private alpha: hardware hash and the signed offline license (license.dat).

license.dat is JSON: {"payload": "<canonical JSON>", "signature": "<hex Ed25519 over the payload's UTF-8 bytes>"}.
The canonical payload is json.dumps(obj, sort_keys=True, separators=(',', ':')); the server signs exactly those bytes.
Only the SHA-256 hardware hash is stored or sent, never the MachineGuid or the SMBIOS UUID themselves.
"""
import ctypes
import datetime
import hashlib
import json
import struct
import sys

import ed25519

BUILD_ID = 'ocarina-reborn-alpha-001'
LICENSE_VERSION = 1
HW_SALT = b'ocarina-reborn-alpha-hw-v1'


def _machine_guid():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography', 0,
                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        return str(winreg.QueryValueEx(k, 'MachineGuid')[0]).strip().lower()
    except OSError:
        return ''


def _smbios_uuid():
    """The SMBIOS system UUID (structure type 1) via GetSystemFirmwareTable('RSMB'); '' when unavailable."""
    if sys.platform != 'win32':
        return ''
    k32 = ctypes.windll.kernel32
    sig = struct.unpack('>I', b'RSMB')[0]
    n = k32.GetSystemFirmwareTable(sig, 0, None, 0)
    if not n:
        return ''
    buf = ctypes.create_string_buffer(n)
    if k32.GetSystemFirmwareTable(sig, 0, buf, n) != n:
        return ''
    raw = buf.raw
    length = struct.unpack_from('<I', raw, 4)[0]
    data, i = raw[8:8 + length], 0
    while i + 4 <= len(data):
        typ, ln = data[i], data[i + 1]
        if ln < 4:
            break
        if typ == 1 and ln >= 0x19:
            u = data[i + 8:i + 24]
            if u in (b'\x00' * 16, b'\xff' * 16):
                return ''
            return (u[3::-1] + u[5:3:-1] + u[7:5:-1] + u[8:]).hex()   # SMBIOS 2.6+ byte order
        j = i + ln                                     # skip the formatted area, then the strings up to a double NUL
        while j + 1 < len(data) and not (data[j] == 0 and data[j + 1] == 0):
            j += 1
        i = j + 2
    return ''


def hardware_id():
    guid, uuid = _machine_guid(), _smbios_uuid()
    if not guid and not uuid:
        raise RuntimeError('no stable machine identifier is available')
    return hashlib.sha256(HW_SALT + b'|' + guid.encode() + b'|' + uuid.encode()).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


class LicenseError(Exception):
    pass


def check(text, public_key_hex, hw=None, now=None):
    """The payload dict of a valid license text; LicenseError with the reason otherwise."""
    try:
        doc = json.loads(text)
        payload_text, sig = doc['payload'], bytes.fromhex(doc['signature'])
    except (ValueError, KeyError, TypeError):
        raise LicenseError('The license file is damaged.')
    if not ed25519.verify(bytes.fromhex(public_key_hex), payload_text.encode('utf-8'), sig):
        raise LicenseError('The license signature is invalid.')
    p = json.loads(payload_text)
    if p.get('license_version') != LICENSE_VERSION:
        raise LicenseError('The license has an unknown version.')
    if p.get('hardware_id') != (hw or hardware_id()):
        raise LicenseError('This license belongs to another PC.')
    if p.get('build_id') != BUILD_ID:
        raise LicenseError('This license is for another Ocarina Reborn build.')
    now = now or datetime.datetime.now(datetime.timezone.utc)
    exp = datetime.datetime.fromisoformat(p['expires_at'].replace('Z', '+00:00'))
    if now > exp:
        raise LicenseError('The alpha license has expired.')
    return p
