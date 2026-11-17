"""The DJ decks plug-in in XOXO Studio's own code: the DECKS tab, its learn screens, DECKS in the mixer and on
HOME, the Hercules off the MIDI routes while it's on, switched off. Needs a clone of XOXO Studio (xoxo_studio.py),
Pillow and numpy.

  python -m pytest tests/test_decks_studio.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xoxo_studio import PLUGINS, desk_with, studio_app, tab_keys  # noqa: E402,F401

import blemidi  # noqa: E402
import plugins  # noqa: E402
from test_midi import PORTS  # noqa: E402


def test_decks_screen():
    """the DECKS tab: the decks' screen from their status; its buttons send the decks their commands (a pretend
    decks program: no sound, no Hercules)"""
    import bridge
    import deskui
    sent = []

    class Decks:
        library = [["a.mp3", "Curtains", "7 Keys", 140.0, "E", "12B"],
                   ["b.mp3", "Organ Donor", "Zomboy", 140.0, "F#m", "11A"]]
        overviews, note = {0: [0.5] * 220, 1: []}, None
        library_n = note_n = 0

        def start(self):
            pass

        def stop(self):
            pass
        status = {"decks": [{"title": "Curtains", "artist": "7 Keys", "bpm": 140.0, "key": "E", "camelot": "12B",
                             "pos": 10.0, "len": 240.0, "playing": True, "pitch": 0.0, "cues": [0.1]}, {}],
                  "xfade": 0.5, "cursor": 0, "scanning": None}

        def running(self):
            return True

        def send(self, *cmd):
            sent.append(cmd)
    app = studio_app()
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    tab = ui.plugin_tab("DECKS")                           # the DJ decks plug-in's tab (plugins/decks)
    tab.proc, ui.tab = Decks(), "DECKS"
    ui.render(0.0, force=True)
    keys = {w[3]: w for w in ui.widgets}
    assert ("tab", "HOME") not in keys                     # full screen: no tab bar

    def tap(key):
        box = keys[key][0]
        ui.touch("down", box[0] + 2, box[1] + 2, 0.0)
        ui.touch("up", box[0] + 2, box[1] + 2, 0.1)
    tap(("deck", "PLAY", 0))
    tap(("deck", "FX", 0))                                 # FX: a tap switches it, a hold steps to the next
    box = keys[("deck", "FX", 1)][0]
    ui.touch("down", box[0] + 2, box[1] + 2, 0.0)
    ui.touch("move", box[0] + 2, box[1] + 2, 0.7)
    ui.touch("up", box[0] + 2, box[1] + 2, 0.7)
    assert ("fx", 0, "toggle") in sent and ("fx", 1, "next") in sent and ("fx", 1, "toggle") not in sent
    sent[:] = [c for c in sent if c[0] != "fx"]
    tap(("deck-row", 1))
    tap("decks-load-b")
    box = keys[("deck-cue", 1)][0]
    ui.touch("down", box[0] + 2, box[1] + 2, 0.0)
    ui.touch("up", box[0] + 2, box[1] + 2, 0.2)
    box = keys[("deck-seek", 0)][0]                        # dragged along: the deck goes where the finger is
    ui.touch("down", box[0] + 20, box[1] + 6, 0.0)
    ui.touch("move", (box[0] + box[2]) // 2, box[1] + 6, 0.05)
    ui.touch("up", (box[0] + box[2]) // 2, box[1] + 6, 0.1)
    assert sent[:5] == [("play", 0), ("select", 1), ("load", 1), ("cue", 1, True), ("cue", 1, False)]
    assert sent[5][:2] == ("seek", 0) and 0.45 < sent[5][2] < 0.55 and len(sent) == 6
    assert tab.decks_full is None
    ui.touch("down", box[0] + 40, box[1] + 6, 0.0)          # tapped (a resistive screen's wobble): full screen
    ui.touch("move", box[0] + 42, box[1] + 7, 0.05)
    ui.touch("up", box[0] + 42, box[1] + 7, 0.1)
    assert tab.decks_full == 0 and len(sent) == 6
    ui.render(1.0, force=True)
    keys = {w[3]: w for w in ui.widgets}
    assert list(keys) == ["decks-full"]                     # nothing else on it: any tap goes back
    tap("decks-full")
    assert tab.decks_full is None
    tab.decks_full = 0                                      # left full screen: the decks open on their screen
    ui.open_tab("DECKS")
    assert tab.decks_full is None and ui.tab == "DECKS"
    said, say_was = [], ui.app.say
    ui.app.say = lambda text, seconds=3: said.append(text)
    for n in (1, 1, 2):                                     # a note popped up once, the same note again too
        tab.proc.note, tab.proc.note_n = "USB drive Zine: 37 tracks", n
        ui.render(1.5 + n, force=True)
    ui.app.say = say_was
    assert said == ["USB drive Zine: 37 tracks"] * 2
    ui.render(2.0, force=True)
    keys = {w[3]: w for w in ui.widgets}
    tap("decks-home")
    assert ui.tab == "HOME"


def test_decks_learn_screens():
    """DECKS > LEARN: the controllers plugged in, one picked; a control to learn (BACK / SKIP / DONE); a map's
    list (a row tapped: that one learnt again; LEARN ALL; held: forgotten), from a pretend decks program"""
    import bridge
    import deskui
    import decks
    sent = []

    class Decks:
        library, overviews, note = [], {0: [], 1: []}, None
        library_n = note_n = 0
        status = {"decks": [{}, {}], "xfade": 0.5, "cursor": 0, "scanning": None,
                  "ports": [["DJControl Inpulse 200 MK2:DJControl Inpulse 200 MK2 MIDI 1", False, True],
                            ["K.O. Sidekick:K.O. Sidekick MIDI 1", False, False]], "learn": None}

        def start(self):
            pass

        def stop(self):
            pass

        def running(self):
            return True

        def send(self, *cmd):
            sent.append(cmd)
    app = studio_app()
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    tab = ui.plugin_tab("DECKS")
    tab.proc, ui.tab = Decks(), "DECKS"
    now = [0.0]

    def tap(key, hold=0.1):
        ui.render(now[0], force=True)
        box = {w[3]: w for w in ui.widgets}[key][0]
        ui.touch("down", box[0] + 2, box[1] + 2, now[0])
        if hold > 0.5:                                              # held: it goes while the finger's still down
            ui.render(now[0] + hold)
        ui.touch("up", box[0] + 2, box[1] + 2, now[0] + hold)
        now[0] += 1 + hold
    tap("decks-learn")
    assert tab.decks_learn
    tap(("learn-port", "K.O. Sidekick:K.O. Sidekick MIDI 1"))       # no map: learning starts
    tap(("learn-port", "DJControl Inpulse 200 MK2:DJControl Inpulse 200 MK2 MIDI 1"))   # built in: its list
    assert sent == [("learn", "K.O. Sidekick:K.O. Sidekick MIDI 1", True),
                    ("learn_list", "DJControl Inpulse 200 MK2:DJControl Inpulse 200 MK2 MIDI 1")]
    L = decks.Learner("K.O. Sidekick:K.O. Sidekick MIDI 1", [], True, 2)   # what the decks would say: A's SHIFT
    Decks.status["learn"] = L.status()
    for key in ("learn-prev", "learn-skip", "learn-done", "learn-back"):
        tap(key)
    assert sent[2:] == [("learn_back",), ("learn_skip",), ("learn_done",), ("learn_done",)]
    del sent[:]
    L.step = len(decks.LEARN)                                       # the list
    L.binds = [{"action": "a.play", "type": "note", "ch": 1, "num": 7}]
    D = decks.Decks.__new__(decks.Decks)
    D.learner = L
    Decks.status["learn"] = D.learn_status()
    ui.render(now[0], force=True)
    rows = [w[3] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "learn-row"]
    assert len(rows) == 9
    tap(("learn-row", 3))                                           # the 4th control: A's PLAY
    tap("learn-down")
    assert tab.decks_learn_top == 9
    tap("learn-all")
    tap("learn-forget", hold=deskui.HOLD + 0.1)
    tap("learn-back")
    port = "K.O. Sidekick:K.O. Sidekick MIDI 1"
    assert sent == [("learn", port, False, "a.play"), ("learn", port, True), ("learn_forget",), ("learn_end",)]


def test_decks_in_the_mixer():
    """the DJ decks while they run: a DECKS channel in MIXER (its level, CUE on the jack); Settings > Audio > DJ
    decks out (STUDIO / HERCULES) told to the decks; with an app or the decks playing, recordings take the speaker"""
    import bridge
    import deskui
    sent = []

    class Decks:
        library, overviews, note, status = [], {0: [], 1: []}, None, None
        library_n = note_n = 0

        def start(self):
            pass

        def running(self):
            return True

        def send(self, *cmd):
            sent.append(cmd)
    app = studio_app()
    app.jack = {"id": 9, "name": "alsa_output.bcm2835", "label": "PHONES"}
    ui = deskui.DeskUI(app, app.display)
    app.desk = ui
    ui.theme_check = 1e12
    ui.render(0.0, force=True)
    ui.open_tab("MIX")
    ui.render(0.0, force=True)
    assert not any(w[3] == ("slide", "decks") for w in ui.widgets)   # not running: no channel
    ui.plugin_tab("DECKS").proc = Decks()
    ui.open_tab("DECKS")
    assert sent[-1] == ("output", "studio")
    ui.open_tab("MIX")
    ui.render(1.0, force=True)
    keys = {w[3]: w for w in ui.widgets}
    assert ("slide", "decks") in keys and ("cue", "decks") in keys
    keys[("cue", "decks")][2]()
    assert "decks" in app.state["cues"]
    app.screen, app.settings_menu = "settings", "audio"
    row = next(i for i, r in enumerate(app.settings_rows()) if r[1] == "DJ decks out")   # (the plug-in's row)
    assert app.settings_rows()[row][2] == "studio"
    app.setting = row
    app.change_setting()
    assert app.state["plugins"]["decks"]["settings"]["out"] == "hercules" and sent[-1] == ("output", "hercules")
    app.screen = "status"
    app.sink, app.others = {"id": 2, "name": "bluez_output.jbl", "label": "JBL"}, [{"id": 1, "name": "usb-in"}]
    assert app.capture_target() == "monitor:bluez_output.jbl"       # one source: what the speaker plays
    app.app_here = {"decks"}
    assert app.capture_target() == "monitor:bluez_output.jbl"       # the decks playing too: the same
    app.sink = app.jack = app.card = None
    assert app.capture_target() == "usb-in"                         # nothing to play on: the source itself


def test_decks_plugin_off():
    """the DJ decks switched off: no DECKS tab, the decks stopped (their channel gone), no DJ decks out row, nothing
    for the web page; they can't be opened; the MIDI process told (a Hercules is a MIDI device then). Their
    output setting is kept"""
    stopped, dj = [], []

    class Decks:
        library, overviews, note, status = [], {0: [], 1: []}, None, {"decks": [{"title": "A"}, {}]}
        library_n = note_n = 0

        def start(self):
            pass

        def running(self):
            return not stopped

        def stop(self):
            stopped.append(True)

        def send(self, *cmd):
            pass

    class Midi:
        def set_names(self, rules):
            pass

        def set_taken(self, rules):
            dj.append(rules)
    app, ui = desk_with()
    app.plugin_host.entry("decks")["settings"]["out"] = "hercules"
    tab = ui.plugin_tab("DECKS")
    tab.proc = Decks()
    ui.open_tab("DECKS")
    assert ui.tab == "DECKS" and app.web_status()["decks"]
    app.screen, app.settings_menu = "settings", "audio"
    assert "DJ decks out" in [r[1] for r in app.settings_rows()]
    app.screen = "status"
    app.midi = Midi()
    app.plugin_host.set_on("decks", False)
    app.midi = None
    assert stopped and tab.proc is None and ui.tab == "HOME" and dj[-1] == []   # (the Hercules: the routes')
    assert "DECKS" not in tab_keys(ui) and app.web_status()["decks"] is None
    ui.open_tab("DECKS")
    assert ui.tab == "HOME" and tab.proc is None                      # (not started)
    app.screen, app.settings_menu = "settings", "audio"
    assert "DJ decks out" not in [r[1] for r in app.settings_rows()]
    app.screen = "status"
    ui.open_tab("MIX")
    ui.render(0.0, force=True)
    assert not any(w[3] == ("slide", "decks") for w in ui.widgets)
    assert app.state["plugins"]["decks"]["settings"]["out"] == "hercules"   # kept
    app.midi = Midi()
    app.plugin_host.set_on("decks", True)
    assert dj[-1] == [[["djcontrol"], "Studio DJ Music/.studio-dj-controllers.json"]] and "DECKS" in tab_keys(ui)


def test_home_shows_every_source():
    """HOME: every source with its mixer level (a bar and a %), the decks while they run, then the speaker; two
    columns past seven rows; a row opens the mixer"""
    import bridge
    import deskui

    class Decks:
        on = True

        def running(self):
            return self.on
    app = studio_app()
    app.state["mix"] = {"u-xo4": 80, "decks": 150}
    app.volume = 70
    app.others = [{"id": 1, "name": "fm1-xo4", "label": "XO-4", "internal": True}] + [
        {"id": 2 + i, "name": f"alsa_input.usb-{i}", "label": n} for i, n in enumerate(("EP-136", "SMK-37"))]
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    decks = Decks()
    ui.plugin_tab("DECKS").proc = decks
    rows = ui.home_rows()
    assert [(r[0], r[1], r[5]) for r in rows] == [("u-xo4", "XO-4", "80%"), ("u-ep136", "EP-136", "100%"),
                                                  ("u-smk37", "SMK-37", "100%"), ("decks", "DECKS", "150%"),
                                                  ("spk", "SPEAKER", "70%")]
    assert rows[3][3] != rows[4][3]                                 # the decks not in the speaker's colour
    ui.render(0.0, force=True)
    assert [w[3][1] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "row"] == [r[0] for r in rows]
    decks.on = False                                                # the decks off: their row goes
    assert "decks" not in [r[0] for r in ui.home_rows()]
    app.others += [{"id": 9 + i, "name": f"alsa_input.usb-x{i}", "label": f"DEV{i}"} for i in range(5)]
    ui.render(0.0, force=True)                                      # nine rows: two columns, every one there
    boxes = [w[0] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "row"]
    assert len(boxes) == 9 and len({b[0] for b in boxes}) == 2
    box = boxes[0]
    ui.touch("down", box[0] + 10, box[1] + 4, 0.0)
    ui.touch("up", box[0] + 10, box[1] + 4, 0.0)
    assert ui.tab == "MIX"


def test_dj_controllers_free_with_the_decks_off():
    """a Hercules is the DJ decks' (off the routes) while they're on; switched off (MORE > PLUG-INS), it's a MIDI
    device in the routes like any other"""
    import plugins
    controllers = blemidi.UsbControllers(lambda message, name=None: None)
    herc = "DJControl Inpulse 200 MK2:DJControl Inpulse 200 MK2 MIDI 1 24:0"
    on = {"plugins": {"decks": {"on": True}}}
    controllers.taken = plugins.taken_controllers(on, dirs=[PLUGINS])   # (the decks plug-in's manifest)
    assert controllers.taken[0][0] == ["djcontrol"]
    assert "DJControl Inpulse 200 MK2" not in controllers.wanted(PORTS + [herc])
    controllers.taken = plugins.taken_controllers({}, dirs=[PLUGINS])  # (off until switched on)
    assert controllers.taken == [] and controllers.wanted(PORTS + [herc])["DJControl Inpulse 200 MK2"] == herc


def test_the_decks_plugin_takes_the_hercules():
    """the repository's plugins/decks: its manifest's Hercules, kept off the routes only while it's on"""
    found = plugins.find([PLUGINS])
    assert found["decks"][1]["name"] == "DJ decks" and found["decks"][1]["controllers"] == ["djcontrol"]
    on = {"plugins": {"decks": {"on": True}}}
    assert plugins.taken_controllers(on, dirs=[PLUGINS])[0][0] == ["djcontrol"]


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"all {len(tests)} passed")
