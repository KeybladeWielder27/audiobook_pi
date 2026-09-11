"""Tests ONLY the Playback class in isolation -- no display, no buttons,
no battery polling, no haptics. If this produces sound but the full
player.py doesn't, the other subsystems are interfering with audio,
most likely through CPU contention on this much slower single-core chip."""
import sys
import time

from playback import Playback

if len(sys.argv) < 2:
    print("Usage: python test_playback_only.py <path-to-audio-file>")
    sys.exit(1)

path = sys.argv[1]
print(f"Loading: {path}")

pb = Playback()
pb.load_single(path)
print("Playing for 15 seconds...")
time.sleep(15)
pb.stop()
pb.shutdown()
print("Done.")
