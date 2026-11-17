"""The sampler plug-in in XOXO Studio's own code, with the editor and the decks: the tab bar, PADS in the mixer
and the USB-C link, the web page's kit, the Bluetooth warning, MORE > PLUG-INS listing them, off until switched
on. Needs a clone of XOXO Studio (xoxo_studio.py), Pillow and numpy.

  python -m pytest tests/test_sampler_studio.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xoxo_studio import PLUGINS, desk_with, studio_app, tab_keys  # noqa: E402,F401

import json  # noqa: E402
import plugins  # noqa: E402
from test_plugins import GOOD, App, make  # noqa: E402


def test_tab_bar():
    """eight tabs (MIXER, EDITOR, XO-4 with the pads in its DRUMS, DECKS, RECORD with the reel-to-reel meter ...); the
    meters open from MIXER and the DAW from MIDI, each with a back button, their tab lit under them"""
    import bridge
    import deskui
    app = studio_app()
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    ui.render(0.0, force=True)
    assert [w[3][1] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "tab"] ==         ["HOME", "MIX", "MIDI", "REC", "SEQ", "PADS", "EDITOR", "DECKS", "MORE"] and ui.tab_label("SEQ") == "SEQ"
    assert "PADS" not in deskui.TABS and "PADS" not in deskui.TAB_LABEL               # the pads: in XO-4's DRUMS

    def press(key):
        box = next(w[0] for w in ui.widgets if w[3] == key)
        ui.touch("down", box[0] + 4, box[1] + 4, 0.0)
        ui.touch("up", box[0] + 4, box[1] + 4, 0.0)
        ui.render(0.0, force=True)
    for there, button, page, back in (("MIX", "meters", "METER", "meter-back"), ("MIDI", "daw", "DAW", "daw-back")):
        press(("tab", there))
        press(button)
        assert ui.tab == page and deskui.PARENT[page] == there
        assert any(w[3] == ("tab", there) for w in ui.widgets)      # the bar's still there, its tab lit
        press(back)
        assert ui.tab == there
    assert app.screen == "status"                                    # (the meters' reader let go)
    toggled = []
    app.toggle_recording = lambda: toggled.append(True)
    press(("tab", "REC"))                                            # RECORD: its own tab, the reels' levels on
    assert ui.tab == "REC" and app.screen == "meter" and deskui.TAB_LABEL["REC"] == "RECORD" and deskui.TAB_LABEL["MIX"] == "MIXER"
    press("rec-go")
    assert toggled
    press("rec-takes")
    assert app.screen == "pick" or app.message == "No recordings yet"   # the takes (a Studio page), or none
    assert "RECORDINGS" not in [m[0] for m in deskui.MORE]
    for tab in ("REC", "EDITOR", "SEQ"):                            # RECORD, EDITOR and XO-4: full screen, as DECKS
        app.screen = "status"
        ui.open_tab(tab)
        ui.render(0.0, force=True)
        assert not any(isinstance(w[3], tuple) and w[3][0] == "tab" for w in ui.widgets), tab
    app.screen = "status"
    ui.open_tab("HOME")
    ui.render(0.0, force=True)
    opened = []
    ui.plugin_tab("DECKS").opened = lambda: opened.append(True)     # (no decks program here)
    press(("tab", "DECKS"))                                          # the DJ decks: a tab, no longer in MORE
    assert opened and ui.tab == "DECKS" and "DJ DECKS" not in [m[0] for m in deskui.MORE]
    app.pads = None
    for tab in ("MIX", "REC", "MIDI", "MORE"):                      # every tab: < HOME, top left
        app.screen = "status"
        ui.open_tab(tab)
        ui.render(0.0, force=True)
        box = next(w[0] for w in ui.widgets if w[3] == "home")
        assert box[0] < 10 and box[2] <= 70, (tab, box)
        press("home")
        assert ui.tab == "HOME", tab
    for tab, key in (("EDITOR", "ed-back"), ("SEQ", "seq-home")):    # the full screens' own < HOME
        app.screen = "status"
        ui.open_tab(tab)
        ui.render(0.0, force=True)
        box = next(w[0] for w in ui.widgets if w[3] == key)
        assert box[0] < 10, (tab, box)
        press(key)
        assert ui.tab == "HOME" and app.screen == "status", tab


def test_four_usb_devices():
    """all four of the Studio's USB ports with sound and MIDI: every device its own mixer channel (two alike
    numbered), all of them and the sampler in Record parts (six sources), up to eight MIDI controllers"""
    import blemidi
    import bridge
    import deskui
    import meters

    def node(i, label, name):
        return {"type": "PipeWire:Interface:Node", "id": i, "info": {"props": {
            "media.class": "Audio/Source", "node.name": name, "alsa.card_name": label,
            "api.alsa.path": f"front:{i}"}}}
    objects = [node(10, "EP-136", "alsa_input.usb-EP-136-a"), node(11, "EP-136", "alsa_input.usb-EP-136-b"),
               node(12, "SMK-37+VA", "alsa_input.usb-SMK"), node(13, "Scarlett 2i2", "alsa_input.usb-Focusrite"),
               {"type": "PipeWire:Interface:Node", "id": 14, "info": {"props": {
                   "media.class": "Audio/Source", "node.name": "fm1-xo4"}}}]
    app = studio_app()                                               # (the sampler on: its PADS)
    sink, others = bridge.pick_nodes(objects, app.plugin_host)
    assert sink is None and len(others) == 5
    app.others = others
    keys = [k for k, _ in app.mix_channels()]
    assert len(set(keys)) == 5
    names = [app.channel_name(k) for k in keys]
    assert names[:2] == ["EP-136", "EP-136 #2"] and "SCARLETT 2" in names[3] and names[4] == "PADS"
    assert len(meters.PARTS_MAP) // 2 >= len(keys)                    # Record parts: room for every source
    ui = deskui.DeskUI(app, app.display)
    ui.theme_check = 1e12
    ui.open_tab("MIX")
    ui.render(0.0, force=True)
    assert {("slide", k) for k in keys} <= {w[3] for w in ui.widgets}  # a fader each
    b = blemidi.MidiBridge(net=True)
    assert b.controllers.MAX == 8 and blemidi.MidiBridge().controllers.MAX == 4


def test_internal_sources_say_no_usb():
    """HOME's sources: a USB device says USB beside its name; the Studio's own (the pads, XO-4) say nothing"""
    import bridge
    import deskui

    def node(i, name, cls="Audio/Source", nick=None):
        props = {"media.class": cls, "node.name": name}
        if nick:
            props["alsa.card_name"] = nick
        return {"id": i, "type": "PipeWire:Interface:Node", "info": {"props": props}}
    objects = [node(1, "alsa_input.usb-Casio_EP-136-00.analog-stereo", nick="EP-136"), node(3, "fm1-xo4")]
    app = studio_app()                                               # (the sampler on: its PADS)
    sink, sources = bridge.pick_nodes(objects, app.plugin_host)
    app.others = sources
    ui = deskui.DeskUI(app, app.display)
    assert [(label, detail) for _, label, detail, _ in ui.sources()] == [("EP-136", "USB"), ("PADS", "")]


def test_web_studio_status_and_commands():
    """the web page's Studio tab: XO-4's state, the kits, the decks' level in the mixer, a linked Pocket; its
    commands change the Studio as the screen does"""
    app = studio_app()
    sent = []
    app.midi = type("M", (), {"net": ["FM-1 Companion Pocket"], "net_hosts": {"FM-1 Companion Pocket": "169.254.66.49"},
                              "clock": None,
                              "peer": None, "enabled": True, "error": None})()
    st = app.web_status()
    assert st["xo4"]["pattern"] == "A" and "midi_in" not in st["xo4"] and "sounds" not in st["xo4"]
    import pads
    import padkit
    assert st["kits"]["list"] == pads.list_kits()
    assert st["kits"]["current"] == padkit.kit(app.plugin_host.loaded["sampler"])["name"]
    assert st["decks"] is None and st["pocket"] == "cable" and st["box"] == "xoxo-studio"
    app.web_command({"cmd": "xo4", "action": "pattern", "value": "C"})
    st = app.web_status()
    assert st["xo4"]["pattern"] == "C" and sent == []
    app.others = [{"id": 1, "name": "fm1-xo4", "label": "XO-4", "internal": True}]
    app.app_here = {"decks"}
    app.web_command({"cmd": "set", "key": "mix_decks", "value": 150})
    assert [(r["key"], r["level"]) for r in app.web_status()["mixer"]] == [("u-xo4", 100), ("decks", 150)]
    assert app.web_command({"cmd": "kit", "name": "NO-SUCH"}) == "Web: no such kit"
    assert app.plugin_on("sampler")                                  # (a wrong name doesn't stop the plug-in)


def test_studio_as_a_computers_usb_interface():
    """a Pi 4 Studio on a computer's USB (the UAC2 gadget): the computer's sound a source, COMPUTER; the Studio's
    mix to the computer, every source but the computer's own (no feedback through a DAW monitoring its input)"""
    import bridge

    def node(i, name, cls, **props):
        return {"type": "PipeWire:Interface:Node", "id": i,
                "info": {"props": dict({"media.class": cls, "node.name": name}, **props)}}
    objects = [node(30, "alsa_output.platform-fe980000.usb.stereo-fallback", "Audio/Sink", **{"alsa.card_name": "UAC2_Gadget"}),
               node(31, "alsa_input.platform-fe980000.usb.stereo-fallback", "Audio/Source", **{"alsa.card_name": "UAC2_Gadget"}),
               node(32, "fm1-xo4", "Audio/Source"),
               node(33, "alsa_output.platform-bcm2835_audio.stereo-fallback", "Audio/Sink",
                    **{"alsa.card_name": "bcm2835 Headphones"})]
    was = bridge.device.usb_host
    bridge.device.usb_host = lambda: False        # the gadget's cards with nothing on the USB-C port: no computer
    try:
        assert bridge.computer_node(objects) is None
        assert [n["label"] for n in bridge.pick_nodes(objects, studio_app().plugin_host)[1]] == ["PADS"]
    finally:
        bridge.device.usb_host = was
    bridge.device.usb_host = lambda: True
    try:
        computer_plugged_in(bridge, objects)
    finally:
        bridge.device.usb_host = was


def computer_plugged_in(bridge, objects):
    """(test_studio_as_a_computers_usb_interface) a computer on the USB-C port"""
    assert bridge.computer_node(objects) == {"id": 30, "name": "alsa_output.platform-fe980000.usb.stereo-fallback",
                                             "label": "COMPUTER"}
    assert bridge.jack_node(objects)["id"] == 33                      # the computer isn't taken for the jack
    app = studio_app()
    _, sources = bridge.pick_nodes(objects, app.plugin_host)
    assert [(n["label"], n.get("internal")) for n in sources] == [("COMPUTER", True), ("PADS", True)]
    app.others, app.app_here = sources, {"decks"}
    channels = app.mix_channels()
    assert app.computer_feeds(channels) == []                         # no computer: nothing sent
    app.computer = bridge.computer_node(objects)
    assert [k for k, _, _ in app.computer_feeds(channels)] == ["u-xo4", "decks"]
    assert bridge.computer_node(objects[2:]) is None


def test_bluetooth_warning_on_pads_and_decks():
    """PADS or DECKS opened with a speaker on the Pi's own Bluetooth: a word to use the DAC (or the jack) or a USB
    dongle, once a run for each; none on a dongle, none without a speaker"""
    import bridge
    import deskui
    app = studio_app()
    said = []
    app.say = lambda text, seconds=3: said.append(text)
    ui = deskui.DeskUI(app, app.display)
    ui.plugin_tab("DECKS").opened = lambda: False                     # (no decks program here)
    ui.open_tab("PADS")
    assert not said                                   # no speaker
    app.sink = {"id": 9, "name": "bluez_output.x", "label": "JBL Go 3"}
    app.dac = {"id": 63}
    ui.open_tab("SEQ")                                # (the sequencer makes no sound of its own: no word)
    ui.open_tab("PADS")
    ui.open_tab("HOME")
    ui.open_tab("PADS")
    ui.open_tab("DECKS")
    assert said == ["Pi's Bluetooth: dropouts with the pads.\nUse the DAC out or a USB Bluetooth dongle.",
                    "Pi's Bluetooth: dropouts with the decks.\nUse the DAC out or a USB Bluetooth dongle."]
    ui2 = deskui.DeskUI(app, app.display)
    app.bt_usb = True                                 # on a dongle: nothing
    ui2.open_tab("PADS")
    assert len(said) == 2
    app.bt_usb, app.dac = False, None
    ui2.open_tab("PADS")
    assert said[-1].endswith("Use the headphone jack or a USB Bluetooth dongle.")
    app.message, app.message_until = said[-1], time.monotonic() + 5
    ui2.render(time.monotonic(), force=True)          # two lines drawn, no error


def test_plugins_page_lists_the_builtins():
    """MORE > PLUG-INS: the editor, decks and XO-4 listed as any plug-in (their version and author); off at a tap,
    on again after the trust question, as anyone's; XO-4 asks for a hold first (the app starts again)"""
    app, ui = desk_with()
    restarted = []
    app.restart_app = lambda: restarted.append(True)
    ui.open_tab("PLUGINS")
    ui.render(0.0, force=True)
    keys = [w[3] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "plugin-on"]
    assert [k[1] for k in keys] == ["sampler", "editor", "decks"]

    def press(key):
        box = next(w[0] for w in ui.widgets if w[3] == key)
        ui.touch("down", box[0] + 4, box[1] + 4, 0.0)
        ui.touch("up", box[0] + 4, box[1] + 4, 0.0)
        ui.render(0.0, force=True)
    press(("plugin-on", "decks"))
    assert not app.plugin_on("decks") and app.screen == "status"     # off at once, nothing asked
    assert "DECKS" not in tab_keys(ui)
    ui.open_tab("PLUGINS")
    ui.render(0.0, force=True)
    press(("plugin-on", "decks"))
    assert not app.plugin_on("decks") and app.screen == "confirm"    # on: the trust question, as anyone's
    app.confirm["action"]()
    app.screen = "status"
    assert app.plugin_on("decks") and "DECKS" in tab_keys(ui) and not restarted


def test_studio_plugins_are_ordinary():
    """the sampler, the editor and the decks (the repository's plugins/): plug-ins like any other, listed with the rest, off until
    switched on (the trust question is the screen's, as for anyone's), kept; a plug-in whose manifest says
    "restart" starts the Studio app again when it's switched"""
    base = Path(tempfile.mkdtemp(prefix="xoxo-plugins-"))
    make(base, "fm1", GOOD)
    app = App()
    restarts = []
    app.restart_app = lambda: restarts.append(True)
    host = plugins.Host(app, [PLUGINS, base])
    host.start()
    listed = {p["id"]: p for p in host.listing()}
    assert list(listed) == ["sampler", "editor", "decks", "fm1"] and not any(p["on"] for p in listed.values())
    assert listed["decks"]["name"] == "DJ decks" and not hasattr(plugins, "BUILTINS") and "xo4" not in listed
    assert host.loaded == {} and not plugins.switched_on(app.state, "editor") and not plugins.switched_on({}, "decks")
    assert host.set_on("editor", True) == "Sample editor on" and plugins.switched_on(app.state, "editor")
    assert host.tabs()[0][:2] == ("editor", "EDITOR") and not restarts
    assert host.set_on("decks", True) == "DJ decks on" and [t[1] for t in host.tabs()] == ["EDITOR", "DECKS"]
    again = plugins.Host(app, [PLUGINS, base])             # kept at the next start
    again.start()
    assert list(again.loaded) == ["editor", "decks"]
    restart = make(base, "restarts", GOOD)                          # a plug-in whose manifest says "restart"
    manifest = json.loads((restart / "plugin.json").read_text())
    (restart / "plugin.json").write_text(json.dumps(dict(manifest, restart=True)))
    again.start()
    assert again.set_on("restarts", True).endswith("starts again") and restarts == [True]
    assert again.set_on("restarts", False).endswith("starts again") and restarts == [True, True]
    assert again.set_on("restarts", False) == "RESTARTS off" and len(restarts) == 2   # (already off: no restart)


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"all {len(tests)} passed")
