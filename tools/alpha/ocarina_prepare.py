"""Ocarina Reborn: builds the game folder from the player's own .nup with the bundled Hookshot build pipeline.

    python ocarina_prepare.py --nup <game.nup> --dest <game folder> --tools <install dir> [--check-only]
    python ocarina_prepare.py --replay <recorded build.log> [--speed 50]      (developer test of the launcher's build screen)

The game itself is Hookshot (https://github.com/NotRexed/Hookshot, GPL-3.0; its source, tools and LICENSE ship in
<install>/engine, its files renamed ocarina_reborn*): nx2/make_game.py reads the .nup, lifts the code, compiles
ocarina_reborn.exe + ocarina_reborn_vk.dll and prepares the shaders (ocarina_reborn.exe --prepare-shaders). This script runs it with Hookshot's own Python and turns its output into one
JSON line per update for the launcher:

    {"step": <id>, "frac": 0..1, "count": n, "total": n, "unit": "files|shaders", "text": ..., "total_pct": 0..100}
    {"done": <id>}            a step finished          {"log": <line>}    a line of the build's own output
    {"error": "<kind>: <text>", "step": <id>}           {"finished": true}

Steps and where their numbers come from (all of them from the build's own output; nothing is timed):
    nup       the container and version check (@@check)
    extract   the RomFS written out ("<n> files, <x> GB" lines against the title's "romfs <n> files")
    analyze   the code lifted to C (lift stage; its milestones: discovery, translation, chunks, files written)
    build     the C compiled (@@plan files, @@file per finished file, @@progress)
    finish    the game folder put together, the shader list made (finish stage)
    shaders   the shader programs prepared on this GPU (@@stage shaders / @@progress; the first 70 % are the programs)
The .nup is only read.
"""
import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

STEPS = [('nup', 2), ('extract', 20), ('analyze', 8), ('build', 40), ('finish', 2), ('shaders', 28)]
ORDER = [s for s, _ in STEPS]
LANGS = {0x07: 'de', 0x0c: 'fr', 0x10: 'it', 0x0a: 'es', 0x13: 'nl', 0x15: 'pl', 0x19: 'ru', 0x11: 'ja', 0x12: 'ko'}
LIFT_MILESTONES = [('discovered ', 0.35), ('translated instructions', 0.55), ('chunks: ', 0.7), ('oot_patches', 0.8),
                   ('wrote ', 0.95)]


GAME_EXE = 'ocarina_reborn.exe'   # (the engine's build names it so: stage_alpha.py rename_files)


def migrate(D):
    """a game folder built before the rename (hookshot*, .hookshot_*, OcarinaReborn-Game.exe): its files under the new names,
    so an update finds the game data it keeps and the settings and saves carry over"""
    for folder in (D, D / 'user'):
        if not folder.is_dir():
            continue
        for f in list(folder.iterdir()):
            if 'hookshot' in f.name:
                to = f.with_name(f.name.replace('hookshot', 'ocarina_reborn'))
                if f.suffix.lower() in ('.exe', '.dll') or f.name.endswith('.warming'):
                    f.unlink(missing_ok=True) if f.is_file() else None   # (rebuilt: the old program is not kept)
                elif not to.exists():
                    f.rename(to)
    (D / 'OcarinaReborn-Game.exe').unlink(missing_ok=True)


def shown(s):
    """what the launcher shows of the build's text: Ocarina Reborn, not the name of the build pipeline underneath (the
    raw build.log keeps the original lines)"""
    return (s.replace('Hookshot Builder', 'Ocarina Reborn').replace('Hookshot', 'Ocarina Reborn')
            .replace('HOOKSHOT', 'OCARINA REBORN').replace('hookshot', 'ocarina-reborn'))


def out(**m):
    for k in ('log', 'text', 'error'):
        if isinstance(m.get(k), str):
            m[k] = shown(m[k])
    print(json.dumps(m, ensure_ascii=False), flush=True)


class Progress:
    def __init__(self):
        self.step, self.frac, self.done = 'nup', 0.0, set()
        self.files_total = self.plan = self.programs = self.files_done = 0

    def total_pct(self):
        i = ORDER.index(self.step)
        return round(sum(w for _, w in STEPS[:i]) + STEPS[i][1] * min(max(self.frac, 0.0), 1.0), 2)

    def go(self, step, frac=0.0, **extra):
        if step != self.step:
            for s in ORDER[:ORDER.index(step)]:
                if s not in self.done:
                    self.done.add(s)
                    out(done=s)
            self.step = step
            self.frac = 0.0
        self.frac = max(self.frac, frac)
        out(step=step, frac=round(self.frac, 4), total_pct=self.total_pct(), **extra)

    def line(self, raw):
        """one line of make_game.py's output; an error text when it reports one"""
        line = raw.rstrip('\n')
        w = line.strip().split(' ', 2)
        if not line.startswith('@@'):
            out(log=line[:300])
        if w[0] == '@@check' and len(w) > 2:
            if w[1] != 'ok':
                return 'unsupported: ' + w[2]
            self.go('nup', 1.0, text=w[2])
        elif w[0] == '@@stage' and len(w) > 1:
            st = {'read': 'extract', 'lift': 'analyze', 'compile': 'build', 'finish': 'finish', 'shaders': 'shaders'}.get(w[1])
            if st:
                self.go(st, 0.0)
        elif w[0] == '@@plan' and len(w) > 1:
            try:
                self.plan = int(w[1])
            except ValueError:
                pass
        elif w[0] == '@@file' and self.step == 'build':
            self.files_done += 1
            if self.plan:
                self.go('build', self.files_done / self.plan, count=self.files_done, total=self.plan, unit='files')
        elif w[0] == '@@progress' and len(w) > 1:
            try:
                f = float(w[1])
            except ValueError:
                return None
            if self.step == 'shaders':
                extra = {}
                if self.programs:   # (gpu/vk/vk_main.cpp started_up: the programs are the first 70 % of its bar)
                    extra = dict(count=min(self.programs, int(round(min(f, 0.7) / 0.7 * self.programs))), total=self.programs,
                                 unit='shaders')
                self.go('shaders', f, **extra)
            elif self.step == 'build' and not self.plan:
                self.go('build', f)
        elif w[0] == '@@error':
            return 'failed: ' + line[8:]
        elif w[0] == '@@done':
            self.go('shaders', 1.0)
            for s in ORDER:
                if s not in self.done:
                    self.done.add(s)
                    out(done=s)
        else:
            m = re.search(r'romfs (\d+) files', line)
            if m and self.step == 'extract':
                self.files_total = int(m.group(1)) + 5   # (+ the 5 ExeFS files the running count includes)
            m = re.match(r'\s+(\d+) files, ([\d.]+) GB', line)
            if m and self.step == 'extract' and self.files_total:
                n = int(m.group(1))
                self.go('extract', n / self.files_total, count=n, total=self.files_total, unit='files')
            m = re.match(r'done: (\d+) files written', line)
            if m and self.step == 'extract':
                self.go('extract', 1.0, count=int(m.group(1)), total=int(m.group(1)), unit='files')
            if self.step == 'analyze':
                for key, f in LIFT_MILESTONES:
                    if line.startswith(key):
                        self.go('analyze', f)
            m = re.match(r'(\d+) programs from \d+ stages', line)
            if m:
                self.programs = int(m.group(1))
            if 'the game prepares them at its first start' in line:   # (make_game.not_prepared: no GPU work now)
                self.go('shaders', 1.0, text='skipped: ' + line)
        return None


def language():
    try:
        return LANGS.get(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff, 'en-US')
    except (AttributeError, OSError):
        return 'en-US'


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--nup', type=Path)
    ap.add_argument('--dest', type=Path)
    ap.add_argument('--tools', type=Path)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--language', help="the game's language code (default: Windows' language)")
    ap.add_argument('--jobs', help='parallel compiles (default: Hookshot decides by CPU and memory)')
    ap.add_argument('--logs', type=Path, help='folder for build.log (default: beside the game folder)')
    ap.add_argument('--update', action='store_true',
                    help='rebuild the game folder in --dest from the game files it keeps (no .nup): a new Ocarina Reborn version')
    ap.add_argument('--replay', type=Path, help='feed a recorded build.log through the progress parser (test)')
    ap.add_argument('--speed', type=float, default=50.0, help='with --replay: lines per second')
    a = ap.parse_args()
    prog = Progress()
    if a.replay:
        for line in a.replay.read_text(encoding='utf-8', errors='replace').splitlines(True):
            line = re.sub(r'^\[\d\d:\d\d:\d\d\] ', '', line)
            err = prog.line(line)
            if err:
                out(error=err, step=prog.step)
                return 3
            time.sleep(1.0 / a.speed)
        out(finished=True)
        return 0
    if not (a.dest and a.tools and (a.nup or a.update)):
        ap.error('--dest, --tools and --nup (or --update) are needed')
    H = a.tools.resolve() / 'engine'
    D = a.dest.resolve()
    logs = a.logs or D.parent / 'PrepareLogs'   # not inside <dest>: make_game.py owns it
    logs.mkdir(parents=True, exist_ok=True)
    if a.update:
        migrate(D)
    cmd = [str(H / 'python' / 'python.exe'), '-I', str(H / 'nx2' / 'make_game.py')]
    cmd += ['--update', str(D)] if a.update else ['--nup', str(a.nup)]
    if not a.check_only:
        cmd += ['--fsr']   # (AMD FSR 4 built in: AMD's headers only; its DLLs are AMD's, found beside the game at run time)
    if a.update:
        cmd += ['--work', str(Path(os.environ.get('LOCALAPPDATA', str(D.parent))) / 'Ocarina Reborn' / 'GameBuild')]
        if a.jobs:
            cmd += ['--jobs', str(a.jobs)]
    elif a.check_only:
        cmd += ['--check']
    else:
        cmd += ['--out', str(D), '--language', a.language or language(),
                '--work', str(Path(os.environ.get('LOCALAPPDATA', str(D.parent))) / 'Ocarina Reborn' / 'GameBuild')]
        if a.jobs:
            cmd += ['--jobs', str(a.jobs)]
    env = dict(os.environ, HOOKSHOT_MINGW=str(H / 'llvm-mingw'), RX_CPM=str(H / 'cpm'), WGPU_NATIVE=str(H / 'wgpu-native'),
               HOOKSHOT_NO_UPDATE_CHECK='1',
               HOOKSHOT_KEEP_BUILD_FILES='1')   # (the compiled objects stay: an update compiles only what changed)
    prog.go('nup', 0.0, text='Validating game file')
    err = None
    with open(logs / ('check.log' if a.check_only else 'build.log'), 'w', encoding='utf-8', errors='replace') as log:
        log.write(f'[{time.strftime("%H:%M:%S")}] {" ".join(cmd)}\n')
        p = subprocess.Popen(cmd, cwd=str(H), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for line in p.stdout:
            log.write(f'[{time.strftime("%H:%M:%S")}] {line}')
            log.flush()
            err = err or prog.line(line)
        code = p.wait()
        log.write(f'[{time.strftime("%H:%M:%S")}] exit {code}\n')
    if code or err:
        out(error=err or f'failed: the game build stopped (exit code {code}); see {logs / "build.log"}', step=prog.step)
        return 3
    if not a.check_only:
        try:   # (which Ocarina Reborn built it: a newer install offers an update, launcher.py)
            info = json.loads((a.tools.resolve() / 'build-info.json').read_text())
        except (OSError, ValueError):
            info = {}
        (D / 'ready.json').write_text(json.dumps(dict(game='Ocarina of Time', backend='Hookshot', version=info.get('version'),
                                                      commit=info.get('commit'), built_by=info.get('stamp'),
                                                      prepared=time.strftime('%Y-%m-%d %H:%M:%S')), indent=2))
    out(finished=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
