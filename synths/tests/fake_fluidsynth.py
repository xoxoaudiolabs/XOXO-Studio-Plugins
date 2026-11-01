"""A pretend FluidSynth for the Synths plug-in's tests: its shell on stdin, as the real one's (load, unload,
select, gain, quit), each command written to $FAKE_FLUIDSYNTH_LOG. $FAKE_FLUIDSYNTH_FAIL: it says that and stops."""
import os
import sys


def main():
    log = open(os.environ["FAKE_FLUIDSYNTH_LOG"], "a", buffering=1)
    if os.environ.get("FAKE_FLUIDSYNTH_FAIL"):
        print(os.environ["FAKE_FLUIDSYNTH_FAIL"], flush=True)
        return 3
    print("FluidSynth runtime version 2.4.4 (pretend)", flush=True)
    fonts = 0
    for line in sys.stdin:
        line = line.strip()
        log.write(line + "\n")
        if line.startswith("load "):
            path = line[5:].strip('"')
            if os.path.isfile(path):
                fonts += 1
                print(f"> loaded SoundFont has ID {fonts}", flush=True)
            else:
                print("> fluidsynth: error: Unable to open file", flush=True)
        elif line == "quit":
            return 0
        else:
            print(">", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
