"""Developer side: the launcher's flying fairy (assets/fairy.bin) from the user's GIF.

Each frame cropped to the fairy, scaled to SIZE, as light: its brightness becomes its opacity (premultiplied BGRA, what
UpdateLayeredWindow takes), so the glow and the pale wings blend softly over any background instead of showing the GIF's hard
edges. The frames are stored facing right, then the same mirrored (facing left).
    python make_fairy.py <fairy.gif> <out fairy.bin>
File: b'FAIRY1', u16 size, u16 frames per side, u16 frame ms, then frames*2 of size*size*4 bytes.
"""
import struct
import sys

from PIL import Image, ImageOps, ImageSequence

SIZE = 160


def main():
    src, out = sys.argv[1], sys.argv[2]
    im = Image.open(src)
    frames = [f.convert('RGBA') for f in ImageSequence.Iterator(im)]
    ms = im.info.get('duration', 140)
    box = None
    for f in frames:   # (one crop for all: the fairy does not jump between frames)
        b = f.getbbox()
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    side = max(box[2] - box[0], box[3] - box[1])
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    sq = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    data = bytearray(b'FAIRY1' + struct.pack('<HHH', SIZE, len(frames), ms))
    for mirror in (False, True):
        for f in frames:
            f = f.crop(sq).resize((SIZE, SIZE), Image.LANCZOS)
            if mirror:
                f = ImageOps.mirror(f)
            px = f.load()
            for y in range(SIZE):
                for x in range(SIZE):
                    r, g, b, a = px[x, y]
                    light = max(r, g, b) * a // 255   # (as light: as opaque as it is bright)
                    # premultiplied: colour times its opacity
                    data += bytes((b * light // 255, g * light // 255, r * light // 255, light))
    open(out, 'wb').write(data)
    print(out, len(data), 'bytes,', len(frames), 'frames a side,', ms, 'ms')


if __name__ == '__main__':
    main()
