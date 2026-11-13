"""Read-only amiibo selection. No downloads, keys, decrypted saves or tag writes.

Raw NTAG215 dumps: 532/540 bytes, or 572 with the reader's signature trailer.
The public model ID is at 0x54 in tag order (not amiitool's internal order).
Only a private copy is replaced. The host reads the same file for direct-exe use.
"""
import os
from pathlib import Path
import tempfile

FILENAME = 'ocarina_reborn_amiibo.bin'
SIZES = (532, 540, 572)


def validate(data):
    if len(data) not in SIZES:
        raise ValueError('Expected a raw amiibo .bin file (532, 540 or 572 bytes).')
    if (data[0] != 4 or data[3] != 0x88 ^ data[0] ^ data[1] ^ data[2]
            or data[8] != data[4] ^ data[5] ^ data[6] ^ data[7]
            # amiibo's capability container differs from a generic NTAG215.
            or data[12:16] not in (b'\xf1\x10\xff\xee', b'\xe1\x10\x3e\x00')
            or data[0x5b] != 2 or not any(data[0x54:0x5b])):
        raise ValueError('The file could not be recognized as a raw amiibo tag. Check that it is an amiibo .bin dump.')
    return data[0x54:0x5c].hex().upper()


def read(path):
    with Path(path).open('rb') as f:
        data = f.read(max(SIZES) + 1)
    validate(data)
    return data


def select(game, source):
    """Validate completely before atomically replacing the selected tag."""
    data = read(source)
    game = Path(game)
    if not game.is_dir():
        raise ValueError('Prepare the game first, then select an amiibo.')
    fd, temporary = tempfile.mkstemp(prefix='.amiibo-', suffix='.tmp', dir=game)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, game / FILENAME)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return validate(data)


def clear(game):
    (Path(game) / FILENAME).unlink(missing_ok=True)


def selected_id(game):
    try:
        return validate(read(Path(game) / FILENAME))
    except (OSError, ValueError):
        return None
