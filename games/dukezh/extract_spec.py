"""DIRTY ROOM: reduce retail assets to the approved facts. usage: python -m games.dukezh.extract_spec <dirty tree>

Writes games/dukezh/spec/tiles.json: per tile bin {kind, len (unpacked), size (packed slot), w, h, grid 4x4, alpha2}.
Palette-only tiles keep their 16 colours (a colour table, like the grid).
Writes spec/models.json (texture facts per model bin) + spec/models_skel.zip (bins with all texture bytes zeroed:
geometry, commands, lights, vertices).
Writes spec/sounds.json (per sample: frames, loop, spectral outline, pitch) + spec/sounds_skel.zip (ptr banks with
codebooks and loop states zeroed).  Prints a one-screen summary.
"""
import collections
import json
import os
import re
import sys

import zipfile

from games.dukezh import edl, models, pics, sounds, tiles

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
        f['edl'] = blob[:3] == b'EDL'      # storage (bare or EDL) is kept: bare-for-EDL swaps crashed the game
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

    mfacts, ntex = {}, 0
    with zipfile.ZipFile(os.path.join(HERE, 'spec/models_skel.zip'), 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, (tex, cmd) in sorted(models.rows(tree).items()):
            d = open(os.path.join(tree, 'assets/us/models/%s.bin' % name), 'rb').read()
            mfacts[name], skel = models.facts(d, tex, cmd)
            ntex += len(mfacts[name])
            z.writestr(zipfile.ZipInfo(name), skel, zipfile.ZIP_DEFLATED, 9)   # fixed date: stable bytes
    json.dump(mfacts, open(os.path.join(HERE, 'spec/models.json'), 'w'), separators=(',', ':'))
    print('models', len(mfacts), 'textures', ntex, 'skeleton zip %d KB' % (os.path.getsize(os.path.join(HERE, 'spec/models_skel.zip')) // 1024))

    sfacts, frames = {}, 0
    with zipfile.ZipFile(os.path.join(HERE, 'spec/sounds_skel.zip'), 'w') as z:
        for b in range(16):
            base = os.path.join(tree, 'assets/us/sounds/bank%d' % b)
            ptr, wbk = open(base + '.ptr.bin', 'rb').read(), open(base + '.wbk.bin', 'rb').read()
            fs, skel = sounds.facts(ptr, wbk)
            sfacts['bank%d' % b] = {'wbk_len': len(wbk), 'samples': fs}
            frames += sum(f['nframes'] for f in fs)
            z.writestr(zipfile.ZipInfo('bank%d.ptr' % b), skel, zipfile.ZIP_DEFLATED, 9)
    json.dump(sfacts, open(os.path.join(HERE, 'spec/sounds.json'), 'w'), separators=(',', ':'))
    print('sound banks', len(sfacts), 'samples', sum(len(v['samples']) for v in sfacts.values()), 'frames', frames,
          'looped', sum('loop' in f for v in sfacts.values() for f in v['samples']))

    # picture packs + 3D menu textures ("files"): every pixel-bearing file is regenerated whole
    names, tabs, pfacts = pics.file_names(tree), pics.tables(tree), {}

    def load(i):
        b = open(os.path.join(tree, 'assets/us/files/%s.bin' % names[i]), 'rb').read()
        return b, edl.decompress(b)
    ftab = dict(pics.FILE_TABLE)
    ftab.update({12: 'D_800DFFCC', 29: 'D_800E0804'})
    for fid, tab in sorted(ftab.items()):
        b, d = load(fid)
        fs, skel = pics.facts(d, tabs[tab])
        if any(skel):
            raise SystemExit('picture file %d has bytes outside its images' % fid)
        pfacts[names[fid]] = {'kind': 'pics', 'id': fid, 'size': len(b), 'edl': b[:3] == b'EDL', 'len': len(d),
                              'images': fs}
    for mesh, tex, pal, uv, sym in pics.MESH_SETS:
        (bt, dt), (bp, dp) = load(tex), load(pal)
        texs = pics.mesh_textures(load(mesh)[1], pics.mesh_offsets(tree, sym), len(dt))
        pfacts[names[tex]] = {'kind': 'meshtex', 'id': tex, 'size': len(bt), 'edl': bt[:3] == b'EDL', 'len': len(dt),
                              'pal_file': names[pal], 'pal_size': len(bp), 'pal_edl': bp[:3] == b'EDL',
                              'pal_len': len(dp), 'images': pics.mesh_facts(dt, dp, texs)}
    json.dump(pfacts, open(os.path.join(HERE, 'spec/pics.json'), 'w'), separators=(',', ':'))
    print('picture files', len(pfacts), 'images', sum(len(v['images']) for v in pfacts.values()))


if __name__ == '__main__':
    main(sys.argv[1])
