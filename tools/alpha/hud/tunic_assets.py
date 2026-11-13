"""Make a private tunic texture overlay from the player's own RomFS.

No game data is distributed. Only Link's named clothing materials receive new
texture names: shared cloth on NPCs and scenery keeps the original textures.
The overlay is consumed by host/ocr_tunic.c after a restart, also without the
launcher. BFRES v10 layout reference: KillzXGaming/BfresLibrary (MIT).
BNTX/GOB layout follows Hookshot nx2/prompt_assets.py (GPL-3.0).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
import zlib

REVISION = 1
MODELS = {
    'Player_Adult.Player_Adult': ('Mt_Angin', 'Mt_Vest'),
    'Player_Child.Player_Child': ('Mt_Cloth', 'Mt_Vest'),
    'Player_Child_Op.Player_Child_Op': ('Mt_Cloth', 'Mt_Vest'),
    'Armor_Adult_Goron.Armor_Adult_Goron': ('Mt_Leather', 'Mt_Vest'),
    'Armor_Adult_Zora.Armor_Adult_Zora': ('Mt_Angin', 'Mt_Vest'),
}
ASTC = dict(zip(range(0x2D, 0x3B), [(4, 4), (5, 4), (5, 5), (6, 5), (6, 6), (8, 5), (8, 6),
                                  (8, 8), (10, 5), (10, 6), (10, 8), (10, 10), (12, 10), (12, 12)]))


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def ptr(b, o, length=1):
    p = struct.unpack_from('<Q', b, o)[0]
    if not p or p + length > len(b):
        raise ValueError('Resource pointer outside file')
    return p


def string(b, o):
    n = u16(b, o)
    if o + 2 + n >= len(b) or b[o + 2 + n] != 0:
        raise ValueError('Invalid resource string')
    return b[o + 2:o + 2 + n].decode('utf-8')


def rename_string(b, o, new):
    old = string(b, o)
    data = new.encode('ascii')
    if len(data) > len(old.encode('utf-8')):
        raise ValueError('Replacement name is too long')
    struct.pack_into('<H', b, o, len(data))
    b[o + 2:o + 3 + len(old)] = data + bytes(len(old) - len(data) + 1)


def clothing_textures(b, materials):
    """Albedo string offsets for explicitly selected materials in one model."""
    if b[:8] != b'FRES    ' or b[8:12] != b'\0\4\x0a\0':
        raise ValueError('Unsupported tunic model version')
    if u16(b, 0xDC) != 1:
        raise ValueError('Expected one model')
    model = ptr(b, 0x28, 0x78)
    if b[model:model + 4] != b'FMDL':
        raise ValueError('Missing model header')
    count = u16(b, model + 0x6C)
    mats = ptr(b, model + 0x38, count * 0xB0)
    found = {}
    for i in range(count):
        m = mats + i * 0xB0
        if b[m:m + 4] != b'FMAT':
            raise ValueError('Invalid material table')
        if string(b, ptr(b, m + 8, 3)) not in materials:
            continue
        n = b[m + 0xA3]
        textures = ptr(b, m + 0x20, n * 8)
        for t in range(n):
            offset = ptr(b, textures + t * 8, 3)
            name = string(b, offset)
            if name.endswith('_Alb'):
                found.setdefault(name, set()).add(offset)
    if not found:
        raise ValueError('No supported clothing material found')
    return found


def sarc(b):
    if b[:4] != b'SARC' or len(b) < 32:
        raise ValueError('Invalid dictionary archive')
    start, count = u32(b, 12), u16(b, 26)
    names = 0x20 + count * 16 + 8
    result = {}
    for i in range(count):
        _, flags, lo, hi = struct.unpack_from('<4I', b, 0x20 + 16 * i)
        p = names + (flags & 0xFFFFFF) * 4
        name = b[p:b.index(0, p)].decode('utf-8')
        if not 0 <= start + lo <= start + hi <= len(b):
            raise ValueError('Dictionary range outside archive')
        result[name] = b[start + lo:start + hi]
    return result


def gob_offset(x, y, gobs, pitch):
    a = (y // (8 * gobs)) * 512 * gobs * pitch + (x // 64) * 512 * gobs + (y % (8 * gobs) // 8) * 512
    return a + (((x & 63) >> 5) << 8 | ((y & 7) >> 2) << 7 | ((x & 31) >> 4) << 6 |
                ((y >> 1) & 1) << 5 | (y & 1) << 4 | (x & 15))


def recolor_image(im, rgb):
    """Keep luminance detail and alpha; selected RGB is the lit cloth's base."""
    from PIL import Image
    lum = im.convert('RGB').convert('L')
    histogram = lum.histogram(mask=im.getchannel('A').point(lambda x: 255 if x else 0))
    threshold, total = sum(histogram) * .95, 0
    white = 128
    for i, n in enumerate(histogram):
        total += n
        if total >= threshold:
            white = max(32, i)
            break
    channels = [lum.point([min(255, round(v * component / white)) for v in range(256)]) for component in rgb]
    return Image.merge('RGBA', (*channels, im.getchannel('A')))


def recolor_bc3(blocks, rgb):
    # BC3's alpha and interpolation indices remain exact; only its RGB565 endpoints change.
    result = bytearray(blocks)
    def channels(v):
        return ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
    levels = [round(sum(c * w for c, w in zip(channels(u16(blocks, p)), (.299, .587, .114))))
              for o in range(0, len(blocks), 16) for p in (o + 8, o + 10)]
    white = max(32, sorted(levels)[int((len(levels) - 1) * .95)])
    for j, p in enumerate(p for o in range(0, len(blocks), 16) for p in (o + 8, o + 10)):
        r, g, b = (min(255, round(c * levels[j] / white)) for c in rgb)
        struct.pack_into('<H', result, p, (r * 31 // 255) << 11 | (g * 63 // 255) << 5 | b * 31 // 255)
    return result


def recolor_texture(source, rgb, alias):
    import texture2ddecoder as decoder
    from PIL import Image
    b = bytearray(source)
    if b[:8] != b'BNTX\0\0\0\0' or b[0x20:0x24] != b'Ounc' or u32(b, 0x24) != 1:
        raise ValueError('Unsupported tunic texture container')
    p = ptr(b, ptr(b, 0x28, 8), 0x78)
    if b[p:p + 4] != b'BRTI':
        raise ValueError('Missing texture header')
    fmt = u32(b, p + 0x1C) >> 8
    if fmt != 0x1C and fmt not in ASTC:
        raise ValueError(f'Unsupported tunic texture format {fmt:#x}')
    if u32(b, p + 0x2C) != 1 or u32(b, p + 0x30) != 1:
        raise ValueError('Expected a 2D clothing texture')
    width, height = u32(b, p + 0x24), u32(b, p + 0x28)
    mips = u16(b, p + 0x16)
    if not 1 <= width <= 8192 or not 1 <= height <= 8192 or not 1 <= mips <= 14:
        raise ValueError('Invalid texture dimensions')
    pointers = ptr(b, p + 0x70, mips * 8)
    block_w, block_h = ASTC.get(fmt, (4, 4))
    base_gobs = 1 << (u32(b, p + 0x34) & 7)
    for level in range(mips):
        w, h = max(1, width >> level), max(1, height >> level)
        bw, bh = (w + block_w - 1) // block_w, (h + block_h - 1) // block_h
        gobs = min(base_gobs, 1 << max(0, ((bh + 7) // 8 - 1).bit_length()))
        pitch = (bw * 16 + 63) // 64
        data = ptr(b, pointers + 8 * level)
        offsets = [data + gob_offset(x * 16, y, gobs, pitch) for y in range(bh) for x in range(bw)]
        if any(o + 16 > len(b) for o in offsets):
            raise ValueError('Texture mip outside file')
        blocks = b''.join(b[o:o + 16] for o in offsets)
        if fmt == 0x1C:
            encoded = recolor_bc3(blocks, rgb)
        else:
            import astc_encoder as A
            im = Image.frombytes('RGBA', (w, h), decoder.decode_astc(blocks, w, h, block_w, block_h), 'raw', 'BGRA')
            im = recolor_image(im, rgb)
            profile = A.ASTCProfile.LDR_SRGB if (u32(b, p + 0x1C) & 255) == 6 else A.ASTCProfile.LDR
            ctx = A.ASTCContext(A.ASTCConfig(profile, block_w, block_h, 1, A.ASTCQualityPreset.FAST))
            encoded = ctx.compress(A.ASTCImage(A.ASTCType.U8, w, h, 1, im.tobytes()), A.ASTCSwizzle.from_str('RGBA'))
        if len(encoded) != len(blocks):
            raise ValueError('Texture encoder changed the block count')
        for i, o in enumerate(offsets):
            b[o:o + 16] = encoded[16 * i:16 * i + 16]
    rename_string(b, ptr(b, p + 0x60, 3), alias)
    return bytes(b)


def add_sizes(table, aliases):
    if table[:6] != b'RESTBL' or len(table) < 22:
        raise ValueError('Invalid resource size table')
    name_size, count, named = struct.unpack_from('<3I', table, 10)
    if len(table) != 22 + count * 8 + named * (name_size + 4):
        raise ValueError('Invalid resource size table length')
    entries = dict(struct.unpack_from('<II', table, 22 + 8 * i) for i in range(count))
    for original, alias in aliases.items():
        old, new = (zlib.crc32(('Tex/' + name + '.bntx').encode()) for name in (original, alias))
        if old not in entries or new in entries:
            raise ValueError('Missing source size or conflicting tunic resource name')
        entries[new] = entries[old]
    head = bytearray(table[:22])
    struct.pack_into('<I', head, 14, len(entries))
    return bytes(head) + b''.join(struct.pack('<II', *e) for e in sorted(entries.items())) + table[22 + count * 8:]


def resource_reader(romfs, sources):
    import zstandard as zstd
    romfs = Path(romfs)
    def source(rel):
        return Path(sources.get(rel.lower(), romfs / rel))
    raw = zstd.ZstdDecompressor().decompress(source('Pack/ZsDic.pack.zs').read_bytes(), max_output_size=1 << 26)
    dictionaries = {}
    for name, blob in sarc(raw).items():
        if name.endswith('.zsdic'):
            d = zstd.ZstdCompressionDict(blob)
            dictionaries[d.dict_id()] = d
    def read(rel):
        b = source(rel).read_bytes()
        return zstd.ZstdDecompressor(dict_data=dictionaries.get(zstd.get_frame_parameters(b).dict_id)).decompress(b, max_output_size=1 << 28)
    return source, read


def build(romfs, output, rgb, sources=None):
    """Build into an unpublished directory; caller activates only after success."""
    import zstandard as zstd
    romfs, output = Path(romfs), Path(output)
    rgb = tuple(int(v) for v in rgb)
    if len(rgb) != 3 or any(not 0 <= v <= 255 for v in rgb):
        raise ValueError('RGB must be three values from 0 to 255')
    source, read = resource_reader(romfs, sources or {})
    def write(rel, data):
        p = output / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(zstd.ZstdCompressor(level=3).compress(data))
    models, aliases = {}, {}
    for model, mats in MODELS.items():
        rel = 'Model/' + model + '.bfres.zs'
        if not source(rel).is_file() and '_Op.' in model:
            continue
        b = bytearray(read(rel))
        refs = clothing_textures(b, mats)
        for name, offsets in refs.items():
            if name not in aliases:
                aliases[name] = f'OCR_Tunic_{len(aliases):02d}'
            for offset in offsets:
                rename_string(b, offset, aliases[name])
        models[rel] = b
    for name, alias in aliases.items():
        print('Tunic: ' + name, flush=True)
        write('Tex/' + alias + '.bntx.zs', recolor_texture(read('Tex/' + name + '.bntx.zs'), rgb, alias))
    for rel, b in models.items():
        write(rel, b)
    tables = sorted((romfs / 'System/Resource').glob('ResourceSizeTable.*.rsizetable.zs'))
    if len(tables) != 1:
        raise ValueError('Expected one resource size table')
    rel = tables[0].relative_to(romfs).as_posix()
    write(rel, add_sizes(read(rel), aliases))
    return {'revision': REVISION, 'rgb': rgb, 'models': list(models), 'textures': aliases, 'size_table': rel}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def cache_key(romfs, rgb, sources):
    romfs = Path(romfs)
    source, read = resource_reader(romfs, sources)
    paths = ['Pack/ZsDic.pack.zs'] + ['Model/' + n + '.bfres.zs' for n in MODELS]
    textures = set()
    for model, materials in MODELS.items():
        rel = 'Model/' + model + '.bfres.zs'
        if not source(rel).is_file() and '_Op.' in model:
            continue
        textures.update(clothing_textures(read(rel), materials))
    paths += ['Tex/' + n + '.bntx.zs' for n in sorted(textures)]
    paths += [p.relative_to(romfs).as_posix() for p in (romfs / 'System/Resource').glob('*.rsizetable.zs')]
    h = hashlib.sha256(json.dumps([REVISION, list(rgb), digest(__file__)]).encode())
    for rel in sorted(paths):
        p = Path(sources.get(rel.lower(), romfs / rel))
        h.update(json.dumps([rel, str(p.resolve()), digest(p) if p.is_file() else None]).encode())
    # Only clothing dependencies, including textures selected by model mods. Large
    # scenery texture packs are not scanned at each start. Hashes catch same-size edits.
    return h.hexdigest()[:32]


def valid_cache(folder, key):
    try:
        m = json.loads((folder / 'tunic-manifest.json').read_text(encoding='utf-8'))
        if m.get('cache_key') != key or not m.get('files'):
            return False
        for rel, sha in m['files'].items():
            p = (folder / rel).resolve()
            if not p.is_relative_to(folder.resolve()) or len(str(p).encode('utf-8')) >= 260 or digest(p) != sha:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def cached_build(romfs, cache, rgb, sources=None):
    sources = sources or {}
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    key = cache_key(romfs, rgb, sources)
    target = cache / key
    if valid_cache(target, key):
        print('Tunic: cached color ready', flush=True)
        return key
    with tempfile.TemporaryDirectory(prefix='building-', dir=cache) as temp:
        folder = Path(temp) / 'ready'
        m = build(romfs, folder, rgb, sources)
        m['cache_key'] = key
        m['files'] = {p.relative_to(folder).as_posix(): digest(p) for p in folder.rglob('*.zs')}
        # Hookshot's mod index still uses MAX_PATH byte buffers. Fail before activation
        # instead of letting a truncated resource-size-table path crash the game.
        if any(len(str(target / rel).encode('utf-8')) >= 260 for rel in m['files']):
            raise ValueError('Game folder path is too long for a tunic overlay; use a shorter game folder')
        (folder / 'tunic-manifest.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
        if target.exists():
            # Keep an invalid earlier cache for diagnosis; never activate a partial one.
            target.rename(cache / ('invalid-' + uuid.uuid4().hex))
        folder.rename(target)
    return key


def ship_runtime(engine, out):
    """Carry the offline helper beside the game, including direct-exe launches."""
    engine, out = Path(engine), Path(out)
    target = out / '.ocarina_reborn_tunic_tools'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(engine / 'python', target / 'python', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'tests', 'test', 'idlelib', 'turtledemo'))
    shutil.copy2(__file__, target / 'tunic_assets.py')
    for name in ('LICENSE', 'NOTICE-OCARINA-REBORN.txt'):
        if (engine / name).is_file():
            shutil.copy2(engine / name, target / name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--romfs', required=True)
    parser.add_argument('--output')
    parser.add_argument('--cache')
    parser.add_argument('--mods-map')
    parser.add_argument('--ready')
    parser.add_argument('--rgb', type=int, nargs=3, required=True)
    args = parser.parse_args()
    sources = {}
    if args.mods_map:
        for line in Path(args.mods_map).read_text(encoding='utf-8').splitlines():
            rel, host = line.split('\t', 1)
            sources[rel.lower()] = host
    if args.cache and args.ready:
        key = cached_build(args.romfs, args.cache, args.rgb, sources)
        Path(args.ready).write_text(key, encoding='ascii')
    elif args.output:
        manifest = build(args.romfs, args.output, args.rgb, sources)
        (Path(args.output) / 'tunic-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    else:
        parser.error('Use --output or --cache with --ready')
