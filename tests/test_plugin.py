"""The FM-1 Companion plug-in in XOXO Studio's own code: its host (plugins.py) and touchscreen UI (deskui.py), with
stand-in devices. Needs a clone of XOXO Studio next to this repository (or $XOXO_STUDIO), Pillow and numpy.

  python -m pytest tests
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = Path(os.environ.get("XOXO_STUDIO") or ROOT.parent / "XOXO-Studio")
TMP = Path(tempfile.mkdtemp(prefix="fm1-plugin-ui-"))
os.environ.update(FM1_LIBRARY=str(TMP / "library"), XDG_RUNTIME_DIR=str(TMP / "run"),
                  FM1_SETTINGS=str(TMP / "settings.json"))
if not (STUDIO / "fm1-bt-bridge" / "plugins.py").is_file():
    pytest.skip(f"no XOXO Studio at {STUDIO}", allow_module_level=True)
sys.path.insert(0, str(STUDIO / "fm1-bt-bridge"))

import bridge  # noqa: E402
import deskui  # noqa: E402
import plugins  # noqa: E402


class RgbCapture:
    def __init__(self):
        self.image, self.theme = None, None

    def show_rgb(self, img):
        self.image = img.copy()


def studio_with_plugin(others):
    app = bridge.App(RgbCapture(), dict(bridge.DEFAULTS))
    app.save_settings = lambda: None
    app.others = others
    app.plugin_host = plugins.Host(app, [ROOT])
    app.plugin_host.start()
    assert app.plugin_host.set_on("fm1-companion", True) == "FM-1 Companion on", app.plugin_host.errors
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    pid, label, screen = app.plugin_host.screens()[0]
    assert (pid, label) == ("fm1-companion", "FM-1")
    ui.open_plugin((pid, label, screen))
    ui.render(0.0, force=True)
    return app, ui, ui.plugin_screen[2]


def tap(ui, key, now=0.0):
    box = next(w[0] for w in ui.widgets if w[3] == key)
    ui.touch("down", box[0] + 2, box[1] + 2, now)
    ui.touch("up", box[0] + 2, box[1] + 2, now)
    ui.render(now, force=True)


def keys(ui):
    return {w[3] for w in ui.widgets}


def test_library_screens():
    """the FM-1 screen: a backup is a tap, a restore a file picked and a 2 s hold; nothing switches it off"""
    backups = TMP / "library" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    (backups / "2026-10-31_101500_sloop-2.8_manual.json").write_text("{}")
    app, ui, screen = studio_with_plugin([{"id": 1, "name": "alsa_input.usb-felucca", "label": "FM-1 A"}])
    started = []
    screen.lib.start = lambda args: started.append([str(a) for a in args])
    assert {"fm1-BACKUP", "fm1-RESTORE", "fm1-FIRMWARE"} <= keys(ui)
    tap(ui, "fm1-BACKUP")
    assert started == [["backup"]]
    tap(ui, "fm1-RESTORE")
    path = backups / "2026-10-31_101500_sloop-2.8_manual.json"
    assert "fm1-hold" not in keys(ui)                                # nothing picked: nothing to hold
    tap(ui, ("fm1-file", str(path)))
    assert screen.picked == path and "fm1-hold" in keys(ui)
    box = next(w[0] for w in ui.widgets if w[3] == "fm1-hold")
    ui.touch("down", box[0] + 2, box[1] + 2, 10.0)
    ui.touch("up", box[0] + 2, box[1] + 2, 10.5)                     # let go too soon: nothing
    ui.render(10.5, force=True)
    assert started == [["backup"]]
    ui.touch("down", box[0] + 2, box[1] + 2, 20.0)
    ui.render(22.5, force=True)                                      # held 2.5 s: restore
    assert started[-1] == ["restore", str(path)]
    tap(ui, "fm1-back")
    tap(ui, "fm1-SAMPLE")
    tap(ui, ("fm1-choice", "level", "full"))
    assert app.state["plugins"]["fm1-companion"]["settings"]["sample_level"] == "full"
    assert app.plugin_host.errors == {} and "fm1-companion" in app.plugin_host.loaded


def test_project_from_a_backup_or_a_file():
    projects = TMP / "library" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    (projects / "night-drive.json").write_text("{}")
    backup = TMP / "library" / "backups" / "2026-10-31_101500_sloop-2.8_manual.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("{}")
    _, ui, screen = studio_with_plugin([])
    started = []
    screen.lib.start = lambda args: started.append([str(a) for a in args])
    tap(ui, "fm1-PROJECT")
    tap(ui, ("fm1-file", str(projects / "night-drive.json")))
    assert ("fm1-choice", "source", "A") not in keys(ui)             # a project file: one project
    tap(ui, ("fm1-choice", "target", "C"))
    screen.hold()
    assert started[-1] == ["load-project", str(projects / "night-drive.json"), "-", "C"]
    tap(ui, ("fm1-file", str(backup)))
    tap(ui, ("fm1-choice", "source", "B"))
    screen.hold()
    assert started[-1] == ["load-project", str(backup), "B", "C"]


def test_two_fm1s_and_the_job_line():
    app, ui, screen = studio_with_plugin([{"id": 1, "name": "a", "label": "FM-1 A"},
                                          {"id": 2, "name": "b", "label": "FM-1 B"}])
    tap(ui, "fm1-lib-B")
    assert screen.lib.which() == "B"
    said = []
    screen.studio.say = lambda text, seconds=2: said.append(text)
    job_file = TMP / "run" / "fm1-companion-job.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)
    job_file.write_text(json.dumps({"job": "backup", "state": "running", "step": "Backing up", "percent": 40,
                                    "pid": os.getpid()}))
    screen.lib.tick()
    assert screen.lib.busy()
    ui.render(1.0, force=True)
    job_file.write_text(json.dumps({"job": "backup", "state": "done", "message": "Backed up SLOOP 2.8"}))
    screen.lib.tick()
    assert said == ["DONE: Backed up SLOOP 2.8"]
    status = app.plugin_host.web_status()["fm1-companion"]
    assert status["version"] == "0.3.0" and status["library_fm1"] == "B" and status["job"]["state"] == "done"
    assert app.plugin_host.web_command("fm1-companion", "fetch", {"firmware": "nope"}) == "firmware: sloop or clipper"
    assert app.plugin_host.web_command("fm1-companion", "use", {"fm1": "D"}) == "The library works on FM-1 D"
    assert app.plugin_host.web_command("fm1-companion", "use", {"fm1": "E"}) == "FM-1 A to D"   # E-G: a Pocket's
    assert screen.lib.which() == "D"


# the Studio's sound cards with Pat's FM-1s (2026-10-24): two FM-1s on a hub, an SMK-37 running Clipper (an FM-1's
# name and USB ID), and two more FM-1s and a fifth to show the limit
CARDS = """ 0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones
                      bcm2835 Headphones
 2 [Felucca        ]: USB-Audio - Felucca
                      Hügelton Instruments Felucca at usb-3f980000.usb-1.2, full speed
 3 [Felucca_1      ]: USB-Audio - Felucca
                      Hügelton Instruments Felucca at usb-3f980000.usb-1.1.3, full speed
 4 [Clipper        ]: USB-Audio - Clipper
                      Hügelton Instruments Clipper at usb-3f980000.usb-1.1.2, full speed
"""
MORE = """ 5 [Felucca_2      ]: USB-Audio - Felucca
                      Hügelton Instruments Felucca at usb-3f980000.usb-1.3, full speed
 6 [Felucca_3      ]: USB-Audio - Felucca
                      Hügelton Instruments Felucca at usb-3f980000.usb-1.4, full speed
 7 [Felucca_4      ]: USB-Audio - Felucca
                      Hügelton Instruments Felucca at usb-3f980000.usb-1.5, full speed
"""


def test_fm1s_by_usb_port_in_the_mixer_and_midi():
    """two FM-1s and a Clipper SMK-37: A and B by USB port in both the mixer and the MIDI routes, the SMK-37 a
    keyboard; a lone Clipper is FM-1 A; four FM-1s are A-D and a fifth isn't named"""
    import blemidi
    app, _, screen = studio_with_plugin([])
    host = app.plugin_host
    assert host.card_names(CARDS) == {3: "FM-1 A", 2: "FM-1 B"}               # the hub's port 1.1.3 first
    node = lambda card, name: {"node.name": f"alsa_input.usb-H__gelton_Instruments_{name}-0{card}",  # noqa: E731
                               "alsa.card_name": name, "api.alsa.path": f"front:{card}"}
    counts = {"cards": host.card_names(CARDS)}
    assert [host.source_label(node(c, n), counts) for c, n in ((2, "Felucca"), (3, "Felucca"), (4, "Clipper"))] \
        == ["FM-1 B", "FM-1 A", None]                                         # the Clipper: a USB source of its own
    lines = CARDS.splitlines()
    assert host.card_names("\n".join(lines[:2] + lines[-2:])) == {4: "FM-1 A"}  # a lone Clipper: the FM-1
    assert host.card_names(CARDS + MORE) == {3: "FM-1 A", 2: "FM-1 B", 5: "FM-1 C", 6: "FM-1 D"}   # 7: no letter
    keys = blemidi.UsbControllers(lambda *a: None)
    keys.cards = host.card_names(CARDS)
    ports = ["Felucca:Felucca MIDI 1 24:0", "Felucca:Felucca MIDI 1 28:0", "Clipper:Clipper MIDI 1 32:0"]
    assert keys.wanted(ports) == {"FM-1 B": ports[0], "FM-1 A": ports[1], "Clipper": ports[2]}


def test_web_page_writes_are_confirmed_on_the_studio():
    """the web page's Restore: checked, then the Studio's hold-to-confirm screen, and only then the job"""
    backup = TMP / "library" / "backups" / "2026-10-31_101500_sloop-2.8_manual.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("{}")
    app, _, screen = studio_with_plugin([])
    started = []
    screen.lib.start = lambda args: started.append([str(a) for a in args])
    command = lambda args: app.plugin_host.web_command("fm1-companion", "ask", args)   # noqa: E731
    assert command({"cmd": "restore", "file": "../secrets.json"}) == "no such backup"
    assert command({"cmd": "load-sample", "files": ["x.wav"], "slot": 9}) == "pick WAV files and a slot"
    assert command({"cmd": "restore", "file": backup.name}) == "Confirm on the Studio: hold 2 s"
    assert started == [] and app.screen == "confirm" and app.confirm["title"] == "Restore?"
    assert app.plugin_host.web_status()["fm1-companion"]["waiting"] is True
    app.confirm["action"]()                                          # held 2 s
    assert started == [["restore", str(backup)]]


def test_a_real_job_process():
    """Library.start runs lib/fm1lib.py as its own process: with no FM-1 here, it says so in the job file"""
    app, _, screen = studio_with_plugin([])
    job_file = TMP / "run" / "fm1-companion-job.json"
    job_file.unlink(missing_ok=True)
    screen.lib.started = 0.0
    screen.lib.job = None
    assert screen.lib.start(["identify"]) is None
    deadline = time.time() + 30
    while time.time() < deadline:
        job = screen.lib.read()
        if job and job.get("state") != "running":
            break
        time.sleep(0.2)
    assert job and job["job"] == "identify" and job["state"] == "error", job
