# XOXO Studio Plugins

First-party plug-ins for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), by XOXO Audio Labs. Each
folder is one plug-in, laid out as anyone's would be: `plugin.json` and its Python. How plug-ins work, and the
API they use, is in XOXO Studio's `docs/PLUGINS.md` and its `fm1-bt-bridge/plugins.py`.

| Plug-in | Version | What it does |
|---|---|---|
| [fm1-companion](fm1-companion/) | 0.4.1 | The FM-1 on the Studio: up to four FM-1s, FM-1 A to D by USB port, as sound sources in the mixer and MIDI devices in the routes, the FM-1 keeping the clock; a linked Pocket's three as FM-1 E to G, its library jobs run through the Pocket. A Clipper is an FM-1 only when no other FM-1 is plugged in. The FM-1 library on its screen (MORE › PLUG-INS › FM-1) and the web page: backups, projects, songs, sample slots, DX7 patches and firmware, the FM-1 Companion's own jobs. Card names and the web page need a Studio with the plug-in additions to API 1 |

XOXO Studio's default plug-ins (XO-4, the DJ decks, the Pocket link, the computer link) aren't here: they come
with the Studio.

## Installing a plug-in

On the Studio, plug-ins live in `~/xoxo-plugins/`. Put the plug-in's folder there (or this whole repository: its
plug-ins are found one level down), for example from a PC:

```
scp -r fm1-companion YOUR_USER@xoxostudio.local:~/xoxo-plugins/
```

Then on the Studio's screen: **MORE › PLUG-INS**, tap the plug-in's **OFF** to switch it on (the Studio asks
first: a plug-in is code that runs as the Studio does, so only switch on ones you trust). Its screens open from the
same page. A plug-in that has a problem is switched off by the Studio, with a message, and the Studio carries on.

## Tested

- **fm1-companion 0.1.0** (2026-10-31): on a PC with XOXO Studio's own code and stand-in devices: it's found,
  switched on, names two FM-1 sound sources FM-1 A and FM-1 B (their mixer keys `u-fm1a`, `u-fm1b`), and its
  screen draws. **Not yet tried on a Studio with a real FM-1**.
- **fm1-companion 0.1.1** (2026-10-31): on a PC, as 0.1.0, plus: a Clipper is FM-1 A's sound when it's the only
  FM-1, and its own mixer channel next to a Felucca or SLOOP one. **Not yet tried on a Studio with a real FM-1**.
- **fm1-companion 0.2.0** (2026-10-31): on a PC: the library's jobs against the FM-1 Companion's pretend FM-1
  (backup, restore, projects, a sample slot, errors), a real job process started by the plug-in, and its screens
  in XOXO Studio's own touchscreen code (taps, the 2 s hold, a picked file's job). **Not yet tried on a Studio
  with a real FM-1**: that's where a backup, a restore and a firmware install need trying first.
- **fm1-companion 0.3.0** (2026-10-31): on a PC with XOXO Studio's plug-in additions: the Studio's real sound
  card list (two FM-1s and an SMK-37 running Clipper) gives FM-1 A and B by USB port in the mixer and in the MIDI
  routes, the SMK-37 a keyboard; a lone Clipper is FM-1 A; four FM-1s are A-D and a fifth has no letter; a write
  the web page asks for waits for the Studio's hold; the web page's Library shows the plug-in's job and files and
  sends its commands. **Not yet tried on a Studio with a real FM-1**.
- **fm1-companion 0.4.0** (2026-10-31): on a PC, against the FM-1 Companion Pocket's own web server (its jobs
  pretended, `tests/pocket_server.py`): FM-1 E and F are the Pocket's A and B; a backup on E comes back into the
  Studio's library; a restore on F sends the backup first, runs confirmed, and its safety backup comes back; a
  file that can't be sent is an error. **Not yet tried with a real Pocket**, and the Studio's side of E-G (its
  receivers, sources, MIDI sessions, `pocket()`) is still to be built in XOXO Studio.
- **fm1-companion 0.4.1** (2026-10-31): on a PC: HOME's detail for each FM-1 (`set_detail`): asked once when it
  appears, "SLOOP 2.8" or its USB name ("FELUCCA") when its firmware doesn't answer, gone when it's unplugged.
  **Not yet tried with a real FM-1**.

### On the Studio, with two FM-1s and the SMK-37 Pro

1. Both FM-1s plugged in: MIXER and the MIDI routes say FM-1 A and FM-1 B, A the one on the lower USB port
   (a hub's port counts after the Studio's own). Swap their ports: the letters follow the ports.
2. The SMK-37 Pro: under its own name, a keyboard. If it runs Clipper, unplug both FM-1s: it's FM-1 A then.
3. MORE › PLUG-INS › FM-1: LIBRARY FM-1 A / FM-1 B; BACKUP with each picked (the file names say which firmware).
4. While a backup runs, play FM-1 A from the SMK-37: does the backup finish, and do notes still get through?
5. RESTORE that backup (hold 2 s), then the same from the web page (Library › Backups › Restore…: the Studio's
   screen asks for the hold).
6. A firmware install with only one FM-1 plugged in (the job refuses with two, as the Pocket's does).

Run the tests with a clone of XOXO Studio next to this repository (or `XOXO_STUDIO=` its folder):

```
python -m pytest tests
```

## The FM-1 library: what's next

- **A linked Pocket's FM-1s as FM-1 E-G**: the plug-in's side is here (0.4.0), the Pocket's is built in
  `FM-1-Companion` (not committed). XOXO Studio still needs: receivers for the Pocket's three streams (UDP
  46002/46004/46006), those as mixer sources while linked, each "... Pocket FM-1 A/B/C" network MIDI session its
  own device in the routes, `"pocket_fm1s": true` in its status, and `pocket()` (the Pocket's address) for plug-ins.
- **The FM-1's MIDI while a job runs**: the Studio's MIDI routes hold the FM-1's port too; on a real Studio, check
  a backup and a firmware install don't trip over them.
- **The shared page**: XOXO Studio's `web.py` page now differs from the FM-1 Companion's copy (the Studio-only
  parts); copy it across when the Pocket's is next changed.

## License

GPL-3.0 (see [LICENSE](LICENSE)), like XOXO Studio and the FM-1 Companion it comes from.
