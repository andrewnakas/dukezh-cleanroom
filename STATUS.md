# Duke Nukem: Zero Hour clean room: status

_Last update: 2026-10-01 ~14:40._ **Published (first pass)**: https://andrewnakas.github.io/dukezh-cleanroom/
(repo https://github.com/andrewnakas/dukezh-cleanroom). Update with `sh games/dukezh/publish.sh` (refuses if taint fails).

Verified headless: logos -> title -> menus -> intro cutscene -> third-person gameplay, Duke moves with the stick,
HUD present, audio running with signal. Everything is the first-pass colour-grid look: blurry logos/backgrounds,
blobby HUD and small fonts.

## For the morning
- **Play it** in a real browser (arrows = stick, Enter = Start, A = Z/fire, D = A, S = B, J/K/I/L = C buttons).
  Press Start through the menus; the intro cutscene runs about 2 minutes before control starts.
- Please review the taint rule for palettised art (see Decisions): decoded RGBA fails at 32 *pixels*, not 32 bytes.
- Not done yet: readable small fonts / HUD / sign textures, drawn logos and title art, faces, placeholder voices
  and the practice pack.

## Hard-won facts
- The tile loader reads `gTileInfo.filesize` bytes, and most tile bins are padded past that: a regenerated blob must
  fit `filesize`, not the bin size (one 4-byte overrun in tile 6091 blacked out all gameplay; found by ddmin).
- Headless runs: press Start every 7 s (`range(40,130,7)`); fixed key times are unreliable under CPU load.
- Port 8131 belongs to another session; this one uses 8457 (dev, retail, local only) and 8458 (clean site).

## Works
- **All four asset classes are regenerated** (`python -m games.dukezh.extract_spec <dirty>`, `generate <clean>`):
  1976 tiles, 5449 model textures (1604 bins), 283 pictures/glyphs in 21 picture files (logos, title, menu
  backgrounds, two fonts, 3D menu letter textures), 1210 sound samples in 16 banks (25.9 M frames).
- **Taint: 19,750 streams, 0 failing** (`python -m games.dukezh.taint_report <dirty> <clean>`).
- Clean ROM builds (`GEN=0 sh games/dukezh/build_clean.sh`), same 32 MB layout; boots to the menus in N64Wasm.
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
- **Tile storage type is kept** (bare or EDL, as retail), and every tile keeps its unpacked length.
- **Taint rule for palettised art**: index streams, packed blobs, ADPCM and PCM fail at a 32-byte shared run. Decoded
  RGBA of CI4/CI8 art fails at 32 *pixels* (128 B): two common 5-bit colours meeting at an edge of flat bands coincide
  constantly (4 bytes per pixel carry at most 4-8 bits). Longest coincidental RGBA run now: 111 B (27 px).
- Sounds: all samples are VADPCM order 2 with 4 predictors; ours are written with our own books in the same
  space (two designed predictors, repeated). The bank has no sample rate (libmus tunes by note), 22050 Hz is
  only the analysis convention.
- Picture files 16-27 are the 3D menu objects: meshes + uv (kept), textures + palettes (regenerated).
  The sixteen 0x800-byte chunks at the start of `files` are demo input recordings (kept).
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
