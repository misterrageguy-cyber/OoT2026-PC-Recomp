"""Check packaging for listed payloads and unrecorded media; not a rights assessment."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zipfile

FORBIDDEN_NAMES = {'oot_younglink.zip', 'oot_adultlink.zip', 'music.wav', 'music.mp3', 'fairy.bin', 'fairy.gif',
                   'prod.keys', 'title.keys', 'signing.key', 'image.bin'}
GAME_SUFFIXES = {'.nup', '.nsp', '.xci', '.nca', '.nso', '.rom', '.z64', '.n64', '.v64', '.bwav', '.bars', '.bfwav'}
MEDIA_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.raw', '.wav', '.mp3', '.ogg',
                  '.gif', '.mp4', '.webm', '.flac', '.aac', '.m4a', '.avi'}

FAIRY_SOURCE = 'tools/alpha/launcher/assets/fairy.bin'

def recorded_launcher_fairy(path, rel, manifest):
    """Only the explicitly recorded launcher animation may use the fairy.bin name."""
    if rel not in (FAIRY_SOURCE, 'launcher/assets/fairy.bin'):
        return False
    expected = manifest.get('restored_launcher_media', {}).get('files', {}).get(FAIRY_SOURCE)
    if not expected or path.stat().st_size > 16 * 1024 * 1024:
        return False
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:6] != b'FAIRY1' or hashlib.sha256(raw).hexdigest() != expected:
        return False
    size, frames, ms = struct.unpack_from('<HHH', raw, 6)
    return (0 < size <= 256 and 0 < frames <= 120 and ms > 0
            and len(raw) == 12 + 2 * frames * size * size * 4)

def problems(root, manifest):
    root = Path(root)
    trusted = set(manifest['files'].values())
    issues = []
    for path in root.rglob('*'):
        if not path.is_file() or '.git' in path.relative_to(root).parts or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if path.name.lower() == 'fairy.bin' and recorded_launcher_fairy(path, rel, manifest):
            continue
        if path.name.lower() in FORBIDDEN_NAMES or path.suffix.lower() in GAME_SUFFIXES:
            issues.append(rel + ': prohibited distribution payload')
            continue
        if path.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(path) as archive:
                    if any(Path(n.replace('\\', '/')).suffix.lower() in GAME_SUFFIXES | {'.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a', '.mp4', '.webm', '.avi'}
                           or Path(n.replace('\\', '/')).name.lower() in FORBIDDEN_NAMES for n in archive.namelist()):
                        issues.append(rel + ': archive contains recordings, keys or game data')
            except zipfile.BadZipFile:
                issues.append(rel + ': unreadable ZIP cannot be cleared for distribution')
        project_art = rel.startswith(('tools/alpha/', 'launcher/assets/', 'assets/',
                                      'engine/assets/', 'engine/builder/', 'engine/docs/images/')) or '/' not in rel or rel in (
            'OcarinaReborn.ico', 'tools/alpha/OcarinaReborn.ico', 'tools/alpha/startup-logo.png', 'tools/alpha/ocarina-icon.png')
        if project_art and path.suffix.lower() in MEDIA_SUFFIXES:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest not in trusted:
                issues.append(rel + ': project media has no matching provenance hash')
    return issues

def check(root):
    manifest = json.loads((Path(__file__).parent / 'MEDIA-PROVENANCE.json').read_text(encoding='utf-8'))
    found = problems(root, manifest)
    if found:
        raise SystemExit('Distribution guard failed:\n' + '\n'.join(found[:40]))
    print('Distribution guard passed: no prohibited payloads or unrecorded project media.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    check(parser.parse_args().root)
