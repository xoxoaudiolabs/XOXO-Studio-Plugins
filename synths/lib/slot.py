"""One synth slot, as its own process (started by the Synths plug-in, a systemd user unit on the Studio): its
pw-loopback pair and its engine, kept running while the plug-in is.

  python3 slot.py --slot a

  - the pw-loopback pair, as XO-4's: an Audio/Sink "synths-a-in" the engine plays into, its other side the
    Audio/Source "synths-a", which the Studio's mixer takes as SYNTH A (the plug-in's add_sound_source)
  - FluidSynth: its sound into synths-a-in (its PipeWire driver, PIPEWIRE_NODE), its MIDI an ALSA sequencer client
    "FLUID Synth (synths-a)" (the MIDI routes' SYNTH A), its shell on a pipe from here (never its TCP shell: that
    one listens on every network the Studio is on)
  - the sound wanted, from the plug-in: $XDG_RUNTIME_DIR/synths-a.want, {"id", "font", "bank", "program", "gain"};
    a new id is loaded and picked (the SoundFont, then the preset on all 16 channels), the one before let go
  - its state in $XDG_RUNTIME_DIR/synths-a.json: starting, running (with the id it has), stopped or error (with
    what the engine said)
  - it stops, and takes the engine and the loopback with it, when the plug-in stops touching
    $XDG_RUNTIME_DIR/synths-a.alive (switched off, the Studio stopped), when the engine stops, or on SIGTERM

For a PC test: $SYNTHS_FLUIDSYNTH a JSON list (the pretend engine's command), $SYNTHS_LOOPBACK "off" for no loopback.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
STALE = float(os.environ.get("SYNTHS_STALE") or 10)   # s without the plug-in's touch: it's gone, so is this
LOAD_TIME = 30.0                                # s a SoundFont may take to load (a big one, on a Pi 3)


def files(slot):
    """{what: path} of a slot's files in the runtime folder"""
    return {k: RUNTIME / f"synths-{slot}.{k}" for k in ("json", "alive", "want")}


def engine_command(slot, gain=0.5):
    """FluidSynth's command line (or $SYNTHS_FLUIDSYNTH's), None if it isn't installed"""
    if os.environ.get("SYNTHS_FLUIDSYNTH"):
        return json.loads(os.environ["SYNTHS_FLUIDSYNTH"])
    found = shutil.which("fluidsynth")
    if not found:
        return None
    return [found, "-a", "pipewire", "-m", "alsa_seq", "-r", "48000", "-g", f"{gain:.2f}",
            "-o", f"midi.alsa_seq.id=synths-{slot}", "-o", "synth.polyphony=64", "-o", "synth.cpu-cores=1",
            "-o", "synth.chorus.active=0", "-o", "synth.default-soundfont="]   # (none of its own: 148 MB)


def loopback_command(slot):
    if os.environ.get("SYNTHS_LOOPBACK") == "off":
        return None
    name = f"SYNTH-{slot.upper()}"
    return ["pw-loopback", "--capture-props", f"media.class=Audio/Sink node.name=synths-{slot}-in "
                                              f"audio.position=[FL,FR] node.description={name}-in priority.session=1",
            "--playback-props", f"media.class=Audio/Source node.name=synths-{slot} audio.position=[FL,FR] "
                                f"node.description={name}"]


def read_json(path):
    try:
        found = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def write_json(path, info):
    """written whole (a reader never sees half of it); tried again for a moment if the file is open (Windows)"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(info))
    for _ in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


class Slot:
    def __init__(self, slot):
        self.slot, self.files = slot, files(slot)
        self.loop = self.engine = None
        self.quit = self.stopped = False        # quit: SIGTERM
        self.lines, self.count = [], 0          # the engine's last 200 lines, and how many it has said
        self.heard = threading.Condition()
        self.applied, self.fonts, self.message = None, [], None

    def say(self, state, message=None):
        info = {"state": state, "pid": os.getpid(), "slot": self.slot, "at": time.time(), "applied": self.applied}
        message = message or self.message
        if message:
            info["message"] = str(message)[:200]
        write_json(self.files["json"], info)

    def touched(self):
        try:
            return time.time() - self.files["alive"].stat().st_mtime < STALE
        except OSError:
            return False

    # ---- the engine's shell

    def listen(self):
        for raw in iter(self.engine.stdout.readline, b""):
            with self.heard:
                self.lines = (self.lines + [raw.decode(errors="replace").rstrip()])[-200:]
                self.count += 1
                self.heard.notify_all()

    def send(self, line):
        self.engine.stdin.write((line + "\n").encode())
        self.engine.stdin.flush()

    def wait_for(self, pattern, since, timeout):
        """the first line it said after since (self.count then) that matches, or None"""
        end = time.monotonic() + timeout
        with self.heard:
            while True:
                new = min(self.count - since, len(self.lines))
                for line in (self.lines[-new:] if new > 0 else []):
                    m = re.search(pattern, line)
                    if m:
                        return m
                left = end - time.monotonic()
                if left <= 0 or self.engine.poll() is not None:
                    return None
                self.heard.wait(min(left, 0.5))

    def apply(self, want):
        """the wanted sound: its SoundFont loaded (if it isn't already), its preset on all 16 channels"""
        font = str(want.get("font") or "")
        if font and (not self.fonts or self.fonts[-1][1] != font):
            with self.heard:
                since = self.count
            self.send(f"load \"{font}\"" if " " in font else f"load {font}")
            m = self.wait_for(r"loaded SoundFont has ID (\d+)|error:.*|[Ff]ailed to load.*", since, LOAD_TIME)
            if not m or not m.group(1):
                self.message = f"couldn't load {Path(font).name}" + (f": {m.group(0)}" if m else "")
                return
            for old, _ in self.fonts:
                self.send(f"unload {old}")
            self.fonts = [(int(m.group(1)), font)]
        if self.fonts:
            bank, program = int(want.get("bank") or 0), int(want.get("program") or 0)
            for channel in range(16):
                self.send(f"select {channel} {self.fonts[-1][0]} {bank} {program}")
        if want.get("gain") is not None:
            self.send(f"gain {float(want['gain']):.2f}")
        self.message = None

    # ---- running

    def run(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        self.say("starting")
        command = engine_command(self.slot)
        if command is None:
            self.say("error", "FluidSynth isn't installed (sudo apt install fluidsynth)")
            return 1
        loop = loopback_command(self.slot)
        if loop:
            subprocess.run(["pkill", "-f", f"^pw-loopback .*node.name=synths-{self.slot}-in"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.loop = subprocess.Popen(loop, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)                     # (the sink there before the engine looks for it)
        env = dict(os.environ, PIPEWIRE_NODE=f"synths-{self.slot}-in")
        try:
            self.engine = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, env=env)
        except OSError as e:
            self.say("error", e)
            self.stop(keep_state=True)
            return 1
        threading.Thread(target=self.listen, daemon=True).start()
        self.say("running")
        try:
            while not self.quit:
                if self.engine.poll() is not None:
                    time.sleep(0.2)             # (its last words read)
                    said = [line for line in self.lines if line.strip() and not line.strip() == ">"]
                    self.say("error", f"the engine stopped ({self.engine.returncode}): "
                                      + (said[-1].lstrip("> ") if said else "it didn't say why"))
                    self.stop(keep_state=True)
                    return 1
                if not self.touched():
                    break
                want = read_json(self.files["want"])
                if want and want.get("id") != self.applied:
                    try:
                        self.apply(want)
                    except OSError as e:        # (the engine's pipe closed: it stopped, said next time round)
                        self.message = str(e)
                    self.applied = want.get("id")
                    self.say("running")
                time.sleep(0.2)
        finally:
            self.stop()
        return 0

    def stop(self, keep_state=False):
        if self.stopped:
            return
        self.stopped = True
        if self.engine and self.engine.poll() is None:
            try:
                self.send("quit")
            except OSError:
                pass
        for proc in (self.engine, self.loop):
            if proc and proc.poll() is None:
                try:
                    proc.wait(2)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        if not keep_state:
            self.say("stopped")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True, choices=list("ab"))
    args = parser.parse_args(argv)
    slot = Slot(args.slot)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: setattr(slot, "quit", True))
    return slot.run()


if __name__ == "__main__":
    sys.exit(main())
