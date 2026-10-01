"""DEV ONLY (never publish): retail ROM with a subset of tile slots replaced by clean ones, to bisect crashes.
usage: python -m games.dukezh.dev_bisect <out.z64> <python expr over f (fact dict), e.g. "f['kind']=='ci4'">"""
import json, sys
from games.dukezh import tiles
rom = bytearray(open('D:/n64work/dukezh/rom/baserom.us.z64', 'rb').read())
spec = json.load(open('games/dukezh/spec/tiles.json'))
n = 0
for i in tiles.infos(rom[0xF8730:0x105F50]):
    name = '%04d' % i['tileid']
    f = spec[name]
    b = open('D:/n64work/dukezh/clean/assets/us/tiles/%s.bin' % name, 'rb').read()
    edl_ = b[:3] == b'EDL'
    was_edl = rom[0x11FC80 + i['fileoff']:][:3] == b'EDL'
    if eval(sys.argv[2]):
        o = 0x11FC80 + i['fileoff']
        rom[o:o + len(b)] = b
        n += 1
open(sys.argv[1], 'wb').write(rom)
print('replaced', n)
