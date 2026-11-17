# Sampler

The 16-pad sampler for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio
Labs. Until 2026-11-17 it was part of the Studio; now it's a plug-in like any other, off until switched on.

| Version | What it does |
|---|---|
| 1.0 | **PADS**: 4×4 pads (pad 1 bottom left, as on an MPC), played by touch or from the MIDI routes' SMP column (notes 36–51 on any channel) while its **MIDI IN** is on. **KIT** (load, save, new; the 808 KIT the first time), **RPT** (note repeat), **FX** (sixteen punch-in FX on the pads' sound: hold one, or LATCH it), **EDIT** a pad (sample, level, pan, tune, one-shot / gate / loop, attack, release, choke group, reverse; PLAY, SAMPLE from any source, TRIM in the sample editor while that plug-in is on, CLEAR). PADS in the mixer, the meters and Record parts; the web page's kits |

Its pads run in a process of their own, started with the Studio app (the manifest's `"process": "pads"`), so
switching it on or off starts the Studio app again (`"restart": true`). Its kit, note repeat and MIDI IN are its
settings; a Studio from before keeps its kit and note repeat (they're moved into the plug-in's settings).

## Installing

As any plug-in (this repository's README): this folder in `~/xoxo-plugins/`, or a clone of the whole repository
there, then **MORE › PLUG-INS**. It needs a Studio from 2026-11-17 or later (the plug-in host's `add_tab`,
`process` and the manifest's `"process"`). A Studio installed before then may have a copy of it in
`~/xoxo-plugins/sampler`, put there by its installer.

## Files

- `plugin.py`: the plug-in (the PADS tab, PADS in the mixer, the web page's kits, its settings).
- `pads.py`: the pads' engine and process; `padfx.py`: the punch-in FX; `padkit.py`: the kit in the settings;
  `deskpads.py`: the PADS tab and its pages.
- `kits/808/`: the 808 KIT's sixteen sounds; `kits/make_kits.py` made them once on a computer.

## Tested

- **1.0** (2026-11-17), on a PC, against XOXO Studio's own code: the pads' voices, chokes, envelopes, kits and FX
  (`tests/test_pads.py`, `tests/test_padfx.py`); the plug-in in the Studio: the PADS tab and its pages, PADS in the
  mixer and in the USB-C link's feeds, the web page's kits, the Bluetooth warning, the tab bar, MORE › PLUG-INS
  listing it off until switched on, the restart (`tests/test_sampler_studio.py`).
- **On a Studio** (2026-11-17, installed by XOXO Studio's installer before it moved here): listed in MORE ›
  PLUG-INS, off; with it off, no pads process runs.

### Not yet tried

Switching it on at a Studio; the pads playing from its own process; SEQ playing it through the route SEQ › SMP;
its MIDI IN from a keyboard; installing it from this repository on a Studio.

## Tests

With a clone of XOXO Studio beside this repository (or `XOXO_STUDIO=` its folder), Python 3 with pytest, numpy and
Pillow, from this folder:

```
python -m pytest tests
```

## Credits and licences

GPL-3.0, as this repository (its [LICENSE](../LICENSE)).

- The sixteen punch-in FX (`padfx.py`) and the pads' drum order are from
  [SLOOP](https://github.com/isod89/sloop-fm1) by isod89 (GPL-3.0; its `punch.c`), rewritten in Python.
- The 808 KIT (`kits/808/`): sixteen recordings of a real Roland TR-808 by Michael Fischer (1994), from
  [tidalcycles/sounds-tr808-fischer](https://github.com/tidalcycles/sounds-tr808-fischer), **CC0 1.0**
  ([kits/808/CREDITS.md](kits/808/CREDITS.md), [kits/808/LICENSE](kits/808/LICENSE)).

Not affiliated with Roland. TR-808 is a trademark of Roland Corporation.
