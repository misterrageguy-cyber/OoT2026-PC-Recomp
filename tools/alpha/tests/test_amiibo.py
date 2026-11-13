"""User-file preservation and the real native reader, with invented NTAG bytes.

No Nintendo dumps, keys, game data or NFC hardware are test inputs.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


amiibo = module('amiibo_under_test', ALPHA / 'launcher/amiibo.py')


def invented_tag(size=540):
    data = bytearray(size)
    data[:16] = bytes.fromhex('041122bf3344556644480fe0f110ffee')
    # Unassigned model; only a structural test vector, not a real figure.
    data[0x54:0x5c] = bytes.fromhex('f1f20304f5f60702')
    return bytes(data)


class AmiiboFilesTests(unittest.TestCase):
    def test_sizes_and_model_identity(self):
        for size in (532, 540, 572):
            self.assertEqual(amiibo.validate(invented_tag(size)), 'F1F20304F5F60702')

    def test_generic_ntag215_capability_container(self):
        data = bytearray(invented_tag())
        data[12:16] = bytes.fromhex('e1103e00')
        self.assertEqual(amiibo.validate(data), 'F1F20304F5F60702')

    def test_corrupt_and_wrong_layouts(self):
        good = invented_tag()
        for data in (b'', good[:531], good + b'x', good * 3, bytes(540)):
            with self.assertRaises(ValueError):
                amiibo.validate(data)
        for offset in (0, 3, 8, 12, 14, 0x5b):
            damaged = bytearray(good); damaged[offset] ^= 0x40
            with self.assertRaises(ValueError):
                amiibo.validate(damaged)

    def test_selection_is_atomic_and_preserves_original(self):
        with tempfile.TemporaryDirectory(prefix='amiibo-\u00e4-') as tmp:
            root = Path(tmp); game = root / 'Spiel'; game.mkdir()
            original = root / 'Meine Figur.bin'; original.write_bytes(invented_tag())
            amiibo.select(game, original)
            self.assertEqual(amiibo.selected_id(game), 'F1F20304F5F60702')
            self.assertEqual((game / amiibo.FILENAME).read_bytes(), original.read_bytes())
            # Selecting the managed copy too is safe (read before replace).
            amiibo.select(game, game / amiibo.FILENAME)
            bad = root / 'broken.bin'; bad.write_bytes(b'no tag')
            with self.assertRaises(ValueError):
                amiibo.select(game, bad)
            self.assertEqual(amiibo.selected_id(game), 'F1F20304F5F60702')
            amiibo.clear(game); amiibo.clear(game)
            self.assertIsNone(amiibo.selected_id(game))
            self.assertEqual(original.read_bytes(), invented_tag())
            self.assertEqual(list(game.iterdir()), [])

    def test_real_native_reader_lifecycle(self):
        compiler = shutil.which('clang') or shutil.which('gcc')
        if not compiler or os.name != 'nt':
            self.skipTest('Windows C compiler required for the native reader')
        engine = ROOT / 'engine'
        if not engine.is_dir():
            engine = ROOT / 'build/alpha/stage/engine'
        with tempfile.TemporaryDirectory(prefix='amiibo-reader-') as tmp:
            folder = Path(tmp)
            # Compile the production source, substituting only guest memory/events.
            for name in ('ocr_amiibo.c', 'ocr_amiibo_file.h'):
                shutil.copy2(ALPHA / 'hud' / name, folder / name)
            shutil.copy2(engine / 'host/hos_paths.h', folder / 'hos_paths.h')
            shutil.copy2(ALPHA / 'tests/amiibo_hos_stub.h', folder / 'hos.h')
            binary = folder / 'reader.exe'
            commands = [[compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                         '-I' + str(folder), str(ALPHA / 'tests/amiibo_reader_test.c'), '-o', str(binary)],
                        [str(binary)]]
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, timeout=45,
                                        creationflags=subprocess.CREATE_NO_WINDOW, cwd=folder)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_menu_patch_checks_anchors_before_writing(self):
        patcher = module('amiibo_patch_test', ALPHA / 'engine_amiibo.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'gpu/vk').mkdir(parents=True); (root / 'host').mkdir()
            target = root / 'gpu/vk/vk_menu.cpp'
            source = '\n'.join(old for old, _ in patcher.CHANGES)
            target.write_text(source, encoding='utf-8')
            patcher.apply(root)
            once = target.read_bytes(); patcher.apply(root)
            self.assertEqual(once, target.read_bytes())
            target.write_text('changed upstream', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                patcher.apply(root)
            self.assertEqual(target.read_text(), 'changed upstream')


if __name__ == '__main__':
    unittest.main()
