# Duke Nukem: Zero Hour — clean-room web build

Play: https://andrewnakas.github.io/dukezh-cleanroom/

The game code is built from the community decompilation
([Gillou68310/DukeNukemZeroHour](https://github.com/Gillou68310/DukeNukemZeroHour), USA) with the original
KMC GCC 2.7.2. **Every texture, sprite, font, picture and sound sample is regenerated** from coarse facts; no original
pixels or samples are in the ROM that the page runs. It runs on [N64Wasm](https://github.com/nbarkhina/N64Wasm) (MIT).

## What is kept, what is regenerated
- Kept as facts: game code, level geometry (maps), model geometry, animation data, text, music note sequences,
  demo inputs, sound bank structure, RSP microcode and boot code, colour tables.
- Regenerated: 1976 tiles, 5449 model textures, 283 pictures and font glyphs, 1210 sound samples.
  A texture keeps its format, size, a 4x4 colour grid (16x16 for full-screen pictures) and a 2-bit alpha outline.
  A sample keeps its length, loop points, a coarse spectral outline and its median pitch.
- A taint scan compares every generated stream with the retail extraction (`games/dukezh/taint_report.py`).

## Layout
- `games/dukezh/` — the game module: `extract_spec.py` (dirty room: retail -> facts in `spec/`),
  `generate.py` (clean room: facts -> assets), `edl.py` (EDL codec), `tiles.py`, `models.py`, `pics.py`, `sounds.py`,
  `build_clean.sh`, `taint_report.py`.
- `cleanroom/` — shared library (texture painting, VADPCM, descriptors, taint).
- `ports/emu/` — the web page around the emulator.
- `STATUS.md` — state, decisions, what is next.

You need your own copy of the game to run the dirty room. No ROM is in this repository.
