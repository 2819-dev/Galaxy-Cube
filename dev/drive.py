"""Drives the Cube in fake mode like a person would: reads the screen, turns the knob to an item, presses it.

    python3 dev/mock_site.py &        then        python3 dev/drive.py

Runs a full check (link, broadcast, voice, groups, TALK, MUTE, unlink) against the pretend website.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

SITE = "http://localhost:8099"
screen, log_lines = [], []
lock = threading.Lock()


def site(path):
    return urllib.request.urlopen(SITE + path).read().decode()


def voice():
    return json.loads(site("/dev/voice"))


def start():
    env = dict(os.environ, CUBE_FAKE="1", CUBE_STUN="", CUBE_HEARTBEAT="5", CUBE_API=SITE,
               CUBE_DATA=tempfile.mkdtemp(prefix="cube-test-"))
    p = subprocess.Popen([sys.executable, "-m", "cube.main"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, env=env, bufsize=1,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    current = []

    def read():
        for line in p.stdout:
            line = line.rstrip("\n")
            if line.startswith("+-"):
                if current:
                    with lock:
                        screen[:] = current[:]
                    current.clear()
            elif line.startswith("|"):
                current.append(line[1:-1].rstrip())
            else:
                log_lines.append(line)
    threading.Thread(target=read, daemon=True).start()
    return p


def key(p, k, wait=0.35):
    p.stdin.write(k + "\n")
    p.stdin.flush()
    time.sleep(wait)


def shown():
    with lock:
        return list(screen)


def wait_for(text, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if any(text.lower() in line.lower() for line in shown()):
            return True
        time.sleep(0.2)
    raise AssertionError(f"never showed {text!r}; screen: {shown()}")


def pick(p, label):
    """In a menu: turn the knob until `label` is selected, then press."""
    for _ in range(12):
        sel = next((line for line in shown() if line.startswith("> ")), "")
        if label.lower() in sel.lower():
            key(p, "")
            return
        key(p, "d", 0.25)
    raise AssertionError(f"no menu item {label!r}; screen: {shown()}")


def back(p, times=1):
    """Choose "< Back" (it's always at the top)."""
    for _ in range(times):
        key(p, "uuuuuuuuuuuu", 0.4)
        key(p, "")


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok:
        check.failed = True


check.failed = False


def main():
    p = start()
    try:
        wait_for("type this code")
        site("/dev/link")
        wait_for("Linked to")
        wait_for("Online", 12)
        check("links with a code and shows the account", "Steve" in shown()[0])

        key(p, ""); pick(p, "Xbox Broadcast"); wait_for("Broadcasting!")
        check("Xbox Broadcast shows the join steps", any("LAN Games" in s for s in shown()))
        key(p, "")
        wait_for("Broadcasting")
        check("broadcast runs Phantom", any("would run" in s and "galaxymc.smp.live:9030" in s for s in log_lines))

        key(p, ""); pick(p, "Voice Chat"); pick(p, "Join voice")
        wait_for("hold TALK", 25)
        check("joins voice", voice()["connected"])
        time.sleep(1.5)
        check("hears Mia (nearby, 5 blocks)", any("Hearing Mia" in s for s in log_lines))

        key(p, ""); pick(p, "Voice Chat"); pick(p, "Group:"); pick(p, "Builders")
        wait_for("Builders - hold", 5)
        check("joins the Builders group", voice()["group"] == "g1")

        key(p, "h", 1.0)
        check("holding TALK shows Talking and tells the server", voice()["talking"] is True and any("Talking" in s for s in shown()))
        key(p, "h", 0.8)
        check("letting go stops talking", voice()["talking"] is False)
        frames = voice()["mic_frames"]
        time.sleep(1)
        check("the mic audio reaches the server", voice()["mic_frames"] > frames)

        key(p, "m", 0.8)
        check("MUTE turns the mic off", voice()["mic"] is False and any("Mic off" in s for s in shown()))
        key(p, "m", 0.5)
        key(p, "M", 0.8)
        check("long MUTE deafens", voice()["deafened"] is True and any("Deafened" in s for s in shown()))
        key(p, "M", 0.5)

        key(p, ""); pick(p, "Voice Chat"); pick(p, "Group:"); pick(p, "Secret base")
        wait_for("password")
        check("a locked group explains how to get in", True)
        key(p, "")          # close the message
        back(p, 3)          # Groups -> Voice Chat -> Menu -> home

        key(p, ""); pick(p, "Voice Chat"); pick(p, "Who's here")
        wait_for("Mia")
        check("Who's here lists Mia", True)
        key(p, "")
        back(p, 2)

        key(p, ""); pick(p, "Stop Broadcast")
        wait_for("Broadcast off")
        check("Stop Broadcast", True)

        site("/dev/unlink")
        wait_for("unlinked", 15)
        wait_for("type this code", 10)
        check("unlinking on the website sends the Cube back to pairing", not voice()["connected"])
        token_files = [l for l in log_lines if "Bearer" in l]
        check("never prints the device token", not token_files)
    finally:
        key(p, "q", 1.5)
        p.kill()
    print("ALL PASSED" if not check.failed else "SOME FAILED")
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
