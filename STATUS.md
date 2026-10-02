# Duke Nukem: Zero Hour clean room: status

_Last update: 2026-10-01 ~19:10._ **PAUSED: low memory** (the harness killed the background build/taint/voice jobs at ~19:05;
they are not to be restarted unattended). Live site is still the **first pass** from 14:38:
https://andrewnakas.github.io/dukezh-cleanroom/ (repo https://github.com/andrewnakas/dukezh-cleanroom).

## For the morning
- **To resume** (one at a time, when RAM is free):
  1. `python -m games.dukezh.generate D:/n64work/dukezh/clean --only pics` (tiles were regenerated at 19:04)
  2. `GEN=0 sh games/dukezh/build_clean.sh` then a headless check (`ports/emu/shot.py`, Start every 7 s, site on port 8458)
  3. `sh games/dukezh/publish.sh` (taint takes > 20 min on a loaded machine; give it a long timeout)
  4. `python -m games.dukezh.voice_scan D:/n64work/dukezh/dirty D:/n64work/dukezh/voice_scan.json` (Whisper words of
     the 745 candidate speech samples; never ran to completion), then voice_lines.json, Piper placeholders, practice pack.
- Seen working in the emulator (ROM of 18:37, not published): legal screen, "EXPANSION PAK FOUND", menu and message
  fonts, HUD numbers, cutscene terminal text, 3D Realms card, clock menu background.
- Written but **not yet seen in-game**: health icon (tile 5692), thinner terminal font, bar-graph tile 3964 (was a
  garbage patch in the intro cutscene), rounder clock ring, GT / Eurocom cards, "ZER:0 H:0UR" title words.
- The clock ring proportions are a guess (how the 320x512 picture maps to the screen is not pinned down).
- Please review the taint rule for palettised art (see Decisions): decoded RGBA fails at 32 *pixels*, not 32 bytes.
- Not done: faces / model textures, sign textures, level-select thumbnails, placeholder voices, practice pack.

## Hard-won facts
- Text: picture fonts = files 11 (small) / 12 (big), maps in 7FCE0.c; tile fonts = 2822+ (debug), 5682+ (HUD digits),
  6087+/6117+ (messages), **3856+/3866+ (terminal font, drawString2: glyph in the bottom-left 6x7 of a 16x16 cell)**.
- `generate ... | tail -1 && next` hides a crash of generate: check the "tiles written ... drawn N" line (N = 195 now).
- Stale duplicate `serve.py` listeners on one port give ERR_EMPTY_RESPONSE: kill all listeners before serving.
- Local-only reference sheets: `D:/n64work/dukezh/sheets/dirty_pics.png` (what each picture file is), `shots/retail5`.
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
