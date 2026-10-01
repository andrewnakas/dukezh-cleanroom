"""EDL codec (Eurocom/Edge "EDL" container used by Duke Nukem: Zero Hour).

Format (from the decomp's src/code0/edl.c and tools/scripts/edl.py):
  "EDL", type byte (bit7 = big endian words, low nibble 0 = stored, 1 = LZ+Huffman), u32 packed size, u32 unpacked size.
  Type 1 body = 32-bit words read LSB first. Blocks:
    1 bit: 1 = Huffman block, 0 = raw block (15-bit count, then bytes)
    Huffman block: lit/len table (9-bit count; per entry 1 bit "new length" + 4-bit length, else repeat),
    distance table (same), then symbols: <256 literal, 256 end of block, >256 match (deflate length/distance bases).
    1 bit after each block: 1 = end of stream.
The compressor is ours: greedy hash-chain LZ77 + canonical Huffman, code lengths capped at the decoder's
first-level table size (10 bits lit/len, 8 bits distance) so the second-level path is never needed.
"""
import heapq

LBASE = [0, 1, 2, 3, 4, 5, 6, 7, 8, 0xA, 0xC, 0xE, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x28, 0x30, 0x38, 0x40, 0x50, 0x60,
         0x70, 0x80, 0xA0, 0xC0, 0xE0, 0xFF]
LEXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
DBASE = [0, 1, 2, 3, 4, 6, 8, 0xC, 0x10, 0x18, 0x20, 0x30, 0x40, 0x60, 0x80, 0xC0, 0x100, 0x180, 0x200, 0x300, 0x400,
         0x600, 0x800, 0xC00, 0x1000, 0x1800, 0x2000, 0x3000, 0x4000, 0x6000]
DEXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
MAXLEN, MAXDIST, MINLEN = 258, 32768, 3


# ---------------------------------------------------------------- bit IO
class _BitW:
    def __init__(self):
        self.acc = 0
        self.n = 0

    def put(self, v, bits):
        self.acc |= (v & ((1 << bits) - 1)) << self.n
        self.n += bits

    def bytes(self, endian):
        nw = (self.n + 31) // 32 + 1          # one spare word: the decoder peeks ahead
        return b''.join(((self.acc >> (32 * i)) & 0xFFFFFFFF).to_bytes(4, endian) for i in range(nw))


class _BitR:
    def __init__(self, data, endian):
        self.acc = 0
        for i in range(0, len(data), 4):
            self.acc |= int.from_bytes(data[i:i + 4].ljust(4, b'\0'), endian) << (8 * i)
        self.pos = 0

    def peek(self, bits):
        return (self.acc >> self.pos) & ((1 << bits) - 1)

    def get(self, bits):
        v = self.peek(bits)
        self.pos += bits
        return v


# ---------------------------------------------------------------- Huffman
def _lengths(freq, limit):
    """Code lengths (0 = unused) for symbol frequencies, capped at `limit` bits."""
    f = list(freq)
    while True:
        used = [(w, i) for i, w in enumerate(f) if w]
        L = [0] * len(f)
        if len(used) == 1:
            L[used[0][1]] = 1
            return L
        heap = [(w, i, (i,)) for w, i in used]
        heapq.heapify(heap)
        tick = len(f)
        while len(heap) > 1:
            a = heapq.heappop(heap)
            b = heapq.heappop(heap)
            for s in a[2] + b[2]:
                L[s] += 1
            heapq.heappush(heap, (a[0] + b[0], tick, a[2] + b[2]))
            tick += 1
        if max(L) <= limit:
            return L
        f = [(w + 1) // 2 if w else 0 for w in f]   # flatten the distribution and retry


def _codes(L):
    """Canonical codes, bit-reversed (the stream is LSB first). Order: by length, then symbol."""
    out = {}
    code, prev = 0, None
    for ln in range(1, 16):
        for s, l in enumerate(L):
            if l != ln:
                continue
            if prev is not None and ln != prev:
                code <<= (ln - prev)
            prev = ln
            out[s] = (int(format(code, '0%db' % ln)[::-1], 2), ln)
            code += 1
    return out


# ---------------------------------------------------------------- LZ77
def _lz(data, chain=48):
    n = len(data)
    out = []
    head = {}
    prev = [0] * n
    i = 0

    def ins(p):
        if p + 2 < n:
            k = data[p:p + 3]
            prev[p] = head.get(k, -1)
            head[k] = p

    while i < n:
        bl, bd = 0, 0
        if i + 2 < n:
            p = head.get(data[i:i + 3], -1)
            c = chain
            mx = min(MAXLEN, n - i)
            while p >= 0 and c and i - p <= MAXDIST:
                if bl < mx and data[p + bl] == data[i + bl] or bl == 0:
                    l = 0
                    while l < mx and data[p + l] == data[i + l]:
                        l += 1
                    if l > bl:
                        bl, bd = l, i - p
                        if l == mx:
                            break
                p = prev[p]
                c -= 1
        if bl >= MINLEN:
            out.append((bl, bd))
            for p in range(i, i + bl):
                ins(p)
            i += bl
        else:
            out.append((data[i], 0))
            ins(i)
            i += 1
    return out


def _lsym(l):
    v = l - 3
    for s in range(28, -1, -1):
        if LBASE[s] <= v and (s == 28) == (v == 0xFF):
            return s, v - LBASE[s]
    raise ValueError(l)


def _dsym(d):
    v = d - 1
    for s in range(29, -1, -1):
        if DBASE[s] <= v:
            return s, v - DBASE[s]
    raise ValueError(d)


# ---------------------------------------------------------------- API
def compress(data, endian='big', store=False):
    data = bytes(data)
    typ = 0x80 if endian == 'big' else 0
    if store or len(data) < 8:
        body = data + b'\0' * (-len(data) % 4)
        return b'EDL' + bytes([typ]) + (len(body) + 12).to_bytes(4, endian) + len(data).to_bytes(4, endian) + body
    toks = _lz(data)
    lf = [0] * 286
    df = [0] * 30
    enc = []
    for a, d in toks:
        if d == 0:
            lf[a] += 1
            enc.append((a,))
        else:
            ls, le = _lsym(a)
            ds, de = _dsym(d)
            lf[257 + ls] += 1
            df[ds] += 1
            enc.append((257 + ls, le, ds, de))
    lf[256] = 1
    LL = _lengths(lf, 10)
    DL = _lengths(df, 8) if any(df) else []
    while LL and LL[-1] == 0:
        LL.pop()
    while DL and DL[-1] == 0:
        DL.pop()
    lc, dc = _codes(LL), _codes(DL)
    w = _BitW()
    w.put(1, 1)
    stack = 0
    for tab in (LL, DL):
        w.put(len(tab), 9)
        for l in tab:
            if l != stack:
                w.put(1, 1)
                w.put(l, 4)
                stack = l
            else:
                w.put(0, 1)
    for e in enc + [(256,)]:
        c, n = lc[e[0]]
        w.put(c, n)
        if len(e) == 4:
            if LEXTRA[e[0] - 257]:
                w.put(e[1], LEXTRA[e[0] - 257])
            c, n = dc[e[2]]
            w.put(c, n)
            if DEXTRA[e[2]]:
                w.put(e[3], DEXTRA[e[2]])
    w.put(1, 1)
    body = w.bytes(endian)
    if len(body) >= len(data) + 4:
        return compress(data, endian, store=True)
    return b'EDL' + bytes([typ | 1]) + (len(body) + 12).to_bytes(4, endian) + len(data).to_bytes(4, endian) + body


def _table(L):
    """symbol lookup: {(reversed code, length): symbol}"""
    return {v: s for s, v in _codes(L).items()}


def decompress(blob):
    """Reference decoder (independent of the decomp's script; used for self-checks and the dirty room)."""
    if blob[:3] != b'EDL':
        return bytes(blob)
    endian = 'big' if blob[3] & 0x80 else 'little'
    typ = blob[3] & 0xF
    dec = int.from_bytes(blob[8:12], endian)
    if typ == 0:
        return bytes(blob[12:12 + dec])
    r = _BitR(blob[12:], endian)
    out = bytearray()
    stack = 0
    lt, dt = {}, {}

    def rd_tab():
        nonlocal stack
        n = r.get(9)
        if not n:
            return None
        L = []
        for _ in range(n):
            if r.get(1):
                stack = r.get(4)
            L.append(stack)
        return _table(L)

    def sym(t):
        for n in range(1, 16):
            s = t.get((r.peek(n), n))
            if s is not None:
                r.pos += n
                return s
        raise ValueError('bad code')

    while len(out) < dec:
        if r.get(1):
            t = rd_tab()
            lt = t if t is not None else lt
            t = rd_tab()
            dt = t if t is not None else dt
            while True:
                s = sym(lt)
                if s < 256:
                    out.append(s)
                elif s == 256:
                    break
                else:
                    l = LBASE[s - 257] + 3 + (r.get(LEXTRA[s - 257]) if LEXTRA[s - 257] else 0)
                    d = sym(dt)
                    p = len(out) - (DBASE[d] + 1 + (r.get(DEXTRA[d]) if DEXTRA[d] else 0))
                    for i in range(l):
                        out.append(out[p + i] if p + i >= 0 else 0)
        else:
            for _ in range(r.get(15)):
                out.append(r.get(8))
        if r.get(1):
            break
    return bytes(out[:dec])


if __name__ == '__main__':
    import random
    random.seed(1)
    tests = [b'', b'a', bytes(64), bytes(range(256)) * 9, bytes(random.randrange(4) * 17 for _ in range(5000)),
             bytes(random.randrange(256) for _ in range(3000)), b'abcabcabcabd' * 700,
             bytes((i // 4 * 7) & 255 for i in range(40000))]
    ok = True
    for t in tests:
        for e in ('big', 'little'):
            c = compress(t, e)
            ok &= decompress(c) == t
            print(len(t), '->', len(c), e, 'ok' if decompress(c) == t else 'FAIL')
    print('edl self-test', 'OK' if ok else 'FAILED')
