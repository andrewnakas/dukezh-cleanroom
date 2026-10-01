# Duke Nukem: Zero Hour clean room: status

_Last update: 2026-10-01 ~12:15._ **Not published yet** (only tiles are regenerated so far; models, sounds and
full-screen pictures are still retail in the dev tree, so nothing may be published).

## For the morning
- Nothing to play yet in public. Local dev checks only.

## Works
- ROM verified: `Duke Nukem - Zero Hour (USA).zip` sha1 de4db292... (matches the decomp).
- **Dirty build matches retail byte for byte** with the Windows KMC GCC 2.7.2 toolchain (`sh games/dukezh/setup_dirty.sh <zip>`).
- Emulator: the game runs in N64Wasm in headless Edge (dev check with the retail ROM, local only): logos, title,
  menu, rumble-pak screen. Use a free port (8131 belongs to another session; I use 8457).
- EDL codec (`games/dukezh/edl.py`): decoder reads all 1976 real tiles; compressor cross-checked with the decomp's decoder.
- Tiles: facts in `games/dukezh/spec/tiles.json` (1906 ci4, 38 ci4r, 26 pal, 5 ci8, 1 ci4x2), repainted by
  `games/dukezh/generate.py`, each blob padded to its retail slot (layout unchanged). 1490 fit with full detail,
  the rest with less detail/colours (6 end up flat).

## Decisions (log)
- 2026-10-01 **Web route = 3: clean N64 ROM + WASM N64 emulator** (playbook §4).
  Why: there is no PC port of Zero Hour (only the matching decomp and the WIP N64Recomp port DNZHRecomp 0.0.3);
  the decomp is 100% matching and builds a ROM; sibling sessions already ship this route. N64Recomp stays last resort.
  Emulator page: `ports/emu` (N64Wasm, copied from the snowboardkids session; EmulatorJS in bk/dk64 `ports/ejs` as fallback).
- **Compiler = the real KMC GCC 2.7.2 + KMC gas, Windows build** made by the snowboardkids session
  (copied to `D:/n64work/dukezh/tc/kmc`; cross binutils = libdragon mips64-elf via shims in `tc/cross`; env `tools/dz_env.sh`).
  Changes here: `mips-linux-gnu-cpp` shim adds `-mabi=32` and the quotes of `-D__FILE__=` (make on Windows mangles
  them); the gcc driver takes `.i` input without re-running cccp and rewrites `# 0` line markers.
  Makefile patches: `games/dukezh/tree_patches.py`. Build with `mk -j4` (= `make CHECK=0` with retries).
- Decomp: Gillou68310/DukeNukemZeroHour, depth 1, LF, at `D:/n64work/dukezh/pristine` (+ libs submodules).
- **ROM layout kept**: tile blobs are padded to their retail size, so `gTileInfo` (literal sizes in the decomp C) is untouched.
- Kept as facts (please review): code, boot/IPL3, RSP microcode, maps (EDL geometry), `blks` (s16 animation data),
  the 16 0x800-byte `files` chunks (to confirm: demo inputs), song bins (note sequences), bank `.ptr` structure,
  the 26 bare 16-colour palettes among the tiles and the 256-colour table in the decomp's C (colour tables).
- The first ROM that arrived (`D:/Duke Nukem 64 (USA).zip`) is a different game; untouched, not used.

## Asset layout
- `tiles`: 1976 Build-engine tiles, EDL-packed (or bare when tiny), table `gTileInfo`.
  ci4r = odd-width HUD/weapon sprites stored in rows of dimx, cut short.
- `models`: 1604 bins; each has a table of CI4 textures (dimx, dimy, offset) + vertices. **TODO**
- `files`: 26 EDL blobs; eleven unpack to 164352 bytes (full-screen pictures: logos, title, menus). **TODO**
- `sounds`: 16 banks `bankN.ptr/.wbk` (libmus), `sfx.bfx`, 21 song bins. **TODO** (wbk samples)
- Text: `strinfo_us.c` (kept, in the decomp).

## Next
1. First clean-tiles ROM boots in the emulator (building now).
2. Models' textures, pictures (`files`), sound banks; then the taint scan over everything.
3. Readability: font tiles (8x8 glyphs), HUD, sign textures; faces/sprites.
4. Publish when taint = 0 failing; placeholder voices + practice pack.
