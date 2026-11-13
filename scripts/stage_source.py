"""Assemble the published source with third-party tools from an existing distribution."""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/alpha'))
import distribution_guard


def stage(runtime, output):
    runtime, output = runtime.resolve(), output.resolve()
    distribution_guard.check(ROOT)
    version = (ROOT / 'tools/alpha/VERSION').read_text().strip()
    required = ['python/python.exe', 'engine/python/python.exe', 'engine/llvm-mingw/bin/clang.exe',
                'engine/cpm', 'engine/third_party/sdl2/SDL2.dll', 'engine/third_party/sdl2/SDL3.dll']
    missing = [name for name in required if not (runtime / name).exists()]
    if missing:
        raise ValueError('Runtime dependencies missing: ' + ', '.join(missing))
    if output.exists():
        raise ValueError('Use a new output directory; existing files are never deleted: ' + str(output))
    if output == ROOT or ROOT in output.parents and output.relative_to(ROOT).parts[0] != 'build':
        raise ValueError('Inside this checkout, choose an output below build/.')
    if output == runtime or runtime in output.parents or output in runtime.parents:
        raise ValueError('Runtime and output directories must be separate.')
    output.mkdir(parents=True)
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.git')
    shutil.copytree(ROOT / 'engine', output / 'engine', ignore=ignore)
    shutil.copytree(ROOT / 'tools/alpha/launcher', output / 'launcher', ignore=ignore)
    shutil.copytree(ROOT / 'data', output / 'data', ignore=ignore)
    shutil.copytree(runtime / 'python', output / 'python', ignore=ignore)
    # Only dependency directories, never the donor's host/GPU/launcher source or game files.
    for name in ('python', 'llvm-mingw', 'cpm'):
        src = runtime / 'engine' / name
        if src.is_dir():
            shutil.copytree(src, output / 'engine' / name, dirs_exist_ok=True, ignore=ignore)
    if (runtime / 'engine/wgpu-native/lib').is_dir():
        shutil.copytree(runtime / 'engine/wgpu-native/lib', output / 'engine/wgpu-native/lib', dirs_exist_ok=True)
    (output / 'engine/third_party/sdl2').mkdir(parents=True, exist_ok=True)
    for name in ('SDL2.dll', 'SDL3.dll'):
        shutil.copy2(runtime / 'engine/third_party/sdl2' / name, output / 'engine/third_party/sdl2' / name)
    # Resource files must come from our reviewed source art, never the donor's old icon.
    (output / 'engine/work').mkdir(exist_ok=True)
    subprocess.run([str(output / 'engine/python/python.exe'), '-I',
                    str(output / 'engine/nx2/make_icon.py'),
                    str(ROOT / 'tools/alpha/ocarina-icon.png'), str(output / 'engine/work')], check=True)
    if (runtime / 'amd-fsr4').is_dir():
        shutil.copytree(runtime / 'amd-fsr4', output / 'amd-fsr4')
    shutil.copy2(ROOT / 'tools/alpha/ocarina_prepare.py', output / 'ocarina_prepare.py')
    shutil.copy2(ROOT / 'tools/alpha/OcarinaReborn.ico', output / 'OcarinaReborn.ico')
    for name in ('CREDITS.md', 'LICENSE-HOOKSHOT'):
        shutil.copy2(ROOT / name, output / name)
    info = json.loads((ROOT / 'build-info.json').read_text())
    info.update(version=version, commit='source-v' + version,
                stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    (output / 'build-info.json').write_text(json.dumps(info, indent=2))
    distribution_guard.check(output)
    print('Source staged:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    stage(args.runtime, args.out)
