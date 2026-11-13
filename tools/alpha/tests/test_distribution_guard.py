import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import distribution_guard as guard

class DistributionGuard(unittest.TestCase):
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
