import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ALPHA / 'launcher'))
import diagnostics
sys.path.insert(0, str(ALPHA))
import engine_stability


def function_block(source, name):
    start = source.index(name)
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class PatchingTests(unittest.TestCase):
    def test_clean_engine_upgrade_is_idempotent_and_flush_cannot_deadlock(self):
        engine = ALPHA.parents[1] / 'engine'
        if not engine.exists():
            engine = ALPHA.parents[1] / 'build/alpha/stage/engine'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ('gpu/vk/vk_memory.cpp', 'gpu/vk/vk_texture.cpp', 'host/hos_thread.c', 'host/mkw_glue.c', 'nx2/make_game.py')
            for rel in names:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(engine / rel, root / rel)
            engine_stability.apply(root)
            first = [(root / rel).read_bytes() for rel in names]
            engine_stability.apply(root)
            self.assertEqual(first, [(root / rel).read_bytes() for rel in names])
            cxx = shutil.which('clang++')
            if cxx:
                source = (root / 'gpu/vk/vk_texture.cpp').read_text(encoding='utf-8')
                helper = function_block(source, 'uint64_t preset_texture_budget(')
                start = source.index('    const bool vram_env = getenv("RX_VK_VRAM_MB")')
                end = source.index('    // (near what the driver allows', start)
                fixture = (ALPHA / 'tests/texture_budget_test.cpp').read_text().replace('/* HELPER */', helper)
                fixture = fixture.replace('/* SELECTION */', source[start:end])
                cpp, exe = root / 'budget.cpp', root / 'budget.exe'
                cpp.write_text(fixture)
                subprocess.run([cxx, '-std=c++17', '-O1', str(cpp), '-o', str(exe)], check=True, capture_output=True)
                subprocess.run([str(exe)], check=True, capture_output=True, timeout=6)
            compiler = shutil.which('clang')
            if compiler and os.name == 'nt':
                source = (root / 'host/hos_thread.c').read_text(encoding='utf-8')
                block = function_block(source, 'static void log_flush(void)')
                fixture = (ALPHA / 'tests/log_flush_test.c').read_text().replace('/* ACTUAL_FLUSH */', block)
                c, exe = root / 'flush.c', root / 'flush.exe'
                c.write_text(fixture)
                subprocess.run([compiler, '-O1', str(c), '-o', str(exe)], check=True, capture_output=True)
                subprocess.run([str(exe)], check=True, capture_output=True, timeout=6)


class DiagnosticsTests(unittest.TestCase):
    def test_gpu_memory_failure_is_recorded_even_after_clean_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            (folder / 'ocarina_reborn_log.txt').write_text('vk: submit 92402 failed (-2)\nwindow: closed, exiting\n')
            diagnostics.finish(run, 0, folder)
            self.assertEqual(run['record']['result'], 'runtime_errors_on_exit')
            self.assertEqual(run['record']['gpu_errors']['device_memory_errors'], 1)

    def test_failed_start_does_not_blame_an_old_crash_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'ocarina_reborn_log.txt').write_text('FATAL: old run, unrelated error\n')
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            diagnostics.finish(run, 3, folder)
            self.assertFalse(run['record']['runtime_log_updated'])
            self.assertEqual(run['record']['result'], 'nonzero_exit_without_recorded_cause')
            self.assertEqual(run['record']['last_runtime_lines'], [])

    def test_unknown_exit_three_and_build_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'ready.json').write_text('{"version":"1.0.5","built_by":"test-build"}')
            (folder / 'ocarina_reborn_log.txt').write_text('vk: ready\nmap: HyruleField_Child\n')
            env = {'SECRET': 'must not be recorded', 'PROTON_VERSION': 'test'}
            run = diagnostics.start(folder / 'reports', folder, {}, {'hdr': '0'}, {}, env)
            diagnostics.finish(run, 3, folder)
            data = json.loads(run['path'].read_text())
            self.assertEqual(data['result'], 'nonzero_exit_without_recorded_cause')
            self.assertEqual(data['game_build']['built_by'], 'test-build')
            self.assertNotIn('SECRET', str(data))
            self.assertEqual(data['runtime']['environment']['PROTON_VERSION'], 'test')
            self.assertEqual(env['OCR_CRASH_FILE'], str(run['native'].resolve()))

    def test_native_crash_is_packaged_and_tail_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log = folder / 'ocarina_reborn_log.txt'
            log.write_bytes(b'x' * 100000 + b'\nlatest line\n')
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            run['native'].write_text('FAILURE: CRT abort (SIGABRT)\n')
            diagnostics.finish(run, 3, folder)
            self.assertEqual(run['record']['result'], 'native_failure_recorded')
            self.assertLessEqual(len(diagnostics.tail(log)), 65536)
            files = dict(diagnostics.package_files(folder / 'reports', folder))
            self.assertIn(run['native'], files)
            self.assertIn(run['path'], files)


class NativeTests(unittest.TestCase):
    def test_capture_refill_and_lock_contention(self):
        compiler = shutil.which('clang++')
        if not compiler:
            self.skipTest('clang++ needed')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'capture.exe'
            subprocess.run([compiler, '-std=c++17', '-O1', str(ALPHA / 'tests/capture_pool_test.cpp'), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, timeout=15, capture_output=True)

    @unittest.skipUnless(os.name == 'nt', 'Windows native crash handler')
    def test_actual_abort_and_unhandled_exception(self):
        compiler = shutil.which('clang')
        if not compiler:
            self.skipTest('clang needed')
        with tempfile.TemporaryDirectory() as tmp:
            exe, report = Path(tmp) / 'crash.exe', Path(tmp) / 'report.txt'
            subprocess.run([compiler, '-O0', str(ALPHA / 'tests/crash_report_test.c'), '-o', str(exe)], check=True, capture_output=True)
            env = dict(os.environ, OCR_CRASH_FILE=str(report))
            for mode, expected in [('normal', None), ('abort', 'CRT abort (SIGABRT)'), ('exception', 'unhandled exception')]:
                with self.subTest(mode=mode):
                    result = subprocess.run([str(exe), mode], env=env, capture_output=True, timeout=15)
                    data = report.read_text()
                    if expected:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('FAILURE: ' + expected, data)
                        self.assertIn('host stack (module + offset):', data)
                        self.assertIn('crash.exe+', data)
                    else:
                        self.assertEqual(result.returncode, 0)
                        self.assertNotIn('FAILURE: ', data)


if __name__ == '__main__':
    unittest.main()
