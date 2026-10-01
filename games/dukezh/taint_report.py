"""Taint report: every generated asset of the clean tree vs the retail extraction (dirty tree).

    python -m games.dukezh.taint_report <dirty tree> <clean tree>

Streams scanned (any run >= taint.FAIL_RUN bytes shared with any retail stream fails):
  tiles     unpacked pixel indices (1 byte per pixel) + decoded RGBA, and the packed blob
  models    per texture: indices + RGBA
  pictures  per image: indices + RGBA, and the packed file; 3D menu textures the same way
  sounds    per sample: ADPCM bytes + decoded PCM
Kept facts are not scanned: code, geometry (maps, model skeletons, meshes, uv), sequences, demo inputs, bank
structure, the 26 bare palettes and the 256-colour table of the decomp C.
"""
import json
import os
import struct
import sys

import numpy as np

from cleanroom import taint
from cleanroom.audio import vadpcm
from games.dukezh import edl, pics, sounds, tiles

HERE = os.path.dirname(os.path.abspath(__file__))


def _idx4(b, n):
    a = np.frombuffer(b, np.uint8)
    i = np.empty(len(a) * 2, np.uint8)
    i[0::2], i[1::2] = a >> 4, a & 15
    return i[:n]


def _rgba16(pal, big):
    v = np.frombuffer(pal, '>u2' if big else '<u2').astype(np.int64)
    out = np.zeros((len(v), 4), np.uint8)
    for k, sh in enumerate((11, 6, 1)):
        out[:, k] = ((v >> sh) & 31) * 255 // 31
    out[:, 3] = (v & 1) * 255
    return out


def streams(tree, part):
    S = lambda n: json.load(open(os.path.join(HERE, 'spec', n)))
    A = os.path.join(tree, 'assets/us')
    if part == 'tiles':
        pal256 = tiles.pal256_from_c(os.path.join(tree, 'src/static/F6D70.c'))
        for name, f in S('tiles.json').items():
            if f['kind'] == 'pal':
                continue
            blob = open(os.path.join(A, 'tiles', name + '.bin'), 'rb').read()
            yield 'tile-packed:' + name, blob
            d = edl.decompress(blob)[:f['len']]
            if f['kind'] == 'ci8':
                yield 'tile-idx:' + name, d
                continue
            idx = _idx4(d[32:], (len(d) - 32) * 2)
            yield 'tile-idx:' + name, idx.tobytes()
            yield 'tile-rgba:' + name, _rgba16(d[:32], False)[idx].tobytes()
    elif part == 'models':
        for name, fs in S('models.json').items():
            d = open(os.path.join(A, 'models', name + '.bin'), 'rb').read()
            for n, f in enumerate(fs):
                if 'grid' not in f:
                    continue
                b = d[f['off']:f['off'] + f['len']]
                idx = _idx4(b[32:], (len(b) - 32) * 2)
                yield 'model-idx:%s/%d' % (name, n), idx.tobytes()
                yield 'model-rgba:%s/%d' % (name, n), _rgba16(b[:32], True)[idx].tobytes()
    elif part == 'pics':
        for name, f in S('pics.json').items():
            blob = open(os.path.join(A, 'files', name + '.bin'), 'rb').read()
            yield 'pic-packed:' + name, blob
            d = edl.decompress(blob)
            pd = edl.decompress(open(os.path.join(A, 'files', f['pal_file'] + '.bin'), 'rb').read()) \
                if f['kind'] == 'meshtex' else d
            for n, im in enumerate(f['images']):
                px = im['w'] * im['h']
                if im.get('bits', 8) == 4:
                    idx = _idx4(d[im['tex']:im['tex'] + (px + 1) // 2], px)
                else:
                    idx = np.frombuffer(d[im['tex']:im['tex'] + px], np.uint8)
                ncol = im.get('ncol', 256)
                yield 'pic-idx:%s/%d' % (name, n), idx.tobytes()
                yield 'pic-rgba:%s/%d' % (name, n), _rgba16(pd[im['pal']:im['pal'] + 2 * ncol], True)[
                    np.minimum(idx, ncol - 1)].tobytes()
    elif part == 'sounds':
        for bank, b in S('sounds.json').items():
            ptr = open(os.path.join(A, 'sounds', bank + '.ptr.bin'), 'rb').read()
            wbk = open(os.path.join(A, 'sounds', bank + '.wbk.bin'), 'rb').read()
            for n, w in enumerate(sounds.waves(ptr)):
                raw = wbk[w['base']:w['base'] + w['len']]
                yield 'adpcm:%s/%d' % (bank, n), raw
                pcm = vadpcm.decode(raw, sounds._book(ptr, w['book']), w['len'] // 9 * 16)
                yield 'pcm:%s/%d' % (bank, n), np.asarray(pcm, '<i2').tobytes()


def main(argv):
    dirty, clean = argv[1], argv[2]
    parts = argv[3].split(',') if len(argv) > 3 else ['tiles', 'models', 'pics', 'sounds']
    total = failing = 0
    for part in parts:
        index = taint.build_index(s for _, s in streams(dirty, part))
        n = 0

        def counted():
            nonlocal n
            for item in streams(clean, part):
                n += 1
                yield item
        hits = taint.scan(index, counted())
        # Decoded RGBA of palettised art is 4 bytes per pixel but carries at most 4 (CI4) or 8 (CI8) bits per pixel:
        # flat bands of two common 5-bit colours meeting at an edge coincide all the time. The limit for those
        # streams is therefore FAIL_RUN *pixels* (4x the bytes); everything else fails at FAIL_RUN bytes.
        limit = lambda label: taint.FAIL_RUN * 4 if '-rgba:' in label else taint.FAIL_RUN
        bad = sorted((h for h in hits if h[3] >= limit(h[0])), key=lambda h: -h[3])
        longest = max([h[3] for h in hits if '-rgba:' in h[0]] + [0])
        print('taint %-7s %6d streams, %5d with short coincidental matches (longest RGBA run %d B), %d failing '
              '(run >= %d B, RGBA >= %d px)' % (part, n, len(hits), longest, len(bad), taint.FAIL_RUN, taint.FAIL_RUN))
        for label, off, cnt, run in bad[:6]:
            print('   FAIL', label, 'run', run, 'B')
        total += n
        failing += len(bad)
    print('taint total: %d streams, %d failing' % (total, failing))
    return 1 if failing else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
