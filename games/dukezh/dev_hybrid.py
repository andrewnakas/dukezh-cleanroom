"""DEV ONLY (never publish): retail ROM with one ROM range replaced by the clean ROM's bytes.
usage: python -m games.dukezh.dev_hybrid <out.z64> <start hex> <end hex> [...more ranges]"""
import sys
W = 'D:/n64work/dukezh'
rom = bytearray(open(W + '/rom/baserom.us.z64', 'rb').read())
clean = open(W + '/clean/build/us/dukenukemzerohour.z64', 'rb').read()
a = sys.argv[2:]
for i in range(0, len(a), 2):
    s, e = int(a[i], 16), int(a[i + 1], 16)
    rom[s:e] = clean[s:e]
open(sys.argv[1], 'wb').write(rom)
print('hybrid written')
