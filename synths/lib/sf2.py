"""A SoundFont's presets (.sf2, and .sf3: the same RIFF layout, its samples compressed), read straight from the
file: its pdta list's phdr chunk, the sample data skipped. No FluidSynth needed, so the screen can list a SoundFont's
sounds before it's loaded.

  python3 sf2.py FILE        the presets, one "bank program name" a line
"""
import struct
import sys

PHDR = struct.Struct("<20sHHHIII")              # name, program, bank, bag, library, genre, morphology: 38 bytes


class SoundFontError(Exception):
    pass


def chunks(f, end):
    """(id, size, offset of its data) for each chunk from here to end"""
    while f.tell() + 8 <= end:
        head = f.read(8)
        if len(head) < 8:
            return
        cid, size = head[:4], struct.unpack("<I", head[4:])[0]
        at = f.tell()
        yield cid, size, at
        f.seek(at + size + (size & 1))          # (chunks are padded to an even length)


def presets(path):
    """[(bank, program, name)] of a SoundFont, sorted by bank and program; SoundFontError if it isn't one"""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
            if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"sfbk":
                raise SoundFontError("not a SoundFont")
            end = 8 + struct.unpack("<I", head[4:8])[0]
            for cid, size, at in chunks(f, end):
                if cid != b"LIST":
                    continue
                if f.read(4) != b"pdta":
                    continue
                for sub, sub_size, sub_at in chunks(f, at + size):
                    if sub != b"phdr":
                        continue
                    f.seek(sub_at)
                    data = f.read(sub_size)
                    found = []
                    for i in range(sub_size // PHDR.size - 1):          # (the last one: "EOP", the end)
                        name, program, bank = PHDR.unpack_from(data, i * PHDR.size)[:3]
                        name = name.split(b"\0", 1)[0].decode("latin-1").strip()
                        found.append((bank, program, name or f"Preset {program}"))
                    return sorted(set(found))
    except OSError as e:
        raise SoundFontError(str(e)) from None
    raise SoundFontError("no presets in it")


if __name__ == "__main__":
    for bank, program, name in presets(sys.argv[1]):
        print(bank, program, name)
