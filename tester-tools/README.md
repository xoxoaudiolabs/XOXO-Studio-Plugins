# Tester Tools

Small tools for testing XOXO Studio and its gear, as a plug-in. Its screen: **MORE › PLUG-INS › TESTER**.
GPL-3.0, by XOXO Audio Labs.

| Version | What changed |
|---|---|
| 0.1.0 | LATENCY: a note out, its sound timed back in |
| 0.2.0 | The web command takes a `note` (36 plays a Studio's first pad, for timing a Studio that follows another); NET picks its own sound: POCKET for a linked Pocket, else STUDIO |

## LATENCY

How long from a note leaving the Studio to its sound coming back in, measured on the Studio itself:

1. **MIDI TO**: the device to play (a linked Pocket's **POCKET FM-1 A**, **NET** for a linked Pocket's or a
   following Studio's whole session, or a USB device such as an FM-1).
2. **SOUND**: where its sound comes back (picked for you when it has the same name as the device).
3. **START**: all notes off (every channel) and a wait for quiet, then it listens to the sound for 0.4 s (its
   noise), and plays middle C five times, each when a known number of samples has come in, and finds the first
   sample over the noise after it.

The result is the round trip: MIDI out, the synth, its sound back through the Studio's capture. The one-way
sound delay is less than that. It's accurate to about one of the Studio's audio blocks (SAFE: 21 ms, LOW: 11,
LOWER: 5, LOWEST: 3). Each result is kept with the Studio's latency step, so the steps can be compared: the
last four on the screen, eight on the web page (`plugins.tester-tools.results`). The web page can start one:
command `latency` with `device`, `source` and, from 0.2.0, `note` (0-127, 60 when left out).

For the Pocket link: run it at SAFE, then step MORE › AUDIO › Latency down and run it again at each step,
listening for clicks too.

Needs a Studio with `send_midi`, `midi_devices`, `source_nodes` (in the XOXO Studio 0.1 beta).

## Tests

`python -m pytest tests`: the test against a pretend synth whose sound comes back a known number of samples after
the note; pw-record's AU stream; the plug-in in XOXO Studio's own code (a clone next to this repository's folder).

## Tested

- **0.1.0** (2026-11-01): on a PC: the pretend synth's delay comes out exactly, five notes, each note off and all
  notes off after; nothing back is an error; the AU stream both ways round; in XOXO Studio's plug-in host the
  Pocket's FM-1 A and its sound are picked, START sends through `send_midi`, and the result is kept with SAFE.
- **0.1.0 on the Studio** (Pi 3 B+, 2026-11-01), started from the web page: the Felucca on USB, 70 ms round trip
  at SAFE (all five heard; the same code by hand: 68.5 ms), 67 at LOW, 57 at LOWER, 55 at LOWEST; a linked
  Pocket's FM-1 A through NET, 177 ms at SAFE (165-200, five of five). A note still sounding from before (a
  Pocket's FM-1 whose note-offs were lost) spoilt runs until it sent all notes off first (now on every channel,
  then waits for quiet). The first run on a Felucca heard nothing (its input sends silence when just opened): it
  now makes a second attempt afresh.
- **0.2.0 on two Studios** (2026-11-01), started from the leader's web page: NET, STUDIO, note 36 timed the
  following Studio's first pad at every Latency step: SAFE 172 ms round trip, LOW 128, LOWER 87-107 (two runs),
  LOWEST 87, five of five heard.

## Not yet tried

Its screen by hand (MORE › PLUG-INS › TESTER); picking the note on the screen (the note is web-only); NET's
STUDIO picked on the screen with no source given; SYNTH A or another USB synth than the Felucca.
