"""DEV ONLY (never publish): find a minimal set of clean tiles that makes the retail ROM crash in the emulator.
usage: python -m games.dukezh.dev_ddmin [port]   (needs the dev site served; writes D:/n64work/dukezh/ddmin.log)"""
import json
import subprocess
import sys

from cleanroom.gfx import png
from games.dukezh import tiles

PORT = sys.argv[1] if len(sys.argv) > 1 else '8457'
W = 'D:/n64work/dukezh'
ROM = open(W + '/rom/baserom.us.z64', 'rb').read()
INFO = {'%04d' % i['tileid']: i for i in tiles.infos(ROM[0xF8730:0x105F50])}
LOG = open(W + '/ddmin.log', 'a')


def crashes(names):
    rom = bytearray(ROM)
    for n in names:
        b = open(W + '/clean/assets/us/tiles/%s.bin' % n, 'rb').read()
        o = 0x11FC80 + INFO[n]['fileoff']
        rom[o:o + len(b)] = b
    open(W + '/site_dev_retail/dev.z64', 'wb').write(rom)
    subprocess.run([sys.executable, 'ports/emu/shot.py', W + '/shots/dd', '--url',
                    'http://localhost:%s/index.html' % PORT, '--secs', '100', '--keys',
                    '45:Enter:0.3,55:Enter:0.3,64:Enter:0.3,72:Enter:0.3,80:Enter:0.3,88:Enter:0.3', '--query', 'nosave=1&rom=dev.z64'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    img = png.read(W + '/shots/dd/shot_100.png')
    dark = img[190:630, 115:745, :3].mean() < 8      # the game canvas only
    print(len(names), 'crash' if dark else 'ok', file=LOG, flush=True)
    return dark


def ddmin(s):
    n = 2
    while len(s) >= 2:
        size = max(1, len(s) // n)
        parts = [s[i:i + size] for i in range(0, len(s), size)]
        for p in parts:
            if crashes(p):
                s, n = p, 2
                break
        else:
            for p in parts:
                rest = [x for x in s if x not in p]
                if n > 2 and crashes(rest):
                    s, n = rest, max(n - 1, 2)
                    break
            else:
                if n >= len(s):
                    break
                n = min(len(s), n * 2)
    return s


if __name__ == '__main__':
    allt = sorted(json.load(open('games/dukezh/spec/tiles.json')))
    assert crashes(allt), 'the full set does not crash'
    r = ddmin(allt)
    print('MINIMAL', r, file=LOG, flush=True)
    print('minimal crashing set:', r)
