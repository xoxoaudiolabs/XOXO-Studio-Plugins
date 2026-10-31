# Files from the FM-1 Companion

The FM-1 library's code comes from the [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion) (the
Pocket), `fm1-bt-bridge/`, at commit `b025033`:

| File | From | Changed? |
|---|---|---|
| `sloop.py` | `sloop.py` | No: SLOOP's editor protocol, backups, projects, songs, sample slots, `fm1_cards` |
| `dx7.py` | `dx7.py` | No |
| `samplefast.py` | `samplefast.py` | No |
| `vendor/sloop/` | `vendor/sloop/` | No: isod89's SLOOP tools, see `vendor/sloop/VENDORED.md` |
| `fm1lib.py` | `library.py` | Cut down to the FM-1's jobs: no X0X, SLOOP on the Studio, SD card, recordings, updates or screen themes, which the Studio has its own of; `--fm1 A-D` and `--level` instead of the Pocket's settings file; its own state file (`fm1-companion-job.json`) |

Keep the unchanged files unchanged, so a newer FM-1 Companion's can be copied over them. `tests/fake_fm1.py` is the
FM-1 Companion's too, unchanged.
