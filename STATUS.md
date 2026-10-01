# Duke Nukem: Zero Hour clean room: status

**BLOCKED: ROM** (2026-10-01 09:25). The file that arrived, `D:/Duke Nukem 64 (USA).zip`, is **Duke Nukem 64**
(8 MB, game code NDNE, sha1 98d67780...), a different game. Needed: **Duke Nukem: Zero Hour (USA)**, 32 MB,
sha1 `de4db292cc6cf5dd1dd1d3c9700cf8e5c3078410` (from the decomp's yaml). Put the zip/z64 in `C:/Users/andre/Downloads`
or `D:/`; the loop looks in both. Everything that needs no ROM is done (below).

## For the morning
- Nothing to play yet. If the ROM is somewhere else, put the zip/z64 in Downloads with "Duke" in the name.

## Decisions (log)
- 2026-10-01 **Web route = 3: clean N64 ROM + WASM N64 emulator** (playbook §4).
  Why: there is no PC port of Zero Hour (only the matching decomp and the WIP N64Recomp port DNZHRecomp 0.0.3);
  the decomp is 100% matching and builds a ROM; sibling sessions already ship this route. N64Recomp stays last resort.
  Emulator page: `ports/emu` (N64Wasm, copied from the snowboardkids session; EmulatorJS in bk/dk64 `ports/ejs` as fallback).
- **Compiler = the real KMC GCC 2.7.2 + KMC gas, Windows build** made by the snowboardkids session
  (copied to `D:/n64work/dukezh/tc/kmc`; cross binutils = libdragon mips64-elf via shims in `tc/cross`; env `tools/dz_env.sh`).
  Changes here: `mips-linux-gnu-cpp` shim adds `-mabi=32`; the gcc driver takes `.i` input without re-running cccp
  and rewrites `# 0` line markers (modern cpp emits them, cc1 2.7.2 rejects them).
  Verified: a libultra file compiles and disassembles. Game files need splat's `gen/us/ld_symbols.h` (needs the ROM).
- Decomp: Gillou68310/DukeNukemZeroHour, depth 1, LF, at `D:/n64work/dukezh/pristine` (+ libs submodules).
  DNZHRecomp at `D:/n64work/dukezh/recomp` (reference only).
- Build flags for Windows: `make CHECK=0` (the host `gcc -m32` syntax check is skipped), `-j4`.

## Asset layout (read from the decomp, no ROM needed)
- `tiles` 0x11FC80-0x385980: 6143 Build-engine tiles, each EDL-compressed, table `gTileInfo` (0x1C per entry:
  fileoff, size, dims, flags). Kinds: CI4 + own 16-colour palette, CI4 half-height, CI8 with external palette, palettes.
- `models` from 0x385980: ~1600 model bins; each has a table of CI4 textures (dimx, dimy, offset) + vertices.
- maps: 4 EDL blobs each (vertex, walls, sectors, sprites) = geometry, kept.
- sounds: libmus `bankN.ptr/.wbk` + ambient/music song bins (sequences kept, wbk samples regenerated).
- Text: `strinfo_us.c` (kept, in the decomp).
- EDL: the decomp has only a decompressor, so `games/dukezh/edl.py` is our own EDL1 compressor (deflate-like:
  hash-chain LZ77 + canonical Huffman capped at 10/8 bits). Verified against the decomp's Python decoder on synthetic
  data. To check on real data: whether the header's packed size includes the 12-byte header (currently: yes).

## Next (once the ROM is there)
1. `sh games/dukezh/setup_dirty.sh "<zip>"`: sha1, split, dirty build must match.
2. Census + spec of tiles / model textures / wbk samples; generate; clean build; taint.
3. Emulator page, headless shots, publish.
4. Readability (fonts, HUD, text tiles), faces/sprites, placeholder voices + practice pack.
