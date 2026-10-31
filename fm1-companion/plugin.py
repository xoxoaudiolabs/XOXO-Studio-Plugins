"""FM-1 Companion for XOXO Studio: the FM-1 on the Studio, as a plug-in (XOXO Studio's docs/PLUGINS.md).

The Pocket (xoxoaudiolabs/FM-1-Companion) is the FM-1-focused box; this plug-in brings its FM-1 work to the Studio.
Version 0.1:
  - an FM-1 on USB (Felucca, SLOOP or FM-1 firmware) is a sound source in the Studio's mixer, FM-1 A (a second:
    FM-1 B), in HOME, MIXER and recordings
  - its USB MIDI is FM-1 A / FM-1 B in the MIDI routes, both ways (its notes and clock to the other devices, theirs
    and the Studio's clock to it)
  - the FM-1 keeps the clock when it's plugged in (the Studio's WirePlumber rule, already there: priority.driver)
  - a FM-1 screen (MORE > PLUG-INS > FM-1): the FM-1s it has found
Not yet: the FM-1 library (backups, projects, sample slots, firmware).

A Clipper (isod89's Clipper firmware, on an FM-1 or on M-Vave's SMK-37 keyboard, under the same name and USB ID)
follows the FM-1 Companion's rule for its sound: it's the FM-1 only when no other FM-1 (Felucca, SLOOP) is plugged
in; next to one it's an instrument, a mixer channel of its own (the FM-1 Companion's sloop.fm1_cards). Its MIDI is a
keyboard either way, and two FM-1s get A and B in the order the Studio finds them, not by USB port: both wait for the
Studio's plug-in API to name devices by sound card.
"""
import re
from pathlib import Path

API = 1

FM1_SOUND = r"felucca|sloop|fm-1|fm1|m-vave"    # in a USB sound card's names (the FM-1 Companion's source_match)
FM1_MIDI = r"^(felucca|sloop|fm-1|fm1)\b"       # an FM-1's ALSA MIDI client name ("Felucca", "SLOOP")
FM1_CARD = r"felucca|sloop|fm-1|fm1"            # a real FM-1 (not a Clipper) in /proc/asound/cards
CARDS = Path("/proc/asound/cards")
LETTERS = "ABCDEFGH"


def real_fm1_plugged(text=None):
    """is an FM-1 other than a Clipper (Felucca, SLOOP) plugged in? From /proc/asound/cards (False without it)"""
    if text is None:
        try:
            text = CARDS.read_text(errors="replace")
        except OSError:
            return False
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"\s*\d+ \[", line):
            continue
        both = f"{line} {lines[i + 1] if i + 1 < len(lines) else ''}".lower()
        if "usb-audio" in both and re.search(FM1_CARD, both) and "clipper" not in both:
            return True
    return False


def is_fm1(text):
    """a sound source's names -> is it an FM-1? A Clipper only when no other FM-1 is plugged in"""
    if re.search(FM1_SOUND, text, re.I):
        return True
    return bool(re.search(r"clipper", text, re.I)) and not real_fm1_plugged()


def fm1_name(n):
    """the n-th FM-1 found (0, 1, ...): FM-1 A, FM-1 B"""
    return "FM-1 " + LETTERS[min(n, len(LETTERS) - 1)]


class FM1Screen:
    """MORE > PLUG-INS > FM-1: the FM-1s the Studio has, and where they are"""

    def __init__(self, ui, studio):
        self.ui, self.studio = ui, studio

    def found(self):
        return [name for name in self.studio.sources() if name.startswith("FM-1")]

    def view(self, now):
        return tuple(self.found())

    def draw(self, img, d, now):
        ui, t = self.ui, self.ui.theme
        fm1s = self.found()
        y = 50
        if not fm1s:
            ui.centre(img, (0, y, 480, y + 30), "NO FM-1 PLUGGED IN", t.c[3])
            ui.centre(img, (0, y + 34, 480, y + 64), "PLUG ONE INTO A USB PORT", t.c[2])
            return
        for name in fm1s:
            d.rectangle((8, y, 472, y + 44), fill=t.grey[0])
            ui.centre(img, (8, y, 240, y + 44), name, t.hi)
            ui.centre(img, (240, y, 472, y + 44), "MIXER + MIDI ROUTES", t.c[3])
            y += 52
        ui.centre(img, (0, 236, 480, 262), "THE FM-1 LIBRARY COMES IN A LATER VERSION", t.c[2])


def setup(studio):
    studio.add_audio_source(is_fm1, fm1_name)
    studio.add_midi_device(FM1_MIDI, "FM-1 {n}")
    studio.add_screen("FM-1", FM1Screen)
    studio.add_web(status=lambda: {"version": "0.1.1"})
