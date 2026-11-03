# Files from the FM-1 Companion

The FM-1 library's code comes from the [FM-1 Companion](https://github.com/xoxoaudiolabs/FM-1-Companion) (the
Pocket), `fm1-bt-bridge/`, at commit `e43a551` (Pocket v3.0.2; these files last changed in `0f1f93a`, Pocket v3.0):

| File | From | Changed? |
|---|---|---|
| `sloop.py` | `sloop.py` | No: SLOOP's editor protocol, backups, projects, songs, sample slots, `fm1_cards`; Felucca's backup commands and file (Felucca, JIANT, Melodee), Jangada's file, sloopDX's DX7 banks |
| `mvave.py` | `mvave.py` | No: M-VAVE's handshake (who an FM-1 is), a stock FM-1's sound read back; its X0X frames go unused here |
| `baudgirl.py` | `baudgirl.py` | No: Baud Girl's FM-1+VA's 128 presets, backed up and put back |
| `dx7.py` | `dx7.py` | No |
| `samplefast.py` | `samplefast.py` | No |
| `vendor/sloop/` | `vendor/sloop/` | No: isod89's SLOOP tools, see `vendor/sloop/VENDORED.md` |
| `fm1lib.py` | `library.py` | Cut down to the FM-1's jobs: no X0X (on the Studio or on an FM-1), SLOOP on the Studio, SD card, recordings, updates or screen themes, which the Studio has its own of; `--fm1 A-D`, `--level` and `--keep` instead of the Pocket's settings file; DX7 patches only to `--fm1`'s FM-1, never on to another; its own state file (`fm1-companion-job.json`) |

Keep the unchanged files unchanged, so a newer FM-1 Companion's can be copied over them. `tests/fake_fm1.py` is the
FM-1 Companion's too, unchanged; `tests/test_dx7.py`'s `random_voice` is its `tests/test_dx7.py`'s, which
`fake_fm1.py` imports.
