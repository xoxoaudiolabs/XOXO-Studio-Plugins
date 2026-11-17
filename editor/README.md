# Sample editor

The sample editor for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio
Labs. Until 2026-11-17 it was part of the Studio; now it's a plug-in like any other, off until switched on.

| Version | What it does |
|---|---|
| 1.0 | **EDITOR**: a take or a sample full width on the touch screen, its markers dragged; zoom, the fades, NORMALIZE, REVERSE, its note, PLAY, SAVE (a new sample), and TO PAD while the sampler plug-in is on; OPEN lists the samples and takes. A pad's TRIM and "Edit as sample" open it; the web page's Editor works only while it's on |

What it edits and the sums (`sampleui.SampleEditor`, `sampler.py`) are XOXO Studio's own: sampling a pad uses
them, and so does the Pocket's OLED editor. Off, nothing is deleted: the file last edited is kept.

## Installing

As any plug-in (this repository's README). It needs a Studio from 2026-11-17 or later (the plug-in host's
`add_tab` and `add_editor_screen`). A Studio installed before then may have a copy of it in
`~/xoxo-plugins/editor`, put there by its installer.

## Files

`plugin.py` (the EDITOR tab and the touch editor's screen) and `deskeditor.py` (that screen).

## Tested

- **1.0** (2026-11-17), on a PC, against XOXO Studio's own code: the EDITOR tab with an empty file; the Studio with
  it switched off (no EDITOR tab, no TRIM), and on again (`tests/test_editor_studio.py`).
- **On a Studio** (2026-11-17, installed by XOXO Studio's installer before it moved here): listed in MORE ›
  PLUG-INS, off.

### Not yet tried

Switching it on at a Studio and editing there; the web page's Editor in a browser with it on and off; installing
it from this repository on a Studio.

## Tests

With a clone of XOXO Studio beside this repository (or `XOXO_STUDIO=` its folder), Python 3 with pytest, numpy and
Pillow, from this folder:

```
python -m pytest tests
```

## Credits and licences

GPL-3.0, as this repository (its [LICENSE](../LICENSE)). XOXO Audio Labs' own code; nothing copied in.
