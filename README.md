# XOXO Studio Plugins

First-party plug-ins for [XOXO Studio](https://github.com/xoxoaudiolabs/XOXO-Studio), by XOXO Audio Labs. Each
folder is one plug-in, laid out as anyone's would be: `plugin.json` and its Python. How plug-ins work, and the
API they use, is in XOXO Studio's `docs/PLUGINS.md` and its `fm1-bt-bridge/plugins.py`.

| Plug-in | Version | What it does |
|---|---|---|
| [fm1-companion](fm1-companion/) | 0.1.1 | The FM-1 on the Studio: FM-1 A and FM-1 B as sound sources in the mixer and as MIDI devices in the routes, the FM-1 keeping the clock. A Clipper is the FM-1's sound when no other FM-1 is plugged in. The FM-1 library (backups, projects, sample slots, firmware) comes in a later version |

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

## License

GPL-3.0 (see [LICENSE](LICENSE)), like XOXO Studio and the FM-1 Companion it comes from.
