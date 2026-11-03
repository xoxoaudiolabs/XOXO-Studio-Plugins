# FM-1 Companion

The FM-1 on [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), as a plug-in, by XOXO Audio Labs. It
brings the [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion)'s FM-1 work to the Studio.

**Status: experimental, not part of the XOXO Studio 0.1 beta, and not yet tried with a real FM-1.** Everything
below has only been tried on a PC, with stand-in devices. The library's jobs write to the FM-1 (restore, projects,
songs, samples, firmware): try them only with a backup you can do without.

## What it does

- **FM-1s as sound and MIDI**: up to four FM-1s on the Studio's USB (Felucca, SLOOP or FM-1 firmware), named
  FM-1 A to FM-1 D by USB port (A: the lowest port), each a sound source in the mixer and a MIDI device in the
  routes under the same name. A Clipper (on an FM-1, or M-Vave's SMK-37) counts as an FM-1 only when no other FM-1
  is plugged in; next to one it's a keyboard with its own mixer channel.
- **HOME** shows what each FM-1 runs ("SLOOP 2.8", or its USB name when its firmware doesn't say).
- **The FM-1 library** (MORE › PLUG-INS › FM-1, and the web page's Library): backups, restores, projects, songs,
  sample slots, DX7 patches and firmware installs, in `~/fm1-library`. Each job runs as its own process. A backup
  is a tap; anything that writes to the FM-1 is a 2 s hold on the Studio's screen, also when the web page asks.
  Firmware can be downloaded from SLOOP's and Clipper's GitHub releases (Clipper: experimental).
- **A linked FM-1 Companion Pocket's FM-1s** as FM-1 E to G, their library jobs run through the Pocket's web API.

| Version | What changed |
|---|---|
| 0.1.0 | FM-1s as sound sources and MIDI devices |
| 0.1.1 | A lone Clipper is the FM-1's sound |
| 0.2.0 | The FM-1 library on the Studio's screen |
| 0.3.0 | Up to four FM-1s by USB port; the web page's Library |
| 0.4.0 | A linked Pocket's FM-1s as FM-1 E-G |
| 0.4.1 | HOME shows what each FM-1 runs |

The XOXO Studio 0.1 beta has the plug-in API this needs (`add_card_names`, `confirm`, `set_detail`, `pocket()`).
The library's jobs need `mido`, which the Studio's installer puts in.

## Tested

All on a PC, against XOXO Studio's own code and stand-in devices (the FM-1 Companion's pretend FM-1):

- **0.1.0-0.1.1** (2026-10-31): found and switched on; two FM-1 sources named FM-1 A and FM-1 B; a Clipper is
  FM-1 A's sound when it's the only FM-1, and its own channel next to a Felucca or SLOOP one; its screen draws.
- **0.2.0** (2026-10-31): the library's jobs against the pretend FM-1 (backup, restore, projects, a sample slot,
  errors), a real job process started by the plug-in, its screens in the Studio's touchscreen code (taps, the 2 s
  hold, a picked file's job).
- **0.3.0** (2026-10-31): a real sound card list (two FM-1s and an SMK-37 running Clipper) gives FM-1 A and B by
  USB port in the mixer and the MIDI routes, the SMK-37 a keyboard; four FM-1s are A-D and a fifth has no letter;
  a write the web page asks for waits for the Studio's hold; the web page's Library shows the job and the files.
- **0.4.0** (2026-10-31): against the FM-1 Companion Pocket's own web server, its jobs pretended
  (`tests/pocket_server.py`): FM-1 E and F are the Pocket's A and B; a backup on E comes back into the Studio's
  library; a restore on F sends the backup first and its safety backup comes back; a file that can't be sent is
  an error.
- **0.4.1** (2026-10-31): HOME's detail for each FM-1: asked once when it appears, "SLOOP 2.8" or its USB name
  when its firmware doesn't answer, gone when it's unplugged.

## Not yet tried

Anything on a real Studio with a real FM-1: the names in the mixer and routes, a backup, a restore, a project,
song, sample or DX7 load, a firmware install or download, MIDI still getting through while a job runs, HOME's
firmware label. A real linked Pocket's FM-1s as E-G. Its screen by hand.

To try first, on a Studio with two FM-1s:

1. Both plugged in: MIXER and the MIDI routes say FM-1 A and FM-1 B, A on the lower USB port. Swap their ports:
   the letters follow.
2. MORE › PLUG-INS › FM-1: BACKUP with each one picked.
3. While a backup runs, play FM-1 A from a keyboard: does the backup finish, do notes still get through?
4. RESTORE that backup (hold 2 s), then the same from the web page (Library › Backups › Restore…).
5. A firmware install with only one FM-1 plugged in (the job refuses with two).

## Tests

From the repository's top folder, with a clone of XOXO Studio next to it (or `XOXO_STUDIO=` its folder), and for
the E-G test a clone of FM-1 Companion next to it too (or `FM1_COMPANION=`): `python -m pytest tests` (needs
`mido`, Pillow and numpy).

## Credits and licence

GPL-3.0 (see the repository's [LICENSE](../LICENSE)).

- The library's code comes from the [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion) (GPL-3.0),
  as `lib/FROM-POCKET.md` lists; `tests/fake_fm1.py` is its pretend FM-1.
- `lib/vendor/sloop/` is copied unchanged from [SLOOP](https://github.com/isod89/sloop-fm1) by isod89 (GPL-3.0),
  based on [Felucca](https://github.com/hugelton/Felucca) by Leo Kuroshita / Hügelton Instruments; see
  `lib/vendor/sloop/VENDORED.md`. `lib/sloop.py` speaks SLOOP's editor protocol.
- SLOOP and Clipper firmware (isod89) aren't included: the library downloads them from their GitHub releases when
  asked, each under its own licence.
