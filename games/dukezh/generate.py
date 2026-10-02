"""CLEAN ROOM: paint assets from games/dukezh/spec into a tree. usage: python -m games.dukezh.generate <clean tree> [--only tiles]

Tiles: every blob is repainted from its facts, EDL-packed with our compressor and zero-padded to the retail slot size
(gTileInfo keeps its literal sizes, the ROM layout does not move). If a blob does not fit, detail is dropped, then colours.
Models: skeleton (geometry) + textures repainted in place (uncompressed, same size).
"""
import json
import os
import sys

import zipfile

from cleanroom.decomp import gen
from games.dukezh import drawn, edl, models, pics, sounds, tiles

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
                d = tiles.build(f, seed=f['id'], rgba=rgba, pal256=pal, amount=amount, colours=colours,
                                ramp=rgba is not None and f['kind'] != 'ci8' and name not in drawn.COLOUR_TILES)
                blob = edl.compress(d) if f['edl'] else d      # same storage as retail (bare or EDL)
                if len(blob) > f['fit'] and f['edl']:
                    blob = edl.compress(d, store=True)
                if len(blob) <= f['fit']:
                    steps[n] += 1
                    break
            else:
                raise SystemExit('tile %s does not fit: %d > %d' % (name, len(blob), f['fit']))
        packed += len(blob)
        open(os.path.join(out_dir, name + '.bin'), 'wb').write(blob.ljust(f['size'], b'\0'))
    print('tiles written', len(spec), 'drawn', drawn_n, 'fit at step', steps, 'packed %d KB' % (packed // 1024))


def gen_models(tree):
    spec = json.load(open(os.path.join(HERE, 'spec/models.json')))
    out_dir = os.path.join(tree, 'assets/us/models')
    os.makedirs(out_dir, exist_ok=True)
    ntex = 0
    with zipfile.ZipFile(os.path.join(HERE, 'spec/models_skel.zip')) as z:
        for name, fs in spec.items():
            open(os.path.join(out_dir, name + '.bin'), 'wb').write(models.build(z.read(name), fs, seed=name))
            ntex += len(fs)
    print('models written', len(spec), 'textures', ntex)


def gen_sounds(tree, procs=2):
    import multiprocessing
    spec = json.load(open(os.path.join(HERE, 'spec/sounds.json')))
    out_dir = os.path.join(tree, 'assets/us/sounds')
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    with zipfile.ZipFile(os.path.join(HERE, 'spec/sounds_skel.zip')) as z, multiprocessing.Pool(procs) as pool:
        for bank, b in spec.items():
            res = pool.map(sounds.encode_one, sounds.jobs(b['samples'], seed=bank), chunksize=4)
            ptr, wbk = sounds.build(z.read(bank + '.ptr'), b['samples'], b['wbk_len'], res)
            open(os.path.join(out_dir, bank + '.ptr.bin'), 'wb').write(ptr)
            open(os.path.join(out_dir, bank + '.wbk.bin'), 'wb').write(wbk)
            n += len(res)
    print('sound banks written', len(spec), 'samples', n)


def gen_pics(tree):
    """Picture packs and 3D menu textures: whole files rebuilt; padded to the retail size when they fit (they are
    linked by ROM_START/ROM_END symbols, so a bigger file is also fine)."""
    spec = json.load(open(os.path.join(HERE, 'spec/pics.json')))
    out_dir = os.path.join(tree, 'assets/us/files')
    os.makedirs(out_dir, exist_ok=True)
    n, bigger = 0, []
    from games.dukezh import drawn
    drawn_pics = drawn.pic_overrides(tree, spec)
    drawn_pics.update(drawn.picture_overrides(spec, lambda f, n: pics.paint(f, gen.h32(0, n))))
    for name, f in spec.items():
        if f['kind'] == 'pics':
            outs = [(name, pics.build(bytes(f['len']), f['images'], seed=name, drawn=drawn_pics.get(name)),
                     f['edl'], f['size'])]
        else:
            tex, pal = pics.mesh_build(f['images'], f['len'], f['pal_len'], seed=name)
            outs = [(name, tex, f['edl'], f['size']), (f['pal_file'], pal, f['pal_edl'], f['pal_size'])]
        for nm, d, is_edl, size in outs:
            blob = edl.compress(d) if is_edl else d
            if len(blob) > size:
                bigger.append(nm)
                blob += bytes(-len(blob) % 16)
            open(os.path.join(out_dir, nm + '.bin'), 'wb').write(blob.ljust(size, bytes(1)))
        n += len(f['images'])
    print('picture files written', len(spec), 'images', n, 'bigger than the retail slot:', bigger)


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else ''
    if only in ('', 'pics'):
        gen_pics(sys.argv[1])
    if only in ('', 'tiles'):
        gen_tiles(sys.argv[1])
    if only in ('', 'models'):
        gen_models(sys.argv[1])
    if only in ('', 'sounds'):
        gen_sounds(sys.argv[1])
