"""The DJ decks' music folder on XOXO Studio's web page (web.py), the decks plug-in found as in ~/xoxo-plugins.
Needs a clone of XOXO Studio (xoxo_studio.py). A run of its own:

  python tests/test_decks_web.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xoxo_studio import PLUGINS  # noqa: E402

os.environ["XOXO_PLUGINS"] = str(PLUGINS)                # (before XOXO Studio's test_web sets its own)
import test_web as studio_web  # noqa: E402
from test_web import call, jcall, library  # noqa: E402

studio_web.setup()


def test_dj_music():
    """the DJ decks' music folder: listed, a track added (streamed to disk), deleted; only audio, only plain names"""
    import djlib
    library.write_status({"live": True, "plugins": {"builtin": {"decks": True}}})   # (the decks plug-in on)
    status, body, _ = call("/api/upload?folder=music&name=Night%20Drive.mp3", raw=b"ID3" + b"\0" * 4096)
    assert status == 200, body
    assert (djlib.MUSIC / "Night Drive.mp3").stat().st_size == 4099
    (djlib.MUSIC / "Crate").mkdir(exist_ok=True)
    (djlib.MUSIC / "Crate" / "Deep.flac").write_bytes(b"fLaC")
    tracks = {m["name"]: m for m in jcall("/api/music")[1]}
    assert tracks["Night Drive.mp3"]["top"] and tracks["Night Drive.mp3"]["title"] == "Night Drive"
    assert not tracks["Crate/Deep.flac"]["top"]                       # in a subfolder: listed, not deleted here
    assert call("/api/upload?folder=music&name=notes.txt", raw=b"hi")[0] == 400
    assert call("/api/upload?folder=music&name=..%2Fx.mp3", raw=b"ID3")[0] == 400
    assert jcall("/api/delete", {"folder": "music", "name": "Crate/Deep.flac"})[0] == 404
    assert jcall("/api/delete", {"folder": "music", "name": "Night Drive.mp3"})[1]["ok"]
    assert not (djlib.MUSIC / "Night Drive.mp3").exists()


def test_decks_on_take_music():
    """the decks switched on: a track is taken into their folder; off, it isn't (it's kept)"""
    data = b"ID3" + bytes(64)
    library.write_status({"live": True, "plugins": {"builtin": {"decks": False}}})
    assert call("/api/upload?folder=music&name=t.mp3", raw=data)[0] == 400
    library.write_status({"live": True, "plugins": {"builtin": {"decks": True}}})
    status, reply = jcall("/api/upload?folder=music&name=t.mp3", raw=data)
    assert status == 200 and reply["ok"], reply
    assert jcall("/api/delete", {"folder": "music", "name": "t.mp3"})[1]["ok"]
    library.STATUS.unlink(missing_ok=True)


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"all {len(tests)} passed")
