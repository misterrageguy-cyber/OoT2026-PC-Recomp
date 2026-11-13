"""Save data: backups the player can see and choose a place for, restore, and import of the game's own saves from elsewhere.

The game's saves are <game>/user/save/<account id>/{account.sav, option.sav, slot_NN/caption.sav, slot_NN/progress.sav}: the
files the game itself writes (every one starts with the bytes 04 03 02 01). An emulator's save folder for this game holds the
same files, so an import is a checked copy; a save of another game (the N64 original and its PC ports) is another format and
is refused, as are emulator save states (snapshots of an emulator's memory, not save data).

A backup is a folder <backup root>/<Kind>/<time>-<reason>/ with the save tree under save/ and backup.json (time, version,
reason, every file's size and SHA-256). It counts as made only when every copied file's checksum matches its source.
Nothing here deletes or overwrites the live save except restore() and import_save(), which first back it up and then swap a
complete, verified copy in: when anything fails before the swap, the live save is as it was.
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

MAGIC = bytes((4, 3, 2, 1))
KINDS = ('Manual', 'Before-Update', 'Before-Import', 'Automatic')
DEFAULT_ACCOUNT = '5a3c9e1f0b7d24680000000000000001'   # (the account id the game's saves are under in a new folder)
STATE_EXT = {'.state', '.st', '.ss', '.sav0', '.savestate', '.frz', '.zst', '.snapshot'}   # (emulator save states)
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class SaveError(Exception):
    pass


def save_root(game):
    return Path(game) / 'user' / 'save'


def game_running():
    """whether the game's process is running (its saves may be mid-write)"""
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ocarina_reborn.exe', '/NH'], capture_output=True,
                             creationflags=NO_WINDOW, timeout=10).stdout or b''
        return b'ocarina_reborn.exe' in out.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def tree(root):
    """{relative posix path: (size, sha256)} of every file under root"""
    root = Path(root)
    return {p.relative_to(root).as_posix(): (p.stat().st_size, sha256(p)) for p in sorted(root.rglob('*')) if p.is_file()}


def has_saves(game):
    r = save_root(game)
    return r.is_dir() and any(p.is_file() for p in r.rglob('*'))


def copy_verified(src, dst):
    """src's tree copied to dst (new), every file's size and checksum compared with its source; the tree's listing"""
    src, dst = Path(src), Path(dst)
    shutil.copytree(src, dst)
    want, got = tree(src), tree(dst)
    if want != got:
        bad = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
        shutil.rmtree(dst, ignore_errors=True)
        raise SaveError(f'copy check failed for {bad[:3]}')
    return got


# ---- backups
def backup(game, backup_root, kind, reason, version=''):
    """a verified backup of the live save; its folder, or None when there is no save yet"""
    assert kind in KINDS
    if not has_saves(game):
        return None
    stamp = datetime.datetime.now()
    dst = Path(backup_root) / kind / f'{stamp:%Y-%m-%d-%H%M%S}-{reason}'
    n = 1
    while dst.exists():
        n += 1
        dst = dst.with_name(f'{stamp:%Y-%m-%d-%H%M%S}-{reason}-{n}')
    dst.mkdir(parents=True)
    try:
        files = copy_verified(save_root(game), dst / 'save')
        accounts = sorted({k.split('/')[0] for k in files})
        (dst / 'backup.json').write_text(json.dumps(dict(
            timestamp=stamp.isoformat(timespec='seconds'), ocarina_reborn_version=version, save_id=accounts, reason=reason,
            kind=kind, files={k: dict(size=s, sha256=h) for k, (s, h) in files.items()}), indent=2), encoding='utf-8')
    except (OSError, SaveError) as e:
        shutil.rmtree(dst, ignore_errors=True)
        raise SaveError(f'backup failed: {e}')
    return dst


def list_backups(backup_root):
    """every backup under backup_root, newest first: dicts with path, kind, timestamp, reason, files, size"""
    out = []
    for kind in KINDS:
        d = Path(backup_root) / kind
        if not d.is_dir():
            continue
        for b in d.iterdir():
            try:
                meta = json.loads((b / 'backup.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            out.append(dict(path=b, kind=kind, timestamp=meta.get('timestamp', ''), reason=meta.get('reason', ''),
                            files=len(meta.get('files', {})), size=sum(f.get('size', 0) for f in meta.get('files', {}).values())))
    return sorted(out, key=lambda b: b['timestamp'], reverse=True)


def check_backup(backup_dir):
    """the backup's files against its backup.json; raises SaveError when one is missing or changed"""
    b = Path(backup_dir)
    try:
        meta = json.loads((b / 'backup.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise SaveError(f'backup.json unreadable: {e}')
    have = tree(b / 'save')
    want = {k: (v['size'], v['sha256']) for k, v in meta.get('files', {}).items()}
    if not want or have != want:
        raise SaveError('the backup is incomplete or was changed')
    return meta


def prune(backup_root, keep):
    """the oldest automatic backups past keep removed (Automatic, Before-Update, Before-Import each); Manual never. keep 0:
    unlimited"""
    if not keep:
        return 0
    removed = 0
    for kind in ('Automatic', 'Before-Update', 'Before-Import'):
        d = Path(backup_root) / kind
        if d.is_dir():
            for old in sorted(p for p in d.iterdir() if p.is_dir())[:-keep]:
                shutil.rmtree(old, ignore_errors=True)
                removed += 1
    return removed


def replace_save(game, new_tree_dir):
    """the live save replaced by the complete tree in new_tree_dir (on the same drive: beside it), in one swap: the old one
    is moved aside first and moved back when the swap fails"""
    live = save_root(game)
    live.parent.mkdir(parents=True, exist_ok=True)
    aside = live.with_name('save.replaced')
    if aside.exists():
        shutil.rmtree(aside)
    had = live.exists()
    if had:
        os.replace(live, aside)
    try:
        os.replace(new_tree_dir, live)
    except OSError:
        if had:
            os.replace(aside, live)
        raise
    if had:
        shutil.rmtree(aside, ignore_errors=True)


def restore(game, backup_dir, backup_root, version=''):
    """the live save backed up (Before-Import is for imports; this one is Automatic, reason before-restore), then the
    backup's tree swapped in. Returns the safety backup's folder (None: there was no live save)"""
    if game_running():
        raise SaveError('the game is running: close it first')
    check_backup(backup_dir)
    safety = backup(game, backup_root, 'Automatic', 'before-restore', version)
    staging = save_root(game).with_name('save.incoming')
    if staging.exists():
        shutil.rmtree(staging)
    copy_verified(Path(backup_dir) / 'save', staging)
    replace_save(game, staging)
    return safety


# ---- import
def find_save_folder(path):
    """the folder under path (at most 6 levels down) that holds the game's save files: account.sav or slot_NN/progress.sav"""
    path = Path(path)
    best = None
    for dirpath, dirs, files in os.walk(path):
        depth = len(Path(dirpath).relative_to(path).parts)
        if depth > 6:
            dirs[:] = []
            continue
        if 'account.sav' in files or any((Path(dirpath) / d / 'progress.sav').is_file() for d in dirs if d.startswith('slot_')):
            best = Path(dirpath)
            break
    return best


def inspect(path):
    """what an import source is: dict(folder, files, slots, problems). Raises SaveError for what cannot be a save at all"""
    path = Path(path)
    if path.is_file():
        if path.suffix.lower() in STATE_EXT or 'state' in path.suffix.lower():
            raise SaveError('Unsupported emulator save state. Please select the game\'s actual save-data folder.')
        if path.suffix.lower() == '.zip':
            raise SaveError('zip')   # (import_save unpacks it first)
        if path.name.endswith('.sav'):
            path = path.parent.parent if path.parent.name.startswith('slot_') else path.parent
        else:
            raise SaveError('This file is not Ocarina Reborn save data. Select the save folder (it holds account.sav and slot_00 ...).')
    folder = find_save_folder(path)
    if not folder:
        states = [p.name for p in path.rglob('*') if p.is_file() and p.suffix.lower() in STATE_EXT][:1]
        if states:
            raise SaveError('Unsupported emulator save state. Please select the game\'s actual save-data folder.')
        if any(p.suffix.lower() in ('.sra', '.eep', '.fla', '.sav') and p.stat().st_size in (0x8000, 0x20000, 0x800) for p in path.rglob('*') if p.is_file()):
            raise SaveError('This looks like a save of the Nintendo 64 game (or one of its PC ports). That is another game with another '
                            'save format; it cannot be converted to this game\'s saves.')
        raise SaveError('No save data of this game found there (looked for account.sav and slot_00/progress.sav).')
    files, problems = [], []
    for p in sorted(folder.rglob('*.sav')):
        rel = p.relative_to(folder).as_posix()
        parts = rel.split('/')
        ok_place = (len(parts) == 1 and parts[0] in ('account.sav', 'option.sav')) or \
                   (len(parts) == 2 and parts[0].startswith('slot_') and parts[1] in ('caption.sav', 'progress.sav'))
        if not ok_place:
            continue
        with open(p, 'rb') as f:
            head = f.read(4)
        if head != MAGIC:
            problems.append(f'{rel}: not this game\'s save format')
        elif p.stat().st_size < 64:
            problems.append(f'{rel}: too small')
        files.append(rel)
    slots = sorted({f.split('/')[0] for f in files if f.endswith('progress.sav')})
    if not slots:
        problems.append('no save slot (slot_NN/progress.sav) in it')
    return dict(folder=folder, files=files, slots=slots, problems=problems)


def account_dir(game):
    """the account folder the game uses (the one there is, else the default)"""
    r = save_root(game)
    if r.is_dir():
        for d in sorted(r.iterdir()):
            if d.is_dir() and len(d.name) == 32:
                return d
    return r / DEFAULT_ACCOUNT


def import_save(game, source, backup_root, version=''):
    """a save from elsewhere made the live one: inspected, the live save backed up (Before-Import; the import is cancelled when
    that fails), the files copied and checked in a folder beside the save, then swapped in. Returns (info, backup folder)"""
    if game_running():
        raise SaveError('the game is running: close it first')
    source = Path(source)
    unpacked = None
    try:
        if source.is_file() and source.suffix.lower() == '.zip':
            unpacked = save_root(game).with_name('save.unzipped')
            if unpacked.exists():
                shutil.rmtree(unpacked)
            unpacked.mkdir(parents=True)
            with zipfile.ZipFile(source) as z:
                for m in z.infolist():   # (only plain relative paths: nothing written outside the folder)
                    name = Path(m.filename)
                    if m.is_dir() or name.is_absolute() or '..' in name.parts:
                        continue
                    target = unpacked / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(m) as src, open(target, 'wb') as out:
                        shutil.copyfileobj(src, out)
            source = unpacked
        info = inspect(source)
        if info['problems']:
            raise SaveError('; '.join(info['problems'][:3]))
        safety = backup(game, backup_root, 'Before-Import', 'before-import', version)   # (raises: the import stops here)
        staging = save_root(game).with_name('save.incoming')
        if staging.exists():
            shutil.rmtree(staging)
        target = staging / account_dir(game).name
        target.mkdir(parents=True)
        for rel in info['files']:
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(info['folder'] / rel, dst)
            if sha256(dst) != sha256(info['folder'] / rel):
                shutil.rmtree(staging, ignore_errors=True)
                raise SaveError(f'copy check failed for {rel}')
        replace_save(game, staging)
        return info, safety
    finally:
        if unpacked:
            shutil.rmtree(unpacked, ignore_errors=True)


def auto_detect():
    """save folders of this game found in the usual emulator places on this PC: [(label, folder)]"""
    found = []
    roots = []
    for env, subs in (('APPDATA', ('yuzu', 'suyu', 'sudachi', 'eden', 'citron', 'Ryujinx', 'Torzu')),
                      ('LOCALAPPDATA', ('yuzu', 'suyu', 'eden', 'citron'))):
        base = os.environ.get(env)
        if base:
            roots += [(s, Path(base) / s) for s in subs]
    for label, root in roots:
        if not root.is_dir():
            continue
        for sub in ('nand/user/save', 'bis/user/save'):
            d = root / sub
            if not d.is_dir():
                continue
            for dirpath, dirs, files in os.walk(d):
                if len(Path(dirpath).relative_to(d).parts) > 4:
                    dirs[:] = []
                    continue
                if 'account.sav' in files:
                    try:
                        with open(Path(dirpath) / 'account.sav', 'rb') as f:
                            if f.read(4) == MAGIC:
                                found.append((label, Path(dirpath)))
                    except OSError:
                        pass
    return found
