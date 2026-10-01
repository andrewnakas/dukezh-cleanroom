"""Build-engine tiles of Duke Nukem: Zero Hour (layout from the decomp's tools/scripts/extract_assets.py).

gTileInfo entry (0x1C, big endian): fileoff i32, ramaddr u32, picanm i32, sizex i16, sizey i16, filesize u16,
dimx u16, dimy u16, flags u8, pad, tileid u16, pad2.  Each tile is an EDL blob in the `tiles` segment.
Unpacked kinds:
  pal   32 bytes              16 RGBA5551 colours (little-endian words), a bare palette
  ci8   dimx*dimy bytes       8-bit indices, palette elsewhere (flags & 0x80)
  ci4   32 + dimx*dimy/2      own palette + 4-bit indices
  ci4x2 32 + dimx*dimy        own palette + 4-bit indices, stored height = 2*dimy
  ci4r  32 + (dimx&~15)*dimy/2   own palette + 4-bit indices in rows of dimx, cut short (HUD/weapon sprites)
  ci8 uses the game's 256-colour table D_01000008 (in the decomp's src/static/F6D70.c, big-endian RGBA5551).

Dirty room: `fact()` reduces a tile to the approved facts (kind, size, 4x4 colour grid, 2-bit alpha).
Clean room: `build()` paints a tile from those facts with a fresh 16-colour palette.
Checked on the US ROM: 1976 tiles = 1906 ci4, 38 ci4r, 26 pal, 5 ci8, 1 ci4x2.
"""
import struct

import numpy as np

from cleanroom.decomp import gen, spec

INFO = struct.Struct('>iIihhHHHBxHxx')
FIELDS = 'fileoff ramaddr picanm sizex sizey filesize dimx dimy flags tileid'.split()


def infos(table):
    return [dict(zip(FIELDS, INFO.unpack_from(table, o)), num=o // INFO.size)
            for o in range(0, len(table) - INFO.size + 1, INFO.size)]


def kind(info, n):
    px = info['dimx'] * info['dimy']
    if n == 32:
        return 'pal'
    if info['flags'] & 0x80 or px == n:
        return 'ci8'
    if px == n - 32:
        return 'ci4x2'
    if px // 2 == n - 32:
        return 'ci4'
    if ((info['dimx'] & ~15) * info['dimy']) // 2 == n - 32:
        return 'ci4r'
    return 'raw'


def stored(info, k, n=0):
    """(w, h) of the stored pixel block (n = unpacked length)."""
    if k == 'ci4r':                       # rows are dimx wide (autocorrelation on real data); the block is cut short
        return info['dimx'], (n - 32) * 2 // info['dimx']
    return info['dimx'], info['dimy'] * (2 if k == 'ci4x2' else 1)


def _pal_rgba(b):
    v = np.frombuffer(b[:32], '<u2').astype(np.int64)
    out = np.zeros((16, 4), np.uint8)
    for i, sh in enumerate((11, 6, 1)):
        out[:, i] = ((v >> sh) & 31) * 255 // 31
    out[:, 3] = (v & 1) * 255
    return out


def _pal_bytes(rgba):
    c = np.asarray(rgba, np.int64)
    v = ((c[:, 0] >> 3) << 11) | ((c[:, 1] >> 3) << 6) | ((c[:, 2] >> 3) << 1) | (c[:, 3] >= 128)
    return v.astype('<u2').tobytes()


CI4 = ('ci4', 'ci4x2', 'ci4r')


def decode(info, d, pal256=None):
    """(kind, rgba or None) for an unpacked tile."""
    k = kind(info, len(d))
    w, h = stored(info, k, len(d))
    if k == 'ci8' and pal256 is not None:
        return k, pal256[np.frombuffer(d[:w * h], np.uint8)].reshape(h, w, 4)
    if k not in CI4:
        return k, None
    a = np.frombuffer(d[32:32 + (w * h + 1) // 2], np.uint8)
    idx = np.empty(len(a) * 2, np.uint8)
    idx[0::2], idx[1::2] = a >> 4, a & 15
    idx = idx[:w * h]
    return k, _pal_rgba(d)[idx].reshape(h, w, 4)


def fact(info, d, pal256=None):
    """Approved facts only. Dirty room."""
    k, rgba = decode(info, d, pal256)
    w, h = stored(info, k, len(d))
    f = {'kind': k, 'len': len(d), 'w': w, 'h': h}
    if rgba is not None:
        f['grid'] = spec.grid(rgba.astype(np.float32), 4)
        if (rgba[..., 3] < 250).any():
            f['alpha2'] = spec.alpha2(rgba[..., 3])
    return f


def quantize(rgb, n):
    """Median cut to at most n colours -> (palette (m,3) uint8, index array)."""
    px = rgb.reshape(-1, 3).astype(np.int32)
    boxes = [np.arange(len(px))]
    while len(boxes) < n:
        spans = [np.ptp(px[b], 0).max() if len(b) > 1 else 0 for b in boxes]
        i = int(np.argmax(spans))
        if spans[i] == 0:
            break
        b = boxes.pop(i)
        ch = int(np.argmax(np.ptp(px[b], 0)))
        o = b[np.argsort(px[b, ch], kind='stable')]
        cut = len(o) // 2
        boxes += [o[:cut], o[cut:]]
    pal = np.array([px[b].mean(0) for b in boxes]).round().astype(np.uint8)
    idx = np.zeros(len(px), np.uint8)
    for i, b in enumerate(boxes):
        idx[b] = i
    return pal, idx


def paint(f, seed=0, amount=0.06):
    w, h = f['w'], f['h']
    rgba = gen.upsample_grid(f['grid'], 4, w, h)
    rgba[..., :3] *= gen.detail(seed, w, h, amount)[..., None]
    rgba[..., 3] = gen.unpack_alpha2(f['alpha2'], w, h) if 'alpha2' in f else 255
    return np.clip(rgba, 0, 255)


def build(f, seed=0, rgba=None, pal256=None, amount=0.06, colours=16, ramp=False):
    """Unpacked tile bytes from facts (or from a supplied drawn RGBA image of the stored size)."""
    w, h = f['w'], f['h']
    if rgba is None:
        rgba = paint(f, seed, amount)
    rgba = np.clip(np.asarray(rgba, np.float32), 0, 255)
    if f['kind'] == 'ci8':
        px = rgba.reshape(-1, 4)
        op = np.where(pal256[:, 3] > 127)[0]
        tr = np.where(pal256[:, 3] <= 127)[0]
        u, inv = np.unique((px[:, :3] // 8).astype(np.int32), axis=0, return_inverse=True)
        dist = ((u[:, None, :] * 8 + 4 - pal256[op][None, :, :3].astype(np.int32)) ** 2).sum(-1)
        idx = op[dist.argmin(1)][inv.ravel()]
        if len(tr):
            idx = np.where(px[:, 3] < 128, tr[0], idx)
        return idx.astype(np.uint8).tobytes()
    if f['kind'] not in CI4:
        raise ValueError('build: kind %s is not painted here' % f['kind'])
    clear = rgba[..., 3].ravel() < 128
    pal = np.zeros((16, 4), np.uint8)
    idx = np.zeros(w * h, np.uint8)
    first = 1 if clear.any() else 0            # entry 0 = transparent when the tile has holes
    solid = ~clear
    if ramp:                                   # grey ramp: index = brightness (font tiles are also drawn as I4)
        pal[:, :3] = (np.arange(16) * 17)[:, None]
        pal[:, 3] = 255
        pal[0, 3] = 0 if first else 255
        lv = max(2, colours)                   # fewer brightness levels pack smaller
        lum = np.rint(rgba.reshape(-1, 4)[:, :3].mean(1) / 255 * (lv - 1))
        lum = np.rint(lum * 15 / (lv - 1)).astype(np.uint8)
        idx = np.where(clear, 0, np.maximum(lum, first)).astype(np.uint8)
        unused = np.setdiff1d(np.arange(16), idx)
        pal[unused] = 0                        # unused entries stay zero: the palette then packs to almost nothing
    elif solid.any():
        p, i = quantize(rgba.reshape(-1, 4)[solid, :3], colours - first)
        pal[first:first + len(p), :3] = p
        pal[first:first + len(p), 3] = 255
        idx[solid] = i + first
    if len(idx) % 2:
        idx = np.append(idx, 0)
    body = ((idx[0::2] << 4) | idx[1::2]).astype(np.uint8).tobytes()
    out = _pal_bytes(pal) + body
    return out[:f['len']].ljust(f['len'], b'\0')

def pal256_from_c(path):
    """The game's 256-colour table from the decomp C source (u8 D_01000008[0x200], big-endian RGBA5551)."""
    import re
    src = open(path, encoding='utf-8').read()
    body = src[src.index('D_01000008[0x200]'):]
    body = body[body.index('{') + 1:body.index('};')]
    b = bytes(int(x, 0) for x in re.findall(r'0x[0-9A-Fa-f]+|\d+', body))[:0x200]
    v = np.frombuffer(b, '>u2').astype(np.int64)
    out = np.zeros((256, 4), np.uint8)
    for i, sh in enumerate((11, 6, 1)):
        out[:, i] = ((v >> sh) & 31) * 255 // 31
    out[:, 3] = (v & 1) * 255
    return out


if __name__ == '__main__':
    rng = np.random.default_rng(3)
    ok = True
    for k, (w, h) in (('ci4', (32, 32)), ('ci4x2', (64, 16)), ('ci4', (16, 64)), ('ci4r', (48, 20))):
        hh = h * (2 if k == 'ci4x2' else 1)
        if k == 'ci4r':
            w = w + 3
        pal = rng.integers(0, 256, (16, 4)).astype(np.uint8)
        pal[:, 3] = 255
        pal[0, 3] = 0
        d = _pal_bytes(pal) + rng.integers(0, 256, (w & ~15) * hh // 2).astype(np.uint8).tobytes()
        info = dict(dimx=w, dimy=h, flags=0)
        f = fact(info, d)
        out = build(f, seed=1)
        k2, img = decode(info, out)
        k0, src = decode(info, d)
        same_alpha = ((img[..., 3] > 127) == (src[..., 3] > 127)).mean()
        ok &= f['kind'] == k == k2 and len(out) == len(d) and same_alpha == 1.0
        print(k, w, h, 'len', len(out), 'alpha match %.2f' % same_alpha, 'colours', len(np.unique(img.reshape(-1, 4), axis=0)))
    print('tiles self-test', 'OK' if ok else 'FAILED')

