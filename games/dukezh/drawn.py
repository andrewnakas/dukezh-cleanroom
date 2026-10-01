"""Drawn replacements (clean room): re-typeset fonts and text. Nothing here reads retail pixels.

Picture fonts: file 11 (small font, 16x12 cells) and file 12 (big orange font, 8/16/24 x 18/20 cells).
Their character maps and advance widths are tables in the decomp C (src/code0/7FCE0.c): map[char - 0x20] = glyph index.
Glyphs are drawn left-aligned in the cell (the game advances by the width table).
"""
import os
import re

import numpy as np

from cleanroom.gfx import glyphs, strokefont

FONTS = {11: ('D_800E0994', 'D_800E09F4', 'small'), 12: ('D_800E0A54', 'D_800E0AB4', 'big')}


def _c_array(src, sym):
    b = src[src.index(sym + '['):]
    b = b[b.index('{') + 1:b.index('};')]
    b = re.sub(r'#if VERSION_(?:FR|PROTO)(.*?)#else(.*?)#endif', r'\2', b, flags=re.S)     # US branch
    return [int(x, 0) for x in re.findall(r'0x[0-9A-Fa-f]+|\b\d+\b', b)]


def font_maps(tree):
    """{file id: ({glyph index: char}, {char: advance}, style)} from the decomp's tables."""
    src = open(os.path.join(tree, 'src/code0/7FCE0.c'), encoding='utf-8').read()
    out = {}
    for fid, (cm, wd, style) in FONTS.items():
        m, w = _c_array(src, cm), _c_array(src, wd)
        inv, adv = {}, {}
        for c in range(96):               # prefer upper case / first use when several chars share a glyph
            if m[c] != 0xFF and m[c] not in inv:
                inv[m[c]] = chr(c + 0x20)
                adv[chr(c + 0x20)] = w[c] if w[c] < 64 else 0
        out[fid] = (inv, adv, style)
    return out


def _dilate(m, r=1):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            o = np.maximum(o, np.roll(np.roll(m, dy, 0), dx, 1))
    return o


def glyph(ch, w, h, adv, style):
    """rgba (h, w, 4): the character in the left `adv` pixels of the cell, dark outline, bright fill."""
    img = np.zeros((h, w, 4), np.float32)
    if strokefont.extent(ch) is None:
        return img
    gw = int(max(4, min(w, adv if adv else w)))
    m = np.zeros((h, w), np.float32)
    m[1:h - 1, :gw] = strokefont.render(ch, gw, h - 2, thickness=1.6 if style == 'big' else 1.15)[:, :gw]
    m = np.clip(m * 1.4, 0, 1)
    edge = _dilate(m)
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    if style == 'big':                    # orange, lighter at the top
        fill = np.stack([250 - 30 * g, 190 - 110 * g, 40 + 0 * g], -1)
    else:                                 # white, slightly grey at the bottom
        fill = np.stack([255 - 40 * g] * 3, -1)
    img[..., :3] = fill * m[..., None]
    img[..., 3] = np.where(np.maximum(m, edge) > 0.35, 255, 0)
    return img


def tile_chars():
    """{tile id: char} for the in-game font tiles (mappings from src/code0/1A7C0.c: drawDebugString,
    drawNumberString, drawString)."""
    m = {2822 + i: chr(33 + i) for i in range(94)}                 # debug font: tile = char + (2822 - '!')
    m.update({5682 + i: str(i) for i in range(10)})                # HUD numbers: tile = digit + (5682 - '0')
    m.update({6134: ':', 3951: '-'})
    m.update({6087 + i: chr(65 + i) for i in range(26)})           # message font
    m.update({6117 + i: str(i) for i in range(10)})
    m.update({6127: '.', 6128: ':', 6129: "'", 6130: '!', 6131: '?', 6132: ',', 6133: '"', 6135: '-', 6136: '+'})
    return m


def tile_glyph(ch, f):
    """Grey-ramp glyph for a font tile, placed in the bounding box of the tile's kept alpha outline (or the whole
    cell). Bright fill, dark rim; brightness is what counts (the game draws some of these as intensity)."""
    from cleanroom.decomp import gen
    w, h = f['w'], f['h']
    x0, y0, x1, y1 = 0, 0, w, h
    has_alpha = 'alpha2' in f
    if has_alpha:
        a = gen.unpack_alpha2(f['alpha2'], w, h) > 127
        ys, xs = np.where(a)
        if len(ys):
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bw, bh = max(5, x1 - x0), max(7, y1 - y0)
    x0, y0 = min(x0, w - bw), min(y0, h - bh)
    m = np.zeros((h, w), np.float32)
    if ch == '.' and has_alpha and bh <= 4:        # a dot keeps its own size and place
        m[y0:y0 + bh, x0:x0 + bw] = 1.0
    else:
        if not has_alpha:                 # opaque cell: leave a 1 px margin
            x0, y0, bw, bh = 1, 1, w - 2, h - 2
        th = 0.9 if bh <= 9 else max(1.0, bh * 0.1)
        m[y0:y0 + bh, x0:x0 + bw] = np.clip(strokefont.render(ch, bw, bh, thickness=th) * 1.3, 0, 1)
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = (60 + 195 * m)[..., None]
    img[..., 3] = np.where(_dilate(m) > 0.3, 255, 0) if has_alpha else 255
    if not has_alpha:
        img[..., :3] = (255 * m)[..., None]
    return img


def tile_overrides():
    """{tile bin name: callable(fact) -> rgba}. Tiles drawn here use a grey ramp palette (index = brightness)."""
    chars = tile_chars()
    return {'%04d' % t: (lambda f, c=c: tile_glyph(c, f)) for t, c in chars.items()}


def pic_overrides(tree, spec):
    """{file name: {image index: rgba}} for the picture files that hold fonts."""
    maps = font_maps(tree)
    out = {}
    for name, f in spec.items():
        if f.get('id') not in maps:
            continue
        inv, adv, style = maps[f['id']]
        out[name] = {n: glyph(inv[n], im['w'], im['h'], adv.get(inv[n], 0), style)
                     for n, im in enumerate(f['images']) if n in inv}
    return out
