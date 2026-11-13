"""Game-free tests of color persistence, texture isolation and atomic caches."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

ALPHA = Path(__file__).resolve().parents[1]


def module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ALPHA / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


colors = module('tunic_colors', 'launcher/tunic_colors.py')
settings = module('tunic_settings', 'launcher/game_settings.py')
assets = module('tunic_assets_test', 'hud/tunic_assets.py')


class TunicSettings(unittest.TestCase):
    def test_all_rgb_values_hex_and_invalid_inputs(self):
        for n in range(256):
            rgb = (n, 255 - n, n // 2)
            values = colors.from_hex('#%02x%02x%02x' % rgb)
            self.assertEqual(colors.rgb(values), rgb)
            self.assertEqual(values['custom_tunic_color'], 1)
        for text in ('', '#123', '#1234567', '#ffffff;cmd', 'gg0000'):
            with self.assertRaises(ValueError):
                colors.from_hex(text)
        self.assertEqual(colors.rgb({'tunic_red': -2, 'tunic_green': 900, 'tunic_blue': 'bad'}), (0, 255, 75))

    def test_save_and_graphics_reset_keep_color_and_other_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            settings.write(game, {'volume': 42, 'shadow_distance': 3, 'game_language': 4})
            settings.write(game, colors.from_hex('#a021ff'))
            settings.reset(game)
            saved = settings.read(game)
            self.assertEqual(colors.hex_color(saved), '#A021FF')
            self.assertEqual(saved['custom_tunic_color'], '1')
            self.assertEqual(saved['volume'], '42')
            self.assertNotIn('shadow_distance', saved)
            settings.write(game, {'custom_tunic_color': 0})
            self.assertEqual(colors.hex_color(settings.read(game)), '#A021FF')


class TunicAssets(unittest.TestCase):
    def test_bc3_keeps_alpha_and_indices_even_for_black_and_white(self):
        block = bytes(range(8)) + struct.pack('<HHI', 0x3ca4, 0x1a02, 0xdeadbeef)
        for rgb in [(0, 0, 0), (255, 255, 255), (31, 97, 253)]:
            result = assets.recolor_bc3(block * 3, rgb)
            self.assertEqual(len(result), len(block) * 3)
            for start in range(0, len(result), 16):
                self.assertEqual(result[start:start + 8], block[:8])
                self.assertEqual(result[start + 12:start + 16], block[12:])
        self.assertEqual(assets.recolor_bc3(block, (0, 0, 0))[8:12], bytes(4))

    def test_material_allowlist_does_not_change_shared_texture_or_skin(self):
        b = bytearray(2048)
        b[:12] = b'FRES    \0\4\x0a\0'
        struct.pack_into('<Q', b, 0x28, 0x100)
        struct.pack_into('<H', b, 0xDC, 1)
        b[0x100:0x104] = b'FMDL'
        struct.pack_into('<Q', b, 0x138, 0x180)
        struct.pack_into('<H', b, 0x16c, 2)
        def string(p, text):
            raw = text.encode()
            struct.pack_into('<H', b, p, len(raw))
            b[p + 2:p + 3 + len(raw)] = raw + b'\0'
        for i, name in enumerate(('Mt_Cloth', 'Mt_Skin')):
            m, text, refs, tex = 0x180 + i * 0xb0, 0x400 + i * 0x40, 0x500 + i * 8, 0x600 + i * 0x40
            b[m:m + 4] = b'FMAT'
            struct.pack_into('<Q', b, m + 8, text)
            struct.pack_into('<Q', b, m + 0x20, refs)
            b[m + 0xa3] = 1
            struct.pack_into('<Q', b, refs, tex)
            string(text, name)
            string(tex, 'Shared_Cloth_Alb' if i == 0 else 'Skin_Alb')
        found = assets.clothing_textures(b, ('Mt_Cloth',))
        self.assertEqual(found, {'Shared_Cloth_Alb': {0x600}})
        before = bytes(b)
        assets.rename_string(b, 0x600, 'OCR_Tunic_00')
        self.assertEqual(len(b), len(before))
        self.assertEqual(b[0x640:], before[0x640:])
        self.assertEqual(assets.string(b, 0x600), 'OCR_Tunic_00')
        with self.assertRaises(ValueError):
            assets.clothing_textures(b'bad', ('Mt_Cloth',))

    def test_resource_sizes_add_alias_without_changing_original_or_named_entries(self):
        original = zlib.crc32(b'Tex/Shared_Cloth_Alb.bntx')
        named = b'named\0\0\0' + struct.pack('<I', 456)
        table = b'RESTBL' + struct.pack('<4I', 1, 8, 1, 1) + struct.pack('<II', original, 123) + named
        result = assets.add_sizes(table, {'Shared_Cloth_Alb': 'OCR_Tunic_00'})
        self.assertEqual(result[-len(named):], named)
        entries = dict(struct.unpack_from('<II', result, 22 + 8 * i) for i in range(2))
        self.assertEqual(entries[original], 123)
        self.assertEqual(entries[zlib.crc32(b'Tex/OCR_Tunic_00.bntx')], 123)
        with self.assertRaises(ValueError):
            assets.add_sizes(result, {'Shared_Cloth_Alb': 'OCR_Tunic_00'})

    def test_failed_generation_never_publishes_and_corruption_rebuilds(self):
        with tempfile.TemporaryDirectory() as temp:
            cache, key = Path(temp), 'a' * 32
            def fake_build(romfs, output, rgb, sources):
                output.mkdir()
                (output / 'clothes.zs').write_bytes(b'generated')
                return {'rgb': rgb}
            with patch.object(assets, 'cache_key', return_value=key), patch.object(assets, 'build', side_effect=fake_build) as generate:
                self.assertEqual(assets.cached_build('unused', cache, [3, 4, 5]), key)
                assets.cached_build('unused', cache, [3, 4, 5])
                self.assertEqual(generate.call_count, 1)
                (cache / key / 'clothes.zs').write_bytes(b'corrupt')
                assets.cached_build('unused', cache, [3, 4, 5])
                self.assertEqual(generate.call_count, 2)
                self.assertTrue(assets.valid_cache(cache / key, key))
            with patch.object(assets, 'cache_key', return_value='b' * 32), patch.object(assets, 'build', side_effect=ValueError('unsupported model')):
                with self.assertRaises(ValueError):
                    assets.cached_build('unused', cache, [3, 4, 5])
            self.assertFalse((cache / ('b' * 32)).exists())
            self.assertFalse(list(cache.glob('building-*')))


if __name__ == '__main__':
    unittest.main()
