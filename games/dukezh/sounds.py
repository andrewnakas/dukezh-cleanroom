"""libmus sample banks of Duke Nukem: Zero Hour: bankN.ptr ("N64 PtrTablesV2") + bankN.wbk ("N64 WaveTables").

ptr file (big endian): name[16], flags u32, wbk_name[12], count s32, basenote off, detune off, wave_list off;
wave_list = count offsets to ALWaveTable {base u32 (offset in wbk), len s32, type u8, flags u8, loop off, book off};
book = {order s32, npred s32, s16[order*npred*8]}; loop = {start u32, end u32, count u32, state s16[16]}.
All samples in the US ROM are VADPCM with order 2, 4 predictors.

Dirty room: `facts()` -> per sample: frames, loop points, coarse spectral outline (cleanroom.audio.descriptor), median
pitch; plus the ptr skeleton = the ptr file with every codebook and loop state zeroed (bank structure, tuning tables kept).
Clean room: `build()` resynthesises each sample from its outline, designs our own codebook, encodes, fills the skeleton.
The sample rate is not stored in the bank (libmus tunes by basenote/detune); RATE is only the analysis convention.
"""
import struct

import numpy as np

from cleanroom.audio import descriptor, vadpcm
from cleanroom.audio.pitch import median_f0
from cleanroom.decomp import gen

RATE = 22050
HDR = struct.Struct('>16sI12siIII')
WT = struct.Struct('>IiBBxxII')


def waves(ptr):
    name, flags, wname, count, bn, dt, wl = HDR.unpack_from(ptr, 0)
    assert name.startswith(b'N64 PtrTables'), name
    out = []
    for q in struct.unpack_from('>%dI' % count, ptr, wl):
        base, ln, typ, fl, loop, book = WT.unpack_from(ptr, q)
        assert typ == 0 and book, 'only VADPCM samples are handled'
        out.append(dict(at=q, base=base, len=ln, loop=loop, book=book))
    return out


def _book(ptr, o):
    order, npred = struct.unpack_from('>ii', ptr, o)
    return {'order': order, 'npred': npred, 'book': list(struct.unpack_from('>%dh' % (order * npred * 8), ptr, o + 8))}


def facts(ptr, wbk):
    """(sample facts list, ptr skeleton). Dirty room."""
    skel = bytearray(ptr)
    out = []
    for w in waves(ptr):
        book = _book(ptr, w['book'])
        assert book['order'] == 2
        n = w['len'] // 9 * 16
        pcm = vadpcm.decode(wbk[w['base']:w['base'] + w['len']], book, n).astype(np.float64)
        f = {'base': w['base'], 'len': w['len'], 'nframes': n, 'npred': book['npred'],
             'desc': descriptor.describe(pcm, RATE)}
        f0 = median_f0((pcm / 32768).astype(np.float32), RATE) if n >= 2048 else None
        if f0:
            f['f0'] = round(float(f0), 1)
        skel[w['book'] + 8:w['book'] + 8 + 2 * 16 * book['npred']] = bytes(2 * 16 * book['npred'])
        if w['loop']:
            s, e, c = struct.unpack_from('>IIi', ptr, w['loop'])
            f['loop'] = [s, e, c]
            skel[w['loop'] + 12:w['loop'] + 44] = bytes(32)
        out.append(f)
    return out, bytes(skel)


def pcm_for(f, seed, supplied=None):
    n = f['nframes']
    if supplied is not None:
        x = np.asarray(supplied, np.float32)[:n]
        x = np.pad(x, (0, n - len(x)))
    else:
        x = np.asarray(descriptor.synthesize(f['desc'], n, RATE, seed=seed), np.float32)[:n]
        x = np.pad(x, (0, n - len(x)))
        if 'loop' in f and 0 <= f['loop'][0] < f['loop'][1] <= n:
            x = descriptor.make_loop_seamless(x, f['loop'][0], f['loop'][1])
    dither = np.random.default_rng(seed).integers(-1, 2, n)
    return np.clip(np.round(np.clip(x, -1, 1) * 32000) + dither, -32768, 32767).astype(np.int16)


def encode_one(job):
    """(f, seed, supplied) -> (adpcm bytes, book values, loop state or None). Runs in worker processes."""
    f, seed, supplied = job
    pcm = pcm_for(f, seed, supplied)
    preds = gen.two_predictors(pcm.astype(np.float64))
    book = vadpcm.make_book((preds * f['npred'])[:f['npred']])           # our book, retail size (npred entries)
    data, book, dec = vadpcm.encode(pcm, book)
    st = None
    if 'loop' in f:
        st = vadpcm.loop_state(dec, f['loop'][0] & ~15) if f['loop'][0] >= 16 else [0] * 16
    return data[:f['len']].ljust(f['len'], b'\0'), book['book'], st


def jobs(fs, seed=0, supplied=None):
    return [(f, gen.h32(seed, n), supplied.get(n) if supplied else None) for n, f in enumerate(fs)]


def build(skel, fs, wbk_len, results):
    """(ptr bytes, wbk bytes) from the skeleton, facts and the encode_one results (same order as fs)."""
    ptr = bytearray(skel)
    wbk = bytearray(wbk_len)
    wbk[:16] = b'N64 WaveTables \0'
    for w, f, (data, book, st) in zip(waves(skel), fs, results):
        wbk[f['base']:f['base'] + f['len']] = data
        struct.pack_into('>%dh' % len(book), ptr, w['book'] + 8, *book)
        if st is not None:
            struct.pack_into('>16h', ptr, w['loop'] + 12, *st)
    return bytes(ptr), bytes(wbk)
