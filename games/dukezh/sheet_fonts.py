"""Contact sheet of the drawn font tiles in a (clean) tree. usage: python -m games.dukezh.sheet_fonts <tree> <out.png>"""
import json
import sys

import numpy as np

from cleanroom.gfx import png
from games.dukezh import drawn, edl, tiles

s = json.load(open('games/dukezh/spec/tiles.json'))
ids = sorted(drawn.tile_chars())
S, N = 3, 32
C = 16 * S + 4
out = np.zeros(((len(ids) + N - 1) // N * C, N * C, 4), np.uint8)
out[..., :3] = (90, 0, 90)
out[..., 3] = 255
for n, t in enumerate(ids):
    f = s['%04d' % t]
    d = edl.decompress(open('%s/assets/us/tiles/%04d.bin' % (sys.argv[1], t), 'rb').read())
    k, im = tiles.decode(dict(dimx=f['w'], dimy=f['h'], flags=0), d[:f['len']])
    a = im[..., 3:4] / 255.0
    rgb = (im[..., :3] * a + np.array([90, 0, 90]) * (1 - a)).astype(np.uint8)
    big = np.repeat(np.repeat(rgb, S, 0), S, 1)
    y, x = (n // N) * C, (n % N) * C
    out[y:y + big.shape[0], x:x + big.shape[1], :3] = big
png.write(sys.argv[2], out)
print('sheet', out.shape)
