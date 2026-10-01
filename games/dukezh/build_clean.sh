#!/bin/sh
# Clean room build: tree = decomp + splat's code/linker output + assets regenerated from games/dukezh/spec.
# usage: sh games/dukezh/build_clean.sh        -> D:/n64work/dukezh/clean/build/us/dukenukemzerohour.z64
# Kept facts (maps, blks, boot, ucode, songs, meshes, demo inputs) come from the dirty tree copy made on first run.
set -e
W=/d/n64work/dukezh
R="$(cd "$(dirname "$0")/../.." && pwd)"
. "$R/tools/dz_env.sh"
if [ ! -d $W/clean ]; then
  mkdir -p $W/clean
  (cd $W/dirty && tar cf - --exclude=./build --exclude='./baserom*' --exclude=./.git --exclude=./assets/us/tiles .) | (cd $W/clean && tar xf -)
  cd "$R" && python -m games.dukezh.tree_patches $W/clean --clean
  install_kmc $W/clean
fi
cd "$R"
[ "$GEN" = "0" ] || python -m games.dukezh.generate $W/clean ${ONLY:+--only $ONLY}     # GEN=0: assets already generated; ONLY=tiles|models|pics|sounds
cd $W/clean
rm -f build/us/assets/us/tiles/*.o build/us/*.z64 build/us/*.elf
mk -j4 > $W/build_clean.log 2>&1 || { grep -v "Compiling\|objcopying\|Assembling" $W/build_clean.log | tail -8; exit 1; }
ls -la build/us/dukenukemzerohour.z64
