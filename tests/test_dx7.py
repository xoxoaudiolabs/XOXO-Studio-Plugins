"""Tests for DX7 patches (fm1-companion/lib/dx7.py, the FM-1 Companion's): a voice packed into a bank and unpacked
again, and the single-voice message. random_voice is the FM-1 Companion's tests/test_dx7.py's, which fake_fm1.py's
FakeFM1VA imports from here.

  python -m pytest tests        (needs mido: pip install mido)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fm1-companion" / "lib"))

import dx7  # noqa: E402

# each unpacked parameter's largest value, as the DX7's own voice data allows (21 an operator, then the rest)
OP_MAX = [99] * 8 + [99, 99, 99, 3, 3, 7, 3, 7, 99, 1, 31, 99, 14]
GLOBAL_MAX = [99] * 8 + [31, 7, 1, 99, 99, 99, 99, 1, 5, 7, 48] + [126] * 10


def random_voice(seed, name="TEST VOICE"):
    rng = random.Random(seed)
    voice = [rng.randint(0, m) for m in OP_MAX * 6 + GLOBAL_MAX]
    voice[145:155] = list(name.ljust(10)[:10].encode())
    return bytes(voice)


def test_pack_and_unpack():
    for seed in range(50):
        voice = random_voice(seed)
        packed = dx7.pack(voice)
        assert len(packed) == 128 and dx7.unpack(packed) == voice, seed


def test_voice_message_names_it():
    message = dx7.voice_message(random_voice(1, "BRASS 1"))
    assert message[0] == 0xF0 and message[-1] == 0xF7
    assert dx7.voice_name(random_voice(1, "BRASS 1")).strip() == "BRASS 1"
