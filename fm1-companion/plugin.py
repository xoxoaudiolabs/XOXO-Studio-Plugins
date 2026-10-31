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

A Clipper (Clipper firmware on an SMK-37) is a keyboard here, not an FM-1. The FM-1 Companion's own rule treats it
as an FM-1 when no other is plugged in; that's left for later.
"""
API = 1

FM1_SOUND = r"felucca|sloop|fm-1|fm1|m-vave"    # in a USB sound card's names (the FM-1 Companion's source_match)
FM1_MIDI = r"^(felucca|sloop|fm-1|fm1)\b"       # an FM-1's ALSA MIDI client name ("Felucca", "SLOOP")
LETTERS = "ABCDEFGH"


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
    studio.add_audio_source(FM1_SOUND, fm1_name)
    studio.add_midi_device(FM1_MIDI, "FM-1 {n}")
    studio.add_screen("FM-1", FM1Screen)
    studio.add_web(status=lambda: {"version": "0.1.0"})
