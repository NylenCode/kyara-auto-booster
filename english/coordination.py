"""
Coordination between several copies of kyara_booster.py (one per browser).

- DETECTION is never blocked: each script reads its counter all the time.
- OPENING is exclusive (a single mouse): a shared lock says who opens.
- The one that just opened lets the others go first: if one of them is
  full, it opens; otherwise each one keeps detecting.

Names are free (NAME in each script), but must be different.

Command line usage:
    python coordination.py          -> shows the state
    python coordination.py reset    -> resets the state
"""

import json
import msvcrt
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ---------- CONFIGURATION ----------
LOCAL_DIR = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
)

# Separate from the French version: the two do not mix.
DIRECTORY = LOCAL_DIR / "KyaraAutoBooster"
STATE_FILE = DIRECTORY / "state.json"
LOCK_FILE = DIRECTORY / "state.lock"

# A reported "full counter" stays valid for this many seconds.
READY_VALIDITY = 20
# If a script crashes in the middle of an opening, its lock expires after this delay.
MAX_TURN_DURATION = 300

DIRECTORY.mkdir(parents=True, exist_ok=True)

last_detections = {}
last_waiting_message = {}


# ---------- STATE FILE ACCESS ----------
def _empty_state():
    return {
        "owner": None,
        "reason": None,
        "since": 0.0,
        # Last script that opened: it lets the others go first.
        "last": None,
        "ready": {},
    }


@contextmanager
def _locked_state():
    """Reads, lets modify then writes back the state, under an inter-process lock."""
    with open(LOCK_FILE, "a+b") as lock:
        lock.seek(0)
        start = time.monotonic()
        while True:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() - start > 10:
                    raise TimeoutError(f"Lock stuck: {LOCK_FILE}")
                time.sleep(0.05)

        try:
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    raise ValueError
            except (OSError, ValueError):
                state = _empty_state()

            base = _empty_state()
            base.update(state)
            base["ready"] = dict(state.get("ready") or {})
            state = base

            # Orphan lock (crashed script): release it.
            if (
                state["owner"]
                and time.time() - state["since"] > MAX_TURN_DURATION
            ):
                print(
                    f"[COORDINATION] Lock of {state['owner'].upper()} "
                    "expired: released."
                )
                state["owner"] = None
                state["reason"] = None

            yield state

            STATE_FILE.write_text(
                json.dumps(state, indent=2), encoding="utf-8"
            )
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _check_name(name):
    name = str(name).lower().strip()
    if not name:
        raise ValueError("Empty script name: fill in NAME in the configuration.")
    return name


def _others_ready(state, name):
    now = time.time()
    return [
        other for other, date in state["ready"].items()
        if other != name and now - date < READY_VALIDITY
    ]


# ---------- API ----------
def report_counter(name, detected, ocr_text=""):
    """Publishes the counter state (read by the other scripts) and prints it if it changes."""
    name = _check_name(name)

    with _locked_state() as state:
        state["ready"][name] = time.time() if detected else 0.0

    if last_detections.get(name) != detected:
        state_txt = "DETECTED" if detected else "NOT detected"
        print(f"[{name.upper()}] Full counter {state_txt}.")
        if ocr_text:
            print(f"[{name.upper()}] Reading: {ocr_text}")
        last_detections[name] = detected


def request_turn(name, priority=False, reason="opening"):
    """
    Tries to take the mouse, without ever waiting.

    Returns True if the script can act now, False otherwise
    (it then keeps detecting and will ask again at the next pass).

    priority=True ignores the priority of the others (popup click, very short).
    """
    name = _check_name(name)

    with _locked_state() as state:
        owner = state["owner"]

        if owner == name:
            return True

        if owner is None:
            others = _others_ready(state, name)
            if not priority and state["last"] == name and others:
                cause = f"priority to {others[0].upper()} (full counter)"
            else:
                state["owner"] = name
                state["reason"] = reason
                state["since"] = time.time()
                last_waiting_message.pop(name, None)
                return True
        else:
            cause = f"{owner.upper()} is opening"

    if last_waiting_message.get(name) != cause:
        print(f"[{name.upper()}] Waiting: {cause}. Detection goes on.")
        last_waiting_message[name] = cause
    return False


def end_turn(name, hand_over=True):
    """
    Releases the mouse. With hand_over=True (end of an opening), the other
    scripts get priority: they will open as soon as their counter is full.
    """
    name = _check_name(name)

    with _locked_state() as state:
        if state["owner"] != name:
            return
        state["owner"] = None
        state["reason"] = None
        state["since"] = 0.0
        if hand_over:
            state["last"] = name
        # The counter has just been used up: no longer say it is ready.
        state["ready"][name] = 0.0

    if hand_over:
        print(
            f"[COORDINATION] {name.upper()} is done. "
            "The others can open if they are full."
        )


def release_at_startup(name):
    """Clears a lock left by a previous run of the same script."""
    name = _check_name(name)
    with _locked_state() as state:
        if state["owner"] == name:
            print(f"[COORDINATION] Old lock of {name.upper()} released.")
            state["owner"] = None
            state["reason"] = None
        state["ready"][name] = 0.0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        STATE_FILE.write_text(json.dumps(_empty_state(), indent=2), encoding="utf-8")
        print(f"State reset: {STATE_FILE}")
    else:
        with _locked_state() as state:
            print(json.dumps(state, indent=2))
