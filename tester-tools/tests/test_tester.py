"""Tester Tools: the latency test against a pretend synth (its sound back a known number of samples after the
note), the AU stream pw-record writes to a pipe, and the plug-in's screen in XOXO Studio's own code (needs a clone
of XOXO Studio next to this repository's folder, or $XOXO_STUDIO, and Pillow).

  python -m pytest tests
"""
import importlib.util
import io
import os
import struct
import sys
import time
from array import array
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
spec = importlib.util.spec_from_file_location("tester_plugin", PLUGIN / "plugin.py")
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


class PretendSynth:
    """a synth's sound, chunk by chunk: noise, then a note's sound from delay samples after its note-on (by the
    reader's count, as the Studio's would be) till its note-off"""

    def __init__(self, delay, noise=50, loud=8000, deaf=False):
        self.delay, self.noise, self.loud, self.deaf = delay, noise, loud, deaf
        self.pos, self.on_at, self.sent = 0, None, []

    def send(self, messages):
        self.sent += messages
        for m in messages:
            if m[0] & 0xF0 == 0xB0 and m[1] == 123:
                self.on_at = None
            if m[0] == 0x90 and not self.deaf:
                self.on_at = self.pos
            elif m[0] == 0x80:
                self.on_at = None

    def samples(self):
        while True:
            chunk = array("h", [0] * tester.CHUNK)
            for i in range(tester.CHUNK):
                n = self.pos + i
                on = self.on_at is not None and n >= self.on_at + self.delay
                chunk[i] = (self.loud if on else self.noise) * (1 if n % 2 else -1)
            self.pos += tester.CHUNK
            yield chunk


def test_latency_measured():
    """the round trip comes out as the pretend synth's delay, every note; each note off and all notes off after"""
    synth = PretendSynth(delay=1234)
    test = tester.LatencyTest("POCKET FM-1 A", "fm1-pocket-a", synth.send, synth.samples())
    test.run()
    assert test.state == "done" and len(test.times) == tester.TRIES
    assert all(abs(t - 1234 * 1000 / tester.RATE) < 0.01 for t in test.times)
    found = test.result()
    assert found["median"] == round(1234 * 1000 / tester.RATE, 1) and found["heard"] == tester.TRIES
    assert synth.sent.count([0x90, tester.NOTE, tester.VELOCITY]) == tester.TRIES
    assert synth.sent.count([0x80, tester.NOTE, 0]) == tester.TRIES and synth.sent[-1] == [0xBF, 123, 0]


def test_a_note_left_sounding_first():
    """a note still sounding from before: all notes off first, then measured as usual"""
    synth = PretendSynth(delay=480)
    synth.on_at = -10000                                      # (sounding before the test)
    test = tester.LatencyTest("FM-1 A", "fm1-a", synth.send, synth.samples())
    test.run()
    assert synth.sent[:16] == [[0xB0 | ch, 123, 0] for ch in range(16)]
    assert test.state == "done" and test.result()["median"] == 10.0


def test_nothing_comes_back():
    synth = PretendSynth(delay=100, deaf=True)
    test = tester.LatencyTest("FM-1 A", "fm1-a", synth.send, synth.samples())
    test.run()
    assert test.state == "error" and "no sound" in test.error and test.result() is None


def test_au_stream():
    """pw-record to a pipe: an AU header ("dns.": little-endian, as on the Studio; ".snd": big-endian), then
    16-bit samples; the header skipped, the samples as they are"""
    values = [0, 1, -1, 32767, -32768, 1234] * 100
    little = struct.pack("<4sI", b"dns.", 24) + b"\0" * 16 + array("h", values).tobytes() if sys.byteorder == "little" \
        else None
    big_samples = array("h", values)
    if sys.byteorder == "little":
        big_samples.byteswap()
    big = struct.pack(">4sI", b".snd", 32) + b"\0" * 24 + big_samples.tobytes()
    for stream in [s for s in (little, big) if s]:
        got = [v for chunk in tester.au_samples(io.BytesIO(stream)) for v in chunk]
        assert got == values


def studio_code():
    found = Path(os.environ.get("XOXO_STUDIO") or PLUGIN.parent.parent / "XOXO-Studio") / "fm1-bt-bridge"
    if not (found / "plugins.py").exists():
        pytest.skip("needs XOXO Studio's code next to this repository")
    sys.path.insert(0, str(found))
    return found


def test_in_the_studio(tmp_path):
    """switched on in XOXO Studio's plug-in host: its screen picks the Pocket's FM-1 A and its sound, START runs a
    test through send_midi, the result is kept with the Studio's latency step"""
    studio_code()
    import bridge
    import deskui
    import plugins
    (tmp_path / "tester-tools").mkdir()
    for f in ("plugin.json", "plugin.py"):
        (tmp_path / "tester-tools" / f).write_bytes((PLUGIN / f).read_bytes())

    class Capture:
        image, theme = None, None

        def show_rgb(self, img):
            self.image = img

    class Midi:
        net, net_hosts, pads, xo4, controllers, receive_only, send_only = [], {}, False, False, [], [], []

        def __init__(self):
            self.sent = []

        def send_to(self, device, messages):
            self.sent.append((device, messages))
            synth.send(messages)

    synth = PretendSynth(delay=960)
    app = bridge.App(Capture(), dict(bridge.DEFAULTS))
    app.save_settings = lambda: None
    app.midi = Midi()
    app.matrix_lists = lambda: (["BT", "U:POCKET FM-1 A"], ["BT", "U:FM-1 A", "U:POCKET FM-1 A"])
    app.others = [{"id": 1, "name": "alsa_input.felucca", "label": "FM-1 A"},
                  {"id": 2, "name": "fm1-pocket-a", "label": "POCKET FM-1 A"}]
    app.plugin_host = plugins.Host(app, [tmp_path])
    app.plugin_host.start()
    app.plugin_host.set_on("tester-tools", True)
    plugin = app.plugin_host.loaded["tester-tools"]
    assert plugin.midi_devices() == ["FM-1 A", "POCKET FM-1 A"]
    assert plugin.source_nodes()["POCKET FM-1 A"] == "fm1-pocket-a"
    assert plugin.latency() == {"name": "SAFE", "block": 1024, "buffer_ms": 44, "rate": 48000}

    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    label, make = plugin.screens[0]
    screen = make(ui, plugin)
    tool = screen.tester
    assert label == "TESTER" and tool.picked() == ("POCKET FM-1 A", "POCKET FM-1 A")
    tool.pick("device", 1)
    assert tool.picked() == ("FM-1 A", "FM-1 A")             # a device's own sound follows it
    tool.pick("device", 1)
    assert tool.start(synth.samples()) is None
    end = time.monotonic() + 10
    while tool.running() and time.monotonic() < end:
        time.sleep(0.05)
    assert ("POCKET FM-1 A", [[0x90, tester.NOTE, tester.VELOCITY]]) in app.midi.sent
    result = plugin.settings["results"][0]
    assert result["median"] == 20.0 and result["step"] == "SAFE" and result["device"] == "POCKET FM-1 A"
    assert "ROUND TRIP 20 MS" in tool.text()
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (480, 320))
    screen.draw(img, ImageDraw.Draw(img), 0.0)               # (draws, with a result in its list)
