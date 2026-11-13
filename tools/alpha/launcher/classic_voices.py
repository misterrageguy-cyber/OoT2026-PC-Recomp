"""Import the player's own voice ZIP against their local game files.

Only the named gameplay whitelist below is changed. Original RomFS stays read-only;
each age is an ordinary, independently switchable RomFS mod. BARS/AMTA metadata and
all other BWAVs are preserved. Banks retain their original allocation size, so no
resource-size-table override (which would conflict with controller fonts) is needed.

Format references: https://epd.zeldamods.org/wiki/Bwav and
https://github.com/vgmstream/vgmstream/blob/master/src/meta/bwav.c
"""
import hashlib
import io
import json
import re
import struct
import tempfile
import wave
import zipfile
import zlib
from pathlib import Path

AGES = {'child': ('Child', 'YoungLink', 'Young Link'), 'adult': ('Adult', 'AdultLink', 'Adult Link')}
KEYS = tuple('classic_voice_' + age for age in AGES)
MARKER = 'classic-voices.json'
FORMAT = 1
# Fixed, stable second-order predictors; each 14-sample frame selects its best fit.
COEFS = ((0, 0), (2048, 0), (3072, -1024), (3584, -1536),
         (3840, -1792), (4096, -2048), (1024, 0), (1024, 1024))
RULES = (
    (r'(?:Big)?SwordAttack_[SM]', ('Attack1', 'Attack2', 'Attack3', 'Attack4')),
    (r'(?:Big)?SwordAttack_B|(?:BS_|H_)?JumpAttack|RotaryCut_[BS]|Hammer', ('StrongAttack1', 'StrongAttack2')),
    (r'Damage_[SMB]|RollAttackDamage_[SB]|FireDamage_[SL]|ElectricDamage_[SL]|PoisonDamage|IceDamage|AntlionDamage|LavaDamage|LavaSwallowedDamage', ('Hurt1', 'Hurt2', 'Hurt3')),
    (r'Jump_[SB]|BackFlip|SideStep|RollAttack|GrabJump|JumpCliffs', ('Jump1', 'Jump2')),
    (r'FallingScream|Death', ('Scream1', 'Scream2')),
    (r'LandingDamage', ('FallDown1', 'FallDown2', 'FallDown3')),
    (r'Climb|ClimbSt|ClimbJump|ReachingTop', ('LedgeClimb1', 'LedgeClimb2')),
    (r'GrabFall|FallSuddenly00|FallSuddenly01', ('LedgeFall1', 'LedgeFall2')),
    (r'Push|lifting|liftingImpossible', ('Push1', 'Push2')),
    (r'HeavyBbreathing', ('Huff1', 'Huff2')),
    (r'DinsFire_Charge|DinsFire_Shoot|DinsFire_01|DinsFire_02', ('DinsFire',)),
    (r'ThrowingBom|ThrowingNuts|Boomerang|BoomerangC|HookShot', ('Attack1', 'Attack2', 'Attack3', 'Attack4')),
    (r'BottleDrink', ('Gulp',)),
    (r'BottleDrinkEd|Emerge', ('Gasp1', 'Gasp2')),
)


def source_for(name, age):
    prefix = 'Vo_Pl' + AGES[age][0] + '_'
    if not name.startswith(prefix):
        return None
    action = name[len(prefix):]
    # Full matches deliberately exclude Dm_, Npc_, Wait_ and *_For_Demo_*.
    for pattern, clips in RULES:
        match = re.fullmatch('(?:' + pattern + r')(?:_(\d+))?(?:_alt(?:_\d+)?)?', action)
        if match:
            return clips[(int(match[1] or 1) - 1) % len(clips)]
    return None


def read_pack(path, age):
    prefix = 'OOT_' + AGES[age][1] + '_'
    clips = {}
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 512 or sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError('Voice ZIP is too large (maximum 64 MB / 512 files).')
        for info in archive.infolist():
            # Read bytes directly: archive paths are never extracted to disk.
            name = info.filename.replace('\\', '/').rsplit('/', 1)[-1]
            if not name.startswith(prefix) or not name.lower().endswith('.wav'):
                continue
            key = name[len(prefix):-4]
            if key in clips:
                raise ValueError('Duplicate voice: ' + name)
            if info.file_size > 4 * 1024 * 1024:
                raise ValueError('Voice clip is too large: ' + name)
            with wave.open(io.BytesIO(archive.read(info)), 'rb') as wav:
                rate, count = wav.getframerate(), wav.getnframes()
                if (wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (1, 2, 'NONE'):
                    raise ValueError('Expected mono PCM16 WAV: ' + name)
                if not 8000 <= rate <= 48000 or not 0 < count <= rate * 15:
                    raise ValueError('Unsupported sample rate or length: ' + name)
                pcm = wav.readframes(count)
                if len(pcm) != count * 2:
                    raise ValueError('Truncated WAV: ' + name)
                clips[key] = (rate, struct.unpack('<%dh' % count, pcm))
    required = {'Attack1', 'Attack2', 'Attack3', 'Attack4', 'Hurt1', 'Hurt2', 'Hurt3', 'Jump1', 'Jump2'}
    if not required <= clips.keys():
        raise ValueError('Incomplete or wrong ZIP. Expected ' + prefix + 'Attack1.wav, Hurt1.wav, Jump1.wav, ...')
    return clips


def encode_dsp(samples):
    """Nintendo DSP ADPCM, 14 samples / 8 bytes, with reconstructed history feedback."""
    result = bytearray()
    h1 = h2 = 0
    for base in range(0, len(samples), 14):
        block = list(samples[base:base + 14])
        block += [0] * (14 - len(block))
        best = None
        for predictor, (a, b) in enumerate(COEFS):
            x, y, peak = h1, h2, 0
            for sample in block:
                peak = max(peak, abs(sample - ((a * x + b * y + 1024) >> 11)))
                y, x = x, sample
            start = min(12, max(0, (max(1, peak) - 1).bit_length() - 3))
            for scale in range(max(0, start - 1), min(12, start + 1) + 1):
                x, y, error, nibbles = h1, h2, 0, []
                step = 1 << scale
                for sample in block:
                    estimate = (a * x + b * y + 1024) >> 11
                    delta = sample - estimate
                    q = (delta + step // 2) // step
                    q = max(-8, min(7, q))
                    decoded = max(-32768, min(32767, estimate + q * step))
                    error += (sample - decoded) ** 2
                    y, x = x, decoded
                    nibbles.append(q & 15)
                if best is None or error < best[0]:
                    best = (error, predictor, scale, nibbles, x, y)
        _, predictor, scale, nibbles, h1, h2 = best
        result.append((predictor << 4) | scale)
        result.extend((nibbles[i] << 4) | nibbles[i + 1] for i in range(0, 14, 2))
    return bytes(result)


def bwav(rate, count, encoded, prefetch=False):
    cached = min(count, 14336) if prefetch else count
    header = bytearray(128)
    struct.pack_into('<4sHHIHHHHIII', header, 0, b'BWAV', 0xFEFF, 1,
                     zlib.crc32(encoded), int(prefetch), 1, 1, 2, rate, count, cached)
    struct.pack_into('<16h', header, 0x20, *(c for pair in COEFS for c in pair))
    struct.pack_into('<IIHHiIHHHH', header, 0x40, 128, 128, 1, 0, -1, 0, encoded[0], 0, 0, 0)
    return bytes(header) + encoded[:((cached + 13) // 14) * 8]


def bank_entries(data):
    """Read this game's BARS 1.2 / AMTA 5 with bounds and CRC validation."""
    if len(data) < 16 or data[:4] != b'BARS' or struct.unpack_from('<I', data, 4)[0] != len(data):
        raise ValueError('Invalid BARS bank.')
    if data[8:12] != b'\xff\xfe\x02\x01':
        raise ValueError('Unsupported BARS version.')
    count = struct.unpack_from('<I', data, 12)[0]
    if not count or 16 + count * 12 > len(data):
        raise ValueError('Invalid BARS table.')
    entries = []
    for i in range(count):
        field = 16 + 4 * count + 8 * i
        meta, audio = struct.unpack_from('<II', data, field)
        if meta + 0x28 > len(data) or data[meta:meta + 8] != b'AMTA\xff\xfe\x00\x05':
            raise ValueError('Unsupported AMTA metadata.')
        end = meta + struct.unpack_from('<I', data, meta + 8)[0]
        namepos = meta + 0x24 + struct.unpack_from('<I', data, meta + 0x24)[0]
        if end > len(data) or not meta + 0x28 <= namepos < end:
            raise ValueError('Invalid AMTA name offset.')
        name = data[namepos:data.index(0, namepos, end)].decode('ascii')
        if zlib.crc32(name.encode('ascii')) != struct.unpack_from('<I', data, 16 + i * 4)[0]:
            raise ValueError('BARS name hash mismatch.')
        if audio != 0xFFFFFFFF and (audio + 128 > len(data) or data[audio:audio + 4] != b'BWAV'):
            raise ValueError('Invalid BWAV offset.')
        entries.append(dict(name=name, field=field, meta_end=end, audio=audio))
    return entries


def convert_bank(data, age, clips, stream_root, progress=lambda text: None):
    entries = bank_entries(data)
    offsets = sorted({e['audio'] for e in entries if e['audio'] != 0xFFFFFFFF})
    if not offsets or max(e['meta_end'] for e in entries) > offsets[0]:
        raise ValueError('Unsupported interleaved BARS layout.')
    replacements, streams, mapping, encoded_cache = {}, {}, {}, {}
    aliases = {}
    for entry in entries:
        aliases.setdefault(entry['audio'], []).append(entry['name'])
    for entry in entries:
        name, offset = entry['name'], entry['audio']
        clip = source_for(name, age)
        if not clip or clip not in clips or offset == 0xFFFFFFFF:
            continue
        if len(aliases[offset]) > 1:
            # Keep shared BWAVs shared, and give all their stream files the same
            # replacement. A cutscene/NPC alias disqualifies the entire group.
            choices = [source_for(n, age) for n in sorted(aliases[offset])]
            if any(c is None or c not in clips for c in choices):
                continue
            clip = choices[0]
        if struct.unpack_from('<H', data, offset + 14)[0] != 1:
            raise ValueError('Expected a mono voice: ' + name)
        flags = struct.unpack_from('<H', data, offset + 12)[0]
        if flags not in (0, 1) or struct.unpack_from('<i', data, offset + 0x4c)[0] != -1:
            raise ValueError('Unsupported looping voice: ' + name)
        stream = Path(stream_root) / (name + '.bwav')
        if flags and not stream.is_file():
            raise ValueError('Missing voice stream: ' + name)
        if clip not in encoded_cache:
            progress('Converting ' + clip)
            rate, samples = clips[clip]
            encoded_cache[clip] = (rate, len(samples), encode_dsp(samples))
        rate, count, encoded = encoded_cache[clip]
        replacements[offset] = bwav(rate, count, encoded, bool(flags))
        if stream.is_file():
            streams[name + '.bwav'] = bwav(rate, count, encoded)
        mapping[name] = clip
    if not mapping:
        raise ValueError('No supported gameplay voices in this bank.')
    rebuilt = bytearray(data[:offsets[0]])
    relocated = {}
    for i, offset in enumerate(offsets):
        rebuilt.extend(b'\0' * (-len(rebuilt) % 64))
        relocated[offset] = len(rebuilt)
        end = offsets[i + 1] if i + 1 < len(offsets) else len(data)
        rebuilt.extend(replacements.get(offset, data[offset:end]))
    if len(rebuilt) > len(data):
        raise ValueError('The imported voices exceed this bank\'s allocation. Original files were not changed.')
    rebuilt.extend(b'\0' * (len(data) - len(rebuilt)))
    for entry in entries:
        if entry['audio'] != 0xFFFFFFFF:
            struct.pack_into('<I', rebuilt, entry['field'] + 4, relocated[entry['audio']])
    bank_entries(rebuilt)
    return bytes(rebuilt), streams, mapping


def paths(game, age):
    name = 'Ocarina Reborn - Classic ' + AGES[age][2]
    root = Path(game) / 'mods'
    return root / name, root / ('_' + name)


def status(game, age):
    on, off = paths(game, age)
    if on.exists() and off.exists():
        raise ValueError('Duplicate classic voice folders: ' + AGES[age][2])
    path = on if on.exists() else off
    if not path.exists():
        return dict(installed=False, enabled=False, count=0)
    manifest = json.loads((path / MARKER).read_text(encoding='utf-8'))
    if manifest.get('format') != FORMAT or manifest.get('age') != age:
        raise ValueError('Unrecognized classic voice mod: ' + str(path))
    return dict(installed=True, enabled=path == on, count=len(manifest['mapping']))


def set_enabled(game, age, enabled):
    current = status(game, age)
    if enabled and not current['installed']:
        raise ValueError('Select Classic (N64) for ' + AGES[age][2] + ' first to prepare the voice.')
    if current['installed'] and current['enabled'] != bool(enabled):
        on, off = paths(game, age)
        (off if enabled else on).rename(on if enabled else off)


def validate_active(game):
    """Fail before launching if a game-data update made an active bank obsolete."""
    for age in AGES:
        current = status(game, age)
        if current['enabled']:
            manifest = json.loads((paths(game, age)[0] / MARKER).read_text(encoding='utf-8'))
            original = Path(game) / 'romfs' / manifest['bank']
            if hashlib.sha256(original.read_bytes()).hexdigest() != manifest['original_sha256']:
                raise ValueError('Game audio changed. Select Default, then Classic (N64) again for ' + AGES[age][2] + '.')


def prepare(game, age, zip_path):
    """Prepare once on selection; reuse a matching bank on subsequent selections."""
    pack = Path(zip_path)
    if not pack.is_file():
        raise ValueError('Select your own voice ZIP. Voice recordings are not included or downloaded.')
    current = status(game, age)
    if current['installed']:
        path = paths(game, age)[0 if current['enabled'] else 1]
        manifest = json.loads((path / MARKER).read_text(encoding='utf-8'))
        original = Path(game) / 'romfs' / manifest['bank']
        if (manifest.get('pack_sha256') == hashlib.sha256(pack.read_bytes()).hexdigest()
                and manifest['original_sha256'] == hashlib.sha256(original.read_bytes()).hexdigest()):
            return current['count']
    return import_pack(game, age, pack)


def import_pack(game, age, zip_path, progress=lambda text: None):
    import zstandard
    game = Path(game)
    current = status(game, age)
    clips = read_pack(zip_path, age)
    relative = 'Sound/Resource/Player_' + AGES[age][0] + '.bars.zs'
    original = (game / 'romfs' / relative).read_bytes()
    data = zstandard.ZstdDecompressor().decompress(original, max_output_size=128 * 1024 * 1024)
    converted, streams, mapping = convert_bank(data, age, clips, game / 'romfs/Sound/Resource/Stream', progress)
    manifest = dict(format=FORMAT, age=age, bank=relative, original_sha256=hashlib.sha256(original).hexdigest(),
                    mapping=mapping, imported_zip=Path(zip_path).name,
                    pack_sha256=hashlib.sha256(Path(zip_path).read_bytes()).hexdigest())
    on, off = paths(game, age)
    root = on.parent
    root.mkdir(parents=True, exist_ok=True)
    # Staging/backups begin with '_' so the game's loader never indexes half an import.
    with tempfile.TemporaryDirectory(prefix='_voice-import-', dir=root) as tmp:
        tmp = Path(tmp)
        prepared = tmp / 'ready'
        bank = prepared / 'romfs' / relative
        bank.parent.mkdir(parents=True)
        bank.write_bytes(zstandard.ZstdCompressor(level=6).compress(converted))
        stream_dir = bank.parent / 'Stream'
        stream_dir.mkdir()
        for name, payload in streams.items():
            (stream_dir / name).write_bytes(payload)
        (prepared / MARKER).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        target = on if current['enabled'] else off
        backup = tmp / 'previous'
        if target.exists():
            target.rename(backup)
        try:
            prepared.rename(target)
        except BaseException:
            if backup.exists():
                backup.rename(target)
            raise
    return len(mapping)
