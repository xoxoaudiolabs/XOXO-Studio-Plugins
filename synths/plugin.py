"""Synths for XOXO Studio: software synths as sound sources, as a plug-in (XOXO Studio's docs/PLUGINS.md).

The synth programs Zynthian plays, on the Studio: Zynthian itself is a whole system (its own image, screen and
sound card), so it can't be a plug-in; its synths can.
  - SYNTH A: FluidSynth playing a SoundFont (0.1). Its sound a source in the Studio's mixer (add_sound_source:
    needs a Studio that has it), its MIDI a device in the routes under the same name, so a keyboard, an FM-1 or
    XO-4 plays it
  - the SYNTHS screen (MORE > PLUG-INS > SYNTHS): the slot on or off, its SoundFont, its preset. The SoundFonts:
    ~/fm1-library/soundfonts (the web page's, plugin.json "library") and the system's (/usr/share/sounds/sf2, sf3:
    timgm6mb-soundfont, fluid-soundfont-gm). HOME shows the preset's name beside SYNTH A (set_detail)
  - each slot runs as its own process (lib/slot.py, a systemd user unit on the Studio): a synth that crashes or
    takes too much doesn't stop the Studio, and it stops itself when the plug-in is switched off or the Studio
    stops (the plug-in touches its .alive file on each tick)

Later: setBfree and ZynAddSubFX, SYNTH B, the web page's rows.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

API = 1
VERSION = "0.1.1"

HERE = Path(__file__).resolve().parent
SLOT = HERE / "lib" / "slot.py"
LIBRARY = Path(os.environ.get("FM1_LIBRARY", Path.home() / "fm1-library")) / "soundfonts"
SYSTEM_FONTS = [Path(p) for p in os.environ.get("SYNTHS_FONTS", os.pathsep.join(
    ("/usr/share/sounds/sf2", "/usr/share/sounds/sf3", "/usr/share/soundfonts"))).split(os.pathsep) if p]
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
SUFFIXES = (".sf2", ".sf3")
SLOTS = "A"                                     # (B: later, with a CPU check first)
DEFAULT_FONTS = ("TimGM6mb.sf2", "FluidR3_GM.sf2", "FluidR3_GM.sf3", "MuseScore_General.sf3")
LEVELS = (0.4, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0)      # FluidSynth's gain, picked on the screen (0.1.0: 0.5, quiet)
LEVEL = 1.0
RETRY = 30.0                                    # s before a slot that stopped with an error is started again
ROWS = 4                                        # presets on the screen at once


def load_lib(name):
    spec = importlib.util.spec_from_file_location(f"xoxo_synths_{name}", HERE / "lib" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sf2 = load_lib("sf2")


def fonts():
    """the SoundFonts there are: the library's, then the system's; by name, one of each name"""
    found = {}
    for folder in [LIBRARY, *SYSTEM_FONTS]:
        try:
            for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
                if (p.is_file() and not p.is_symlink() and p.suffix.lower() in SUFFIXES   # (default-GM.sf2: a
                        and not p.name.startswith(".")):                                # link to one of them)
                    found.setdefault(p.name, p)
        except OSError:
            continue
    return sorted(found.values(), key=lambda p: p.name.lower())


_presets = {}


def presets(path):
    """[(bank, program, name)] of a SoundFont ([] if it can't be read), read again only when the file changes"""
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return []
    if key not in _presets:
        try:
            _presets[key] = sf2.presets(path)
        except sf2.SoundFontError:
            _presets[key] = []
    return _presets[key]


def alive(pid):
    if os.name == "nt":                         # (os.kill there ends the process: PC test runs only)
        return True
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def read_json(path):
    try:
        found = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


class Synth:
    """one slot: its settings (on, font, bank, program, level under settings["slots"][letter]), its process
    (lib/slot.py) started, kept alive and told the sound wanted; what it says read back on each tick"""

    def __init__(self, studio, letter):
        self.studio, self.letter, self.slot = studio, letter, letter.lower()
        self.name = f"SYNTH {letter}"
        self.files = {k: RUNTIME / f"synths-{self.slot}.{k}" for k in ("json", "alive", "want")}
        self.started, self.detail = 0.0, None

    @property
    def conf(self):
        slots = self.studio.settings.setdefault("slots", {})
        conf = slots.setdefault(self.letter, {})
        conf.setdefault("on", True)
        if conf.get("level") not in LEVELS:
            conf["level"] = LEVEL
        conf.pop("gain", None)                  # (0.1.0's, always 0.5)
        if not conf.get("font"):
            names = [p.name for p in fonts()]
            conf["font"] = next((n for n in DEFAULT_FONTS if n in names), names[0] if names else None)
        return conf

    def font(self):
        """the slot's SoundFont's path, or None"""
        return next((p for p in fonts() if p.name == self.conf.get("font")), None)

    def preset(self):
        """(bank, program, name) of the preset picked, or None: the SoundFont's first, if it hasn't that one"""
        found = presets(self.font()) if self.font() else []
        conf = self.conf
        return next((p for p in found if p[:2] == (conf.get("bank", 0), conf.get("program", 0))),
                    found[0] if found else None)

    def state(self):
        """the slot process's state ({"state": starting / running / stopped / error, ...}), None if it hasn't one"""
        state = read_json(self.files["json"])
        if state and state.get("state") in ("starting", "running") and not alive(state.get("pid")):
            state = dict(state, state="error", message="it stopped without saying why")
        return state

    def running(self):
        state = self.state()
        return bool(state) and state.get("state") in ("starting", "running")

    # ---- what the plug-in does on each tick

    def tick(self):
        if not self.conf.get("on"):
            if self.running():
                self.stop()
            self.show(None)
            return
        RUNTIME.mkdir(parents=True, exist_ok=True)
        self.files["alive"].touch()
        self.want()
        state = self.state() or {}
        if state.get("state") in ("starting", "running") or time.monotonic() - self.started < 3:
            self.show(self.preset()[2] if self.preset() and state.get("state") == "running" else None)
            return
        if state.get("state") == "error" and time.monotonic() - self.started < RETRY:
            self.show(None)
            return
        self.start()

    def want(self):
        """the sound wanted, for the slot process (a new id only when it changes)"""
        preset, font = self.preset(), self.font()
        want = {"font": str(font) if font else None, "bank": preset[0] if preset else 0,
                "program": preset[1] if preset else 0, "gain": float(self.conf["level"])}
        had = read_json(self.files["want"]) or {}
        if {k: had.get(k) for k in want} != want:
            tmp = self.files["want"].with_name(self.files["want"].name + ".tmp")
            tmp.write_text(json.dumps(dict(want, id=time.time_ns())))
            try:
                os.replace(tmp, self.files["want"])
            except PermissionError:             # (the slot reading it, on Windows: next tick)
                pass

    def start(self):
        """lib/slot.py in the background -> an error message, or None"""
        command = [sys.executable, str(SLOT), "--slot", self.slot]
        if shutil.which("systemd-run"):
            command = ["systemd-run", "--user", "--collect", "--quiet", f"--unit=synths-{self.slot}-{time.time_ns()}",
                       *command]
        self.started = time.monotonic()
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            return str(e)
        return None

    def stop(self):
        """the slot process told to stop (it would anyway, 10 s after the last touch)"""
        try:
            self.files["alive"].unlink()
        except OSError:
            pass
        state = self.state() or {}
        if state.get("pid") and os.name != "nt":
            try:
                os.kill(int(state["pid"]), 15)
            except (OSError, ValueError):
                pass

    def show(self, text):
        """HOME's few words beside SYNTH A: the preset playing"""
        if text != self.detail and hasattr(self.studio, "set_detail"):
            self.studio.set_detail(self.name, text[:16] if text else None)
        self.detail = text

    # ---- what a tap does

    def set_on(self, on):
        self.conf["on"] = bool(on)
        self.studio.save()
        if not on:
            self.stop()

    def set_font(self, step):
        """the next (step 1) or the one before (-1) SoundFont"""
        found = [p.name for p in fonts()]
        if not found:
            return
        at = found.index(self.conf["font"]) if self.conf.get("font") in found else -step
        self.conf["font"] = found[(at + step) % len(found)]
        first = presets(self.font())[:1]
        self.conf["bank"], self.conf["program"] = first[0][:2] if first else (0, 0)
        self.studio.save()

    def set_level(self, step):
        """a step louder (1) or quieter (-1)"""
        at = LEVELS.index(self.conf["level"])
        self.conf["level"] = LEVELS[max(0, min(at + step, len(LEVELS) - 1))]
        self.studio.save()

    def set_preset(self, bank, program):
        self.conf["bank"], self.conf["program"] = int(bank), int(program)
        self.studio.save()

    def text(self):
        """what the slot is doing, in a few words"""
        if not self.conf.get("on"):
            return "OFF"
        if not self.font():
            return "NO SOUNDFONT: SEE THE README"
        state = self.state() or {}
        if state.get("state") == "error":
            return ("ERROR: " + str(state.get("message") or "")).upper()
        if state.get("message"):
            return str(state["message"]).upper()
        if state.get("state") == "running":
            return "PLAYING"
        return "STARTING"

    def web_status(self):
        preset = self.preset()
        return {"on": bool(self.conf.get("on")), "text": self.text(), "font": self.conf.get("font"),
                "level": self.conf["level"],
                "preset": list(preset) if preset else None}


class SynthsScreen:
    """MORE > PLUG-INS > SYNTHS: the slot on or off, its SoundFont, its presets (480x320: 34 header)"""

    def __init__(self, ui, studio, synths):
        self.ui, self.studio, self.synths = ui, studio, synths
        self.synth, self.top = synths[0], None

    def view(self, now):
        conf = self.synth.conf
        return (self.synth.letter, self.top, conf.get("on"), conf.get("font"), conf.get("bank"), conf.get("program"),
                conf.get("level"), self.synth.text())

    def scroll(self, step):
        self.top = max(0, min((self.top or 0) + step, len(self.list()) - ROWS))

    def list(self):
        return presets(self.synth.font()) if self.synth.font() else []

    def font(self, step):
        self.synth.set_font(step)
        self.top = None

    def draw(self, img, d, now):
        ui, t, synth = self.ui, self.ui.theme, self.synth
        conf = synth.conf
        ui.centre(img, (4, 40, 104, 70), synth.name, t.hi)
        ui.button(img, d, (108, 40, 188, 70), "ON" if conf.get("on") else "OFF",
                  lambda: synth.set_on(not conf.get("on")), on=bool(conf.get("on")), key="synths-on")
        ui.centre(img, (192, 40, 330, 70), synth.text()[:16], t.c[3])
        ui.button(img, d, (334, 40, 370, 70), "-", lambda: synth.set_level(-1), key="synths-level-down")
        ui.centre(img, (372, 40, 436, 70), f"LVL {conf['level']:.1f}", t.hi)
        ui.button(img, d, (440, 40, 476, 70), "+", lambda: synth.set_level(1), key="synths-level-up")
        ui.button(img, d, (4, 76, 56, 104), "<", lambda: self.font(-1), key="synths-font-prev")
        ui.centre(img, (60, 76, 420, 104), (conf.get("font") or "NO SOUNDFONT")[:40], t.hi)
        ui.button(img, d, (424, 76, 476, 104), ">", lambda: self.font(1), key="synths-font-next")
        found = self.list()
        picked = synth.preset()
        if self.top is None:                    # (opened, or a new SoundFont: its preset in view)
            at = found.index(picked) if picked in found else 0
            self.top = max(0, min(at - 1, len(found) - ROWS))
        if not found:
            ui.centre(img, (4, 110, 476, 230), "NO PRESETS: PUT A .SF2 IN ~/FM1-LIBRARY/SOUNDFONTS", t.c[3])
        for row, preset in enumerate(found[self.top:self.top + ROWS]):
            y = 110 + row * 30
            bank, program, name = preset
            ui.button(img, d, (4, y, 420, y + 26), f"{bank:03d}-{program:03d}  {name}"[:44],
                      lambda b=bank, p=program: synth.set_preset(b, p), on=preset == picked,
                      key=("synths-preset", bank, program))
        if len(found) > ROWS:
            ui.button(img, d, (424, 110, 476, 164), "UP", lambda: self.scroll(-ROWS), key="synths-up")
            ui.button(img, d, (424, 170, 476, 224), "DOWN", lambda: self.scroll(ROWS), key="synths-down")
        said = synth.text()
        ui.centre(img, (4, 236, 476, 262), said[:58] if len(said) > 16 else f"PLAY IT FROM THE MIDI ROUTES: {synth.name}",
                  t.c[3] if len(said) > 16 else t.c[2])


def setup(studio):
    synths = [Synth(studio, letter) for letter in SLOTS]
    for synth in synths:
        if hasattr(studio, "add_sound_source"):     # (an older Studio: its MIDI only, its sound not in the mixer)
            studio.add_sound_source(f"synths-{synth.slot}", synth.name)
        studio.add_midi_device(rf"^FLUID Synth \(synths-{synth.slot}\)", synth.name)
    studio.add_screen("SYNTHS", lambda ui, s: SynthsScreen(ui, s, synths))

    def status():
        return {"version": VERSION, "slots": {s.letter: s.web_status() for s in synths},
                "fonts": [p.name for p in fonts()]}

    def command_on(args):
        synth = next((s for s in synths if s.letter == str(args.get("slot", "A")).upper()), None)
        if synth is None:
            return f"slot: {SLOTS}"
        synth.set_on(bool(args.get("on")))
        return f"{synth.name} {'on' if synth.conf['on'] else 'off'}"

    def command_preset(args):
        synth = next((s for s in synths if s.letter == str(args.get("slot", "A")).upper()), None)
        if synth is None:
            return f"slot: {SLOTS}"
        if args.get("font") is not None:
            if args["font"] not in [p.name for p in fonts()]:
                return "no such SoundFont"
            synth.conf["font"] = args["font"]
        synth.set_preset(int(args.get("bank") or 0), int(args.get("program") or 0))
        return f"{synth.name}: {(synth.preset() or (0, 0, 'no preset'))[2]}"

    def command_level(args):
        synth = next((s for s in synths if s.letter == str(args.get("slot", "A")).upper()), None)
        if synth is None:
            return f"slot: {SLOTS}"
        synth.set_level(1 if args.get("step", 1) > 0 else -1)
        return f"{synth.name} level {synth.conf['level']:.1f}"

    studio.add_web(status=status, commands={"on": command_on, "preset": command_preset, "level": command_level})
    studio.on("tick", lambda: [s.tick() for s in synths])
