"""Bounded per-run diagnostics. No full environment, keys, saves or memory dumps."""
import datetime
import json
import os
from pathlib import Path
import platform
import time
import uuid
import performance

ENV_KEYS = ('PROTON_VERSION', 'WINEVERSION', 'SteamGameId', 'SteamAppId', 'DXVK_VERSION',
            'HOS_HEADLESS', 'HOS_FPS_MAX', 'HOS_AUDIO_TRACE', 'RX_VK_CAP_PREWARM',
            'RX_VK_CAP_SPARE_MB', 'OCR_RAM_RESERVE_MB')


def runtime_info(env):
    wine = None
    if os.name == 'nt':
        try:
            import ctypes
            fn = ctypes.CDLL('ntdll').wine_get_version
            fn.restype = ctypes.c_char_p
            wine = fn().decode('utf-8', 'replace')[:200]
        except (AttributeError, OSError):
            pass
    return dict(platform=platform.platform(), wine_version=wine,
                environment={k: str(env[k])[:200] for k in ENV_KEYS if k in env})


def tail(path, limit=65536):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            data = stream.read(limit)
        return data.decode('utf-8', 'replace')
    except OSError:
        return ''


def log_fingerprints(game):
    result = {}
    for name in ('ocarina_reborn_log.txt', 'hookshot_log.txt'):
        try:
            stat = (Path(game) / name).stat()
            result[name] = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        except OSError:
            pass
    return result


def start(folder, game, build, settings, hardware, env):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = 'run-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    path = folder / (name + '.json')
    native = folder / (name + '-native.txt')
    env['OCR_CRASH_FILE'] = str(native.resolve())
    record = dict(schema=1, started=datetime.datetime.now().astimezone().isoformat(),
                  build=build, settings=settings, hardware=hardware, runtime=runtime_info(env),
                  state='running', native_report=native.name)
    try:
        ready = json.loads((Path(game) / 'ready.json').read_text(encoding='utf-8'))
        record['game_build'] = {k: ready[k] for k in ('built_by', 'version', 'commit') if k in ready}
    except (OSError, ValueError):
        pass
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
    return dict(path=path, native=native, record=record, clock=time.monotonic(), logs_before=log_fingerprints(game))


def finish(run, code, game):
    record = run['record']
    record.update(state='finished', exit_code=code, exit_hex=f'{code & 0xffffffff:#x}',
                  seconds=round(time.monotonic() - run['clock'], 3))
    changed = [name for name, stat in log_fingerprints(game).items() if run['logs_before'].get(name) != stat]
    record['runtime_log_updated'] = bool(changed) and 'launch_error' not in record
    text = tail(Path(game) / changed[0]) if record['runtime_log_updated'] else ''
    # Preserve the current run's evidence before later starts rotate the game logs.
    record['last_runtime_lines'] = text.splitlines()[-150:]
    native = tail(run['native'])
    record['native_failure_recorded'] = 'FAILURE: ' in native
    record['gpu_errors'] = performance.gpu_failures(text.splitlines())
    if 'launch_error' in record:
        record['result'] = 'launch_failed'
    elif code == 0:
        record['result'] = 'runtime_errors_on_exit' if any(record['gpu_errors'].values()) else 'normal_exit'
    elif record['native_failure_recorded']:
        record['result'] = 'native_failure_recorded'
    elif 'FATAL:' in text or 'CRASH:' in text:
        record['result'] = 'runtime_failure_recorded'
    else:
        record['result'] = 'nonzero_exit_without_recorded_cause'
    if code == 3:
        record['note'] = 'Exit 3 alone does not identify a Vulkan, memory or driver failure.'
    run['path'].write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
    # Keep the last 20 runs, including their paired native report.
    for old in sorted(run['path'].parent.glob('run-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[20:]:
        try:
            old.unlink()
            old.with_name(old.stem + '-native.txt').unlink(missing_ok=True)
        except OSError:
            pass


def package_files(crash, game):
    for path in sorted(Path(crash).glob('*'), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
            yield path, 'crash/' + path.name
    # Direct game launches have no launcher-supplied report path.
    for path in sorted(Path(game).glob('ocarina_reborn_crash_*.txt'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        if path.stat().st_size <= 2 * 1024 * 1024:
            yield path, 'crash/native/' + path.name
