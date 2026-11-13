"""Enemy and boss health x1..x5 in the player's own game folder: the MaxLife of every enemy actor pack multiplied.

Each enemy's pack (romfs/Pack/Actor/Enemy_*.pack.zs: a SARC compressed with the game's pack.zsdic) carries
Life/LifeParameters/<actor>.game__life__LifeParameters.bgyml, a BYML whose root holds MaxLife (an int: Gohma 21, Skulltula 2).
The int is changed in place, so the decompressed file keeps its size (the game sizes its buffers from a table of those); the pack
is compressed again with the same dictionary. Bosses are the packs named Enemy_DungeonBoss_*; every other Enemy_* is a monster.
The first change keeps the original pack in <game>/.ocarina_reborn_original_packs; x1 puts the original back. Everything stays in
the player's folder; nothing is uploaded.

    python enemy_health.py <game folder> <monster multiplier> <boss multiplier>
"""
import json
import shutil
import struct
import sys
from pathlib import Path

import zstandard as zstd

STATE = '.ocarina_reborn_enemy_health.json'
BACKUP = '.ocarina_reborn_original_packs'


def sarc_files(data):
    """{name: (start, end)} of a SARC's files, offsets into data"""
    if data[:4] != b'SARC':
        raise ValueError('not a SARC')
    data_off = struct.unpack_from('<I', data, 0xC)[0]
    count = struct.unpack_from('<H', data, 0x1A)[0]
    names = 0x20 + count * 16 + 8
    out = {}
    for i in range(count):
        _, attr, s, e = struct.unpack_from('<IIII', data, 0x20 + i * 16)
        at = names + (attr & 0xFFFFFF) * 4
        out[data[at:data.index(b'\0', at)].decode()] = (data_off + s, data_off + e)
    return out


def max_life_offset(b):
    """the file offset of the root dictionary's MaxLife int value in a BYML, or None"""
    if b[:2] != b'YB':
        return None
    keys_off, _, root = struct.unpack_from('<III', b, 4)
    if not root or b[root] != 0xC1:
        return None
    n = struct.unpack_from('<I', b, keys_off)[0] >> 8
    keys = []
    for i in range(n):
        s = struct.unpack_from('<I', b, keys_off + 4 + 4 * i)[0] + keys_off
        keys.append(b[s:b.index(b'\0', s)])
    entries = struct.unpack_from('<I', b, root)[0] >> 8
    for i in range(entries):
        e = root + 4 + 8 * i
        k = struct.unpack_from('<I', b, e)[0] & 0xFFFFFF
        if k < len(keys) and keys[k] == b'MaxLife' and b[e + 3] == 0xD1:
            return e + 4
    return None


def apply(game, monsters, bosses, progress=None):
    game = Path(game)
    actors = game / 'romfs' / 'Pack' / 'Actor'
    want = {'monsters': int(monsters), 'bosses': int(bosses)}
    state = game / STATE
    try:
        if json.loads(state.read_text()) == want:
            return 0
    except (OSError, ValueError):
        pass
    if want == {'monsters': 1, 'bosses': 1} and not (game / BACKUP).is_dir():
        state.write_text(json.dumps(want))
        return 0
    raw = zstd.ZstdDecompressor().decompress((game / 'romfs' / 'Pack' / 'ZsDic.pack.zs').read_bytes(), max_output_size=1 << 26)
    files = sarc_files(raw)
    s, e = files['pack.zsdic']
    zdict = zstd.ZstdCompressionDict(raw[s:e])
    unz, comp = zstd.ZstdDecompressor(dict_data=zdict), zstd.ZstdCompressor(level=6, dict_data=zdict)
    packs = sorted(p for p in actors.glob('Enemy_*.pack.zs') if '_Dictionary' not in p.name)
    backup = game / BACKUP
    backup.mkdir(exist_ok=True)
    changed = 0
    for i, pack in enumerate(packs):
        mult = want['bosses'] if 'DungeonBoss' in pack.name else want['monsters']
        orig = backup / pack.name
        if mult == 1:
            if orig.is_file():   # (back to the game's own file)
                shutil.copy2(orig, pack)
                changed += 1
        else:
            if not orig.is_file():
                shutil.copy2(pack, orig)
            data = bytearray(unz.decompress(orig.read_bytes(), max_output_size=1 << 28))
            hit = False
            for name, (fs, fe) in sarc_files(data).items():
                if '/LifeParameters/' not in '/' + name:
                    continue
                off = max_life_offset(bytes(data[fs:fe]))
                if off is None:
                    continue
                life = struct.unpack_from('<i', data, fs + off)[0]
                if life > 0:
                    struct.pack_into('<i', data, fs + off, min(life * mult, 0x7FFFFFFF))
                    hit = True
            if hit:
                pack.write_bytes(comp.compress(bytes(data)))
                changed += 1
        if progress and i % 20 == 0:
            progress(i / len(packs))
    state.write_text(json.dumps(want))
    return changed


def read_life(game, actor):
    """(for checks) MaxLife of one actor as the folder has it now"""
    game = Path(game)
    raw = zstd.ZstdDecompressor().decompress((game / 'romfs' / 'Pack' / 'ZsDic.pack.zs').read_bytes(), max_output_size=1 << 26)
    s, e = sarc_files(raw)['pack.zsdic']
    unz = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(raw[s:e]))
    data = unz.decompress((game / 'romfs' / 'Pack' / 'Actor' / f'{actor}.pack.zs').read_bytes(), max_output_size=1 << 28)
    for name, (fs, fe) in sarc_files(data).items():
        if '/LifeParameters/' in '/' + name:
            off = max_life_offset(data[fs:fe])
            if off is not None:
                return struct.unpack_from('<i', data, fs + off)[0]
    return None


if __name__ == '__main__':
    print('changed', apply(sys.argv[1], sys.argv[2], sys.argv[3]))
