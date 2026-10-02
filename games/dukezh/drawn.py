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
    m[1:h - 1, :gw] = strokefont.render(ch, gw, h - 2, thickness=1.6 if style == 'big' else 0.9)[:, :gw]
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


def small_chars():
    """{tile id: (char, advance)} for the small terminal font (drawString2 in 1A7C0.c). The cells are 16x16 with the
    glyph in the bottom-left corner; the game advances 6 px (7 for M and W, 3 for I, 1, : and ')."""
    m = {3856 + i: str(i) for i in range(10)}
    m.update({3866 + i: chr(65 + i) for i in range(26)})
    m.update({3896: '.', 3895: ':', 3894: ',', 3893: ')', 3892: '(', 3982: "'"})
    return {t: (c, 7 if c in 'MW' else 3 if c in "I1:'" else 6) for t, c in m.items()}


def small_glyph(ch, adv, f):
    w, h = f['w'], f['h']
    bw, bh, y0 = adv - 1, 7, h - 8
    m = np.zeros((h, w), np.float32)
    if ch in ".,:'":
        if ch in '.,:':
            m[y0 + bh - 2:y0 + bh, 0:2] = 1
        if ch == ':':
            m[y0 + 1:y0 + 3, 0:2] = 1
        if ch == ',':
            m[y0 + bh, 0] = 1
        if ch == "'":
            m[y0:y0 + 3, 0:2] = 1
    else:
        m[y0:y0 + bh, 0:bw] = np.clip(strokefont.render(ch, bw, bh, thickness=0.7) * 1.6, 0, 1)
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = (255 * m)[..., None]
    img[..., 3] = 255
    return img


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


def health_icon(f):
    """HUD health icon: a red cross on a pale square (grey ramp is not used: see generate, colour tile)."""
    w, h = f['w'], f['h']
    yy, xx = np.mgrid[0:h, 0:w]
    u, v = (xx + 0.5) / w - 0.5, (yy + 0.5) / h - 0.5
    img = np.zeros((h, w, 4), np.float32)
    box = (abs(u) < 0.44) & (abs(v) < 0.44)
    img[box] = (235, 235, 235, 255)
    img[box & ((abs(u) > 0.38) | (abs(v) > 0.38))] = (120, 120, 125, 255)
    cross = ((abs(u) < 0.11) & (abs(v) < 0.30)) | ((abs(v) < 0.11) & (abs(u) < 0.30))
    img[cross] = (215, 25, 25, 255)
    return img


def bar_graph(f):
    """Cutscene terminal: a small bar chart on a base line (drawn as intensity)."""
    w, h = f['w'], f['h']
    m = np.zeros((h, w), np.float32)
    x0, x1, y1 = int(w * 0.12), int(w * 0.88), int(h * 0.86)
    m[int(h * 0.14):y1, x0:x0 + 2] = 1
    m[y1 - 2:y1, x0:x1] = 1
    bw = (x1 - x0 - 6) // 5
    for i, k in enumerate((0.75, 0.45, 0.6, 0.3, 0.5)):
        bx = x0 + 5 + i * bw
        m[int(y1 - 4 - k * h * 0.7):y1 - 4, bx:bx + bw - 2] = 1
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = (255 * m)[..., None]
    img[..., 3] = 255
    return img


COLOUR_TILES = {'5692'}


def tile_overrides():
    """{tile bin name: callable(fact) -> rgba}. Tiles drawn here use a grey ramp palette (index = brightness)."""
    chars = tile_chars()
    out = {'%04d' % t: (lambda f, c=c: tile_glyph(c, f)) for t, c in chars.items()}
    out.update({'%04d' % t: (lambda f, c=c, a=a: small_glyph(c, a, f)) for t, (c, a) in small_chars().items()})
    out['5692'] = health_icon
    out['3964'] = bar_graph
    return out


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


# ---------------------------------------------------------------- pictures with lettering (logos, title words, clock)
def _line(text, h, w_max, thickness, aspect=0.9):
    """Mask (h, <= w_max) of one line of text, squeezed horizontally when too wide."""
    m = strokefont.render_line(text, h, aspect=aspect, thickness=thickness)
    if m.shape[1] > w_max:
        from PIL import Image
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((w_max, h), Image.BILINEAR), np.float32) / 255
    return m


def _put(img, text, cx, cy, h, top, bottom, w_max=None, thickness=None, rim=(0, 0, 0), shadow=None):
    """Draw a centred line of text with a vertical gradient fill (top -> bottom), dark rim, optional drop shadow."""
    H, W = img.shape[:2]
    m = _line(text, h, int(w_max or W - 8), thickness or max(1.2, h * 0.13))
    x0, y0 = int(cx - m.shape[1] / 2), int(cy - h / 2)
    full = np.zeros((H, W), np.float32)
    full[y0:y0 + h, x0:x0 + m.shape[1]] = m
    g = np.clip((np.arange(H) - y0) / max(1, h - 1), 0, 1)[:, None, None]
    fill = np.asarray(top, np.float32) * (1 - g) + np.asarray(bottom, np.float32) * g
    if shadow is not None:
        s = np.roll(np.roll(_dilate(full, 1), max(2, h // 10), 0), max(2, h // 10), 1)[..., None]
        img[..., :3] = img[..., :3] * (1 - s) + np.asarray(shadow, np.float32) * s
        img[..., 3] = np.maximum(img[..., 3], 255 * s[..., 0])
    r = _dilate(full, 1)[..., None]
    img[..., :3] = img[..., :3] * (1 - r) + np.asarray(rim, np.float32) * r
    img[..., :3] = img[..., :3] * (1 - full[..., None]) + fill * full[..., None]
    img[..., 3] = np.maximum(img[..., 3], 255 * (r[..., 0] > 0.3))
    return img


def _blank(im, opaque=True):
    img = np.zeros((im['h'], im['w'], 4), np.float32)
    img[..., 3] = 255 if opaque else 0
    return img


def _clock(im, base):
    """Menu background: a riveted clock face with roman numerals and a trefoil hub, over the painted metal."""
    h, w = im['h'], im['w']
    img = base.copy()
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = (xx - w / 2) / (0.30 * w), (yy - h / 2) / (0.33 * h)
    r, a = np.hypot(u, v), np.arctan2(v, u)

    def shade(mask, k):
        img[..., :3] = np.clip(img[..., :3] * (1 + k * mask[..., None]), 0, 255)
    shade(((r > 0.96) & (r < 1.0)).astype(np.float32), -0.55)          # outer ring groove
    shade(((r > 0.50) & (r < 0.53)).astype(np.float32), -0.5)          # inner ring
    blades = (r > 0.14) & (r < 0.46) & (np.cos(3 * (a + np.pi / 2)) > 0.5)
    shade(blades.astype(np.float32), -0.45)
    shade((r < 0.08).astype(np.float32), -0.45)
    for ang in range(12):                                              # hour ticks
        t = ang * np.pi / 6
        d = np.hypot(u - 0.6 * np.cos(t), v - 0.6 * np.sin(t))
        shade((d < 0.025).astype(np.float32), -0.5)
    dark, lite = img[..., :3].mean() * 0.35, img[..., :3].mean() * 0.5
    for text, cx, cy in (('XII', 0.5, 0.26), ('VI', 0.5, 0.74), ('IX', 0.285, 0.5), ('III', 0.715, 0.5)):
        _put(img, text, cx * w, cy * h, int(h * 0.07), (lite,) * 3, (dark,) * 3, w_max=int(w * 0.10),
             rim=(dark * 0.4,) * 3)
    for sx in (0.1, 0.9):                                              # corner screws
        for sy in (0.07, 0.93):
            d = np.hypot((xx - sx * w) / (0.022 * w), (yy - sy * h) / (0.029 * h))
            shade((d < 1).astype(np.float32), -0.4)
            shade(((d < 1) & (np.abs((xx - sx * w) / w - (yy - sy * h) / h) < 0.006)).astype(np.float32), -0.6)
    return img


def picture_overrides(spec, paint):
    """{file name: {image index: rgba}} for pictures that carry lettering. `paint(f, n)` gives the painted base."""
    byid = {f.get('id'): (name, f) for name, f in spec.items()}
    out = {}
    steel = ((225, 225, 215), (95, 92, 85))
    if 5 in byid:                                   # title words (drawn under the 3D "DUKE NUKEM" letters)
        name, f = byid[5]
        d = {}
        for n, word in ((0, 'ZER:0'), (1, 'H:0UR')):
            im = f['images'][n]
            d[n] = _put(_blank(im, False), word, im['w'] / 2, im['h'] / 2, int(im['h'] * 0.8), *steel,
                        w_max=im['w'] - 6, thickness=im['h'] * 0.085, rim=(30, 28, 25))
        out[name] = d
    if 13 in byid:                                  # company cards, re-typeset (plain lettering, our own layout)
        name, f = byid[13]
        ims = f['images']
        a = _blank(ims[0])
        _put(a, 'GT INTERACTIVE', 160, 112, 30, (220, 220, 220), (120, 120, 125), w_max=270)
        _put(a, 'SOFTWARE', 160, 150, 22, (190, 190, 190), (110, 110, 115), w_max=160)
        b = _blank(ims[1])
        _put(b, '3D', 160, 80, 56, (255, 190, 70), (200, 100, 20), shadow=(40, 60, 150), thickness=7)
        _put(b, 'REALMS', 160, 150, 64, (255, 180, 60), (190, 90, 15), w_max=280, shadow=(40, 60, 150), thickness=7)
        c = _blank(ims[2])
        _put(c, 'EUROCOM', 160, 108, 44, (230, 60, 60), (70, 90, 230), w_max=260, thickness=5.5, rim=(60, 20, 90))
        _put(c, 'ENTERTAINMENT', 160, 150, 16, (235, 225, 255), (190, 170, 240), w_max=200)
        _put(c, 'SOFTWARE', 160, 172, 16, (235, 225, 255), (190, 170, 240), w_max=130)
        out[name] = {0: a, 1: b, 2: c}
    if 3 in byid:
        name, f = byid[3]
        out[name] = {0: _clock(f['images'][0], paint(f['images'][0], 0))}
    return out
