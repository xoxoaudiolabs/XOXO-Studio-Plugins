# XOXO Studio Plugins

Plug-ins for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), the portable Raspberry Pi music
studio, by XOXO Audio Labs. Each folder is one plug-in for the Studio's plug-in host, **API 1**
(`fm1-bt-bridge/plugins.py` in XOXO Studio; the design is its `docs/PLUGINS.md`): a `plugin.json` manifest and its
Python. Anyone can write plug-ins the same way; these are XOXO Audio Labs' own.

XOXO Studio's built-in features (XO-4, the DJ decks, the Pocket link, the computer link) aren't here: they come
with the Studio.

## The plug-ins

| Plug-in | Version | Status | What it does |
|---|---|---|---|
| [synths](synths/) | 0.1.1 | Tried on a Studio | **SYNTH A**: FluidSynth playing a SoundFont, a sound source in the mixer and a MIDI device in the routes; its SoundFont, preset and level on its screen (MORE › PLUG-INS › SYNTHS) |
| [tester-tools](tester-tools/) | 0.2.0 | Tried on a Studio | **LATENCY**: a note sent to a MIDI device, its sound timed coming back into the Studio, five times: the round trip, kept with the Studio's latency step (MORE › PLUG-INS › TESTER, or the web page) |
| [fm1-companion](fm1-companion/) | 0.5.0 | Experimental: not yet tried with a real FM-1 | The FM-1 on the Studio: up to four FM-1s, FM-1 A to D by USB port, as sound sources and MIDI devices; the FM-1 library (backups, projects, songs, sample slots, DX7 patches, firmware) on its screen and the web page, for SLOOP, Clipper, sloopDX, Felucca, JIANT, Melodee, Jangada, Baud Girl's FM-1+VA and M-VAVE's stock firmware; a linked FM-1 Companion Pocket's FM-1s as FM-1 E to G. Not part of the XOXO Studio 0.1 beta |

Each plug-in's README has the details, its version history and everything it's been tried with.

## Installing a plug-in

On the Studio, plug-ins live in `~/xoxo-plugins/`: the host looks for `~/xoxo-plugins/<plug-in>/plugin.json`,
and one level further down, so a clone of this whole repository there works too. On the Studio:

```bash
mkdir -p ~/xoxo-plugins && git clone https://github.com/xoxoaudiolabs/XOXO-Studio-Plugins ~/xoxo-plugins/XOXO-Studio-Plugins
```

or copy one plug-in's folder across from a computer:

```bash
scp -r synths YOUR_USER@YOUR_STUDIO.local:~/xoxo-plugins/
```

Then on the Studio's screen: **MORE › PLUG-INS**, tap the plug-in's **OFF** to switch it on (the Studio asks
first: a plug-in is code that runs as the Studio does, so only switch on ones you trust). Its screen opens from
the same page. A plug-in that raises an error is switched off by the Studio, with a message, and the Studio
carries on. Some plug-ins need packages of their own (Synths: FluidSynth and a SoundFont; see its README).

## Tested and not yet tried

Only what has been tried is listed as tried. The details are in each plug-in's README.

### Synths 0.1.1

- **Tested** on a Studio (Raspberry Pi 3 B+, 2026-11-01): FluidSynth 2.4.4 from Raspberry Pi OS plays into the
  Studio; SYNTH A in the mixer and a destination in the MIDI routes; a Felucca's keys routed to SYNTH A play
  TimGM6mb's Piano 1, heard; FluidSynth took 33 MB and about 8-10% of the processor; level 1.0 sounds right beside
  the other channels. On a PC, with a pretend FluidSynth: its slot process and screen in XOXO Studio's own code.
- **Not yet tried:** another SoundFont or preset on a Studio, a crash and its restart, XO-4 or an FM-1 playing it,
  a Pi 4.

### Tester Tools 0.2.0

- **Tested** on a Studio (Pi 3 B+, 2026-11-01), started from the web page: a Felucca on USB (70 ms round trip at
  SAFE, 55 at LOWEST), a linked Pocket's FM-1 A over network MIDI (177 ms at SAFE), and a following Studio's first
  pad over network MIDI at every latency step (172 ms at SAFE, 87 at LOWEST), five notes of five heard each time.
- **Not yet tried:** its screen by hand (MORE › PLUG-INS › TESTER); a USB synth other than the Felucca.

### FM-1 Companion 0.5.0

- **Tested** only on a PC, against XOXO Studio's own code with stand-in devices (the FM-1 Companion's pretend
  FM-1s for each firmware the library knows, and the FM-1 Companion Pocket's own web server with its jobs
  pretended).
- **Not yet tried:** anything with a real FM-1 or a real Pocket: the FM-1s' names in the mixer and routes, the
  library's jobs (backup, restore, project, song, sample, DX7, firmware install and download), its screen by hand.
  Of the firmwares, only SLOOP has been tried on a real FM-1, and that on the Pocket; the rest only against
  stand-ins.
  The library's jobs write to the FM-1: try them only with a backup you can do without.

## Running the tests

With a clone of [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio) next to this repository (or
`XOXO_STUDIO=` its folder), Python 3 with pytest, mido, Pillow and numpy:

```bash
python -m pytest tests
```

```bash
python -m pytest synths/tests
```

```bash
python -m pytest tester-tools/tests
```

(one run each: each suite sets its own library and runtime folders when it's loaded). `tests` is FM-1 Companion's;
its linked-Pocket test also wants a clone of [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion)
next to this repository (or `FM1_COMPANION=` its folder) and is skipped without one.

## Credits and licences

This repository is GPL-3.0 (see [LICENSE](LICENSE)), like XOXO Studio.

- **FM-1 Companion** builds on the [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion) (GPL-3.0):
  its FM-1 library code and pretend FM-1 (`fm1-companion/lib/FROM-POCKET.md`). It includes two tools copied
  unchanged from [SLOOP](https://github.com/isod89/sloop-fm1) by isod89 (GPL-3.0), based on
  [Felucca](https://github.com/hugelton/Felucca) by Leo Kuroshita / Hügelton Instruments
  (`fm1-companion/lib/vendor/sloop/VENDORED.md`). SLOOP and Clipper firmware (isod89) aren't included; the plug-in
  downloads them from their GitHub releases when asked.
- **Synths** runs [FluidSynth](https://www.fluidsynth.org) (LGPL-2.1) and SoundFonts installed from Raspberry Pi
  OS, each under its own licence; none of them is copied here (the TimGM6mb SoundFont it suggests: Tim Brechbill,
  GPL-2; see [synths/README.md](synths/README.md#credits)). It plays the kind of synths
  [Zynthian](https://zynthian.org) does, but isn't Zynthian and isn't made by its people. It has its own copy of
  the GPL-3.0 ([synths/LICENSE](synths/LICENSE)).
- **Tester Tools** uses PipeWire's `pw-record`, from the Studio's own install.
