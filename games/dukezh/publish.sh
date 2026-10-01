#!/bin/sh
# Publish: taint must be 0 failing. Builds the site from the clean ROM and force-pushes it to gh-pages.
# usage: sh games/dukezh/publish.sh
set -e
W=/d/n64work/dukezh
R="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$R"
python -m games.dukezh.taint_report $W/dirty $W/clean | tee $W/taint.log | tail -1
grep -q "taint total: .* 0 failing" $W/taint.log || { echo "taint failing: not publishing"; exit 1; }
python ports/emu/make_site.py $W/site $W/clean/build/us/dukenukemzerohour.z64 --game dukezh | tail -1
cd $W/site
touch .nojekyll
rm -rf .git
git init -q -b gh-pages
git config user.name andre
git config user.email treesixtyweather@gmail.com
git add -A
git commit -q -m "Site: clean ROM + N64Wasm"
git push -q -f https://github.com/andrewnakas/dukezh-cleanroom.git gh-pages
echo "pushed gh-pages"
