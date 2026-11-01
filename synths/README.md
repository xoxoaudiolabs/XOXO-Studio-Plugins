# Synths

Software synths on [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio Labs:
the synth programs [Zynthian](https://zynthian.org) plays, on the Studio. Zynthian itself is a whole system (its
own image, screen and sound card), so it can't run inside the Studio; its synths can. This isn't Zynthian and
isn't made by its people.

| Version | What it does |
|---|---|
| 0.1.0 | **SYNTH A**: [FluidSynth](https://www.fluidsynth.org) playing a SoundFont. A sound source in the Studio's mixer and a MIDI device in its routes, both called SYNTH A, so a keyboard, an FM-1 or XO-4 plays it. Its screen (MORE › PLUG-INS › SYNTHS): on or off, the SoundFont, the preset. HOME shows the preset's name beside SYNTH A |

Its sound in the mixer needs a Studio with `add_sound_source` (a plug-in addition to API 1); on an older Studio
SYNTH A is only a MIDI device.

## Installing

On the Studio, the synth and a General MIDI SoundFont (6 MB, fine on a 1 GB Pi):

```
sudo apt install fluidsynth timgm6mb-soundfont
```

On a Pi 4, `fluid-soundfont-gm` (FluidR3, about 140 MB in memory) sounds better. Then the plug-in's folder into
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
  slot. **Not yet tried on a Studio with the real FluidSynth.**

### On the Studio (a Pi 3 B+ or 4, the SMK-37 Pro)

1. Install the packages, switch Synths on: SYNTH A in MIXER and in the MIDI routes, HOME shows its preset.
2. Route the SMK-37 to SYNTH A: notes, how quickly they sound, no crackles; change the SoundFont and the preset.
3. XO-4 or an FM-1 playing at the same time; how busy the Pi is (`top`).
4. `pkill fluidsynth`: the Studio carries on, the screen says so, SYNTH A starts again after 30 s.
5. Switch the plug-in off: SYNTH A goes from the mixer within 10 s.

To check on the Studio: that Raspberry Pi OS's FluidSynth has its PipeWire driver and follows `PIPEWIRE_NODE` to
`synths-a-in` (if not, its sound goes to the speaker directly, outside the mixer).

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
