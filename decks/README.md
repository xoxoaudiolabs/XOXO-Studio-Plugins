# DJ decks

Two DJ decks for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio Labs.
Until 2026-11-17 they were part of the Studio; now they're a plug-in like any other, off until switched on.

| Version | What it does |
|---|---|
| 1.0 | **DECKS**: two decks playing the Studio DJ Music folder (`~/fm1-library/Studio DJ Music`) or a USB drive: each track's BPM and key (from its tags, Serato's among them, or detected), hot cues, loops, loop rolls, SYNC, EQ, a filter, an FX, PFL and the crossfader; played by touch or from a Hercules DJControl Inpulse 200 MK2 or a learnt DJ controller. Their sound in the mixer (DECKS), MORE › AUDIO › DJ decks out, the web page's DJ decks and DJ music |

The decks are a program of their own (`decks.py`), started when the DECKS tab first opens and stopped when the
plug-in is switched off. While it's on, the Hercules and learnt controllers are the decks' (the manifest's
`"controllers"` and `"controller_maps"`), kept off the MIDI routes; off, a Hercules is a MIDI device in the routes
like any other. Off, nothing is deleted: the music, the learnt maps and the output are kept.

## Installing

As any plug-in (this repository's README). It needs a Studio from 2026-11-17 or later (the plug-in host's
`add_tab`, `add_app_sound`, `add_setting` and the manifest's `"controllers"`). A Studio installed before then may
have a copy of it in `~/xoxo-plugins/decks`, put there by its installer. Decoding uses libsndfile, which the Studio
has (for PipeWire), and ffmpeg where it's installed (AAC).

## Files

`plugin.py` (the DECKS tab, their sound, the setting, the web page's status), `decks.py` (the decks and their
program), `djlib.py` (the music folder's scan; the web page's DJ music uses it), `deskdecks.py` (the DECKS tab).

## Tested

- **1.0** (2026-11-17), on a PC, against XOXO Studio's own code, on made-up tracks: sync, tempo, cues, loops, the
  FX, the scan (`tests/test_decks.py`); the DECKS tab and its learn screens, DECKS in the mixer and on HOME, the
  Hercules off the routes while it's on and back in them off (`tests/test_decks_studio.py`); the web page's DJ
  music, and music refused while it's off (`tests/test_decks_web.py`).
- **On a Studio** (2026-11-17, installed by XOXO Studio's installer before they moved here): listed in MORE ›
  PLUG-INS, off.

### Not yet tried

As a plug-in: switching it on at a Studio, the decks playing there, the Hercules with it on and off, the web page's
DJ music in a browser; installing it from this repository on a Studio.

## Tests

With a clone of XOXO Studio beside this repository (or `XOXO_STUDIO=` its folder), Python 3 with pytest, numpy and
Pillow, from this folder:

```
python -m pytest tests
```

## Credits and licences

GPL-3.0, as this repository (its [LICENSE](../LICENSE)). XOXO Audio Labs' own code; nothing copied in. It runs
libsndfile (LGPL-2.1) and, where installed, ffmpeg (LGPL-2.1 or GPL), from Raspberry Pi OS; neither is copied here.

Not affiliated with Hercules. DJControl Inpulse is a trademark of Hercules (Guillemot Corporation).
