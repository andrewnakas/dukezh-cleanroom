"""DIRTY ROOM: reduce retail assets to the approved facts. usage: python -m games.dukezh.extract_spec <dirty tree>

Writes games/dukezh/spec/tiles.json: per tile bin {kind, len (unpacked), size (packed slot), w, h, grid 4x4, alpha2}.
Palette-only tiles keep their 16 colours (a colour table, like the grid). Prints a one-screen summary.
"""
import collections
import json
import os
import re
import sys

from games.dukezh import edl, tiles

HERE = os.path.dirname(os.path.abspath(__file__))


def tile_rows(tree):
    """(bin name, info dict) per gTileInfo row, from the decomp's C table (no ROM parsing needed)."""
    src = open(os.path.join(tree, 'src/static/tileinfo.c'), encoding='utf-8').read()
    rows = []
    for m in re.finditer(r'\{\(s32\)tiles_(\w+)_bin,\s*NULL,\s*([^}]*)\}', src):
        v = [int(x, 0) for x in m.group(2).replace(' ', '').split(',')]
        rows.append((m.group(1), dict(picanm=v[0], sizex=v[1], sizey=v[2], filesize=v[3], dimx=v[4], dimy=v[5],
                                      flags=v[6], tileid=v[7])))
    return rows


def main(tree):
    pal = tiles.pal256_from_c(os.path.join(tree, 'src/static/F6D70.c'))
    out, kinds = {}, collections.Counter()
    for name, info in tile_rows(tree):
        path = os.path.join(tree, 'assets/us/tiles/%s.bin' % name)
        if name in out or not os.path.exists(path):      # rows of other versions (#if) have no US bin
            continue
        blob = open(path, 'rb').read()
        d = edl.decompress(blob[:info['filesize']])
        f = tiles.fact(info, d, pal)
        f['size'] = len(blob)
        f['id'] = info['tileid']
        if f['kind'] == 'pal':
            f['colours'] = d.hex()
        elif 'grid' not in f:
            raise SystemExit('unhandled tile %s kind %s' % (name, f['kind']))
        kinds[f['kind']] += 1
        out[name] = f
    os.makedirs(os.path.join(HERE, 'spec'), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, 'spec/tiles.json'), 'w'), separators=(',', ':'))
    print('tiles', len(out), dict(kinds), 'with alpha', sum('alpha2' in f for f in out.values()))


if __name__ == '__main__':
    main(sys.argv[1])
