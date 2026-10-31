"""The FM-1 Companion Pocket's own web server (its web.py), for the plug-in's tests of FM-1 E-G: two FM-1s plugged
in (A and B), linked to a Studio at 127.0.0.1, and its library jobs pretended (each logged and done at once, a
backup making its file). Run by test_plugin.py in a process of its own (the Pocket's modules share names with the
Studio's):

  python pocket_server.py FM-1-BRIDGE/fm1-bt-bridge FOLDER      prints the port it serves on
"""
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

code, folder = Path(sys.argv[1]), Path(sys.argv[2])
os.environ.update(FM1_LIBRARY=str(folder / "library"), XDG_RUNTIME_DIR=str(folder / "run"),
                  FM1_SD_LIBRARY=str(folder / "sd"), FM1_SETTINGS=str(folder / "settings.json"))
sys.path.insert(0, str(code))

import library  # noqa: E402
import sloop  # noqa: E402
import web  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

import fake_fm1  # noqa: E402  (this folder's: the FM-1 Companion's pretend FM-1)

sloop.fm1_cards = lambda text=None: [2, 3]             # FM-1 A and B plugged in
LOG = folder / "jobs.jsonl"
BACKUP = sloop.Sloop(sloop.Link(mido=fake_fm1.FakeFM1(), time_scale=0.02)).backup()   # a real one, to check uploads


def write_backup(path):
    sloop.save_json(path, BACKUP)


def spawn(args):
    """a library job, pretended: logged, and done (state written as library.py's Job does)"""
    with open(LOG, "a") as f:
        f.write(json.dumps(args) + "\n")
    command = [a for a in args if a not in ("--fm1", "A", "B", "C")][0]
    result = {}
    if command in ("backup", "song-backup"):
        where = "songs" if command == "song-backup" else "backups"
        name = f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_sloop-2.8_manual.json"
        write_backup(library.folder(where) / name)
        result["file"] = name
    elif command in ("restore", "load-project", "song-load", "flash"):
        name = f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_sloop-2.8_before.json"
        write_backup(library.folder("backups") / name)
        result["before"] = name
    now = time.time()
    library.STATE.parent.mkdir(parents=True, exist_ok=True)
    library.STATE.write_text(json.dumps({"job": command, "state": "done", "message": f"{command} done",
                                         "started": now, "finished": now + 0.01, "result": result,
                                         "fm1": args[1] if args[:1] == ["--fm1"] else None}))
    return None


library.spawn = spawn


def keep_status():
    while True:                                        # as the box does: the web page's status, linked to the Studio
        library.write_status({"live": True, "link": {"on": True, "address": "127.0.0.1"}})
        time.sleep(1)


threading.Thread(target=keep_status, daemon=True).start()
time.sleep(0.2)
server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
