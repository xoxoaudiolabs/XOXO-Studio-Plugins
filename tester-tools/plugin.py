"""Tester Tools for XOXO Studio: small tools for testing the Studio and its gear, as a plug-in (XOXO Studio's
docs/PLUGINS.md). Its screen: MORE > PLUG-INS > TESTER.

  - LATENCY (0.1): a note sent to a MIDI device and its sound timed coming back into the Studio, a few times over:
    the round trip from a note leaving the Studio to its sound arriving. For the Pocket link as a snake: POCKET
    FM-1 A (its MIDI over the link) and its sound (over the link, back), at each of the Studio's latency steps.
    It works for a synth on USB too (an FM-1). The sound is read from pw-record as it arrives, the note
    sent when a known number of samples has come in, and the sound's first sample over the noise found after
    that: what comes out is the whole round trip (MIDI out, the synth, its sound back through the Studio's
    capture), give or take a block of the Studio's (SAFE: 21 ms, LOWER: 5 ms). One-way is less than that

Needs a Studio with send_midi, midi_devices and source_nodes (API 1 additions, 2026-11-01).
"""
import statistics
import subprocess
import sys
import threading
import time
from array import array

API = 1
VERSION = "0.2.0"

RATE = 48000
TRIES = 5                                      # notes a test plays
NOTE, VELOCITY = 60, 110
QUIET = 0.4                                    # s of the source before the first note: its noise floor
SETTLE = 4.0                                   # s at most for the synth to go quiet first (all notes off)
LISTEN = 1.5                                   # s a note is listened for before it counts as not heard
GAP = 0.5                                      # s of quiet between notes (its tail gone)
FLOOR = 600                                    # the smallest level that counts as sound (of 32767)
CHUNK = 240                                    # samples read at a time (5 ms)
KEEP = 8                                       # results kept (the screen's list, the web page's)


def record_command(node):
    """the source's sound as it comes, mono 16-bit at RATE, to stdout (pw-record writes it as an AU file there)"""
    return ["pw-record", "--target", node, "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"]


def au_samples(stream):
    """16-bit samples from an AU stream (pw-record's to a pipe: ".snd" big-endian, "dns." little-endian), chunk
    by chunk; raw samples (no header) as they are"""
    head = stream.read(8)
    if len(head) < 8:
        return
    big = head[:4] == b".snd"
    if head[:4] in (b".snd", b"dns."):
        size = int.from_bytes(head[4:8], "big" if big else "little")
        stream.read(max(0, size - 8))
        left = b""
    else:
        big, left = False, head
    while True:
        data = left + stream.read(CHUNK * 2)
        if not data or len(data) < 2:
            return
        cut = len(data) - len(data) % 2
        left = data[cut:]
        samples = array("h", data[:cut])
        if big != (sys.byteorder == "big"):
            samples.byteswap()
        yield samples


class LatencyTest:
    """one test: TRIES notes to device, timed in node's sound. samples: chunks of the sound (a generator), or None
    for pw-record's; send(messages): to the device"""

    def __init__(self, device, node, send, samples=None, note=NOTE):
        self.device, self.node, self.send, self.note = device, node, send, note
        self.samples, self.proc = samples, None
        self.samples_own = samples is None      # (pw-record's: started afresh for a second attempt)
        self.times, self.state, self.error = [], "running", None
        self.source = None
        self.at = 0                            # samples read so far

    def run(self):
        try:
            self.attempt()
            if not self.times and self.state != "stopped" and self.samples_own:   # (a synth's input opened just
                self.close()                    # now can send silence at first, an FM-1's: once more, afresh)
                self.samples, self.at, self.error = None, 0, None
                self.attempt()
            self.state = "done" if self.times else "stopped" if self.state == "stopped" else "error"
            if not self.times and self.state == "error":
                self.error = self.error or "no sound came back"
        except (OSError, ValueError) as e:
            self.state, self.error = "error", str(e)
        finally:
            self.send([[0xB0 | ch, 123, 0] for ch in range(16)])   # (all notes off, whatever happened)
            self.close()

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None

    def attempt(self):
        try:
            if self.samples is None:
                self.proc = subprocess.Popen(record_command(self.node), stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL)
                self.samples = au_samples(self.proc.stdout)
            self.measure()
        finally:
            self.send([[0xB0 | ch, 123, 0] for ch in range(16)])

    def read(self):
        chunk = next(self.samples, None)
        if chunk is None:
            raise ValueError("the sound stopped (is the source there?)")
        self.at += len(chunk)
        return chunk

    def level(self, seconds):
        """the loudest sample over the next seconds"""
        end, loud = self.at + int(seconds * RATE), 0
        while self.at < end:
            chunk = self.read()
            loud = max(loud, max(map(abs, chunk), default=0))
        return loud

    def hush(self):
        """all notes off on every channel, then up to SETTLE s for the sound to die away (a note left sounding
        from before, or a long release, would hide the test's notes)"""
        self.send([[0xB0 | ch, 123, 0] for ch in range(16)])
        end = self.at + int(SETTLE * RATE)
        while self.at < end and self.level(0.1) > FLOOR:
            pass

    def measure(self):
        self.hush()
        noise = self.level(QUIET)
        threshold = max(FLOOR, noise * 4)
        for _ in range(TRIES):
            if self.state == "stopped":
                return
            sent = self.at
            self.send([[0x90, self.note, VELOCITY]])
            heard = None
            while heard is None and self.at - sent < LISTEN * RATE:
                start = self.at
                chunk = self.read()
                heard = next((start + i for i, v in enumerate(chunk) if abs(v) > threshold), None)
            self.send([[0x80, self.note, 0]])
            if heard is None:
                self.error = f"no sound over {threshold} in {LISTEN:g} s"
                continue
            self.times.append((heard - sent) * 1000 / RATE)
            quiet_since, give_up = self.at, self.at + 4 * RATE   # its tail gone before the next
            while self.at - quiet_since < GAP * RATE and self.at < give_up:
                if max(map(abs, self.read()), default=0) > threshold:
                    quiet_since = self.at

    def stop(self):
        self.state = "stopped"

    def result(self):
        """{"median", "min", "max" (ms), "tries", "heard"} or None"""
        if not self.times:
            return None
        return {"median": round(statistics.median(self.times), 1), "min": round(min(self.times), 1),
                "max": round(max(self.times), 1), "tries": TRIES, "heard": len(self.times)}


class Tester:
    """the plug-in: the test running, the results kept (settings["results"])"""

    def __init__(self, studio):
        self.studio, self.test = studio, None
        self.device = self.source = None
        self.note = NOTE                       # (the web command's "note": 36 plays a Studio's first pad)

    def devices(self):
        return self.studio.midi_devices() if hasattr(self.studio, "midi_devices") else []

    def sources(self):
        return self.studio.source_nodes() if hasattr(self.studio, "source_nodes") else {}

    def picked(self):
        """(device, source) to test: the ones picked while they're there, else a Pocket FM-1 and its own sound,
        else the first device and the source of the same name"""
        devices, sources = self.devices(), self.sources()
        device = self.device if self.device in devices else next(
            (d for d in devices if "POCKET" in d.upper() and d in sources), devices[0] if devices else None)
        own = "POCKET" if device == "NET" and "POCKET" in sources else "STUDIO" if device == "NET" else device
        # (NET: a linked Pocket's whole session, its POCKET; or a Studio following this one, its STUDIO)
        source = self.source if self.source in sources else (own if own in sources else next(iter(sources), None))
        return device, source

    def pick(self, which, step):
        devices, sources = self.devices(), list(self.sources())
        device, source = self.picked()
        if which == "device" and devices:
            self.device = devices[((devices.index(device) if device in devices else 0) + step) % len(devices)]
            own = "POCKET" if self.device == "NET" else self.device
            if own in sources:                  # (its own sound, when it has a source of the same name)
                self.source = own
        elif which == "source" and sources:
            self.source = sources[((sources.index(source) if source in sources else 0) + step) % len(sources)]

    def running(self):
        return bool(self.test and self.test.state == "running")

    def start(self, samples=None):
        """a test on the picked device and source -> an error message, or None"""
        if self.running():
            return "a test is running"
        if not hasattr(self.studio, "send_midi"):
            return "needs a newer XOXO Studio (send_midi)"
        device, source = self.picked()
        if not device or not source:
            return "no MIDI device or no sound source"
        node = self.sources()[source]
        self.test = LatencyTest(device, node, lambda m: self.studio.send_midi(device, m), samples, self.note)
        self.test.source = source
        threading.Thread(target=self.finish, args=(self.test,), daemon=True).start()
        return None

    def finish(self, test):
        test.run()
        found = test.result()
        if found:
            step = self.studio.latency() if hasattr(self.studio, "latency") else {}
            entry = dict(found, device=test.device, source=test.source, step=step.get("name"),
                         block=step.get("block"), buffer_ms=step.get("buffer_ms"),
                         when=time.strftime("%Y-%m-%d %H:%M"))
            results = [entry] + list(self.studio.settings.get("results") or [])
            self.studio.settings["results"] = results[:KEEP]
            self.studio.save()
            self.studio.say(f"Round trip {found['median']:g} ms ({found['heard']} of {found['tries']})", 3)
        else:
            self.studio.say(f"Latency test: {test.error}", 3)

    def text(self):
        if not self.test:
            return "PICK A DEVICE AND ITS SOUND, THEN START"
        if self.test.state == "running":
            return f"PLAYING {len(self.test.times) + 1} OF {TRIES} ..."
        if self.test.state == "error":
            return ("ERROR: " + str(self.test.error)).upper()
        found = self.test.result()
        return f"ROUND TRIP {found['median']:g} MS  ({found['min']:g}-{found['max']:g}, {found['heard']}/{TRIES})" \
            if found else "STOPPED"


class TesterScreen:
    """MORE > PLUG-INS > TESTER: LATENCY (480x320: 34 header)"""

    def __init__(self, ui, studio, tester):
        self.ui, self.studio, self.tester = ui, studio, tester

    def view(self, now):
        t = self.tester.test
        return (self.tester.picked(), t and (t.state, len(t.times)), len(self.studio.settings.get("results") or []))

    def draw(self, img, d, now):
        ui, t, tester = self.ui, self.ui.theme, self.tester
        device, source = tester.picked()
        ui.centre(img, (4, 38, 476, 60), "LATENCY: A NOTE OUT, ITS SOUND BACK", t.hi)
        for y, label, which, value in ((64, "MIDI TO", "device", device), (98, "SOUND", "source", source)):
            ui.centre(img, (4, y, 90, y + 28), label, t.c[2])
            ui.button(img, d, (94, y, 140, y + 28), "<", lambda w=which: tester.pick(w, -1), key=("tester", which, -1))
            ui.centre(img, (144, y, 332, y + 28), (value or "NONE")[:22], t.hi)
            ui.button(img, d, (336, y, 382, y + 28), ">", lambda w=which: tester.pick(w, 1), key=("tester", which, 1))
        running = tester.running()
        ui.button(img, d, (388, 64, 476, 126), "STOP" if running else "START",
                  (lambda: tester.test.stop()) if running else (lambda: self.start()), on=running, key="tester-go")
        step = self.studio.latency() if hasattr(self.studio, "latency") else None
        if step:
            ui.centre(img, (4, 132, 476, 152), f"STUDIO LATENCY {step['name']}: BLOCK {step['block']}, "
                      f"LINK BUFFER {step['buffer_ms']} MS", t.c[2])
        ui.centre(img, (4, 154, 476, 176), tester.text()[:58], t.c[4] if tester.test else t.c[2])
        for row, r in enumerate((self.studio.settings.get("results") or [])[:4]):
            y = 182 + row * 20
            ui.centre(img, (4, y, 476, y + 18), f"{r['when'][5:]}  {r.get('step') or ''}  {r['device'][:14]}  "
                      f"{r['median']:g} MS ({r['min']:g}-{r['max']:g})"[:58], t.c[3])

    def start(self):
        error = self.tester.start()
        if error:
            self.studio.say(error, 3)


def setup(studio):
    tester = Tester(studio)
    studio.add_screen("TESTER", lambda ui, s: TesterScreen(ui, s, tester))

    def status():
        t = tester.test
        return {"version": VERSION, "running": tester.running(), "text": tester.text(),
                "times": list(t.times) if t else [], "results": studio.settings.get("results") or []}

    def command_latency(args):
        if args.get("device"):
            tester.device = str(args["device"])
        if args.get("source"):
            tester.source = str(args["source"])
        note = args.get("note")
        tester.note = note if isinstance(note, int) and 0 <= note <= 127 else NOTE
        return tester.start() or "started"

    studio.add_web(status=status, commands={"latency": command_latency})
