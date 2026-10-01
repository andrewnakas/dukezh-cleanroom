"""CLEAN ROOM: paint assets from games/dukezh/spec into a tree. usage: python -m games.dukezh.generate <clean tree> [--only tiles]

Tiles: every blob is repainted from its facts, EDL-packed with our compressor and zero-padded to the retail slot size
(gTileInfo keeps its literal sizes, the ROM layout does not move). If a blob does not fit, detail is dropped, then colours.
"""
import json
import os
import sys

from games.dukezh import edl, tiles

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [(0.06, 16), (0.03, 16), (0.0, 16), (0.0, 8), (0.0, 4), (0.0, 3), (0.0, 2), (0.0, 1)]


def overrides():
    """Drawn replacements {bin name: callable(fact) -> rgba (h, w, 4)} from the drawn modules (text, faces, HUD)."""
    try:
        from games.dukezh import drawn
        return drawn.tile_overrides()
    except ImportError:
        return {}


def gen_tiles(tree):
    spec = json.load(open(os.path.join(HERE, 'spec/tiles.json')))
    pal = tiles.pal256_from_c(os.path.join(tree, 'src/static/F6D70.c'))
    ov = overrides()
    out_dir = os.path.join(tree, 'assets/us/tiles')
    os.makedirs(out_dir, exist_ok=True)
    steps, drawn_n, packed = [0] * len(STEPS), 0, 0
    for name, f in spec.items():
        if f['kind'] == 'pal':
            blob = bytes.fromhex(f['colours'])
        else:
            rgba = ov[name](f) if name in ov else None
            drawn_n += rgba is not None
            for n, (amount, colours) in enumerate(STEPS):
                d = tiles.build(f, seed=f['id'], rgba=rgba, pal256=pal, amount=amount, colours=colours)
                blob = d if len(d) <= f['size'] else edl.compress(d)   # small tiles are stored bare (no EDL header)
                if len(blob) <= f['size']:
                    steps[n] += 1
                    break
            else:
                raise SystemExit('tile %s does not fit: %d > %d' % (name, len(blob), f['size']))
        packed += len(blob)
        open(os.path.join(out_dir, name + '.bin'), 'wb').write(blob.ljust(f['size'], b'\0'))
    print('tiles written', len(spec), 'drawn', drawn_n, 'fit at step', steps, 'packed %d KB' % (packed // 1024))


if __name__ == '__main__':
    gen_tiles(sys.argv[1])
