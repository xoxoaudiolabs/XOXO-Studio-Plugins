"""FM-1 Companion for XOXO Studio: the FM-1 on the Studio, as a plug-in (XOXO Studio's docs/PLUGINS.md).

The Pocket (xoxoaudiolabs/FM-1-Companion) is the FM-1-focused box; this plug-in brings its FM-1 work to the Studio.
  - up to four FM-1s on the Studio's USB (Felucca, SLOOP or FM-1 firmware), FM-1 A to FM-1 D by USB port (A: the
    lowest), as the Pocket names them (its sloop.fm1_cards): each a sound source in the Studio's mixer (HOME, MIXER,
    recordings) and a MIDI device in the routes under the same name, both ways (its notes and clock to the other
    devices, theirs and the Studio's clock to it). E to G are kept for a linked Pocket's (not yet: FM-1-Companion)
  - the FM-1 keeps the clock when it's plugged in (the Studio's WirePlumber rule, already there: priority.driver)
  - the FM-1 screen (MORE > PLUG-INS > FM-1): the FM-1s it has found, and the FM-1 library (0.2): backups,
    projects, songs, sample slots, DX7 patches and firmware in ~/fm1-library, the Pocket's own jobs (lib/fm1lib.py)
    run as their own processes. A backup is a tap; anything that writes to the FM-1 is a 2 s hold
  - the web page's Library (0.3, with a Studio that has the plug-in additions): the job, the files, and its writes
    confirmed on the Studio's screen, as the Pocket's are on the Pocket

A Clipper (isod89's Clipper firmware, on an FM-1 or on M-Vave's SMK-37 keyboard, under the same name and USB ID)
follows the FM-1 Companion's rule: it's an FM-1 only when no other FM-1 (Felucca, SLOOP) is plugged in; next to
one it's an instrument, a keyboard with a mixer channel of its own.

On a Studio without add_card_names (before the plug-in additions to API 1) the FM-1s are named by rules instead:
in the order the Studio finds them, a lone Clipper an FM-1 for its sound only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

API = 1
VERSION = "0.3.0"

FM1_SOUND = r"felucca|sloop|fm-1|fm1|m-vave"    # in a USB sound card's names (the FM-1 Companion's source_match)
FM1_MIDI = r"^(felucca|sloop|fm-1|fm1)\b"       # an FM-1's ALSA MIDI client name ("Felucca", "SLOOP")
FM1_CARD = ("felucca", "sloop", "fm-1", "fm1", "clipper")    # in /proc/asound/cards (sloop.PORT_MATCH)
CARDS = Path("/proc/asound/cards")
LETTERS = "ABCD"                                # the Studio's own FM-1s (E-G: a linked Pocket's)


def read_cards():
    try:
        return CARDS.read_text(errors="replace")
    except OSError:
        return ""


def fm1_cards(text=None):
    """The FM-1s' ALSA sound card numbers, FM-1 A first: in the order of the USB ports they're plugged into (a
    hub's port 1 before its port 3), so the letters stay the same across reboots and replugs. A Clipper card counts
    only when no other FM-1 is plugged in. The FM-1 Companion's sloop.fm1_cards, which lib/fm1lib.py's jobs go by
    too, so the mixer, the MIDI routes and the library agree on which FM-1 is which."""
    text = read_cards() if text is None else text
    lines, found = text.splitlines(), []
    for i, line in enumerate(lines):
        m = re.match(r"\s*(\d+) \[", line)
        if not m:
            continue
        detail = lines[i + 1] if i + 1 < len(lines) else ""
        both = f"{line} {detail}".lower()
        if "usb-audio" not in both or not any(w in both for w in FM1_CARD):
            continue
        path = re.search(r"\.usb-([\d.]+)", detail)          # "at usb-20980000.usb-1.3": hub port 3
        key = tuple(int(p) for p in path.group(1).strip(".").split(".")) if path else (999,)
        found.append((key, int(m.group(1)), "clipper" in both))
    if any(not clipper for _, _, clipper in found):         # a real FM-1 here: a Clipper is an instrument
        found = [f for f in found if not f[2]]
    return [card for _, card, _ in sorted(found)]


def card_names(text):
    """{sound card: "FM-1 A"} for the Studio's FM-1s (add_card_names: the mixer's and the MIDI routes' names)"""
    return {card: fm1_name(n) for n, card in enumerate(fm1_cards(text)[:len(LETTERS)])}


def real_fm1_plugged(text=None):
    """is an FM-1 other than a Clipper (Felucca, SLOOP) plugged in?"""
    lines = (read_cards() if text is None else text).splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"\s*\d+ \[", line):
            continue
        both = f"{line} {lines[i + 1] if i + 1 < len(lines) else ''}".lower()
        if "usb-audio" in both and any(w in both for w in FM1_CARD[:-1]) and "clipper" not in both:
            return True
    return False


def is_fm1(text):
    """a sound source's names -> is it an FM-1? (the rule on a Studio without card names) A Clipper only when no
    other FM-1 is plugged in"""
    if re.search(FM1_SOUND, text, re.I):
        return True
    return bool(re.search(r"clipper", text, re.I)) and not real_fm1_plugged()


def fm1_name(n):
    """the n-th FM-1 (0, 1, ...): FM-1 A, FM-1 B ... FM-1 D"""
    return "FM-1 " + LETTERS[min(n, len(LETTERS) - 1)]


# ---------------------------------------------------------------- the FM-1 library: lib/fm1lib.py's jobs

LIB = Path(__file__).resolve().parent / "lib" / "fm1lib.py"
LIBRARY = Path(os.environ.get("FM1_LIBRARY", Path.home() / "fm1-library"))     # the Studio's library, too
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
JOB = RUNTIME / "fm1-companion-job.json"        # fm1lib.py's progress (its STATE)
SUFFIXES = {"backups": ".json", "projects": ".json", "songs": ".json", "patches": ".syx", "firmware": ".fwsc",
            "samples": ".wav"}                  # (samples: the Studio's own WAVs, the pads' too)
LEVELS = ("-6 dB", "-3 dB", "full")             # a sample's loudest point in its slot (fm1lib.SAMPLE_LEVELS)
FIRMWARES = ("sloop", "clipper")
FOLDERS = ("backups", "projects", "songs", "patches", "firmware")   # the library's own (plugin.json "library")


def files(name):
    """a library folder's files, newest first ([] without the folder)"""
    try:
        found = [p for p in (LIBRARY / name).iterdir()
                 if p.is_file() and p.suffix.lower() == SUFFIXES[name] and not p.name.startswith(".")]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def alive(pid):
    if os.name == "nt":                         # (os.kill there ends the process: PC test runs only)
        return True
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


class Library:
    """the library's jobs: fm1lib.py started as its own process (a systemd user unit on the Studio, so a flash
    carries on if the Studio restarts), its progress read from its state file on each tick. The web page's list
    of the library's files: fm1lib.py list, again whenever a folder changes"""

    def __init__(self, studio):
        self.studio, self.job, self.started = studio, self.read(), 0.0
        self.waiting = 0.0                      # when a write the web page asked for went to the Studio's screen
        self.listing, self.listed, self.listing_at, self.lister = {}, None, 0.0, None
        self.fm1s = min(len(fm1_cards()), len(LETTERS))

    def read(self):
        try:
            job = json.loads(JOB.read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(job, dict):
            return None
        if job.get("state") == "running" and not alive(job.get("pid")):
            job = dict(job, state="error", message="it stopped without saying why")
        return job

    def tick(self):
        self.fm1s = min(len(fm1_cards()), len(LETTERS))
        self.list_if_changed()
        job = self.read()
        if job == self.job:
            return
        was, self.job = self.job, job
        if job and job.get("state") in ("done", "error") and (was or {}).get("state") == "running":
            self.studio.say(job_text(job)[:60], 4)

    def list_if_changed(self):
        """the files, listed again (in the background: it reads every backup) when a folder has changed"""
        seen = []
        for name in FOLDERS:
            try:
                seen.append((LIBRARY / name).stat().st_mtime_ns)
            except OSError:
                seen.append(None)
        if seen == self.listed or (self.lister and self.lister.is_alive()):
            return
        self.listed = seen

        def run():
            try:
                done = subprocess.run([sys.executable, str(LIB), "list"], capture_output=True, text=True, timeout=120)
                self.listing, self.listing_at = json.loads(done.stdout), time.time()
            except (OSError, ValueError, subprocess.SubprocessError):
                self.listed = None              # (tried again next tick)
        self.lister = threading.Thread(target=run, daemon=True)
        self.lister.start()

    def busy(self):
        return (self.job or {}).get("state") == "running" or time.monotonic() - self.started < 3

    def which(self):
        """the FM-1 the library works on with two or more plugged in: A (the lowest USB port) to D"""
        which = self.studio.settings.get("library_fm1")
        return which if isinstance(which, str) and len(which) == 1 and which in LETTERS else "A"

    def use(self, which):
        if len(which) != 1 or which not in LETTERS:
            return f"FM-1 {LETTERS[0]} to {LETTERS[-1]}"
        self.studio.settings["library_fm1"] = which
        self.studio.save()
        return f"The library works on FM-1 {which}"

    def level(self):
        level = self.studio.settings.get("sample_level")
        return level if level in LEVELS else LEVELS[0]

    def start(self, args):
        """fm1lib.py args in the background -> an error message, or None"""
        if self.busy():
            return "a library job is running"
        command = [sys.executable, str(LIB), "--fm1", self.which(), "--level", self.level(), *map(str, args)]
        if shutil.which("systemd-run"):
            command = ["systemd-run", "--user", "--collect", "--quiet", f"--unit=fm1-companion-{time.time_ns()}",
                       *command]
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            return str(e)
        self.started, self.waiting = time.monotonic(), 0.0
        return None

    def web_status(self):
        return {"version": VERSION, "library_fm1": self.which(), "fm1s": list(LETTERS[:self.fm1s]), "job": self.job,
                "waiting": bool(self.waiting) and time.monotonic() - self.waiting < 120,
                "library": self.listing, "library_at": self.listing_at}

    def web_commands(self):
        """the jobs that only read from the FM-1 (or GitHub) start at once; a write (ask) waits for a 2 s hold on
        the Studio's screen, as the Pocket's do for the joystick press"""
        def fetch(args):
            name = str(args.get("firmware", ""))
            if name not in FIRMWARES:
                return "firmware: sloop or clipper"
            return self.start(["fetch", name]) or "started"
        return {"backup": lambda args: self.start(["backup"]) or "started",
                "song-backup": lambda args: self.start(["song-backup"]) or "started",
                "fetch": fetch, "use": lambda args: self.use(str(args.get("fm1", ""))), "ask": self.ask}

    def ask(self, r):
        """a write to the FM-1 the web page asked for (the Pocket's web.py ask): checked, then the Studio's
        hold-to-confirm screen, then the job -> what to say"""
        if not hasattr(self.studio, "confirm"):
            return "this Studio can't ask for a confirmation: update it"
        if self.busy():
            return "a library job is running"
        command, fm1 = r.get("cmd"), f"FM-1 {self.which()}"
        if command == "restore":
            path = library_file("backups", r.get("file"))
            if not path:
                return "no such backup"
            args, title, lines = ["restore", path], "Restore?", [path.name[:16], f"replaces {fm1}'s data"]
        elif command == "load-project":
            folder, target, source = r.get("folder"), r.get("target"), r.get("source") or "-"
            path = library_file(folder, r.get("file")) if folder in ("backups", "projects") else None
            if not path or target not in TARGETS or source not in TARGETS + ("-",):
                return "pick a project and where it goes"
            where = "the working project" if target == "working" else f"project {target}"
            source = source if folder == "backups" else "-"
            args, title = ["load-project", path, source, target], "Load project?"
            lines = [f"{path.stem[:14]} {source if source != '-' else ''}".strip(), f"into {where}", fm1]
        elif command == "dx7-send":
            path, voice = library_file("patches", r.get("file")), r.get("voice")
            if not path or not (voice is None or (isinstance(voice, int) and not isinstance(voice, bool)
                                                  and 1 <= voice <= 32)):
                return "pick a .syx and a voice"
            args, title = ["dx7-send", path] + ([] if voice is None else [voice]), "Send to FM-1?"
            lines = [path.stem[:16], "all 32 voices" if voice is None else f"voice {voice}", fm1]
        elif command == "load-song":
            path = library_file("songs", r.get("file"))
            if not path:
                return "no such song"
            args, title, lines = ["song-load", path], "Load song?", [path.stem[:16], "replaces sections A-D", fm1]
        elif command == "load-sample":
            files, slot = r.get("files"), r.get("slot")
            paths = [library_file("samples", n) for n in files] if isinstance(files, list) and 0 < len(files) <= 8 else []
            if not paths or None in paths or isinstance(slot, bool) or slot not in (1, 2, 3, 4):
                return "pick WAV files and a slot"
            name = re.sub(r"[^A-Za-z0-9 _-]", "", str(r.get("name") or ""))[:8] or paths[0].stem[:8]
            args, title = ["load-sample", slot, name, *paths], "Load sample?"
            lines = [f"{name} ({len(paths)} file{'s' if len(paths) > 1 else ''})", f"into USR{slot}", fm1]
        elif command == "flash":
            path = library_file("firmware", r.get("file"))
            if not path:
                return "no such firmware"
            warning = "Experimental" if "clipper" in path.name.lower() else "Keep it plugged in"
            args, title, lines = ["flash", path], "Install?", [path.stem[:20], warning, fm1]
        else:
            return "unknown library command"
        self.studio.confirm(title, lines, lambda: self.studio.say(self.start(args) or "Started", 2))
        self.waiting = time.monotonic()
        return "Confirm on the Studio: hold 2 s"


def library_file(folder, name):
    """a file in one of the library's folders, or None: a plain name of the right kind, there"""
    if folder not in SUFFIXES or not isinstance(name, str) or Path(name).name != name or name.startswith("."):
        return None
    path = LIBRARY / folder / name
    return path if path.suffix.lower() == SUFFIXES[folder] and path.is_file() else None


def job_text(job):
    """a job's state in a line: "BACKUP: Backing up 40%", "DONE: Backed up SLOOP 2.8", "ERROR: ..." """
    if not job:
        return "NO LIBRARY JOB YET"
    if job.get("state") == "running":
        percent = job.get("percent")
        return (f"{str(job.get('job', '')).upper()}: {job.get('step') or 'starting'}"
                f"{'' if percent is None else f' {percent:.0f}%'}")
    return f"{'DONE' if job.get('state') == 'done' else 'ERROR'}: {job.get('message') or job.get('job')}"


TARGETS = ("working", "A", "B", "C", "D")
# the library's pages: title, the folders it picks from, its choices (key, label, options), its taps (label, job
# args) and its hold: the job it starts, args(the file picked, the choices)
PAGES = {
    "restore": {"title": "RESTORE A BACKUP", "folders": ("backups",), "hold": "HOLD: RESTORE",
                "args": lambda p, c: ["restore", p]},
    "project": {"title": "LOAD A PROJECT", "folders": ("projects", "backups"), "hold": "HOLD: LOAD PROJECT",
                "choices": (("source", "FROM", TARGETS), ("target", "INTO", TARGETS)),
                "args": lambda p, c: ["load-project", p, c["source"] if p.parent.name == "backups" else "-",
                                      c["target"]]},
    "song": {"title": "SONGS", "folders": ("songs",), "hold": "HOLD: LOAD SONG",
             "taps": (("SAVE THE SONG ON THE FM-1", ["song-backup"]),), "args": lambda p, c: ["song-load", p]},
    "sample": {"title": "LOAD A SAMPLE SLOT", "folders": ("samples",), "hold": "HOLD: LOAD SAMPLE",
               "choices": (("slot", "SLOT", ("1", "2", "3", "4")), ("level", "LEVEL", LEVELS)),
               "args": lambda p, c: ["load-sample", c["slot"], p.stem[:8], p]},
    "dx7": {"title": "DX7 PATCHES", "folders": ("patches",), "hold": "HOLD: SEND TO FM-1",
            "args": lambda p, c: ["dx7-send", p]},
    "firmware": {"title": "FIRMWARE", "folders": ("firmware",), "hold": "HOLD: INSTALL",
                 "taps": (("GET SLOOP", ["fetch", "sloop"]), ("GET CLIPPER (EXP.)", ["fetch", "clipper"])),
                 "args": lambda p, c: ["flash", p]},
}
MENU = (("BACKUP", None), ("RESTORE", "restore"), ("PROJECT", "project"), ("SONG", "song"),
        ("SAMPLE", "sample"), ("DX7", "dx7"), ("FIRMWARE", "firmware"))
ROWS = 3                                        # files on a page at once


class FM1Screen:
    """MORE > PLUG-INS > FM-1: the FM-1s the Studio has, and the FM-1 library: a page a kind of job, a file
    picked from its folder, a hold to start anything that writes to the FM-1 (480x320: 34 header, 44 tabs)"""

    def __init__(self, ui, studio, library):
        self.ui, self.studio, self.lib = ui, studio, library
        self.page, self.top, self.picked, self.files, self.choice = None, 0, None, [], {}

    def found(self):
        return [name for name in self.studio.sources() if name.startswith("FM-1")]

    def view(self, now):
        job = self.lib.job or {}
        return (self.page, self.top, str(self.picked), tuple(sorted(self.choice.items())), tuple(self.found()),
                self.lib.which(), self.lib.level(), self.ui.lit("fm1-hold"), job.get("state"), job.get("step"),
                int(job.get("percent") or 0), job.get("message"))

    # ---- what a tap does

    def open(self, page):
        self.page, self.top, self.picked = page, 0, None
        self.choice = {key: options[0] for key, _, options in PAGES.get(page, {}).get("choices", ())}
        if page == "sample":
            self.choice["level"] = self.lib.level()
        self.refresh()

    def refresh(self):
        self.files = [p for name in PAGES[self.page]["folders"] for p in files(name)] if self.page else []
        if self.picked not in self.files:
            self.picked = None
        self.top = max(0, min(self.top, len(self.files) - ROWS))

    def run(self, args):
        error = self.lib.start(args)
        self.studio.say(error or "Started", 2)

    def hold(self):
        page = PAGES[self.page]
        if self.picked is not None and not self.lib.busy():
            self.run(page["args"](self.picked, self.choice))

    def pick(self, key, value):
        self.choice[key] = value
        if key == "level":                      # kept: the next sample goes in as loud
            self.studio.settings["sample_level"] = value
            self.studio.save()

    def set_fm1(self, which):
        self.studio.settings["library_fm1"] = which
        self.studio.save()

    def scroll(self, step):
        self.top = max(0, min(self.top + step, len(self.files) - ROWS))

    # ---- drawing

    def draw(self, img, d, now):
        if self.page:
            self.refresh()                      # (drawn only when something changed: a job, a tap)
            return self.draw_page(img, d)
        ui, t = self.ui, self.ui.theme
        fm1s = self.found()
        letters = [name[-1] for name in fm1s if name[-1] in LETTERS]
        if not fm1s:
            ui.centre(img, (0, 40, 480, 70), "NO FM-1 PLUGGED IN: PLUG ONE INTO A USB PORT", t.c[3])
        elif len(letters) < 2:
            ui.centre(img, (0, 40, 480, 70), "   ".join(fm1s) + "  (MIXER + MIDI ROUTES)", t.hi)
        else:                                   # which one the library works on: A (the lowest USB port) to D
            ui.centre(img, (4, 40, 96, 70), "LIBRARY", t.c[3])
            for i, which in enumerate(letters[:4]):
                ui.button(img, d, (100 + i * 94, 40, 190 + i * 94, 70), f"FM-1 {which}",
                          lambda w=which: self.set_fm1(w), on=self.lib.which() == which, key=f"fm1-lib-{which}")
        for i, (label, page) in enumerate(MENU):
            x, y = 4 + (i % 4) * 118, 78 + (i // 4) * 48
            action = (lambda p=page: self.open(p)) if page else (lambda: self.run(["backup"]))
            ui.button(img, d, (x, y, x + 114, y + 42), label, action, key=f"fm1-{label}")
        d.rectangle((4, 180, 476, 270), fill=t.grey[0])
        job = self.lib.job
        running = bool(job) and job.get("state") == "running"
        ui.centre(img, (4, 186, 476, 212), job_text(job)[:56], t.hi if running else t.c[3])
        if running and job.get("percent") is not None:
            d.rectangle((16, 220, 464, 228), fill=t.bg)
            d.rectangle((16, 220, 16 + int(448 * min(100, job["percent"]) / 100), 228), fill=t.hi)
        ui.centre(img, (4, 236, 476, 262), "BACKUP: A TAP. WRITING TO THE FM-1: A 2 S HOLD", t.c[2])

    def draw_page(self, img, d):
        ui, t, page = self.ui, self.ui.theme, PAGES[self.page]
        ui.button(img, d, (4, 38, 84, 64), "< FM-1", lambda: self.open(None), key="fm1-back")
        ui.centre(img, (90, 38, 476, 64), page["title"], t.hi)
        if not self.files:
            where = " / ".join(f"~/fm1-library/{f}" for f in page["folders"])
            ui.centre(img, (4, 68, 476, 158), f"NOTHING IN {where.upper()}"[:58], t.c[3])
        for row, path in enumerate(self.files[self.top:self.top + ROWS]):
            y = 68 + row * 30
            label = path.stem + (" (BACKUP)" if path.parent.name == "backups" and self.page == "project" else "")
            ui.button(img, d, (4, y, 420, y + 26), label[:48], lambda p=path: setattr(self, "picked", p),
                      on=path == self.picked, key=("fm1-file", str(path)))
        if len(self.files) > ROWS:
            ui.button(img, d, (424, 68, 476, 110), "UP", lambda: self.scroll(-ROWS), key="fm1-up")
            ui.button(img, d, (424, 116, 476, 158), "DOWN", lambda: self.scroll(ROWS), key="fm1-down")
        y = 164
        for key, label, options in page.get("choices", ()):
            if key == "source" and (self.picked is None or self.picked.parent.name != "backups"):
                y += 30                         # a project file is one project: nothing to pick from
                continue
            ui.centre(img, (4, y, 84, y + 26), label, t.c[3])
            w = 392 // len(options)
            for i, option in enumerate(options):
                ui.button(img, d, (88 + i * w, y, 84 + (i + 1) * w, y + 26), option.upper(),
                          lambda k=key, o=option: self.pick(k, o), on=self.choice.get(key) == option,
                          key=("fm1-choice", key, option))
            y += 30
        for i, (label, args) in enumerate(page.get("taps", ())):
            ui.button(img, d, (4 + i * 238, 164, 236 + i * 238, 190), label, lambda a=args: self.run(a),
                      key=f"fm1-tap-{i}")
        box = (4, 226, 476, 254)
        if self.lib.busy():
            ui.centre(img, box, "A LIBRARY JOB IS RUNNING", t.c[3])
        elif self.picked is None:
            ui.centre(img, box, "PICK A FILE", t.c[2])
        else:
            lit = ui.lit("fm1-hold")
            d.rectangle(box, fill=t.hi if lit else t.grey[0])
            ui.centre(img, box, page["hold"], t.bg if lit else t.c[4])
            ui.widget(box, "hold", self.hold, "fm1-hold")
        ui.centre(img, (4, 256, 476, 274), job_text(self.lib.job)[:58], t.c[2])


def setup(studio):
    library = Library(studio)
    if hasattr(studio, "add_card_names"):       # FM-1 A-D by USB port, the same in the mixer and the MIDI routes
        studio.add_card_names(card_names)
    else:                                       # (an older Studio: in the order it finds them)
        studio.add_audio_source(is_fm1, fm1_name)
        studio.add_midi_device(FM1_MIDI, "FM-1 {n}")
    studio.add_screen("FM-1", lambda ui, s: FM1Screen(ui, s, library))
    studio.add_web(status=library.web_status, commands=library.web_commands())
    studio.on("tick", library.tick)
