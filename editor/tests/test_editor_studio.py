"""The sample editor plug-in in XOXO Studio's own code: the EDITOR tab, and the Studio with it switched off.
Needs a clone of XOXO Studio (xoxo_studio.py), Pillow and numpy.

  python -m pytest tests/test_editor_studio.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xoxo_studio import PLUGINS, desk_with, studio_app, tab_keys  # noqa: E402,F401



def test_editor_empty_file():
    """an empty recording or sample in the EDITOR: a flat line, not a crash (the app died on one, 2026-11-03)"""
    import numpy as np
    import bridge
    import deskui
    app = studio_app()
    ui = deskui.DeskUI(app, app.display)
    ed = {"x": np.zeros(0, dtype=np.float32), "rate": 48000, "seconds": 0.0}
    _, screen = ui.editor_screen()                                  # (the editor plug-in's, plugins/editor)
    assert screen.editor_wave(ed, 0.0, 0.0) == [(0.0, 0.0)] * deskui.W and ed["peak"] == 1.0


def test_editor_plugin_off():
    """the sample editor switched off (MORE > PLUG-INS): no EDITOR tab (the bar re-laid with the rest), the tab
    can't be opened, no TRIM on a pad's page, no "Edit as sample" for a take; back on, all of it again. Its file
    last edited is kept"""
    app, ui = desk_with()
    assert tab_keys(ui) == ["HOME", "MIX", "MIDI", "REC", "SEQ", "PADS", "EDITOR", "DECKS", "MORE"]
    app.state["editor_last"] = ["kick_C2.wav", "samples"]
    app.screen = "status"
    ui.open_tab("EDITOR")
    assert ui.tab == "EDITOR" and app.screen == "editor"
    app.plugin_host.set_on("editor", False)                           # off while it's open: HOME
    assert ui.tab == "HOME" and app.screen == "status" and app.ed is None
    assert tab_keys(ui) == ["HOME", "MIX", "MIDI", "REC", "SEQ", "PADS", "DECKS", "MORE"]
    tabs = [w for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "tab"]
    assert tabs[-1][0][2] >= 480 - 480 // 8 - 2                     # (eight across the whole width)
    ui.open_tab("EDITOR")
    assert ui.tab == "HOME" and app.screen != "editor"
    assert app.state["editor_last"] == ["kick_C2.wav", "samples"]    # kept
    app.state["plugins"]["sampler"]["settings"]["kit"] = {"name": "K", "pads": [{"sample": ""}] * 16}
    ui.open_tab("PADS")                                              # the sampler's pad page: no TRIM
    ui.plugin_tab("PADS").pad_edit = 0
    ui.render(0.0, force=True)
    acts = [w[3][1] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "pad-act"]
    assert acts == ["PLAY", "SAMPLE", "CLEAR"]
    assert app.edit_action() == []
    app.plugin_host.set_on("editor", True)
    ui.render(0.0, force=True)
    acts = [w[3][1] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "pad-act"]
    assert acts == ["PLAY", "SAMPLE", "TRIM", "CLEAR"] and app.edit_action()
    ui.plugin_tab("PADS").pad_edit = None
    ui.open_tab("HOME")
    assert "EDITOR" in tab_keys(ui)


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"all {len(tests)} passed")
