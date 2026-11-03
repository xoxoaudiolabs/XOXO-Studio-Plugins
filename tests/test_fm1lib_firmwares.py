"""Tests for the FM-1 firmwares other than SLOOP in the plug-in's library jobs (fm1-companion/lib/fm1lib.py, 0.5):
Felucca, JIANT, Melodee, Jangada and sloopDX by SLOOP's protocol (sloop.py), Baud Girl's FM-1+VA (baudgirl.py) and
M-VAVE's stock firmware (mvave.py), against the FM-1 Companion's pretend FM-1s (fake_fm1.py), each made from that
firmware's published protocol or the community's notes. None of them tried on a real FM-1 here.

  python -m pytest tests        (needs mido: pip install mido)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fm1-companion" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
TMP = Path(tempfile.mkdtemp(prefix="fm1-plugin-firmwares-"))
os.environ.setdefault("FM1_LIBRARY", str(TMP / "library"))       # (test_fm1lib's, when it ran first)
os.environ.setdefault("XDG_RUNTIME_DIR", str(TMP / "run"))
Path(os.environ["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)

import baudgirl  # noqa: E402
import dx7  # noqa: E402
import fake_fm1  # noqa: E402
import fm1lib  # noqa: E402
import sloop  # noqa: E402


def run(fake, args):
    """fm1lib.py ARGS with every link to the FM-1 going to the fake -> its exit code"""
    was, connect = sloop.Link, fm1lib.connect
    try:
        sloop.Link = lambda card=None: was(mido=fake, time_scale=0.02)
        fm1lib.connect = lambda: sloop.Sloop(sloop.Link())
        return fm1lib.main(args)
    finally:
        sloop.Link, fm1lib.connect = was, connect


def voice(name):
    """a DX7 single voice (155 parameters, all in range) named name"""
    return bytes(145) + name.ljust(10)[:10].encode()


def newest(pattern, name="backups"):
    return sorted(fm1lib.folder(name).glob(pattern))[-1]


def message():
    return fm1lib.read_state()["message"]


def test_fm1va_backup_listing_identify():
    for old in fm1lib.folder("backups").glob("*_auto.json"):     # (other tests': "unchanged" is since the newest)
        old.unlink()
    fake = fake_fm1.FakeFM1VA()
    assert run(fake, ["backup"]) == 0
    path = newest("*_manual.json")
    data = sloop.load_json(path)
    assert data["format"] == "fm1va-presets" and baudgirl.presets_of(data) == fake.presets
    entry = next(b for b in fm1lib.listing()["backups"] if b["name"] == path.name)
    assert entry["presets"] == 128 and not entry.get("damaged")
    assert run(fake, ["backup", "--auto"]) == 0 and run(fake, ["backup", "--auto"]) == 0
    assert fm1lib.read_state()["result"].get("unchanged") and fake.writes == 0
    assert run(fake, ["identify"]) == 0 and message() == "FM-1+VA 102" and fm1lib.firmware_label() == "FM-1+VA 102"


def test_fm1va_restore_and_refusals():
    fake = fake_fm1.FakeFM1VA()
    assert run(fake, ["backup"]) == 0
    path = newest("*_manual.json")
    saved = dict(fake.presets)
    fake.presets[7], fake.presets[100] = fake.presets[9], fake.presets[1]
    assert run(fake, ["restore", str(path)]) == 0
    assert fake.presets == saved and fake.writes == 128
    assert fm1lib.read_state()["result"]["before"].endswith("_before-restore.json")
    playing = fake_fm1.FakeFM1VA()
    playing.playing = True
    assert run(playing, ["restore", str(path)]) == 1 and playing.writes == 0 and "stop it first" in message()
    damaged = TMP / "damaged.json"
    data = sloop.load_json(path)
    data["presets"][3]["voice"] = data["presets"][3]["voice"][:-8]
    sloop.save_json(damaged, data)
    fresh = fake_fm1.FakeFM1VA()
    assert run(fresh, ["restore", str(damaged)]) == 1 and fresh.writes == 0


def test_stock_save_the_sound_and_identify():
    fake = fake_fm1.FakeStock(voice=voice("BRASS 1"))
    assert run(fake, ["dx7-read"]) == 0
    path = fm1lib.folder("patches") / fm1lib.read_state()["result"]["file"]
    assert path.read_bytes() == dx7.voice_message(voice("BRASS 1")) and fake.dx7 == []     # (it only reads)
    assert dx7.describe(path) == {"kind": "voice", "voices": ["BRASS 1"]} and "BRASS 1" in message()
    assert run(fake_fm1.FakeStock(ident="FM-1_015"), ["identify"]) == 0 and message() == "Stock 15"
    assert run(fake_fm1.FakeStock(voice=voice("X")), ["backup"]) == 1      # stock: no backup of its presets


def test_dx7_read_only_on_stock():
    """Baud Girl's, Felucca's: the handshake only, never the read; SLOOP's fake doesn't answer it: refused too"""
    for ident in ("FM-1_079", "FM-1_906"):
        fake = fake_fm1.FakeStock(ident=ident, voice=bytes(155))
        assert run(fake, ["dx7-read"]) == 1
        assert fake.vendor and 0x23 not in fake.vendor and "stock firmware" in message()
    assert run(fake_fm1.FakeFM1(), ["dx7-read"]) == 1


def test_felucca_family_backup_restore():
    """Felucca, JIANT and Melodee (Felucca's backup commands and file), Jangada (SLOOP's commands, its own file)"""
    for fake, kind in ((fake_fm1.FakeFelucca(), "felucca-backup"), (fake_fm1.FakeJiant(), "felucca-backup"),
                       (fake_fm1.FakeMelodee(), "felucca-backup"), (fake_fm1.FakeJangada(), "jangada-backup")):
        assert run(fake, ["backup"]) == 0, message()
        path = fm1lib.folder("backups") / fm1lib.read_state()["result"]["file"]
        assert sloop.load_json(path)["format"] == kind
        saved = dict(fake.objects)
        fake.objects[2] = b""
        assert run(fake, ["restore", str(path)]) == 0, message()
        assert fake.objects == saved, kind
        assert fm1lib.read_state()["result"]["before"].endswith("_before-restore.json")


def test_mixed_families_refused():
    sloop_fake = fake_fm1.FakeFM1()
    assert run(sloop_fake, ["backup"]) == 0
    sloop_backup = fm1lib.folder("backups") / fm1lib.read_state()["result"]["file"]
    felucca = fake_fm1.FakeFelucca()
    saved = dict(felucca.objects)
    assert run(felucca, ["restore", str(sloop_backup)]) == 1 and felucca.objects == saved
    assert "SLOOP" in message() and "Felucca" in message()


def test_dx7_into_sloopdx_bank():
    voices = [dx7.pack(voice(f"DX{i}")) for i in range(32)]
    path = fm1lib.folder("patches") / "dx-bank.syx"
    path.write_bytes(dx7.bank_message(voices))
    fake = fake_fm1.FakeSloopDX()
    others = {k: d for k, d in fake.all_banks().items() if k != 2}
    assert run(fake, ["dx7-send", str(path)]) == 0, message()
    assert fake.objects[8] == b"".join(voices) and fake.cur == 2
    assert {k: d for k, d in fake.all_banks().items() if k != 2} == others
    assert fm1lib.read_state()["result"]["before"].endswith("_before-dx7.json")


def test_dx7_to_melodee_not_felucca():
    voices = [dx7.pack(voice(f"M{i}")) for i in range(32)]
    path = fm1lib.folder("patches") / "m-bank.syx"
    path.write_bytes(dx7.bank_message(voices))
    melodee = fake_fm1.FakeMelodee()
    assert run(melodee, ["dx7-send", str(path), "4"]) == 0, message()
    assert melodee.dx7 == [dx7.voice_message(dx7.unpack(voices[3]))]
    felucca = fake_fm1.FakeFelucca()
    assert run(felucca, ["dx7-send", str(path)]) == 1 and "doesn't take DX7" in message()
    assert getattr(felucca, "dx7", []) == []


def test_x0x_on_an_fm1_left_out():
    """an FM-1 running X0X (charlesvestal/fm1-x0x): said so, nothing asked of it or written (INFO "X0X 1.0"
    enough: the Pocket's FakeX0X needs the Studio's x0x.py)"""
    fake = fake_fm1.FakeFM1(version="X0X 1.0")
    before = set(fm1lib.folder("backups").iterdir())
    assert run(fake, ["backup"]) == 1 and "X0X" in message() and "plug-in" in message()
    assert set(fm1lib.folder("backups").iterdir()) == before


def test_keep_and_the_jobs_fm1():
    assert fm1lib.main(["--keep", "0", "list"]) == 2 and fm1lib.main(["--keep", "x", "list"]) == 2
    try:
        fake = fake_fm1.FakeFM1()
        assert run(fake, ["--keep", "2", "--fm1", "A", "backup", "--auto"]) == 0
        assert fm1lib.read_state()["fm1"] == "A"
        for _ in range(3):
            fake.objects[0] = os.urandom(16)                      # (a change: a new auto backup each time)
            assert run(fake, ["backup", "--auto"]) == 0
        own = [p for p in fm1lib.folder("backups").iterdir() if fm1lib.BOX_MADE.search(p.name)]
        assert len(own) == 2 and fm1lib.folder("backups").glob("*_manual.json")
    finally:
        fm1lib.KEEP = fm1lib.KEEP_AUTO
