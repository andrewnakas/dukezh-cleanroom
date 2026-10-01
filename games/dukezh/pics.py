"""Picture packs ("files" 0-15, 28) of Duke Nukem: Zero Hour: EDL blobs holding CI8 images + 256-colour palettes.

The decomp's src/code0/data/E0640.c lists each pack's images: {texture, palette, texoff, paloff, width, height}
(palette = 0x200 bytes of big-endian RGBA5551).  Which table belongs to which file comes from the loader calls
(func_8007FD8C(table, file id)) in the decomp: FILE_TABLE below.

Dirty room: `facts()` -> per image: size, colour grid (16x16 for big pictures, 4x4 otherwise), 2-bit alpha; skeleton =
the unpacked file with all image and palette bytes zeroed.
Clean room: `build()` repaints the images, makes one fresh palette per palette slot, returns the unpacked file.
"""
import os
import re

import numpy as np

from cleanroom.decomp import gen, spec
from games.dukezh import tiles

# file id (index in D_800E0D18, see edl.c) -> table symbol in E0640.c
FILE_TABLE = {0: 'D_800DFA40', 1: 'D_800DFA40', 2: 'D_800DFA90', 3: 'D_800DFAB8', 4: 'D_800DFAE0', 5: 'D_800E0778',
              6: 'D_800E0454', 7: 'D_800E0454', 8: 'D_800E0454', 9: 'D_800E0454', 10: 'D_800E0454',
              11: 'D_800DFB08', 13: 'D_800E0404', 14: 'D_800E047C', 15: 'D_800E064C', 28: 'D_800E07DC'}


def file_names(tree):
    """bin names of D_800E0D18 in order (file id -> name), from edl.c."""
    src = open(os.path.join(tree, 'src/code0/edl.c'), encoding='utf-8').read()
    src = src[src.index('D_800E0D18[32]'):]
    return re.findall(r'\{ files_(\w+)_ROM_START', src[:src.index('};')])


def tables(tree, version='VERSION_US'):
    """{table symbol: [(texoff, paloff, w, h)]} from E0640.c (rows up to the -1 terminator)."""
    src = open(os.path.join(tree, 'src/code0/data/E0640.c'), encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'_E0640UnkStruct (\w+)\[[^\]]*\] = \{(.*?)\n\};', src, re.S):
        rows = []
        for r in re.finditer(r'\{ NULL, NULL, (\w+), (\w+), (\w+), (\w+) \}', m.group(2)):
            rows.append(tuple(int(x, 0) for x in r.groups()))
        out[m.group(1)] = rows
    return out


def _pal(b):
    v = np.frombuffer(b, '>u2').astype(np.int64)
    out = np.zeros((len(v), 4), np.uint8)
    for i, sh in enumerate((11, 6, 1)):
        out[:, i] = ((v >> sh) & 31) * 255 // 31
    out[:, 3] = (v & 1) * 255
    return out


def decode(d, row):
    t, p, w, h = row
    return _pal(d[p:p + 0x200])[np.frombuffer(d[t:t + w * h], np.uint8)].reshape(h, w, 4)


def facts(d, rows):
    """(image facts, skeleton). Dirty room."""
    skel = bytearray(d)
    out = []
    for t, p, w, h in rows:
        if t + w * h > len(d):
            raise SystemExit('picture row outside the file: %x+%dx%d > %x' % (t, w, h, len(d)))
        rgba = decode(d, (t, p, w, h))
        n = 16 if max(w, h) >= 128 else 4
        f = {'tex': t, 'pal': p, 'w': w, 'h': h, 'n': n, 'grid': spec.grid(rgba.astype(np.float32), n)}
        if (rgba[..., 3] < 250).any():
            f['alpha2'] = spec.alpha2(rgba[..., 3])
        out.append(f)
    for f in out:
        skel[f['tex']:f['tex'] + f['w'] * f['h']] = bytes(f['w'] * f['h'])
        skel[f['pal']:f['pal'] + 0x200] = bytes(0x200)
    return out, bytes(skel)


def paint(f, seed):
    w, h = f['w'], f['h']
    rgba = gen.upsample_grid(f['grid'], f['n'], w, h)
    rgba[..., :3] *= gen.detail(seed, w, h, 0.03 if f['n'] > 4 else 0.06, 8.0 if f['n'] > 4 else 4.0)[..., None]
    rgba[..., 3] = gen.unpack_alpha2(f['alpha2'], w, h) if 'alpha2' in f else 255
    return np.clip(rgba, 0, 255)


def build(skel, fs, seed=0, drawn=None):
    """Unpacked file from skeleton + facts. `drawn` = {image index: rgba (h, w, 4)}."""
    out = bytearray(skel)
    imgs = [np.asarray(drawn[n], np.float32) if drawn and n in drawn else paint(f, gen.h32(seed, n))
            for n, f in enumerate(fs)]
    for p in sorted({f['pal'] for f in fs}):
        group = [n for n, f in enumerate(fs) if f['pal'] == p]
        px = np.concatenate([imgs[n].reshape(-1, 4) for n in group])
        clear = px[:, 3] < 128
        first = 1 if clear.any() else 0
        pal = np.zeros((256, 4), np.int64)
        idx = np.zeros(len(px), np.uint8)
        if (~clear).any():
            # quantize on a 5-bit colour histogram (fast), then map
            q = (px[~clear, :3] // 8).astype(np.int32)
            u, inv = np.unique(q, axis=0, return_inverse=True)
            pc, pi = tiles.quantize(u * 8 + 4, 256 - first)
            pal[first:first + len(pc), :3] = pc
            pal[first:first + len(pc), 3] = 255
            idx[~clear] = pi[inv.ravel()] + first
        v = ((pal[:, 0] >> 3) << 11) | ((pal[:, 1] >> 3) << 6) | ((pal[:, 2] >> 3) << 1) | (pal[:, 3] >= 128)
        out[p:p + 0x200] = v.astype('>u2').tobytes()
        o = 0
        for n in group:
            f = fs[n]
            out[f['tex']:f['tex'] + f['w'] * f['h']] = idx[o:o + f['w'] * f['h']].tobytes()
            o += f['w'] * f['h']
    return bytes(out)


# ---------------------------------------------------------------- 3D menu objects (files 16-27)
# mesh file (kept geometry), texture file, palette file, uv file (kept), offset table symbol in edl.c (None = [0])
MESH_SETS = [(16, 19, 17, 18, 'D_800E0BE4'), (20, 23, 21, 22, 'D_800E0C18'), (24, 27, 25, 26, None)]


def mesh_offsets(tree, sym):
    if sym is None:
        return [0]
    src = open(os.path.join(tree, 'src/code0/edl.c'), encoding='utf-8').read()
    m = re.search(sym + r'\[\d+\] = \{(.*?)\};', src, re.S)
    return [int(x, 0) for x in re.findall(r'0x[0-9A-Fa-f]+', m.group(1))]


def mesh_textures(mesh, offsets, tex_len):
    """[(offset, w, h, palette offset, bits)] used by a mesh file (format: see func_80081E20 in 82480.c)."""
    import struct
    texs = set()
    for o in offsets:
        p = o
        n, = struct.unpack_from('>H', mesh, p)
        p += 2 + 6 * n
        faces, = struct.unpack_from('>H', mesh, p)
        p += 2
        i = 0
        while i < faces:
            t, w, h, pl, k = struct.unpack_from('>5H', mesh, p)
            p += 10
            texs.add((t * 8, w, h, pl))
            for _ in range(k):
                l, = struct.unpack_from('>I', mesh, p)
                p += 4 + ((4 if l & 2 else 8) if l & 1 else (3 if l & 2 else 6)) + 2
                i += 1
    ts = sorted(texs)
    out = []
    for t, w, h, pl in ts:
        nxt = min([x[0] for x in ts if x[0] > t] + [tex_len])
        out.append((t, w, h, pl, 8 if nxt - t >= w * h else 4))
    return out


def mesh_facts(tex, pal, texs):
    """Texture facts for one mesh set. Dirty room. The texture and palette files are regenerated whole."""
    pal_offs = sorted({x[3] for x in texs}) + [len(pal)]
    out = []
    for t, w, h, pl, bits in texs:
        ncol = min(256 if bits == 8 else 16, (pal_offs[pal_offs.index(pl) + 1] - pl) // 2)
        raw = np.frombuffer(tex[t:t + (w * h if bits == 8 else (w * h + 1) // 2)], np.uint8)
        if bits == 4:
            idx = np.empty(len(raw) * 2, np.uint8)
            idx[0::2], idx[1::2] = raw >> 4, raw & 15
            raw = idx[:w * h]
        rgba = _pal(pal[pl:pl + 2 * ncol])[np.minimum(raw, ncol - 1)].reshape(h, w, 4)
        f = {'tex': t, 'pal': pl, 'w': w, 'h': h, 'bits': bits, 'ncol': ncol, 'n': 4,
             'grid': spec.grid(rgba.astype(np.float32), 4)}
        if (rgba[..., 3] < 250).any():
            f['alpha2'] = spec.alpha2(rgba[..., 3])
        out.append(f)
    return out


def mesh_build(fs, tex_len, pal_len, seed=0, drawn=None):
    """(texture file, palette file) from facts."""
    tex, pal = bytearray(tex_len), bytearray(pal_len)
    imgs = [np.asarray(drawn[n], np.float32) if drawn and n in drawn else paint(f, gen.h32(seed, n))
            for n, f in enumerate(fs)]
    for p in sorted({f['pal'] for f in fs}):
        group = [n for n, f in enumerate(fs) if f['pal'] == p]
        ncol = min(fs[n]['ncol'] for n in group)
        px = np.concatenate([imgs[n].reshape(-1, 4) for n in group])
        clear = px[:, 3] < 128
        first = 1 if clear.any() else 0
        cols = np.zeros((ncol, 4), np.int64)
        idx = np.zeros(len(px), np.uint8)
        if (~clear).any():
            u, inv = np.unique((px[~clear, :3] // 8).astype(np.int32), axis=0, return_inverse=True)
            pc, pi = tiles.quantize(u * 8 + 4, ncol - first)
            cols[first:first + len(pc), :3] = pc
            cols[first:first + len(pc), 3] = 255
            idx[~clear] = pi[inv.ravel()] + first
        v = ((cols[:, 0] >> 3) << 11) | ((cols[:, 1] >> 3) << 6) | ((cols[:, 2] >> 3) << 1) | (cols[:, 3] >= 128)
        pal[p:p + 2 * ncol] = v.astype('>u2').tobytes()
        o = 0
        for n in group:
            f = fs[n]
            i = idx[o:o + f['w'] * f['h']]
            o += f['w'] * f['h']
            if f['bits'] == 4:
                if len(i) % 2:
                    i = np.append(i, 0)
                i = ((i[0::2] << 4) | i[1::2]).astype(np.uint8)
            tex[f['tex']:f['tex'] + len(i)] = i.tobytes()
    return bytes(tex), bytes(pal)
