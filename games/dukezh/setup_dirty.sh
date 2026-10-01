#!/bin/sh
# Dirty room: unzip the ROM, verify sha1, copy pristine -> dirty, split, build, compare.
# usage: sh games/dukezh/setup_dirty.sh "<rom zip or .z64>"     (prints a one-screen summary)
set -e
W=/d/n64work/dukezh
SHA=de4db292cc6cf5dd1dd1d3c9700cf8e5c3078410
. "$(dirname "$0")/../../tools/dz_env.sh"
mkdir -p $W/rom
case "$1" in
  *.zip) unzip -o -q "$1" -d $W/rom;;
  *) cp "$1" $W/rom/;;
esac
R=$(ls $W/rom/* | head -1)
python - "$R" $W/rom/baserom.us.z64 $SHA <<'EOF'
import sys, hashlib
d = bytearray(open(sys.argv[1], 'rb').read())
if d[:4] == b'\x37\x80\x40\x12': d[0::2], d[1::2] = d[1::2], d[0::2]          # .v64
elif d[:4] == b'\x40\x12\x37\x80': d = bytearray(b''.join(d[i:i+4][::-1] for i in range(0, len(d), 4)))  # .n64
h = hashlib.sha1(d).hexdigest()
print('rom sha1', h, 'OK' if h == sys.argv[3] else 'MISMATCH (expected %s)' % sys.argv[3])
open(sys.argv[2], 'wb').write(d)
sys.exit(0 if h == sys.argv[3] else 1)
EOF
[ -d $W/dirty ] || cp -r $W/pristine $W/dirty
cp $W/rom/baserom.us.z64 $W/dirty/
cd $W/dirty
install_kmc .
python -m splat split versions/us/dukenukemzerohour.yaml > $W/split.log 2>&1 || { tail -5 $W/split.log; exit 1; }
echo "split ok: $(find assets/us -type f | wc -l) asset bins, $(find asm/us -name '*.s' | wc -l) asm"
mk -j4 > $W/build_dirty.log 2>&1 || true
tail -3 $W/build_dirty.log
