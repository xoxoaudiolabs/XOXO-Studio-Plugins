"""Tests for the FM-1 Companion's library jobs (fm1-companion/lib/fm1lib.py) against a pretend FM-1 (fake_fm1.py,
the FM-1 Companion's). No hardware needed.

  python -m pytest tests        (needs mido: pip install mido)
"""
import json
import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fm1-companion" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
TMP = Path(tempfile.mkdtemp(prefix="fm1-plugin-test-"))
os.environ.update(FM1_LIBRARY=str(TMP / "library"), XDG_RUNTIME_DIR=str(TMP / "run"))

import fake_fm1  # noqa: E402
import fm1lib  # noqa: E402
import sloop  # noqa: E402


def use(fake):
    """library jobs connect through the fake"""
    fm1lib.connect = lambda: sloop.Sloop(sloop.Link(mido=fake, time_scale=0.02))


def write_wav(path, seconds=0.3, hz=220):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * i / 44100)))
                               for i in range(int(44100 * seconds))))
    return path


def test_library_jobs():
    fake = fake_fm1.FakeFM1()
    use(fake)
    fm1lib.job_backup(auto=True)
    state = fm1lib.read_state()
    assert state["state"] == "done" and state["job"] == "backup", state
    backups = list((TMP / "library" / "backups").glob("*_auto.json"))
    assert len(backups) == 1 and "sloop-2.7.1" in backups[0].name
    fm1lib.job_backup(auto=True)                                     # nothing changed: no new file
    assert fm1lib.read_state()["result"].get("unchanged")
    fm1lib.job_restore(str(backups[0]))                              # restore backs up first
    assert fm1lib.read_state()["state"] == "done"
    assert list((TMP / "library" / "backups").glob("*_before-restore.json"))
    fm1lib.job_load_project(str(backups[0]), "A", "C")
    assert fake.objects[4] == fake.objects[2]
    saved = fm1lib.job_save_project(str(backups[0]), "D", "Night Drive")
    assert saved.name == "night-drive.json"
    fm1lib.job_load_project(str(saved), "-", "working")
    assert fake.objects[0] == fake.objects[5]
    fm1lib.job_load_sample(4, "drum", [write_wav(TMP / "hit.wav", 0.1)])
    assert fake.objects[35][8:12] == b"DRUM"
    for k in range(25):                                              # pruning keeps the newest 20 auto backups
        (TMP / "library" / "backups" / f"2020-01-01_0000{k:02d}_x_auto.json").write_text("{}")
    fm1lib.prune_auto()
    assert len(list((TMP / "library" / "backups").glob("*_auto.json"))) == 20
    listing = fm1lib.listing()
    assert sorted(listing) == sorted(fm1lib.FOLDERS)
    assert listing["projects"][0]["title"] == "Night Drive"


def test_errors_are_reported():
    use(fake_fm1.FakeFM1())
    bad = TMP / "bad.json"
    bad.write_text("{not json")
    try:
        fm1lib.job_restore(str(bad))
    except sloop.SloopError:
        pass
    state = fm1lib.read_state()
    assert state["state"] == "error" and state["job"] == "restore" and state["message"]


def test_options():
    assert fm1lib.options(["--fm1", "B", "--level", "full", "backup"]) == ["backup"]
    assert fm1lib.FM1 == "B" and fm1lib.PEAK == fm1lib.SAMPLE_LEVELS["full"]
    for bad in (["--fm1", "E", "backup"], ["--level", "loud", "backup"], ["--fm1"]):
        try:
            fm1lib.options(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    fm1lib.FM1, fm1lib.PEAK = "A", fm1lib.SAMPLE_LEVELS["-6 dB"]
    assert fm1lib.main(["--fm1", "E", "backup"]) == 2 and fm1lib.main([]) == 2


def test_newest_firmware_release():
    releases = [{"draft": True, "assets": [{"name": "x.fwsc"}]}, {"tag_name": "v1", "assets": [{"name": "a.zip"}]},
                {"tag_name": "v0", "assets": [{"name": "sloop.fwsc"}]}]
    release, asset = fm1lib.newest_firmware(releases)
    assert release["tag_name"] == "v0" and asset["name"] == "sloop.fwsc"
    assert fm1lib.newest_firmware([]) == (None, None)


def test_firmware_label():
    fm1lib.FIRMWARE.parent.mkdir(parents=True, exist_ok=True)
    fm1lib.FIRMWARE.write_text(json.dumps({"firmware": "FELUCCA SLOOP 2.8"}))
    assert fm1lib.firmware_label() == "SLOOP 2.8"
