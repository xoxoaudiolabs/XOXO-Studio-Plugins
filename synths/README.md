# Synths

Software synths on [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio Labs:
the synth programs [Zynthian](https://zynthian.org) plays, on the Studio. Zynthian itself is a whole system (its
own image, screen and sound card), so it can't run inside the Studio; its synths can. This isn't Zynthian and
isn't made by its people.

| Version | What it does |
|---|---|
| 0.1.0 | **SYNTH A**: [FluidSynth](https://www.fluidsynth.org) playing a SoundFont. A sound source in the Studio's mixer and a MIDI device in its routes, both called SYNTH A, so a MIDI keyboard routed to it plays it. Its screen (MORE › PLUG-INS › SYNTHS): on or off, the SoundFont, the preset. HOME shows the preset's name beside SYNTH A |
| 0.1.1 | Louder: SYNTH A's level 1.0 (0.1.0's was 0.5, quiet beside the other channels), and LEVEL − / + on its screen (0.4 to 2.0) |

Its sound in the mixer needs a Studio with `add_sound_source` (a plug-in addition to API 1, in the XOXO Studio 0.1
beta); on an older Studio SYNTH A is only a MIDI device.

## Installing

On the Studio, the synth and a General MIDI SoundFont (6 MB, fine on a 1 GB Pi):

```
sudo apt install fluidsynth timgm6mb-soundfont
```

`fluid-soundfont-gm` (FluidR3, a bigger General MIDI SoundFont, about 140 MB in memory) is meant for a Pi 4; not
yet tried on the Studio. Then the plug-in's folder into
`~/xoxo-plugins/` and **MORE › PLUG-INS**, as for any plug-in (XOXO-Studio-Plugins' README).

Your own SoundFonts (.sf2, .sf3) go in `~/fm1-library/soundfonts/`; the system's are found in
`/usr/share/sounds/sf2`, `/usr/share/sounds/sf3` and `/usr/share/soundfonts`.

## How it runs

- Each synth is its own process (`lib/slot.py`, a systemd user unit), so a synth that crashes or takes too much
  doesn't stop the Studio. It stops itself 10 s after the plug-in stops ticking (switched off, the Studio stopped).
- Its sound: a `pw-loopback` pair, as XO-4's (the engine plays into `synths-a-in`; `synths-a` is the mixer's
  SYNTH A). FluidSynth reaches it through its PipeWire driver (`PIPEWIRE_NODE`).
- Its MIDI: FluidSynth's ALSA sequencer client, `FLUID Synth (synths-a)`.
- The SoundFont and preset: through FluidSynth's shell on a pipe (never its TCP shell, which would listen on every
  network the Studio is on). A preset is picked on all 16 MIDI channels.

## Tested

- **0.1.0** (2026-11-01): on a PC, with a pretend FluidSynth: a SoundFont's presets read from the file; the slot
  process loads the SoundFont, picks the preset, lets an old SoundFont go, says when the engine stops or a
  SoundFont won't load, and stops when the plug-in does; in XOXO Studio's own code: SYNTH A in the mixer and the
  MIDI routes, its screen (on/off, SoundFonts, presets), the web commands, the plug-in starting and stopping its
  slot.
- **0.1.0 on the Studio** (2026-11-01, a Raspberry Pi 3 B+, XOXO Studio f62b576): FluidSynth 2.4.4 from Raspberry
  Pi OS plays into `synths-a-in`; SYNTH A in the mixer and a destination in the MIDI matrix; the Felucca's keys
  routed to SYNTH A play TimGM6mb's Piano 1, heard. FluidSynth: 33 MB, about 8-10% of the processor. Not yet
  tried: another SoundFont or preset on the Studio, a crash and its restart, XO-4 playing it.
- **0.1.1 on the Studio** (2026-11-01): level 1.0 sounds right beside the other channels.

### Still to try on a Studio

1. Install the packages, switch Synths on: SYNTH A in MIXER and in the MIDI routes, HOME shows its preset.
2. Route the SMK-37 to SYNTH A: notes, how quickly they sound, no crackles; change the SoundFont and the preset.
3. XO-4 or an FM-1 playing at the same time; how busy the Pi is (`top`).
4. `pkill fluidsynth`: the Studio carries on, the screen says so, SYNTH A starts again after 30 s.
5. Switch the plug-in off: SYNTH A goes from the mixer within 10 s.

`apt install fluidsynth` also brings qsynth, Qt, GTK and FluidR3 (148 MB) as its recommendations; with
`--no-install-recommends` it doesn't (then install `timgm6mb-soundfont` by name, as above).

SYNTH A as a destination in the MIDI routes needs XOXO Studio f62b576 or later (the 0.1 beta has it); before it,
SYNTH A is only in the mixer.

## What's next

setBfree (organ) and ZynAddSubFX, a SYNTH B with a check of how busy the Pi is first, rows on the web page, the
Studio remembering each synth's sound with a song.

## Tests

With a clone of XOXO Studio next to this repository (or `XOXO_STUDIO=` its folder), from this folder:

```
python -m pytest tests
```

## License

GPL-3.0 (see [LICENSE](LICENSE)). FluidSynth (LGPL-2.1) and the SoundFonts are installed from Raspberry Pi OS,
each under its own licence; none of them is copied here.

## Credits

- **[FluidSynth](https://www.fluidsynth.org)**, the synth engine: by the FluidSynth project, LGPL-2.1+ (Raspberry
  Pi OS's `fluidsynth` package).
- **TimGM6mb**, the General MIDI SoundFont the install above suggests: by
  [Tim Brechbill](https://www.timbrechbill.com) (2004), changes by David Bolton (2010), GPL-2 (Raspberry Pi OS's
  `timgm6mb-soundfont` package). Played in something you share, a credit to Tim Brechbill is the decent thing.
- **FluidR3_GM** (`fluid-soundfont-gm`), if you install it: by Frank Wen (2000-2002, 2008), MIT.
