import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import mods_manager as mm


def make_mod(root, name, files=('Layout/a.bin',), exefs=False):
    for f in files:
        p = root / name / 'romfs' / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x' * 10)
    if exefs:
        (root / name / 'exefs').mkdir(parents=True, exist_ok=True)
    return root / name


class Mods(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'mods'
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_lists_on_and_off_and_nested(self):
        make_mod(self.root, 'HD Textures', files=('a.bin', 'b/c.bin'))
        make_mod(self.root, '_Old Mod')
        make_mod(self.root / 'contents' / '0100', 'Deep')
        mods = {m['name']: m for m in mm.list_mods(self.root)}
        self.assertEqual(set(mods), {'HD Textures', 'Old Mod', 'Deep'})
        self.assertTrue(mods['HD Textures']['enabled'])
        self.assertEqual(mods['HD Textures']['files'], 2)
        self.assertFalse(mods['Old Mod']['enabled'])
        self.assertTrue(mods['Deep']['enabled'])

    def test_off_parent_turns_children_off(self):
        make_mod(self.root / '-pack', 'Inner')
        self.assertFalse(mm.list_mods(self.root)[0]['enabled'])

    def test_toggle_renames(self):
        p = make_mod(self.root, 'Mod')
        off = mm.set_enabled(p, False)
        self.assertEqual(off.name, '_Mod')
        self.assertFalse(mm.list_mods(self.root)[0]['enabled'])
        on = mm.set_enabled(off, True)
        self.assertEqual(on.name, 'Mod')
        self.assertEqual(mm.set_enabled(on, True), on)

    def test_toggle_refuses_clash(self):
        p = make_mod(self.root, 'Mod')
        make_mod(self.root, '_Mod')
        with self.assertRaises(FileExistsError):
            mm.set_enabled(p, False)

    def test_add_zip_with_wrapper_folder(self):
        z = Path(self.tmp.name) / 'cool.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('Cool Mod/romfs/Layout/x.bin', b'1')
        self.assertEqual(mm.add_mod(z, self.root), ['Cool Mod'])
        self.assertTrue((self.root / 'Cool Mod' / 'romfs' / 'Layout' / 'x.bin').is_file())
        self.assertEqual(mm.add_mod(z, self.root), ['Cool Mod (2)'])
        self.assertFalse(any(p.name.startswith('.adding-') for p in self.root.iterdir()))

    def test_add_zip_with_romfs_at_top(self):
        z = Path(self.tmp.name) / 'flat.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('romfs/a.bin', b'1')
        self.assertEqual(mm.add_mod(z, self.root), ['flat'])

    def test_add_rejects_zip_slip_and_empty(self):
        z = Path(self.tmp.name) / 'bad.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('../../evil/romfs/a.bin', b'1')
        with self.assertRaises(ValueError):
            mm.add_mod(z, self.root)
        e = Path(self.tmp.name) / 'empty.zip'
        with zipfile.ZipFile(e, 'w') as zf:
            zf.writestr('readme.txt', b'hi')
        with self.assertRaises(ValueError):
            mm.add_mod(e, self.root)

    def test_add_folder_with_several_mods(self):
        src = Path(self.tmp.name) / 'pack'
        make_mod(src, 'A')
        make_mod(src, 'B')
        self.assertEqual(sorted(mm.add_mod(src, self.root)), ['A', 'B'])


if __name__ == '__main__':
    unittest.main()
