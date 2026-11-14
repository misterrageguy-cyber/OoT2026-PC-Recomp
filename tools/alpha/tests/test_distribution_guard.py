import hashlib
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import distribution_guard as guard

class DistributionGuard(unittest.TestCase):
    def test_recorded_fairy_is_allowed_only_at_launcher_paths(self):
        raw = b'FAIRY1' + struct.pack('<HHH', 16, 1, 33) + bytes(16 * 16 * 4 * 2)
        manifest = {'files': {}, 'restored_launcher_media': {'files': {
            guard.FAIRY_SOURCE: hashlib.sha256(raw).hexdigest()}}}
        for rel in (guard.FAIRY_SOURCE, 'launcher/assets/fairy.bin'):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                p = root / rel
                p.parent.mkdir(parents=True)
                p.write_bytes(raw)
                self.assertEqual(guard.problems(root, manifest), [])
                p.write_bytes(raw[:-1] + b'X')
                self.assertEqual(len(guard.problems(root, manifest)), 1)
                p.write_bytes(raw)
                (root / 'fairy.bin').write_bytes(raw)
                self.assertEqual(len(guard.problems(root, manifest)), 1)
                self.assertEqual(len(guard.problems(root, {'files': manifest['restored_launcher_media']['files']})), 2)

    def test_recorded_fairy_must_be_a_complete_animation(self):
        for raw in (b'not animation', b'FAIRY1' + struct.pack('<HHH', 16, 1, 33)):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                p = root / guard.FAIRY_SOURCE
                p.parent.mkdir(parents=True)
                p.write_bytes(raw)
                manifest = {'files': {}, 'restored_launcher_media': {'files': {
                    guard.FAIRY_SOURCE: hashlib.sha256(raw).hexdigest()}}}
                self.assertEqual(len(guard.problems(root, manifest)), 1)

    def test_old_animations_and_unreviewed_project_videos_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'tools/alpha').mkdir(parents=True)
            (p / 'tools/alpha/fairy.gif').write_bytes(b'withdrawn fixture')
            (p / 'gameplay.webm').write_bytes(b'unreviewed fixture')
            self.assertEqual(len(guard.problems(p, {'files': {}})), 2)

    def test_disguised_recording_archive_and_game_data_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with zipfile.ZipFile(p/'optional-assets.zip','w') as z:
                z.writestr('sounds/voice.wav',b'synthetic')
            (p/'payload.nsp').write_bytes(b'synthetic')
            self.assertEqual(len(guard.problems(p, {'files':{}})),2)

    def test_modified_media_blocked_but_known_art_and_source_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);art=p/'launcher/assets/logo.png';art.parent.mkdir(parents=True)
            art.write_bytes(b'original fixture')
            manifest={'files':{'logo':hashlib.sha256(art.read_bytes()).hexdigest()}}
            (p/'source.c').write_text('/* original engine code */')
            self.assertEqual(guard.problems(p,manifest),[])
            art.write_bytes(b'unreviewed replacement')
            self.assertEqual(len(guard.problems(p,manifest)),1)

if __name__=='__main__':unittest.main()
