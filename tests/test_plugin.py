"""The FM-1 Companion plug-in in XOXO Studio's own code: its host (plugins.py) and touchscreen UI (deskui.py), with
stand-in devices. Needs a clone of XOXO Studio next to this repository (or $XOXO_STUDIO), Pillow and numpy.

  python -m pytest tests
"""
import copy
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
    app = bridge.App(RgbCapture(), copy.deepcopy(bridge.DEFAULTS))
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
    assert status["version"] == "0.4.1" and status["library_fm1"] == "B" and status["job"]["state"] == "done"
    assert app.plugin_host.web_command("fm1-companion", "fetch", {"firmware": "nope"}) == "firmware: sloop or clipper"
    assert app.plugin_host.web_command("fm1-companion", "use", {"fm1": "D"}) == "The library works on FM-1 D"
    assert app.plugin_host.web_command("fm1-companion", "use", {"fm1": "H"}) == "FM-1 A to G"   # E-G: a Pocket's
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


POCKET_CODE = Path(os.environ.get("FM1_COMPANION") or ROOT.parent / "FM-1 Bridge") / "fm1-bt-bridge"


@pytest.mark.skipif(not (POCKET_CODE / "web.py").is_file()
                    or "confirmed" not in (POCKET_CODE / "web.py").read_text(encoding="utf-8"),
                    reason="no FM-1 Companion with the linked Studio's FM-1 E-G next to this repository")
def test_library_on_a_linked_pockets_fm1s():
    """FM-1 E and F are the linked Pocket's A and B: a backup there comes back into the Studio's library, a
    restore sends its file first and runs confirmed (the hold was on the Studio's screen); against the Pocket's own
    web.py (tests/pocket_server.py), its jobs pretended"""
    import subprocess
    folder = Path(tempfile.mkdtemp(prefix="fm1-pocket-"))
    server = subprocess.Popen([sys.executable, str(Path(__file__).parent / "pocket_server.py"), str(POCKET_CODE),
                               str(folder)], stdout=subprocess.PIPE, text=True)
    try:
        port = int(server.stdout.readline())
        _, _, screen = studio_with_plugin([])
        lib = screen.lib
        lib.pocket = lambda: f"127.0.0.1:{port}"

        def wait(what):
            deadline = time.time() + 20
            while time.time() < deadline and not what():
                time.sleep(0.1)
            assert what()
        lib.ask_pocket()
        wait(lambda: lib.pocket_fm1s == ["A", "B"])
        assert lib.letters()[-2:] == ["E", "F"]
        assert lib.use("G") == "The library works on FM-1 G" and lib.start(["backup"]) == \
            "FM-1 G isn't plugged into the Pocket"
        lib.use("E")
        assert lib.start(["backup"]) is None
        wait(lambda: lib.remote["state"] != "running")
        assert lib.remote["state"] == "done", lib.remote
        name = lib.remote["result"]["file"]
        assert (TMP / "library" / "backups" / name).is_file()                  # copied back to the Studio
        lib.use("F")
        lib.started = 0.0
        backup = TMP / "library" / "backups" / name
        assert lib.start(["restore", backup]) is None
        wait(lambda: lib.remote["state"] != "running")
        assert lib.remote["state"] == "done", lib.remote
        assert (TMP / "library" / "backups" / lib.remote["result"]["before"]).is_file()   # its safety backup too
        jobs = [json.loads(line) for line in (folder / "jobs.jsonl").read_text().splitlines()]
        assert jobs[0] == ["--fm1", "A", "backup"]
        assert jobs[1][:3] == ["--fm1", "B", "restore"] and jobs[1][3].endswith(name)    # sent there first
        lib.started = 0.0
        assert lib.start(["load-sample", 1, "x", TMP / "nope.wav"]) is None              # a file it can't send
        wait(lambda: lib.remote["state"] != "running")
        assert lib.remote["state"] == "error" and "Pocket" in lib.remote["message"]
    finally:
        server.kill()


@pytest.mark.skipif(not hasattr(plugins.Studio, "pocket"), reason="a Studio without a linked Pocket's FM-1s")
def test_a_linked_pockets_fm1s_are_e_to_g():
    """the Pocket's own streams (fm1-pocket-a/c) and network MIDI sessions are FM-1 E-G; its mix stays POCKET"""
    app, _, _ = studio_with_plugin([])
    node = lambda i, name, description: {"type": "PipeWire:Interface:Node", "id": i, "info": {"props": {   # noqa: E731
        "media.class": "Audio/Source", "node.name": name, "node.description": description}}}
    objects = [node(1, "fm1-pocket", "Pocket (link)"), node(2, "fm1-pocket-a", "Pocket FM-1 A"),
               node(3, "fm1-pocket-c", "Pocket FM-1 C")]
    assert [s["label"] for s in bridge.pick_nodes(objects, app.plugin_host)[1]] == ["POCKET", "FM-1 E", "FM-1 G"]
    rules = app.plugin_host.midi_names()
    assert [plugins.name_device(f"FM-1 Companion Pocket FM-1 {x}", rules, set()) for x in "ABC"] == \
        ["FM-1 E", "FM-1 F", "FM-1 G"]
    assert plugins.name_device("Felucca", rules, set()) is None       # (the Studio's own: by card, not by rules)


@pytest.mark.skipif(not hasattr(plugins.Studio, "set_detail"), reason="a Studio without set_detail")
def test_home_shows_what_each_fm1_runs():
    """each FM-1 asked once what it runs when it appears (fm1lib.py label), shown on HOME, gone when it goes"""
    app, _, screen = studio_with_plugin([])
    lib, asked = screen.lib, []

    class Done:
        def __init__(self, stdout):
            self.stdout = stdout

    def run(command, **kw):
        asked.append(command[-2])
        return Done({"A": "SLOOP 2.8\n", "B": "FELUCCA\n"}[command[-2]])
    lib.show_firmware.__globals__["subprocess"] = type("Fake", (), {"run": staticmethod(run),
                                                                    "SubprocessError": Exception})
    try:
        studio = app.plugin_host.loaded["fm1-companion"]
        for _ in range(6):                                           # a tick each: ask A, show it, ask B, show it
            lib.show_firmware(CARDS)
            if lib.labeller:
                lib.labeller.join()
        assert studio.details == {"FM-1 A": "SLOOP 2.8", "FM-1 B": "FELUCCA"} and asked == ["A", "B"]
        lib.show_firmware(CARDS)
        assert asked == ["A", "B"]                                   # asked once
        lines = CARDS.splitlines()
        lib.show_firmware("\n".join(lines[:4]) + "\n")              # FM-1 A (card 3) unplugged: card 2 is A now
        assert "FM-1 B" not in studio.details
    finally:
        lib.show_firmware.__globals__["subprocess"] = __import__("subprocess")
