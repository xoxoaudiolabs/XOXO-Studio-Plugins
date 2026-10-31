#!/usr/bin/env python3
"""The FM-1 library on XOXO Studio: backups, projects, songs, samples, DX7 patches and firmware, one job at a time.
The FM-1 Companion's library.py (xoxoaudiolabs/FM-1-Companion), cut down to the FM-1's jobs for the plug-in: the
Studio has its own samples, recordings and SD import, and its own updates.

  fm1lib.py [--fm1 A-D] [--level full|-3 dB|-6 dB] COMMAND ...
                                      --fm1: which FM-1 with two or more plugged in (A: the lowest USB port), --level: a
                                      sample's loudest point in its slot (-6 dB unless said)
  fm1lib.py backup [--auto]           back up the FM-1 (SLOOP 2.3+) into ~/fm1-library/backups
  fm1lib.py restore FILE              a whole backup back onto the FM-1 (backs up first)
  fm1lib.py load-project FILE SRC TARGET
                                      a project into the FM-1: SRC working/A-D in a backup (- for a project
                                      file), TARGET working/A-D (backs up first)
  fm1lib.py save-project FILE SRC NAME
                                      a backup's project as its own file in ~/fm1-library/projects
  fm1lib.py song-backup [NAME]        the FM-1's song (SLOOP 2.5+: sections A-D and the song order) into
                                      ~/fm1-library/songs
  fm1lib.py song-load FILE            a song back onto the FM-1 (backs up first)
  fm1lib.py dx7-send FILE [VOICE]     a DX7 bank (.syx), or one voice of it (1-32), to an FM-1 firmware that
                                      takes them; not to SLOOP or Clipper, which don't
  fm1lib.py load-sample SLOT NAME WAV...
                                      WAV files into USR SLOT (1-4), one zone each
  fm1lib.py flash FILE.fwsc           install a firmware package (backs up first when it can)
  fm1lib.py fetch sloop|clipper       download the newest SLOOP or Clipper release into ~/fm1-library/firmware
  fm1lib.py identify                  what the FM-1 runs ("SLOOP 2.8"), as a job
  fm1lib.py info                      what the FM-1 runs, as JSON
  fm1lib.py list                      the library as JSON

Progress and the result go to $XDG_RUNTIME_DIR/fm1-companion-job.json (the plug-in reads it); one job runs at a
time. Exit code 0 when the job worked. The plug-in starts these as their own processes (plugin.py's Jobs): the
Studio never imports this, so sloop.py, mido and the vendored SLOOP tools stay out of its process.
"""
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sloop  # noqa: E402

LIBRARY = Path(os.environ.get("FM1_LIBRARY", Path.home() / "fm1-library"))   # the Studio's library, too
FOLDERS = ("backups", "projects", "songs", "patches", "firmware")            # (samples: the Studio's own)
SUFFIXES = {"backups": (".json",), "projects": (".json",), "songs": (".json",), "patches": (".syx",),
            "firmware": (".fwsc",), "samples": (".wav",)}
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
STATE, LOCK = RUNTIME / "fm1-companion-job.json", RUNTIME / "fm1-companion-job.lock"
FIRMWARE = RUNTIME / "fm1-companion-firmware.json"     # what the FM-1 last said it runs
KEEP_AUTO = 20
FIRMWARES = {"sloop": ("SLOOP", "isod89/sloop-fm1"),            # isod89's firmwares, both based on Felucca
             "clipper": ("Clipper", "isod89/clipper-fm1")}       # (Clipper: experimental)
RELEASES = "https://api.github.com/repos/{}/releases?per_page=10"
# a sample's loudest point in the slot (16-bit): SLOOP's own uploader goes to 30000, ~0.8 dB below full scale,
# which leaves the FM-1 no room when it mixes a sample with other notes and sounds: it clips
SAMPLE_LEVELS = {"full": 30000, "-3 dB": 23197, "-6 dB": 16422}
LETTERS = "ABCD"                             # the Studio's FM-1s, by USB port
FM1 = "A"                                    # --fm1
PEAK = SAMPLE_LEVELS["-6 dB"]                # --level


def folder(name):
    path = LIBRARY / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def slug(text):
    return re.sub(r"[^A-Za-z0-9.]+", "-", str(text)).strip("-").lower() or "fm1"


# ---------------------------------------------------------------- one job at a time, with its progress

class Busy(Exception):
    pass


class Job:
    """The running job: holds the lock and writes its progress where the plug-in looks."""

    def __init__(self, name):
        self.name, self.lock = name, None
        self.status = {"job": name, "state": "running", "step": "", "percent": None, "message": "",
                       "started": time.time(), "pid": os.getpid()}

    def __enter__(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        self.lock = open(LOCK, "a")
        try:
            import fcntl
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:                    # (Windows test runs: no lock)
            pass
        except OSError:
            self.lock.close()
            raise Busy("another library job is running")
        self.write()
        return self

    def __exit__(self, kind, error, trace):
        if kind is not None and self.status["state"] == "running":
            message = str(error) if isinstance(error, (sloop.SloopError, Busy, OSError, ValueError)) else repr(error)
            self.fail(message)
        self.lock.close()
        return False

    def write(self):
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.status))
        tmp.replace(STATE)

    def step(self, step, percent=None, message=""):
        self.status.update(step=step, percent=percent, message=message)
        self.write()
        print(f"{step} {'' if percent is None else f'{percent:3.0f}% '}{message}".rstrip(), flush=True)

    def progress(self, step):
        """a progress(done, total) callback that updates at most a few times a second"""
        last = [0.0]

        def report(done, total):
            now = time.monotonic()
            if now - last[0] > 0.3 or done >= total:
                last[0] = now
                self.step(step, min(100.0, 100.0 * done / max(total, 1)))
        return report

    def done(self, message, **result):
        self.status.update(state="done", message=message, percent=100, finished=time.time(), result=result)
        self.write()
        print("done:", message, flush=True)

    def fail(self, message):
        self.status.update(state="error", message=message, finished=time.time())
        self.write()
        print("error:", message, file=sys.stderr, flush=True)


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- the device

def target_card():
    """the sound card of the FM-1 the library works on: with two or more plugged in, FM1 (A: the lowest USB port,
    as the plug-in names them); None with one (whichever it is)"""
    cards = sloop.fm1_cards()
    n = LETTERS.index(FM1)
    if len(cards) < 2 and n == 0:
        return None
    if n >= len(cards):
        raise sloop.SloopError("notfound", f"No FM-1 {FM1} plugged in")
    return cards[n]


def connect():
    dev = sloop.Sloop(sloop.Link(card=target_card()))
    try:
        FIRMWARE.write_text(json.dumps({"firmware": str(dev.version)}))
    except OSError:
        pass
    return dev


def firmware_label():
    """"SLOOP 2.8" from what the FM-1 last said ("FELUCCA SLOOP 2.8"); None if nothing has asked it yet. Its
    USB name says Felucca whatever it runs."""
    try:
        words = str(json.loads(FIRMWARE.read_text())["firmware"]).split()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if len(words) > 1 and words[0].upper() == "FELUCCA" and not any(c.isdigit() for c in words[1]):
        words = words[1:]
    return " ".join(w if any(c.isdigit() for c in w) or w.upper() == "SLOOP" else w.capitalize()
                    for w in words) or None


def safety_backup(dev, job, why):
    """a backup before anything is written to the FM-1; None if this firmware can't make one"""
    if not dev.can_backup():
        return None
    job.step("Backing up first", 0)
    data = dev.backup(job.progress("Backing up first"))
    return write_backup(data, why)


def write_backup(data, kind):
    when = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = folder("backups") / f"{when}_{slug(data.get('firmware'))}_{kind}.json"
    sloop.save_json(path, data)
    if kind == "auto":
        prune_auto()
    return path


def prune_auto():
    autos = sorted(folder("backups").glob("*_auto.json"))
    for old in autos[:-KEEP_AUTO]:
        old.unlink(missing_ok=True)


# ---------------------------------------------------------------- the jobs

def job_backup(auto=False):
    with Job("backup") as job:
        job.step("Connecting")
        dev = connect()
        dev.require_backup()
        data = dev.backup(job.progress("Backing up"))
        if auto:                               # timed backups: no new file when nothing changed
            latest = newest_auto()
            if latest and same_content(latest, data):
                job.done(f"No changes since {latest.name[11:13]}:{latest.name[13:15]}", file=latest.name,
                         unchanged=True)
                return
        path = write_backup(data, "auto" if auto else "manual")
        job.done(f"Backed up {dev.version}", file=path.name)


def newest_auto():
    autos = sorted(folder("backups").glob("*_auto.json"))
    return autos[-1] if autos else None


def same_content(path, data):
    """the backup file holds exactly the objects in data (dates and firmware strings aside)"""
    try:
        return sloop.objects_of(sloop.load_json(path)) == sloop.objects_of(data)
    except sloop.SloopError:
        return False


def job_restore(file):
    with Job("restore") as job:
        backup = sloop.load_json(file)
        sloop.objects_of(backup)               # damaged files stop here, before anything is written
        job.step("Connecting")
        dev = connect()
        sloop.same_family(dev.version, backup.get("firmware"))      # before anything, even the backup
        dev.check_stopped()
        before = safety_backup(dev, job, "before-restore")
        dev.restore(backup, job.progress("Restoring"))
        job.done(f"Restored {Path(file).name}", before=before and before.name)


def job_load_project(file, source, target):
    if target not in sloop.PROJECT_IDS:
        raise ValueError("TARGET is working, A, B, C or D")
    with Job("load-project") as job:
        project = sloop.load_json(file)
        data = sloop.project_from(project, source)
        job.step("Connecting")
        dev = connect()
        sloop.same_family(dev.version, project.get("firmware"))     # before anything, even the backup
        dev.check_stopped()
        before = safety_backup(dev, job, "before-project")
        dev.put_project(data, target, job.progress("Loading project"), firmware=project.get("firmware"))
        where = "the working project" if target == "working" else f"project {target}"
        job.done(f"Loaded into {where}", before=before and before.name)


def job_save_project(file, source, name):
    backup = sloop.load_json(file)
    data = sloop.project_from(backup, source)
    path = folder("projects") / f"{slug(name)}.json"
    sloop.save_json(path, sloop.project_file(data, name, backup.get("firmware"), f"{Path(file).name}:{source}"))
    print("saved", path)
    return path


def job_song_backup(name=None):
    """the song on the FM-1 (its four sections and song order) as a song file"""
    with Job("song-backup") as job:
        job.step("Connecting")
        dev = connect()
        sections, order = dev.read_song(job.progress("Reading the song"))
        when = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        name = name or f"Song {datetime.now().strftime('%m-%d %H:%M')}"
        path = folder("songs") / f"{when}_{slug(name)}.json"
        sloop.save_json(path, sloop.song_file(sections, order, name, dev.version))
        steps, _ = sloop.song_steps(order)
        used = "".join(n for n in sloop.SECTIONS if sections[n])
        job.done(f"Saved {name}: {len(steps)} steps, sections {used or 'none'}", file=path.name)


def job_song_load(file):
    with Job("song-load") as job:
        song = sloop.load_json(file)
        sections, order = sloop.song_from(song)  # damaged files stop here, before anything is written
        job.step("Connecting")
        dev = connect()
        sloop.same_family(dev.version, song.get("firmware"))        # before anything, even the backup
        dev.check_stopped()
        before = safety_backup(dev, job, "before-song")
        dev.put_song(sections, order, job.progress("Loading the song"), firmware=song.get("firmware"))
        job.done(f"Loaded {song.get('name') or Path(file).stem}", before=before and before.name)


def job_dx7_send(file, voice=None):
    """a DX7 bank, or one of its voices (1-32), to the FM-1's MIDI: only the two standard DX7 messages (dx7.py).
    SLOOP and Clipper answer SLOOP's INFO and don't take DX7 SysEx: not sent to them"""
    import dx7
    with Job("dx7-send") as job:
        try:
            message = dx7.to_send(file, None if voice is None else voice - 1)
            what = dx7.describe(file)
        except (OSError, dx7.DX7Error) as e:
            raise sloop.SloopError("bad", f"{Path(file).name}: {e}")
        job.step("Connecting")
        link = sloop.Link(card=target_card())
        try:
            try:
                version = sloop.Sloop(link).version
            except sloop.SloopError as e:
                if e.code != "noreply":
                    raise
                version = None                 # (no SLOOP protocol: another firmware)
            if sloop.family(version):
                raise sloop.SloopError("family", f"{version} doesn't take DX7 patches (SLOOP has its own FM6 bank)")
            job.step("Sending")
            link.out.send(link.mido.Message("sysex", data=list(message[1:-1])))
            time.sleep(0.5)                    # (a bank is 4 KB: let it go out before the port closes)
        finally:
            link.close()
        if voice is None and what["kind"] == "bank":
            job.done(f"Sent {Path(file).stem}: 32 voices (on the FM-1, pick the bank it goes to)")
        else:
            job.done(f"Sent {what['voices'][0 if voice is None else voice - 1] or 'the voice'}")


def job_load_sample(slot, name, wavs):
    if slot not in (1, 2, 3, 4):
        raise ValueError("SLOT is 1, 2, 3 or 4")
    with Job("load-sample") as job:
        # no safety backup: a sample load only replaces that one slot, and the WAV it came from stays in the
        # library. Converting first means a bad WAV stops the job before the FM-1 is touched.
        job.step("Converting")
        header, data = sloop.build_slot(name, wavs, PEAK)
        job.step("Connecting")
        dev = connect()
        dev.require_sample_slots()
        dev.check_stopped()
        done, report = [0], job.progress("Loading sample")

        def moved(n):
            done[0] += n
            report(done[0], len(data))

        dev.write_sample_slot(slot - 1, header, data, moved)
        job.done(f"USR{slot}: {name.upper()[:8]}")


def job_flash(package):
    import fm1_install
    with Job("flash") as job:
        if len(sloop.fm1_cards()) > 1:         # mid-update the FM-1 restarts as another device: the installer
            raise sloop.SloopError("two", "Unplug the other FM-1 first")    # could pick up the wrong one
        job.step("Checking the package")
        product, image = fm1_install.load_package(package, False)   # a bad package stops here
        job.step("Connecting")
        before = None
        try:
            dev = connect()
            dev.check_stopped()
            before = safety_backup(dev, job, "before-flash")
            dev.link.close()
        except sloop.SloopError as e:
            if e.code == "stop":
                raise
            # not SLOOP's editor (Felucca, stock, the update loader): flash without a backup
        updater = fm1_install.Updater(fm1_install.MidoBackend())
        device = updater.find()
        if not device:
            raise sloop.SloopError("notfound", "FM-1 not found for the update")
        steps = {"start": "Starting update", "loader": "Update mode", "reboot": "Restarting", "done": "Done"}

        def progress(kind, arg=None):
            if kind == "write":
                job.step("Writing", arg)
            elif kind == "check":
                job.step("Checking", None)
            else:
                job.step(steps.get(kind, kind))

        try:
            updater.install(device, image, product, progress)
        except fm1_install.InstallError as e:
            raise sloop.SloopError("rc", str(e))
        job.done(f"Installed {Path(package).stem}", product=product, before=before and before.name)


def newest_firmware(releases):
    """(release, its .fwsc asset) of the newest published release that has one (Clipper's are marked
    experimental, so GitHub's "latest" can't be relied on)"""
    for release in releases:
        if release.get("draft"):
            continue
        asset = next((a for a in release.get("assets", []) if a["name"].endswith(".fwsc")), None)
        if asset:
            return release, asset
    return None, None


def job_fetch(name):
    import fm1_install
    if name not in FIRMWARES:
        raise ValueError(f"fetch {' or '.join(FIRMWARES)}")
    title, repo = FIRMWARES[name]
    with Job(f"fetch-{name}") as job:
        job.step("Checking GitHub")
        request = urllib.request.Request(RELEASES.format(repo), headers={"Accept": "application/vnd.github+json",
                                                                         "User-Agent": "fm1-companion-plugin"})
        with urllib.request.urlopen(request, timeout=20) as reply:
            release, asset = newest_firmware(json.load(reply))
        if not asset:
            raise ValueError(f"no {title} firmware file on GitHub")
        target = folder("firmware") / asset["name"]
        if target.exists() and target.stat().st_size == asset["size"]:
            job.done(f"Already have {asset['name']}", file=target.name)
            return
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as reply, open(tmp, "wb") as out:
            total, got = asset["size"], 0
            while chunk := reply.read(65536):
                out.write(chunk)
                got += len(chunk)
                job.step("Downloading", 100.0 * got / max(total, 1))
        fm1_install.load_package(str(tmp), False)      # a damaged download never gets listed
        tmp.replace(target)
        job.done(f"Downloaded {asset['name']}", file=target.name, tag=release.get("tag_name"))


def listing():
    """{folder: [{name, bytes, date, ...}]} newest first, each file with what's in it"""
    out = {}
    for name in FOLDERS:
        entries = []
        for path in sorted(folder(name).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES[name] or path.name.startswith("."):
                continue
            entry = {"name": path.name, "bytes": path.stat().st_size, "date": path.stat().st_mtime}
            if name == "backups":
                try:
                    entry.update(sloop.describe(sloop.load_json(path)))
                except sloop.SloopError:
                    entry["damaged"] = True
            elif name == "songs":
                try:
                    song = sloop.load_json(path)
                    sections, order = sloop.song_from(song)
                    steps, loop = sloop.song_steps(order)
                    entry.update(title=song.get("name"), firmware=song.get("firmware"), steps=len(steps), loop=loop,
                                 sections="".join(n for n in sloop.SECTIONS if sections[n]))
                except sloop.SloopError:
                    entry["damaged"] = True
            elif name == "patches":
                import dx7
                try:
                    entry.update(dx7.describe(path))
                except (OSError, dx7.DX7Error):
                    entry["damaged"] = True
            elif name == "projects":
                try:
                    project = sloop.load_json(path)
                    entry.update(firmware=project.get("firmware"), title=project.get("name"))
                except sloop.SloopError:
                    entry["damaged"] = True
            entries.append(entry)
        out[name] = entries
    return out


def options(argv):
    """--fm1 A|B and --level LEVEL off the front of argv -> the rest"""
    global FM1, PEAK
    while argv and argv[0] in ("--fm1", "--level"):
        if len(argv) < 2:
            raise ValueError(f"{argv[0]} needs a value")
        if argv[0] == "--fm1":
            if len(argv[1]) != 1 or argv[1] not in LETTERS:
                raise ValueError(f"--fm1 is {LETTERS[0]} to {LETTERS[-1]}")
            FM1 = argv[1]
        else:
            if argv[1] not in SAMPLE_LEVELS:
                raise ValueError(f"--level is {', '.join(SAMPLE_LEVELS)}")
            PEAK = SAMPLE_LEVELS[argv[1]]
        argv = argv[2:]
    return argv


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        argv = options(argv)
    except ValueError as e:
        print("error:", e, file=sys.stderr)
        return 2
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    command, args = argv[0], argv[1:]
    try:
        if command == "backup":
            job_backup(auto="--auto" in args)
        elif command == "restore" and len(args) == 1:
            job_restore(args[0])
        elif command == "load-project" and len(args) == 3:
            job_load_project(args[0], args[1], args[2])
        elif command == "save-project" and len(args) == 3:
            job_save_project(*args)
        elif command == "song-backup" and len(args) <= 1:
            job_song_backup(args[0] if args else None)
        elif command == "song-load" and len(args) == 1:
            job_song_load(args[0])
        elif command == "dx7-send" and len(args) in (1, 2):
            job_dx7_send(args[0], int(args[1]) if len(args) == 2 else None)
        elif command == "load-sample" and len(args) >= 3:
            job_load_sample(int(args[0]), args[1], args[2:])
        elif command == "flash" and len(args) == 1:
            job_flash(args[0])
        elif command == "fetch" and len(args) == 1:
            job_fetch(args[0])
        elif command == "identify":
            with Job("identify") as job:
                dev = connect()
                job.done(firmware_label() or str(dev.version))
        elif command == "info":
            dev = connect()
            print(json.dumps({**dev.info, "can_backup": dev.can_backup()}))
        elif command == "list":
            print(json.dumps(listing(), indent=1))
        else:
            print(__doc__)
            return 2
        return 0
    except (sloop.SloopError, Busy, OSError, ValueError) as e:
        print("error:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
