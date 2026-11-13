import io
import json
import math
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import classic_voices as cv


def decode_dsp(bwav):
    """Independent decoder for checking the generated BWAV header and waveform."""
    count = int.from_bytes(bwav[28:32], 'little')
    coefs = struct.unpack_from('<16h', bwav, 32)
    offset = int.from_bytes(bwav[68:72], 'little')
    samples, h1, h2 = [], 0, 0
    for pos in range(offset, len(bwav), 8):
        packet = bwav[pos:pos + 8]
        predictor, scale = packet[0] >> 4, packet[0] & 15
        a, b = coefs[predictor * 2:predictor * 2 + 2]
        for byte in packet[1:]:
            for nibble in (byte >> 4, byte & 15):
                signed = nibble if nibble < 8 else nibble - 16
                sample = ((signed * (1 << scale) * 2048 + a * h1 + b * h2 + 1024) >> 11)
                sample = min(32767, max(-32768, sample))
                samples.append(sample)
                h2, h1 = h1, sample
    return samples[:count]


class ClassicVoices(unittest.TestCase):
    def test_gameplay_whitelist_excludes_cutscenes_and_other_characters(self):
        for age, title in (('child', 'Child'), ('adult', 'Adult')):
            prefix = 'Vo_Pl' + title + '_'
            self.assertEqual(cv.source_for(prefix + 'SwordAttack_S_02', age), 'Attack2')
            self.assertEqual(cv.source_for(prefix + 'Damage_B_03', age), 'Hurt3')
            for name in ('Dm_Test_01', 'Npc_Dream_FirstTalk_L_01', 'FallingScream_For_Demo_01',
                         'Wait_31_01', 'SwordAttack_S_01_extra'):
                self.assertIsNone(cv.source_for(prefix + name, age))
        self.assertIsNone(cv.source_for('Vo_PlAdult_Damage_S_01', 'child'))
        self.assertIsNone(cv.source_for('FootStep_01', 'adult'))

    def test_dsp_roundtrip_quality_and_prefetch_matches_stream(self):
        pcm = [round(18000 * math.sin(i * 0.071) + 4000 * math.sin(i * 0.231)) for i in range(17641)]
        encoded = cv.encode_dsp(pcm)
        full = cv.bwav(22050, len(pcm), encoded)
        pre = cv.bwav(22050, len(pcm), encoded, True)
        decoded = decode_dsp(full)
        snr = 10 * math.log10(sum(x * x for x in pcm) / sum((x-y)**2 for x, y in zip(pcm, decoded)))
        self.assertGreater(snr, 30)
        self.assertEqual(len(decoded), len(pcm))
        self.assertEqual(decode_dsp(pre), decoded[:14336])
        self.assertEqual(pre[8:12], full[8:12])
        self.assertEqual(int.from_bytes(full[8:12], 'little'), zlib.crc32(full[128:]))
        self.assertEqual(full[12:16], b'\x00\x00\x01\x00')
        self.assertEqual(pre[12:16], b'\x01\x00\x01\x00')

    def test_silence_and_extreme_samples(self):
        for pcm in ([0] * 15, [32767, -32768] * 17, [1]):
            decoded = decode_dsp(cv.bwav(16000, len(pcm), cv.encode_dsp(pcm)))
            self.assertEqual(len(decoded), len(pcm))
            self.assertLess(max(abs(a-b) for a, b in zip(pcm, decoded)), 4096)

    def test_wrong_age_or_incomplete_zip_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'voice.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('unrelated.txt', 'nothing')
            with self.assertRaisesRegex(ValueError, 'Incomplete or wrong ZIP'):
                cv.read_pack(path, 'child')

    def test_archive_paths_are_never_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'voice.zip'
            raw = io.BytesIO()
            with wave.open(raw, 'wb') as wav:
                wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\x00\x00' * 20)
            with zipfile.ZipFile(path, 'w') as z:
                for name in ('Attack1', 'Attack2', 'Attack3', 'Attack4', 'Hurt1', 'Hurt2', 'Hurt3', 'Jump1', 'Jump2'):
                    z.writestr('../../OOT_YoungLink_' + name + '.wav', raw.getvalue())
            self.assertEqual(len(cv.read_pack(path, 'child')), 9)
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_independent_switches_and_stale_source_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            pack = game / 'own-voice.zip'
            pack.write_bytes(b'synthetic test data')
            original = game / 'romfs/Sound/Resource/Player_Child.bars.zs'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'original')
            for age in cv.AGES:
                _, off = cv.paths(game, age)
                off.mkdir(parents=True)
                (off / cv.MARKER).write_text(json.dumps(dict(format=cv.FORMAT, age=age, mapping={},
                    bank='Sound/Resource/Player_Child.bars.zs', original_sha256=cv.hashlib.sha256(b'original').hexdigest())))
            cv.set_enabled(game, 'child', True)
            self.assertTrue(cv.status(game, 'child')['enabled'])
            self.assertFalse(cv.status(game, 'adult')['enabled'])
            cv.validate_active(game)
            original.write_bytes(b'updated')
            with self.assertRaisesRegex(ValueError, 'Select Default'):
                cv.validate_active(game)
            cv.set_enabled(game, 'child', False)
            cv.validate_active(game)
            self.assertEqual(original.read_bytes(), b'updated')

    def test_enabling_before_import_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'prepare'):
                cv.set_enabled(tmp, 'child', True)

    def test_selection_prepares_without_download_and_reuses_current_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            pack = game / 'own-voice.zip'
            pack.write_bytes(b'synthetic test data')
            original = game / 'romfs/Sound/Resource/Player_Child.bars.zs'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'original')
            with patch.object(cv, 'import_pack', return_value=3) as convert:
                self.assertEqual(cv.prepare(game, 'child', pack), 3)
                convert.assert_called_once_with(game, 'child', pack)
            _, off = cv.paths(game, 'child')
            off.mkdir(parents=True)
            (off / cv.MARKER).write_text(json.dumps(dict(format=cv.FORMAT, age='child', mapping={'a': 'b'},
                bank='Sound/Resource/Player_Child.bars.zs',
                original_sha256=cv.hashlib.sha256(b'original').hexdigest(),
                pack_sha256=cv.hashlib.sha256((pack).read_bytes()).hexdigest())))
            with patch.object(cv, 'import_pack', return_value=2) as convert:
                self.assertEqual(cv.prepare(game, 'child', pack), 1)
                convert.assert_not_called()
                cv.set_enabled(game, 'child', True)
                self.assertEqual(cv.prepare(game, 'child', pack), 1)
                convert.assert_not_called()
                original.write_bytes(b'updated')
                self.assertEqual(cv.prepare(game, 'child', pack), 2)
                convert.assert_called_once()

    def test_missing_user_file_fails_without_touching_the_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'own voice ZIP'):
                cv.prepare(Path(tmp) / 'game', 'adult', Path(tmp) / 'missing.zip')
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_malformed_bank_is_rejected(self):
        with self.assertRaises(ValueError):
            cv.bank_entries(b'not a bank')


if __name__ == '__main__':
    unittest.main()
