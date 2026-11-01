"""The Synths plug-in: its SoundFont reader, its slot process (lib/slot.py) with a pretend FluidSynth, and the
plug-in in XOXO Studio's own code (plugins.py, deskui.py). The last needs a clone of XOXO Studio next to this
repository's folder (or $XOXO_STUDIO), Pillow and numpy.

  python -m pytest tests
"""
import copy
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
TMP = Path(tempfile.mkdtemp(prefix="synths-test-"))
LOG = TMP / "fluidsynth.log"
os.environ.update(FM1_LIBRARY=str(TMP / "library"), XDG_RUNTIME_DIR=str(TMP / "run"),
                  FM1_SETTINGS=str(TMP / "settings.json"), SYNTHS_FONTS=str(TMP / "system"),
                  SYNTHS_FLUIDSYNTH=json.dumps([sys.executable, str(HERE / "fake_fluidsynth.py")]),
                  SYNTHS_LOOPBACK="off", SYNTHS_STALE="2", FAKE_FLUIDSYNTH_LOG=str(LOG))
sys.path.insert(0, str(PLUGIN / "lib"))

import sf2  # noqa: E402


def chunk(cid, data):
    return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")


def soundfont(path, presets):
    """a SoundFont with these (bank, program, name) presets and no sound in it"""
    phdr = b"".join(struct.pack("<20sHHHIII", name.encode(), program, bank, 0, 0, 0, 0)
                    for bank, program, name in [*presets, (0, 0, "EOP")])
    info = b"INFO" + chunk(b"ifil", struct.pack("<HH", 2, 1))
    sdta = b"sdta" + chunk(b"smpl", b"\0" * 101)           # (odd: the padding)
    pdta = b"pdta" + chunk(b"phdr", phdr)
    body = b"sfbk" + chunk(b"LIST", info) + chunk(b"LIST", sdta) + chunk(b"LIST", pdta)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    return path


def wait(test, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        found = test()
        if found:
            return found
        time.sleep(0.1)
    raise AssertionError("timed out")


def state(slot="a"):
    try:
        return json.loads((TMP / "run" / f"synths-{slot}.json").read_text())
    except (OSError, ValueError):
        return {}


def test_presets_of_a_soundfont():
    path = soundfont(TMP / "a.sf2", [(0, 1, "Bright Piano"), (128, 0, "Standard Kit"), (0, 0, "Grand Piano")])
    assert sf2.presets(path) == [(0, 0, "Grand Piano"), (0, 1, "Bright Piano"), (128, 0, "Standard Kit")]
    (TMP / "not.sf2").write_bytes(b"RIFF\0\0\0\0WAVE")
    for bad in (TMP / "not.sf2", TMP / "missing.sf2"):
        with pytest.raises(sf2.SoundFontError):
            sf2.presets(bad)


def run_slot(want, env=None):
    """lib/slot.py as its own process, as the plug-in starts it, kept alive (touched) by the test"""
    run = TMP / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "synths-a.alive").touch()
    (run / "synths-a.want").write_text(json.dumps(want))
    (run / "synths-a.json").unlink(missing_ok=True)
    LOG.write_text("")
    return subprocess.Popen([sys.executable, str(PLUGIN / "lib" / "slot.py"), "--slot", "a"],
                            env=dict(os.environ, **(env or {})))


def test_a_slot_process():
    """the sound wanted: the SoundFont loaded, its preset on all 16 channels, the gain; a new preset alone isn't a
    new load; a new SoundFont lets the old one go; no touch from the plug-in: it stops"""
    font = soundfont(TMP / "system" / "TimGM6mb.sf2", [(0, 0, "Piano"), (0, 5, "EP")])
    proc = run_slot({"id": 1, "font": str(font), "bank": 0, "program": 5, "gain": 0.4})
    try:
        wait(lambda: state().get("applied") == 1)
        said = LOG.read_text().splitlines()
        assert said[0] == f"load {font}" and said[1:17] == [f"select {c} 1 0 5" for c in range(16)]
        assert said[17] == "gain 0.40" and state()["state"] == "running"
        (TMP / "run" / "synths-a.alive").touch()
        (TMP / "run" / "synths-a.want").write_text(json.dumps({"id": 2, "font": str(font), "program": 0}))
        wait(lambda: state().get("applied") == 2)
        assert not [line for line in LOG.read_text().splitlines()[18:] if line.startswith("load")]
        other = soundfont(TMP / "library" / "soundfonts" / "My Font.sf2", [(0, 0, "Pad")])
        (TMP / "run" / "synths-a.alive").touch()
        (TMP / "run" / "synths-a.want").write_text(json.dumps({"id": 3, "font": str(other)}))
        wait(lambda: state().get("applied") == 3)
        assert f'load "{other}"' in LOG.read_text() and "unload 1" in LOG.read_text()
        proc.wait(10)                           # (no touch for SYNTHS_STALE seconds)
        assert state()["state"] == "stopped" and LOG.read_text().splitlines()[-1] == "quit"
    finally:
        proc.kill()


def test_a_slot_whose_engine_stops():
    proc = run_slot({"id": 1}, {"FAKE_FLUIDSYNTH_FAIL": "fluidsynth: error: no audio driver"})
    try:
        assert proc.wait(10) == 1
        assert state()["state"] == "error" and "no audio driver" in state()["message"]
    finally:
        proc.kill()


def test_a_soundfont_that_wont_load():
    proc = run_slot({"id": 1, "font": str(TMP / "gone.sf2")})
    try:
        wait(lambda: state().get("applied") == 1)
        assert "couldn't load gone.sf2" in state()["message"]
    finally:
        (TMP / "run" / "synths-a.alive").unlink()
        proc.wait(10)


# ---------------------------------------------------------------- the plug-in in XOXO Studio's own code

STUDIO = Path(os.environ.get("XOXO_STUDIO") or PLUGIN.parent.parent / "XOXO-Studio")
if not (STUDIO / "fm1-bt-bridge" / "plugins.py").is_file():
    STUDIO = PLUGIN.parent / "XOXO-Studio"      # (split off: a clone beside this repository)


@pytest.fixture
def studio():
    if not (STUDIO / "fm1-bt-bridge" / "plugins.py").is_file():
        pytest.skip(f"no XOXO Studio at {STUDIO}")
    sys.path.insert(0, str(STUDIO / "fm1-bt-bridge"))
    import bridge
    import deskui
    import plugins

    class Capture:
        image = theme = None

        def show_rgb(self, img):
            self.image = img.copy()

    folder = Path(tempfile.mkdtemp(prefix="synths-plugins-"))
    shutil.copytree(PLUGIN, folder / "synths", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    app = bridge.App(Capture(), copy.deepcopy(bridge.DEFAULTS))
    app.save_settings = lambda: None
    app.others = []
    app.plugin_host = plugins.Host(app, [folder])
    app.plugin_host.start()
    assert app.plugin_host.set_on("synths", True) == "Synths on", app.plugin_host.errors
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    pid, label, screen = app.plugin_host.screens()[0]
    assert (pid, label) == ("synths", "SYNTHS")
    ui.open_plugin((pid, label, screen))
    ui.render(0.0, force=True)
    yield app, ui, ui.plugin_screen[2], bridge, plugins
    for synth in ui.plugin_screen[2].synths:
        synth.stop()


def tap(ui, key, now=0.0):
    box = next(w[0] for w in ui.widgets if w[3] == key)
    ui.touch("down", box[0] + 2, box[1] + 2, now)
    ui.touch("up", box[0] + 2, box[1] + 2, now)
    ui.render(now, force=True)


def test_synth_a_in_the_mixer_and_the_routes(studio):
    app, ui, screen, bridge, plugins = studio
    host = app.plugin_host
    if not hasattr(plugins.Studio, "add_sound_source"):
        pytest.skip("a Studio without add_sound_source")
    node = {"id": 7, "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Audio/Source", "node.name": "synths-a"}}}
    _, sources = bridge.pick_nodes([node], host)
    assert [(s["label"], s["internal"]) for s in sources] == [("SYNTH A", True)]
    assert [r"^FLUID Synth \(synths-a\)", "SYNTH A"] in host.midi_names()


def test_the_synths_screen(studio):
    app, ui, screen, _, _ = studio
    soundfont(TMP / "system" / "TimGM6mb.sf2", [(0, 0, "Piano"), (0, 5, "EP"), (0, 9, "Bells"), (0, 11, "Vibes"),
                                                (0, 19, "Organ"), (128, 0, "Drums")])
    soundfont(TMP / "library" / "soundfonts" / "Strings.sf2", [(0, 48, "Strings")])
    conf = app.state["plugins"]["synths"]["settings"]
    conf.pop("slots", None)
    ui.render(1.0, force=True)
    assert conf["slots"]["A"]["font"] == "TimGM6mb.sf2"        # the system's General MIDI one first
    keys = {w[3] for w in ui.widgets}
    assert {"synths-on", "synths-font-next", ("synths-preset", 0, 0), "synths-down"} <= keys
    tap(ui, ("synths-preset", 0, 5))
    assert (conf["slots"]["A"]["bank"], conf["slots"]["A"]["program"]) == (0, 5)
    tap(ui, "synths-down")
    assert ("synths-preset", 128, 0) in {w[3] for w in ui.widgets}
    tap(ui, "synths-font-prev")                                    # (by name: ... Strings, TimGM6mb)
    assert conf["slots"]["A"]["font"] == "Strings.sf2" and conf["slots"]["A"]["program"] == 48
    assert app.plugin_host.web_command("synths", "preset", {"font": "TimGM6mb.sf2", "program": 9}) == "SYNTH A: Bells"
    assert app.plugin_host.web_status()["synths"]["slots"]["A"]["preset"] == [0, 9, "Bells"]
    assert conf["slots"]["A"]["level"] == 1.0                       # (louder than 0.1.0's 0.5)
    tap(ui, "synths-level-up")
    assert conf["slots"]["A"]["level"] == 1.3 and screen.synth.files["want"] and screen.synth.conf["level"] == 1.3
    for _ in range(9):
        tap(ui, "synths-level-up")
    assert conf["slots"]["A"]["level"] == 2.0                       # (no louder than the last step)
    assert app.plugin_host.web_command("synths", "level", {"step": -1}) == "SYNTH A level 1.6"
    tap(ui, "synths-on")
    assert conf["slots"]["A"]["on"] is False and screen.synth.text() == "OFF"
    assert app.plugin_host.errors == {}


def test_the_plugin_runs_its_slot(studio):
    """a tick starts the slot process; it gets the sound picked, HOME the preset's name; off, it stops"""
    app, ui, screen, _, _ = studio
    font = soundfont(TMP / "system" / "TimGM6mb.sf2", [(0, 0, "Piano"), (0, 5, "EP")])
    conf = app.state["plugins"]["synths"]["settings"].setdefault("slots", {}).setdefault("A", {})
    conf.update(on=True, font="TimGM6mb.sf2", bank=0, program=5, gain=0.5)   # (0.1.0's gain: gone, level 1.0)
    (TMP / "run" / "synths-a.json").unlink(missing_ok=True)
    LOG.write_text("")
    details = []
    studio_api = app.plugin_host.loaded["synths"]
    if hasattr(studio_api, "set_detail"):
        real = studio_api.set_detail
        studio_api.set_detail = lambda source, text: (details.append((source, text)), real(source, text))

    def ticked():
        app.plugin_host.emit("tick")
        return screen.synth.text() == "PLAYING" and f"select 0 1 0 5" in LOG.read_text()
    wait(ticked, 15)
    assert LOG.read_text().splitlines()[0] == f"load {font}"
    assert "gain 1.00" in LOG.read_text() and "gain" not in conf
    app.plugin_host.emit("tick")
    if hasattr(studio_api, "set_detail"):
        assert details[-1] == ("SYNTH A", "EP")
    screen.synth.set_on(False)
    app.plugin_host.emit("tick")
    wait(lambda: state().get("state") == "stopped", 10)
