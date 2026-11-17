"""XOXO Studio for these tests: $XOXO_STUDIO, or a clone of it beside this repository. This repository's sampler,
editor and DJ decks are copied into a folder of their own (PLUGINS), found there as in ~/xoxo-plugins, without the
repository's other plug-ins; their modules can be imported (pads, padkit, deskpads, decks, djlib, deskdecks)."""
import copy
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STUDIO = Path(os.environ.get("XOXO_STUDIO") or REPO.parent / "XOXO-Studio")
if not (STUDIO / "fm1-bt-bridge" / "plugins.py").is_file():
    pytest.skip(f"no XOXO Studio at {STUDIO}", allow_module_level=True)
for path in (STUDIO / "tests", STUDIO / "fm1-bt-bridge"):          # (the Studio's code first, then its test helpers)
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
OURS = ("sampler", "editor", "decks")
PLUGINS = Path(tempfile.mkdtemp(prefix="xoxo-plugins-"))
for pid in OURS:
    shutil.copytree(REPO / pid, PLUGINS / pid, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    sys.path.append(str(REPO / pid))


def studio_app(state=None):
    """bridge.App with the sampler, the editor and the decks found as in ~/xoxo-plugins, switched on, and started,
    as main() does"""
    import bridge
    from test_desk import RgbCapture
    app = bridge.App(RgbCapture(), state or copy.deepcopy(bridge.DEFAULTS))   # (its own plug-ins' settings)
    app.save_settings = lambda: None
    app.plugin_host.dirs = [PLUGINS]
    app.state["plugins"] = {pid: {"on": True, "settings": {}} for pid in OURS}   # (on)
    app.plugin_host.start()
    return app


def desk_with(off=(), tmp=None):
    """a Studio's screens with the sampler, the editor and the decks switched on, then some of them off"""
    import bridge
    import deskui
    from test_desk import RgbCapture
    app = bridge.App(RgbCapture(), copy.deepcopy(bridge.DEFAULTS))   # (its own plug-ins' settings, not the last test's)
    app.save_settings = lambda: None
    app.restart_app = lambda: None
    app.plugin_host.dirs = [PLUGINS] + ([Path(tmp)] if tmp else [])
    app.state["plugins"] = {pid: {"on": True, "settings": {}} for pid in OURS}   # (on)
    app.plugin_host.start()
    ui = deskui.DeskUI(app, app.display)
    app.desk = ui
    ui.theme_check = 1e12
    for pid in off:
        app.plugin_host.set_on(pid, False)
    return app, ui


def tab_keys(ui):
    ui.render(0.0, force=True)
    return [w[3][1] for w in ui.widgets if isinstance(w[3], tuple) and w[3][0] == "tab"]
