"""3D model bins of Duke Nukem: Zero Hour (layout from the decomp's modelinfo.h / extract_assets.py).

A model bin = [CI4 textures][texture table: (s16 dimx, s16 dimy, s32 offset) per texture][commands][lights][vertices].
Each texture = 32-byte palette (16 RGBA5551, big endian) + 4-bit indices, rows of dimx.
`rows(tree)` reads the texture table bounds from the decomp C (ModelInfo.texture_info_off / cmd_off).

Dirty room: `facts(tree)` -> per bin: texture facts (size, 4x4 grid, 2-bit alpha) + the skeleton = the bin with every
texture byte zeroed (geometry, commands, lights, vertices: kept).  Clean room: `build(skel, facts)` repaints the textures.
"""
import os
import re
import struct

import numpy as np

from cleanroom.decomp import gen, spec
from games.dukezh import tiles


def rows(tree):
    """{bin name: (texture_info_off, cmd_off)} from src/code0/data/modelinfo.c."""
    src = open(os.path.join(tree, 'src/code0/data/modelinfo.c'), encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'ModelInfo \w+ = \{\s*\(s32\)models_(\w+)_bin,\s*NULL,\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+),', src):
        tex, cmd = int(m.group(4), 0), int(m.group(5), 0)
        if out.setdefault(m.group(1), (tex, cmd)) != (tex, cmd):
            raise SystemExit('model bin %s has two texture tables' % m.group(1))
    return out


def textures(data, tex, cmd):
    """[(w, h, start, end)] of a bin's textures."""
    ents = [struct.unpack_from('>hhi', data, o) for o in range(tex, cmd, 8)]
    out = []
    for n, (w, h, off) in enumerate(ents):
        end = ents[n + 1][2] if n + 1 < len(ents) else tex
        out.append((w, h, off, end))
    return out


def _pal(b):
    v = np.frombuffer(b[:32], '>u2').astype(np.int64)
    out = np.zeros((16, 4), np.uint8)
    for i, sh in enumerate((11, 6, 1)):
        out[:, i] = ((v >> sh) & 31) * 255 // 31
    out[:, 3] = (v & 1) * 255
    return out


def decode(blob, w):
    a = np.frombuffer(blob[32:], np.uint8)
    idx = np.empty(len(a) * 2, np.uint8)
    idx[0::2], idx[1::2] = a >> 4, a & 15
    h = len(idx) // w
    return _pal(blob)[idx[:w * h]].reshape(h, w, 4)


def facts(data, tex, cmd):
    """(texture facts list, skeleton bytes). Dirty room."""
    skel = bytearray(data)
    out = []
    for w, h, a, b in textures(data, tex, cmd):
        f = {'w': w, 'h': h, 'off': a, 'len': b - a}
        if w > 0 and b - a > 32 and (b - a - 32) * 2 >= w:
            rgba = decode(data[a:b], w)
            f['rows'] = rgba.shape[0]
            f['grid'] = spec.grid(rgba.astype(np.float32), 4)
            if (rgba[..., 3] < 250).any():
                f['alpha2'] = spec.alpha2(rgba[..., 3])
        skel[a:b] = bytes(b - a)
        out.append(f)
    return out, bytes(skel)


def paint(f, seed):
    w, h = f['w'], f['rows']
    rgba = gen.upsample_grid(f['grid'], 4, w, h)
    rgba[..., :3] *= gen.detail(seed, w, h)[..., None]
    rgba[..., 3] = gen.unpack_alpha2(f['alpha2'], w, h) if 'alpha2' in f else 255
    return np.clip(rgba, 0, 255)


def encode(rgba, length):
    """palette (big endian) + indices, cut/padded to `length`."""
    h, w = rgba.shape[:2]
    px = np.asarray(rgba, np.float32).reshape(-1, 4)
    clear = px[:, 3] < 128
    first = 1 if clear.any() else 0
    pal = np.zeros((16, 4), np.int64)
    idx = np.zeros(w * h, np.uint8)
    if (~clear).any():
        p, i = tiles.quantize(px[~clear, :3], 16 - first)
        pal[first:first + len(p), :3] = p
        pal[first:first + len(p), 3] = 255
        idx[~clear] = i + first
    v = ((pal[:, 0] >> 3) << 11) | ((pal[:, 1] >> 3) << 6) | ((pal[:, 2] >> 3) << 1) | (pal[:, 3] >= 128)
    if len(idx) % 2:
        idx = np.append(idx, 0)
    out = v.astype('>u2').tobytes() + ((idx[0::2] << 4) | idx[1::2]).astype(np.uint8).tobytes()
    return out[:length].ljust(length, b'\0')


def build(skel, fs, seed=0, drawn=None):
    """Bin bytes from the skeleton + texture facts. `drawn` = {texture index: rgba} replacements."""
    out = bytearray(skel)
    for n, f in enumerate(fs):
        if 'grid' not in f:
            continue
        rgba = drawn[n] if drawn and n in drawn else paint(f, gen.h32(seed, n))
        out[f['off']:f['off'] + f['len']] = encode(rgba, f['len'])
    return bytes(out)
