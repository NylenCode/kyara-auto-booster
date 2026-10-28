"""
Assistant that sets the whole configuration of kyara_booster.py, without
opening the file.

    python configure_positions.py
        Asks which script to configure (one script per browser, or a
        new one for another browser), then opens the menu:
          1. configure everything: packs then positions;
          2. packs and rotation (e.g. "Sport" or "Sport, Isekai");
          3. positions: mouse on it and G key (the wheel notches for the
             packs lower down the page are counted too); the browser
             (EXECUTABLE) and its screen (SCREEN_AREA) are detected on
             the way;
          4. hunt for a card;
          5. accounts: several Kyara accounts recognized by their avatar,
             each with its packs and its hunt;
          6. opening steps (add, delete, move, waits);
          7. settings (name, browser, pauses, mouse speed);
          8. reset;  9. free mode.
        Each change is saved right away; the previous version is kept
        in backups/kyara_booster.py.bak.

    python configure_positions.py kyara_booster_2.py
        The same, directly for this script (without the choice question).

    python configure_positions.py reset
        Reset of the chosen script (a confirmation is asked):
        1. coordinates to zero: all positions to (0, 0), the rest kept;
        2. everything to default: the original configuration (name, browser
           and screen kept; on another screen, positions to place again).
        For a copy: python configure_positions.py reset kyara_booster_2.py

    python configure_positions.py free
        Free mode: each press on G shows the position and copies it to
        the clipboard (Ctrl+V to paste it wherever you want).

Keys (work even when the browser is in front):
    G       confirm the mouse position
    N       skip (keep the current value)
    Esc     stop
"""

import ast
import ctypes
import ctypes.wintypes as wt
import json
import msvcrt
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import mss
import pyautogui

DIRECTORY = Path(__file__).resolve().parent
DEFAULT_FILE = DIRECTORY / "kyara_booster.py"
# Tidying: same subfolders as kyara_common.py, plus the previous versions
# of the scripts (.bak).
DEBUG_DIR = DIRECTORY / "debug"
HUNTS_DIR = DIRECTORY / "hunts"
BACKUPS_DIR = DIRECTORY / "backups"


def backup_path(file):
    """backups/<script>.bak (folder created if needed)."""
    BACKUPS_DIR.mkdir(exist_ok=True)
    return BACKUPS_DIR / (file.name + ".bak")

KEY_G, KEY_N, KEY_ESC = 0x47, 0x4E, 0x1B

_user32 = ctypes.WinDLL("user32")
_kernel32 = ctypes.WinDLL("kernel32")
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.WindowFromPoint.restype = ctypes.c_void_p
_user32.WindowFromPoint.argtypes = (wt.POINT,)
_user32.GetAncestor.restype = ctypes.c_void_p
_user32.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
_user32.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
_kernel32.OpenProcess.restype = ctypes.c_void_p
_kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
_kernel32.QueryFullProcessImageNameW.argtypes = (
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)
)

# Wheel: global mouse hook (works whatever program is in front).
WH_MOUSE_LL, WM_MOUSEWHEEL, PM_REMOVE = 14, 0x020A, 1
WHEEL_NOTCH = 120


class _MouseInfo(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


_MouseProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = (ctypes.c_int, _MouseProc, ctypes.c_void_p, wt.DWORD)
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
_user32.PeekMessageW.argtypes = (
    ctypes.POINTER(wt.MSG), wt.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
)
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_kernel32.GetModuleHandleW.argtypes = (ctypes.c_wchar_p,)

# Positions to fill in, looked for in the configuration part of the script:
# (pattern, text to show, is a pack). The "pos" group is the position
# "(x, y)"; for a pack, the "scr" group is its scroll setting.
POSITION = r"(?P<pos>\(-?\d+, -?\d+\))"
SCROLL = r'(?P<scr>, "scroll": (?P<notches>\d+))?'
ELEMENTS = (
    (rf"^COUNTER_CENTER = {POSITION}",
     lambda m: "the \"x/10\" counter at the top of the Kyara page: tip of the mouse "
               "on the number right before the \"/\" (the 5 of \"5/10\"; "
               "\"10/10\": between the 1 and the 0; \"20/20\": between the 2 and the 0)", False),
    (rf'^\s*"(?P<name>[^"]+)": \{{"position": {POSITION}, "double_click": (?:True|False){SCROLL}',
     lambda m: f"the pack \"{m['name']}\" on the home page", True),
    (rf"^AVATAR = {POSITION}",
     lambda m: "the avatar of the logged-in account (top right, in the center)", False),
    (rf'^\s*\("(?:click|double_click)", "(?P<name>[^"]+)", {POSITION}',
     lambda m: f"the button \"{m['name']}\"", False),
    (rf'^\s*\("reveal_all", {POSITION}',
     lambda m: "the « Tout révéler » (Reveal all) button (screen of the cards to turn)", False),
)
NOT_SET = "(0, 0)"
EXECUTABLE_PATTERN = re.compile(r'^EXECUTABLE = (?P<val>"[^"]*")', re.MULTILINE)
NAME_PATTERN = re.compile(r'^NAME = "(?P<val>[^"]*)"', re.MULTILINE)
AREA_PATTERN = re.compile(r"^SCREEN_AREA = (?P<val>\(-?\d+, -?\d+, \d+, \d+\))", re.MULTILINE)


# Original configuration of kyara_booster.py (for "reset"), from
# "1. Browser" up to the "END OF CONFIGURATION" line excluded.
DEFAULT_CONFIGURATION = '''\
# ---------- 1. Browser ----------
# Name shown in the terminal. Must be different for each copy running.
NAME = "main"
# Browser program: "opera.exe", "brave.exe", "chrome.exe",
# "msedge.exe", "firefox.exe"… (filled in by configure_positions.py).
# "" = not detected yet.
EXECUTABLE = ""
# Screen where the browser is shown: (x, y, width, height)
# (filled in by configure_positions.py). Main screen: (0, 0, 1920, 1080).
# (0, 0, 0, 0) = not detected yet.
SCREEN_AREA = (0, 0, 0, 0)

# ---------- 2. Booster counter (x/10) ----------
# "x/10" counter at the top of the Kyara page: tip of the mouse on the
# number right before the "/" (the 5 of "5/10"; "10/10": between the 1
# and the 0 of the first 10). If it moves a little,
# the script finds it again by itself (automatic re-centering).
# (0, 0) = position not placed yet (applies to all positions).
COUNTER_CENTER = (0, 0)
# Size of the area read around the center (width, height). Leave as is.
COUNTER_SIZE = (100, 45)
# Number of "full counter" readings in a row before opening (avoids a
# wrong reading).
STABLE_READINGS = 2
# Max capacity of the booster counter: 10 without a subscription, 20 with a
# subscription that adds 10 capacity ("x/20"). 0 = read by itself on
# the counter (recommended: also works with several accounts, subscribed or
# not). In every case, the script opens when the counter is full.
MAX_CAPACITY = 0
# Pause between two readings of the counter, in seconds.
INTERVAL = 2
# Pause after an opening, in seconds.
PAUSE_AFTER_OPENING = 5

# ---------- 3. Packs ----------
# The easiest: configure_positions.py asks for the packs wanted and their
# order (e.g. "Sport" alone, or "Sport, Isekai"), then their positions.
# All the boosters of the game are listed; only the ones that are used
# (ROTATION, hunt, accounts) need a position.
# For a booster added to the game later: copy a line, change the name.
# "double_click": True if a single click is not enough for this pack.
# "scroll": 3   for a pack only visible when going down the page: the
#               script goes back to the top of the page then goes down 3
#               mouse wheel notches before clicking (counted by
#               configure_positions.py). Without "scroll", no scrolling.
PACKS = {
    "Shonen Mix": {"position": (0, 0), "double_click": False},
    "Shonen": {"position": (0, 0), "double_click": False},
    "Isekai": {"position": (0, 0), "double_click": True},
    "Seinen": {"position": (0, 0), "double_click": False},
    "Shojo": {"position": (0, 0), "double_click": False},
    "Sport": {"position": (0, 0), "double_click": False},
    "Mecha": {"position": (0, 0), "double_click": False},
    "Waifus": {"position": (0, 0), "double_click": False},
    "Husbandos": {"position": (0, 0), "double_click": False},
}

# Packs to open, in order, in a loop ([] = not chosen yet):
#   ["Isekai", "Shonen Mix"]  -> Isekai, then Shonen Mix, then Isekai…
#   ["Shonen Mix"]            -> always Shonen Mix
#   ["Isekai", "Isekai", "Shonen Mix"] -> two Isekai for one Shonen Mix
ROTATION = []

# Hunt for a card (optional): open a pack until a card is obtained,
# then switch to another rotation. None = no hunt.
#   HUNT = {"card": "Rimuru", "pack": "Isekai", "then": ["Shonen Mix"]}
# The card is looked for on the screen of the turned cards ("read_cards"
# step of the SEQUENCE). Only the start of the name counts: names are cut there.
# Once found, a hunt_<card>.txt file is created in the "hunts" folder:
# delete it to start the hunt again.
HUNT = None

# Several Kyara accounts on this browser (optional): the logged-in account
# is recognized by the color of its avatar (top right) and each account
# has its packs, its hunt and its counter (subscribed or not). The easiest:
# configure_positions.py, choice "Accounts", once per account while
# logged in on it.
# AVATAR = center of the avatar. ACCOUNTS = None: no accounts (ROTATION and
# HUNT are used for everybody). Example:
#   ACCOUNTS = {
#       "A": {"color": (78, 65, 29), "rotation": ["Isekai", "Shonen Mix"],
#             "hunt": None},
#       "Logo": {"color": (48, 33, 74), "rotation": ["Shonen Mix"],
#                "hunt": {"card": "Rimuru", "pack": "Isekai"}, "capacity": 20},
#   }
# "color" is read by configure_positions.py. With a hunt, the account
# opens the pack of the hunt until the card, then switches to its "rotation".
# "capacity" (optional): MAX_CAPACITY for this account only (20 =
# subscribed account, 10 = no subscription, 0 = read on the counter).
AVATAR = (0, 0)
ACCOUNTS = None

# ---------- 4. Opening sequence ----------
# The steps done when the counter is full (10/10, 20/20), in order:
#   ("pack", wait)                           click on the chosen pack (see PACKS)
#   ("click", "name", (x, y), wait)          single click
#   ("double_click", "name", (x, y), wait)   double-click
#   ("reveal_all", (x, y), wait)             looks for the « Tout révéler »
#                                            ("Reveal all") button and clicks
#                                            it; (x, y) is used if the button
#                                            is not found
#   ("read_cards",)                          looks for the card of the hunt
#                                            (nothing if no hunt going on)
#   ("wait", seconds)                        simple pause
# "wait" = seconds of waiting after the step (page loading…).
SEQUENCE = [
    ("pack", 2),
    ("click", "Open 10 boosters", (0, 0), 2),
    ("click", "Confirm the opening", (0, 0), 3),
    ("reveal_all", (0, 0), 3),
    ("read_cards",),
    ("click", "Back to start", (0, 0), 2),
]

# ---------- 5. « Tu es toujours là ? » ("Are you still there?") popup ----------
# The popup is looked for on the whole SCREEN_AREA; the click is on its button.
# Full check every N seconds (a quick test also runs at each pass and
# triggers it as soon as the red button appears).
POPUP_INTERVAL = 10

# ---------- 6. Mouse ----------
# Putting the mouse in the top-left corner of the main screen stops the script.
CORNER_STOP = True
# Duration of a mouse movement, in seconds (min, max): the mouse glides
# to the button, never jumps at once. At least 0.3 (otherwise refused).
MOVE_DURATION = (0.5, 0.9)


'''

# ============================================================
# KEYBOARD, WINDOW, SCREEN
# ============================================================
def pressed(key):
    return _user32.GetAsyncKeyState(key) & 0x8000


def pump_messages():
    """Lets the Windows messages through (needed by the wheel hook)."""
    message = wt.MSG()
    while _user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        pass


def wait_key():
    """Waits for G, N or Esc (wherever the focus is) and returns the key."""
    while True:
        for key in (KEY_G, KEY_N, KEY_ESC):
            if pressed(key):
                while pressed(key):  # wait for the release
                    pump_messages()
                    time.sleep(0.02)
                return key
        pump_messages()
        time.sleep(0.02)


def flush_terminal_keyboard():
    """Avoids the typed "g" ending up in the terminal at the end."""
    while msvcrt.kbhit():
        msvcrt.getwch()


def copy(text):
    subprocess.run(["clip"], input=text.encode("utf-8"), check=False)


def program_under(position):
    """Name of the program of the window under the mouse (e.g. "opera.exe"), or None."""
    window = _user32.WindowFromPoint(wt.POINT(*position))
    root = _user32.GetAncestor(window, 2) if window else None
    if not root:
        return None
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
    handle = _kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(512)
        size = ctypes.c_ulong(512)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name.lower()
        return None
    finally:
        _kernel32.CloseHandle(handle)


def screen_under(position):
    """(x, y, width, height) of the screen that contains the position."""
    x, y = position
    with mss.MSS() as grabber:
        for screen in grabber.monitors[1:]:
            if (screen["left"] <= x < screen["left"] + screen["width"]
                    and screen["top"] <= y < screen["top"] + screen["height"]):
                return screen["left"], screen["top"], screen["width"], screen["height"]
    return None


def position_text(position):
    return f"({position[0]}, {position[1]})"


class WheelTracker:
    """
    Counts the wheel notches from the top of the page, for each program
    (only the ones turned above the browser count for it).
    Going up higher than the top does not count: the page no longer moves.
    """

    def __init__(self):
        self.levels = {}            # program -> wheel units downwards
        self._hook = None
        self._procedure = _MouseProc(self._receive)

    def _receive(self, code, wparam, lparam):
        if code == 0 and wparam == WM_MOUSEWHEEL:
            try:
                info = ctypes.cast(lparam, ctypes.POINTER(_MouseInfo)).contents
                delta = ctypes.c_short(info.mouseData >> 16).value   # > 0 = upwards
                program = program_under((info.pt.x, info.pt.y))
                if program:
                    self.levels[program] = max(0, self.levels.get(program, 0) - delta)
            except Exception:
                pass
        return _user32.CallNextHookEx(None, code, wparam, lparam)

    def __enter__(self):
        self._hook = _user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._procedure, _kernel32.GetModuleHandleW(None), 0
        )
        return self

    def __exit__(self, *_):
        if self._hook:
            _user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def notches(self, program):
        return round(self.levels.get(program, 0) / WHEEL_NOTCH)


# ============================================================
# FREE MODE
# ============================================================
def free_mode():
    print("Free mode: put the mouse on an element and press G.")
    print("The position is copied: paste it with Ctrl+V. Esc to stop.")
    print("Wheel notches are counted from the top of the page: first go all")
    print("the way up if the page has already scrolled.\n")
    with WheelTracker() as wheel:
        while True:
            key = wait_key()
            if key == KEY_ESC:
                break
            if key != KEY_G:
                continue
            position = tuple(pyautogui.position())
            program = program_under(position)
            copy(position_text(position))
            print(f"{position_text(position)}  copied"
                  f"   (program: {program or '?'}, screen: {screen_under(position)}, "
                  f"wheel: {wheel.notches(program)} notch(es))")
    flush_terminal_keyboard()


# ============================================================
# READING AND WRITING THE CONFIGURATION
# ============================================================
def _offset(text, line, column):
    """Index in the text of a (line, column in UTF-8 bytes) given by ast."""
    lines = text.splitlines(keepends=True)
    before = sum(len(line_text) for line_text in lines[:line - 1])
    return before + len(lines[line - 1].encode("utf-8")[:column].decode("utf-8"))


def assignment(text, name):
    """(start, end, value) of the value of "NAME = …" in the script, or None."""
    for node in ast.parse(text).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name):
            value = node.value
            return (_offset(text, value.lineno, value.col_offset),
                    _offset(text, value.end_lineno, value.end_col_offset),
                    ast.literal_eval(value))
    return None


def read(text, name, default=None):
    found = assignment(text, name)
    return found[2] if found else default


def write_value(value, indent=0):
    """Value written as in the configuration (one line per pack, per step…)."""
    inside = " " * (indent + 4)
    if isinstance(value, dict) and any(isinstance(v, dict) for v in value.values()):
        lines = [f"{inside}{write_value(key)}: {write_value(v, indent + 4)},"
                 for key, v in value.items()]
        return "{\n" + "\n".join(lines) + "\n" + " " * indent + "}"
    if isinstance(value, list) and value and all(isinstance(v, tuple) for v in value):
        lines = [f"{inside}{write_value(v)}," for v in value]
        return "[\n" + "\n".join(lines) + "\n" + " " * indent + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{write_value(key)}: {write_value(v)}"
                               for key, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(write_value(v) for v in value) + "]"
    if isinstance(value, tuple):
        return ("(" + ", ".join(write_value(v) for v in value)
                + ("," if len(value) == 1 else "") + ")")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def replace(text, name, value):
    start, end, _ = assignment(text, name)
    return text[:start] + write_value(value) + text[end:]


def clean_pack(setting):
    """Setting of a pack, keys in the order expected by the assistant."""
    clean = {"position": tuple(setting.get("position", (0, 0))),
             "double_click": bool(setting.get("double_click", False))}
    if setting.get("scroll"):
        clean["scroll"] = setting["scroll"]
    return clean


def write_packs(text, packs):
    return replace(text, "PACKS", {name: clean_pack(s) for name, s in packs.items()})


def tidy_up(text):
    """
    PACKS and SEQUENCE written again in the form read by the assistant; the
    game boosters missing from PACKS are added to it (position to place).
    """
    packs = {name: {"position": (0, 0), "double_click": double}
             for name, double in GAME_BOOSTERS.items()}
    packs.update(read(text, "PACKS"))
    # Order of the game first, then the packs added by hand.
    order = [name for name in GAME_BOOSTERS] + [name for name in packs if name not in GAME_BOOSTERS]
    text = write_packs(text, {name: packs[name] for name in order})
    return replace(text, "SEQUENCE", [tuple(step) for step in read(text, "SEQUENCE")])


class Session:
    """Script being configured; .bak backup at the first change."""

    def __init__(self, file):
        self.file = file
        self.original = file.read_text(encoding="utf-8")
        self.text = self.original
        self.backup_done = False

    def save(self, new):
        if new == self.text:
            return
        compile(new, str(self.file), "exec")  # safety: the script stays valid
        backup = backup_path(self.file)
        if not self.backup_done:
            backup.write_text(self.original, encoding="utf-8")
            self.backup_done = True
        self.file.write_text(new, encoding="utf-8")
        self.text = new
        print(f"Saved in {self.file.name} "
              f"(previous version: backups\\{backup.name}).\n")


# ============================================================
# QUESTIONS
# ============================================================
# Words typed by mistake instead of a pack name.
COMMAND_WORDS = {"reset", "free", "menu", "quit", "q", "help"}

# Boosters of the game, in the order of the page, and whether a double-click is needed.
GAME_BOOSTERS = {
    "Shonen Mix": False, "Shonen": False, "Isekai": True,
    "Seinen": False, "Shojo": False, "Sport": False,
    "Mecha": False, "Waifus": False, "Husbandos": False,
}


def ask(question, default=""):
    flush_terminal_keyboard()
    return input(question).strip() or default


def yes(question, default=False):
    reply = ask(question + (" (Y/n): " if default else " (y/N): ")).lower()
    return default if not reply else reply.startswith(("y", "o"))


def number(text):
    """"2", "2.5" or "2,5" -> 2 or 2.5 (ValueError otherwise, or if negative)."""
    value = float(text.replace(",", "."))
    if value < 0:
        raise ValueError("negative number")
    return int(value) if value.is_integer() else value


def pack_list(reply, packs):
    """
    "6, 3" or "Sport, isekai" -> ["Sport", "Isekai"]: number in the list of
    boosters, or name (a known pack keeps its spelling, accents ignored).
    """
    names = list(packs)
    known = {normalized_text(name): name for name in names}
    result = []
    for piece in reply.replace('"', "").split(","):
        piece = piece.strip()
        if piece.isdigit() and 1 <= int(piece) <= len(names):
            result.append(names[int(piece) - 1])
        elif piece:
            result.append(known.get(normalized_text(piece), piece))
    return result


def show_boosters(packs):
    """Numbered list of the boosters, on three columns."""
    names = list(packs)
    lines = (len(names) + 2) // 3
    for line in range(lines):
        cells = [f"{rank + 1:>3}  {names[rank]:<14}"
                 for rank in range(line, len(names), lines)]
        print("".join(cells).rstrip())


def is_command(reply):
    if reply.lower() in COMMAND_WORDS:
        print(f"\"{reply}\" is a command, not a pack name: nothing changed.")
        print("For the reset, it is choice 8 of the menu.\n")
        return True
    return False


def add_packs(packs, names):
    """Adds the new packs to `packs` (position to place afterwards with G)."""
    for name in names:
        if name not in packs:
            double = yes(f"\"{name}\" is a new pack. Does it need a double-click to open?")
            packs[name] = {"position": (0, 0), "double_click": double}


def normalized_text(text):
    """Like normalize_text of kyara_common: no accents, lowercase."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def hunt_file(hunt, account):
    """Same name as in kyara_booster.py: hunt_[<account>_]<card>.txt."""
    name = normalized_text(hunt["card"])
    if account:
        name = f"{normalized_text(account)} {name}"
    return HUNTS_DIR / f"hunt_{name.replace(' ', '_')}.txt"


def describe_hunt(hunt):
    if not hunt:
        return "none"
    text = f"{hunt['card']} in {hunt['pack']}"
    if hunt.get("then"):
        text += f", then {', '.join(hunt['then'])}"
    return text


def ask_hunt(packs, current, rotation_after):
    """Questions of the hunt; returns the hunt wanted (dict or None)."""
    print(f"Current hunt: {describe_hunt(current)}")
    card = ask("Card to hunt (Enter = keep, \"none\" = no hunt): ")
    if not card:
        return current
    if card.lower() in ("none", "no", "nothing", "aucune", "non"):
        return None
    show_boosters(packs)
    pack = ask(f"Pack to open until getting {card} (number or name): ")
    if not pack or is_command(pack):
        print("No pack: hunt unchanged.")
        return current
    hunt = {"card": card, "pack": pack_list(pack, packs)[0]}
    then = ask(f"Packs to open once {card} is obtained, in order "
               f"(numbers or names; Enter = {', '.join(rotation_after) or 'none'}): ")
    if then and not is_command(then):
        hunt["then"] = pack_list(then, packs)
    add_packs(packs, [hunt["pack"], *hunt.get("then", [])])
    return hunt


def offer_restart(hunt, account):
    """If the card is already marked as obtained, offers to start the hunt again."""
    if not hunt:
        return
    file = hunt_file(hunt, account)
    if file.exists() and yes(f"{hunt['card']} is already marked as obtained ({file.name}). "
                             "Start the hunt again (delete this file)?"):
        file.unlink()
        file.with_suffix(".png").unlink(missing_ok=True)
        print("Hunt started again.")


def used_packs(text):
    """Packs used elsewhere than in ROTATION: {pack: by what}."""
    used = {}

    def note(hunt, by):
        for name in [hunt.get("pack"), *hunt.get("then", [])]:
            if name:
                used.setdefault(name, by)

    if read(text, "HUNT"):
        note(read(text, "HUNT"), "the hunt")
    for account, setting in (read(text, "ACCOUNTS") or {}).items():
        for name in setting.get("rotation", []):
            used.setdefault(name, f"the account \"{account}\"")
        if setting.get("hunt"):
            note(setting["hunt"], f"the hunt of the account \"{account}\"")
    return used


# ============================================================
# 2. PACKS AND ROTATION
# ============================================================
def action_packs(text):
    """Asks for the packs to open and their order, then writes PACKS and ROTATION again."""
    packs, rotation = read(text, "PACKS"), read(text, "ROTATION")
    print("=== Packs to open ===")
    show_boosters(packs)
    print(f"Currently: {', '.join(rotation) or 'no pack chosen'}")
    print("Type the NUMBERS of the packs to open, in order, separated by")
    print("commas. They are opened in a loop in this order. Examples:")
    print("   6          -> always no. 6 (Sport)")
    print("   6, 3       -> Sport, then Isekai, then Sport… (taking turns)")
    print("   3, 3, 6    -> two Isekai, then one Sport, etc.")
    print("A booster that is not in the list: type its name.")
    reply = ask("Packs" + (" (Enter = change nothing)" if rotation else "") + ": ")
    if not reply or is_command(reply):
        if not rotation:
            print("No pack chosen: the script will not be able to start.")
        print()
        return text

    rotation = pack_list(reply, packs)
    add_packs(packs, rotation)
    print(f"Packs to open: {', '.join(rotation)}\n")
    return replace(write_packs(text, packs), "ROTATION", rotation)


# ============================================================
# 3. POSITIONS (G key)
# ============================================================
def find_elements(text, all_=False):
    """
    Positions of the configuration, in the order of the file. Without `all_`,
    only the ones that are used (packs used, avatar if accounts).
    """
    end = text.find("END OF CONFIGURATION")
    configuration = text[:end if end >= 0 else len(text)]
    with_accounts = bool(read(text, "ACCOUNTS"))
    used = set(read(text, "ROTATION") or []) | set(used_packs(text))
    found = []
    for pattern, label, is_pack in ELEMENTS:
        if pattern.startswith("^AVATAR") and not with_accounts and not all_:
            continue
        for m in re.finditer(pattern, configuration, re.MULTILINE):
            if is_pack and m["name"] not in used and not all_:
                continue
            # Pack: place of the scroll setting (to replace, or to add).
            scroll = None
            if is_pack:
                start, end = m.span("scr") if m["scr"] else (m.end(), m.end())
                scroll = (start, end, int(m["notches"] or 0))
            found.append((m.start("pos"), m.end("pos"), label(m), m["pos"], scroll))
    return sorted(found)


def to_set(text):
    return [label for _, _, label, current, _ in find_elements(text)
            if current == NOT_SET]


def unknown_browser(text):
    """True if the browser or its screen have not been detected yet."""
    area = read(text, "SCREEN_AREA", (0, 0, 0, 0))
    return not read(text, "EXECUTABLE") or area[2] <= 0 or area[3] <= 0


def missing(text):
    """What is missing for the script to start, in plain words."""
    items = []
    if not read(text, "ROTATION"):
        items.append("the packs to open (none chosen)")
    if unknown_browser(text):
        items.append("the browser and its screen (detected by themselves at the first position)")
    for label in to_set(text):
        of = "of the " + label[4:] if label.startswith("the ") else "of " + label
        items.append(f"the position {of}")
    return items


def show_missing(text, title="Some settings are missing for the script to start:"):
    items = missing(text)
    if items:
        print(title)
        for item in items:
            print(f"   - {item}")
    return items


def complete(text):
    """Has everything that is missing set, in order."""
    if not read(text, "ROTATION"):
        text = action_packs(text)
    if missing(text):
        text = action_positions(text, only_to_set=True)
    if not show_missing(text, "Still missing:"):
        print("Everything is set: the script can start.\n")
    else:
        print()
    return text


def action_positions(text, only_to_set=False):
    elements = find_elements(text)
    if only_to_set:
        to_place = [element for element in elements if element[3] == NOT_SET]
        # Unknown browser, positions already placed: one G is enough to detect it.
        if not to_place and elements and unknown_browser(text):
            to_place = elements[:1]
        elements = to_place
    if not elements:
        print("No position to place.\n")
        return text

    print("=== Positions ===")
    print(f"{len(elements)} position(s) to place. For each element: put the mouse")
    print("on it, then   G = confirm    N = keep the current value    Esc = stop")
    print("You can click normally to change page (open a pack…):")
    print("only the G key saves. No need to confirm a real opening:")
    print("skip a button with N if its page is not shown.")
    print("Pack lower down the page: scroll down to it with the wheel, then G.")
    print("The notches are counted from the top of the page: if it has already")
    print("scrolled, first go all the way up with the wheel.\n")

    replacements = []           # (start, end, new text)
    browser = screen = None
    with WheelTracker() as tracker:
        for number_, (start, end, label, current, scroll) in enumerate(elements, 1):
            state = "to set" if current == NOT_SET else f"current: {current}"
            if scroll and scroll[2]:
                state += f", wheel {scroll[2]} notch(es)"
            print(f"[{number_}/{len(elements)}] {label}  ({state})")
            key = wait_key()
            if key == KEY_ESC:
                print("   Stopped: the positions already confirmed are saved.")
                break
            if key == KEY_N:
                print("   Kept.")
                continue

            position = tuple(pyautogui.position())
            new = position_text(position)
            replacements.append((start, end, new))
            copy(new)
            if scroll:
                notches = tracker.notches(program_under(position))
                replacements.append(
                    (scroll[0], scroll[1], f', "scroll": {notches}' if notches else "")
                )
                print(f"   -> {new}, wheel: {notches} notch(es)"
                      + ("" if notches else " (pack visible without scrolling)"))
            else:
                print(f"   -> {new}")
            # Browser and screen: those of the first element confirmed.
            if browser is None:
                browser = program_under(position)
                screen = screen_under(position)

    flush_terminal_keyboard()

    for pattern, value, name in (
        (EXECUTABLE_PATTERN, browser and f'"{browser}"', "EXECUTABLE"),
        (AREA_PATTERN, screen and "({}, {}, {}, {})".format(*screen), "SCREEN_AREA"),
    ):
        m = pattern.search(text)
        if m and value and m["val"] != value:
            replacements.append((m.start("val"), m.end("val"), value))
            print(f"{name} detected: {value}")

    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    return text


def action_all(text):
    return action_positions(action_packs(text))


# ============================================================
# 4. HUNT
# ============================================================
def action_hunt(text):
    packs = read(text, "PACKS")
    print("=== Hunt for a card ===")
    print("Open a pack until getting a precise card (read on the screen of the")
    print("turned cards), then switch to other packs.")
    if read(text, "ACCOUNTS"):
        print("With accounts, each account has its own hunt (menu 5): this one")
        print("is only used when the logged-in account is not recognized.")
    hunt = ask_hunt(packs, read(text, "HUNT"), read(text, "ROTATION"))
    offer_restart(hunt, None)
    print(f"Hunt: {describe_hunt(hunt)}\n")
    return replace(write_packs(text, packs), "HUNT", hunt)


# ============================================================
# 5. ACCOUNTS
# ============================================================
# As in kyara_booster.py: square read around the avatar, hue gap.
AVATAR_RADIUS = 20
MAX_ACCOUNT_GAP = 0.1


def color_under(position):
    """Average color (r, g, b) of the avatar around the position."""
    x, y = position
    with mss.MSS() as grabber:
        image = grabber.grab({"left": x - AVATAR_RADIUS, "top": y - AVATAR_RADIUS,
                              "width": 2 * AVATAR_RADIUS, "height": 2 * AVATAR_RADIUS})
    pixels = image.rgb
    pixel_count = len(pixels) // 3
    return tuple(round(sum(pixels[i::3]) / pixel_count) for i in range(3))


def color_gap(a, b):
    def share(color):
        total = sum(color) or 1
        return [component / total for component in color]
    return sum((x - y) ** 2 for x, y in zip(share(a), share(b))) ** 0.5


def describe_account(setting):
    text = f"packs {', '.join(setting.get('rotation', []))}"
    if setting.get("hunt"):
        text += f", hunt for {describe_hunt(setting['hunt'])}"
    capacity = setting.get("capacity", 0)
    text += f", counter /{capacity}" if capacity else ", counter read by itself"
    return text


def ask_capacity(default):
    """Counter capacity of an account: 0 (read by itself), 10, 20…"""
    print("Counter of this account: 0 = read by itself (recommended), 10 = no subscription,")
    print("20 = subscription with +10 capacity (\"x/20\" counter).")
    while True:
        reply = ask(f"Counter capacity for this account (Enter = {default}): ")
        if not reply:
            return default
        if reply.isdigit() and int(reply) in (0, 10, 20, 30, 40, 50):
            return int(reply)
        print("Answer 0, 10 or 20.")


def add_account(text):
    packs, accounts = read(text, "PACKS"), read(text, "ACCOUNTS") or {}
    avatar = read(text, "AVATAR", (0, 0))
    print("In the browser, log in on the account wanted (home page).")
    print("Put the mouse on the center of its avatar (top right) and press")
    print("G.   Esc = cancel")
    if wait_key() != KEY_G:
        flush_terminal_keyboard()
        print("Cancelled.\n")
        return text
    position = tuple(pyautogui.position())
    color = color_under(position)
    print(f"   -> avatar at {position_text(position)}, color {color}")
    if (accounts and tuple(avatar) != (0, 0)
            and max(abs(position[0] - avatar[0]), abs(position[1] - avatar[1])) > 15):
        print("   Warning: the avatar is no longer at the same place as for the other")
        print("   accounts. Do them again too (choice 1, logged in on each one).")

    # Account already saved with this color: offered by default.
    closest = min(((color_gap(color, s["color"]), name) for name, s in accounts.items()),
                  default=None)
    default = closest[1] if closest and closest[0] <= MAX_ACCOUNT_GAP else ""
    name = ask("Name of this account (e.g. main, logo)"
               + (f" (Enter = {default})" if default else "") + ": ", default)
    if not name:
        print("No name: cancelled.\n")
        return text
    name = {known.lower(): known for known in accounts}.get(name.lower(), name)
    for other, setting in accounts.items():
        if other != name and color_gap(color, setting["color"]) < 2 * MAX_ACCOUNT_GAP:
            print(f"   Warning: avatar color close to \"{other}\": the two "
                  "may be mixed up.")

    previous = accounts.get(name, {})
    rotation = previous.get("rotation") or read(text, "ROTATION")
    show_boosters(packs)
    while True:
        reply = ask("Packs to open for this account, in order (numbers or names"
                    + (f"; Enter = {', '.join(rotation)}" if rotation else "") + "): ")
        if reply and not is_command(reply):
            rotation = pack_list(reply, packs)
        if rotation:
            break
        print("Choose at least one pack (for example 1).")
    add_packs(packs, rotation)
    print("Hunt for a card for this account: the card is looked for at each")
    print("opening of its pack; once obtained, the account switches to its packs.")
    hunt = ask_hunt(packs, previous.get("hunt"), rotation)
    offer_restart(hunt, name)
    capacity = ask_capacity(previous.get("capacity", read(text, "MAX_CAPACITY", 0)))

    accounts[name] = {"color": color, "rotation": rotation, "hunt": hunt,
                      "capacity": capacity}
    text = write_packs(text, packs)
    text = replace(text, "AVATAR", position)
    if not read(text, "ROTATION"):
        # Packs of an account that is not recognized: those of the first account.
        text = replace(text, "ROTATION", rotation)
    print(f"Account \"{name}\": {describe_account(accounts[name])}.")
    print("Another account: switch account in the browser, then choice 1 again.\n")
    return replace(text, "ACCOUNTS", accounts)


def action_accounts(text):
    while True:
        accounts = read(text, "ACCOUNTS") or {}
        print("=== Accounts (several Kyara accounts on this browser) ===")
        print("The logged-in account is recognized by the color of its avatar, and each")
        print("account has its packs, its hunt and its counter (subscribed or not).")
        print("To do once per account.")
        for name, setting in accounts.items():
            print(f"   - {name}: {describe_account(setting)}")
        if not accounts:
            print("   No accounts: the same packs for everybody.")
        print("   1  Add or change the logged-in account")
        if accounts:
            print("   2  Delete an account")
            print("   3  Stop using accounts")
        print("   Enter  back to the menu")
        choice = ask("Choice: ")
        if choice == "1":
            text = add_account(text)
        elif choice == "2" and accounts:
            name = ask(f"Account to delete ({', '.join(accounts)}): ")
            name = {known.lower(): known for known in accounts}.get(name.lower())
            if name:
                del accounts[name]
                text = replace(text, "ACCOUNTS", accounts or None)
                print(f"Account \"{name}\" deleted.\n")
            else:
                print("Unknown account.\n")
        elif choice == "3" and accounts:
            if yes("Delete all the accounts?"):
                text = replace(text, "ACCOUNTS", None)
                print("Accounts deleted: same packs for everybody.\n")
        else:
            print()
            return text


# ============================================================
# 6. OPENING STEPS
# ============================================================
# Index of the wait in each kind of step.
WAIT_INDEX = {"pack": 1, "click": 3, "double_click": 3, "reveal_all": 2, "wait": 1}


def describe_step(step):
    action = step[0]
    if action == "pack":
        return "click on the chosen pack (according to the rotation)"
    if action in ("click", "double_click"):
        kind = "click" if action == "click" else "double-click"
        return f"{kind} \"{step[1]}\" at {position_text(step[2])}"
    if action == "reveal_all":
        return f"Reveal all (looked for on screen, fallback {position_text(step[1])})"
    if action == "read_cards":
        return "reading of the turned cards (hunt + capture)"
    if action == "wait":
        return "pause"
    return f"unknown step \"{action}\""


def step_number(text, sequence, end=False):
    rank = int(text) - 1
    if not 0 <= rank < len(sequence) + (1 if end else 0):
        raise ValueError("number does not exist")
    return rank


def add_step(sequence):
    print("Kind of step:  1 click   2 double-click   3 pause   4 Reveal all")
    print("               5 reading of the cards   6 click on the chosen pack")
    kind = ask("Kind: ")
    if kind in ("1", "2"):
        name = ask("Name of the button (shown in the terminal): ")
        if not name:
            return
        wait = number(ask("Wait after the click, in seconds (Enter = 2): ", "2"))
        step = ("click" if kind == "1" else "double_click", name, (0, 0), wait)
    elif kind == "3":
        step = ("wait", number(ask("Length of the pause, in seconds: ")))
    elif kind == "4":
        step = ("reveal_all", (0, 0), 3)
    elif kind == "5":
        step = ("read_cards",)
    elif kind == "6":
        step = ("pack", 2)
    else:
        print("Unknown kind.")
        return
    place = ask(f"Place in the list (1 to {len(sequence) + 1}, Enter = at the end): ")
    rank = step_number(place, sequence, end=True) if place else len(sequence)
    sequence.insert(rank, step)
    if (0, 0) in step:
        print("Its position will be asked with G.")


def action_steps(text):
    sequence = [tuple(step) for step in read(text, "SEQUENCE")]
    while True:
        print("=== Opening steps (done when the counter is full, in order) ===")
        for rank, step in enumerate(sequence, 1):
            wait = (f", then {step[WAIT_INDEX[step[0]]]} s"
                    if step[0] in WAIT_INDEX else "")
            print(f"   {rank:>2}  {describe_step(step)}{wait}")
        print("Commands:   a = add a step              d 3 = delete step 3")
        print("            w 3 5 = wait 5 s after step 3")
        print("            m 3 1 = move step 3 to 1st place")
        print("            Enter = finish")
        command = ask("Command: ").lower().split()
        if not command:
            break
        try:
            if command[0] == "a":
                add_step(sequence)
            elif command[0] == "d":
                print(f"Deleted: {describe_step(sequence.pop(step_number(command[1], sequence)))}")
            elif command[0] == "w":
                rank = step_number(command[1], sequence)
                step = list(sequence[rank])
                step[WAIT_INDEX[step[0]]] = number(command[2])
                sequence[rank] = tuple(step)
            elif command[0] == "m":
                step = sequence.pop(step_number(command[1], sequence))
                sequence.insert(step_number(command[2], sequence, end=True), step)
            else:
                print("Unknown command.")
        except (IndexError, ValueError, KeyError):
            print("Badly written command, number that does not exist, or step without a wait.")
        print()
    if not any(step[0] == "pack" for step in sequence):
        print("Warning: no \"click on the chosen pack\" step: no pack will")
        print("be clicked.")
    print()
    return replace(text, "SEQUENCE", sequence)


# ============================================================
# 7. SETTINGS
# ============================================================
# (name, description, default value; None = none).
SETTINGS = (
    ("NAME", "name shown in the terminal (different for each script)", None),
    ("EXECUTABLE", "browser program, e.g. opera.exe (detected with the positions)", None),
    ("INTERVAL", "pause between two readings of the counter, in seconds", 2),
    ("STABLE_READINGS", "\"full counter\" readings in a row before opening", 2),
    ("MAX_CAPACITY", "max capacity of the booster counter: 0 = read by itself on "
                     "the counter (recommended), 10 = no subscription, 20 = subscription "
                     "with +10 capacity (for the accounts without their own setting: "
                     "Accounts menu)", 0),
    ("PAUSE_AFTER_OPENING", "pause after an opening, in seconds", 5),
    ("POPUP_INTERVAL", "maximum delay between two checks of the popup, in seconds", 10),
    ("MOVE_DURATION", "duration of a mouse movement in seconds, min and max: the mouse "
                      "glides to the button (bigger = slower, minimum 0.3)",
     (0.5, 0.9)),
    ("CORNER_STOP", "mouse in the very top-left corner = emergency stop (y/n)", True),
)
MIN_MOVE_DURATION = 0.3


def convert(reply, current, name):
    """Typed value -> value of the same type as the current one (ValueError otherwise)."""
    if isinstance(current, bool):
        if reply.lower().startswith(("y", "o")):
            return True
        if reply.lower().startswith("n"):
            return False
        raise ValueError("answer y or n")
    if isinstance(current, str):
        value = reply.strip('"').strip()
        if name == "EXECUTABLE":
            value = value.lower()
            if not value.endswith(".exe"):
                value += ".exe"
        if not value:
            raise ValueError("empty value")
        return value
    if isinstance(current, (tuple, list)):
        # "0.5 ; 0.9" or "0.5 0.9" or "0.5,0.9" (also "0,5 ; 0,9", decimal comma).
        pieces = (re.split(r"[;\s]+", reply) if re.search(r"[;\s]", reply)
                  else reply.split(","))
        values = tuple(number(piece) for piece in pieces if piece)
        if len(values) != len(current):
            raise ValueError(f"{len(current)} numbers expected")
        if name == "MOVE_DURATION":
            if values[0] < MIN_MOVE_DURATION:
                raise ValueError(f"too fast: at least {show_value(MIN_MOVE_DURATION)}")
            if values[1] < values[0]:
                raise ValueError("the max must be at least equal to the min")
        return values
    value = number(reply)
    if isinstance(current, int) and not isinstance(value, int):
        raise ValueError("whole number expected")
    if value == 0 and name == "STABLE_READINGS":
        raise ValueError("at least 1")
    if name == "MAX_CAPACITY" and value not in (0, 10, 20, 30, 40, 50):
        raise ValueError("0 (automatic), 10, 20, 30, 40 or 50")
    return value


def show_value(value):
    if isinstance(value, bool):
        return "y" if value else "n"
    if isinstance(value, (tuple, list)):
        return " ; ".join(show_value(v) for v in value)
    if isinstance(value, float):
        return str(value).replace(",", ".")
    return str(value)


def action_settings(text):
    print("=== Settings ===")
    print("Default: mouse that glides in 0.5 to 0.9 second, never jumps")
    print("at once.")
    if yes("Put everything back to default at once?"):
        for name, _, default in SETTINGS:
            if default is not None and assignment(text, name) is not None:
                text = replace(text, name, default)
        print("Settings put back to default (the name and the browser are kept).\n")
        return text

    print("For each setting:   Enter = keep    d = default value")
    for name, description, default in SETTINGS:
        if assignment(text, name) is None:
            continue
        current = read(text, name)
        by_default = "" if default is None else f"   (default: {show_value(default)})"
        reply = ask(f"\n{description}\n   {name} = {show_value(current)}"
                    f"{by_default}  -> ")
        if not reply:
            continue
        if reply.lower() == "d" and default is not None:
            value = default
        else:
            try:
                value = convert(reply, current, name)
            except ValueError as error:
                print(f"   Refused ({error}): value kept.")
                continue
        text = replace(text, name, value)
        print(f"   {name} = {show_value(value)}")
    print()
    return text


# ============================================================
# 8. RESET
# ============================================================
SECTION_START = "# ---------- 1."
SECTION_END = "# ============================================================\n# END OF CONFIGURATION"


def positions_to_zero(text):
    """All positions to (0, 0), scroll settings removed."""
    for start, end, _, _, scroll in sorted(find_elements(text, all_=True), reverse=True):
        if scroll:
            text = text[:scroll[0]] + text[scroll[1]:]
        text = text[:start] + NOT_SET + text[end:]
    return text


def created_files(name):
    """Files created while running: debug captures and finished hunts."""
    patterns = ((DEBUG_DIR, f"debug_{name}.png"), (DEBUG_DIR, f"debug_{name}_*.png"),
                (DEBUG_DIR, f"debug_popup_{name}.png"),
                (HUNTS_DIR, "hunt_*.txt"), (HUNTS_DIR, "hunt_*.png"))
    return sorted({path for folder, pattern in patterns for path in folder.glob(pattern)})


def reset_mode(file):
    original = file.read_text(encoding="utf-8")
    print(f"=== Reset of {file.name} ===")
    print("   1  Coordinates to zero: all positions go to (0, 0) and the scroll")
    print("      settings are removed. Packs, rotation, hunt, accounts and")
    print("      settings are kept. To place again afterwards (menu 3).")
    print("   2  Everything to zero: the whole configuration (packs chosen, hunt,")
    print("      accounts, positions, steps, settings) goes back to that of a new")
    print("      file: no pack chosen, positions at (0, 0). Kept: the name,")
    print("      the browser and its screen.")
    print("   Enter  cancel")
    choice = ask("Choice: ")

    if choice == "1":
        try:
            new = positions_to_zero(original)
        except (SyntaxError, ValueError):
            print("Unreadable configuration: use choice 2 instead.")
            return
        summary = "Coordinates put back to (0, 0)."
    elif choice == "2":
        start, end = original.find(SECTION_START), original.find(SECTION_END)
        if start < 0 or end < start:
            print("Configuration part not found (markers deleted?): nothing is done.")
            print("Take a new copy of kyara_booster.py.")
            return
        new = original[:start] + DEFAULT_CONFIGURATION + original[end:]
        # Kept: the name (unique per script), the browser and its screen.
        kept = []
        for pattern in (NAME_PATTERN, EXECUTABLE_PATTERN, AREA_PATTERN):
            current = pattern.search(original[start:end])
            if current:
                new = pattern.sub(lambda _: current[0], new, count=1)
                kept.append(current[0])
        summary = ("Configuration reset"
                   + (f" (kept: {', '.join(kept)})" if kept else "") + ".")
    else:
        print("Cancelled: nothing changed.\n")
        return

    compile(new, str(file), "exec")  # safety: the script stays valid
    if not yes(f"{summary.rstrip('.')}: confirm?"):
        print("Cancelled: nothing changed.\n")
        return
    backup = backup_path(file)
    backup.write_text(original, encoding="utf-8")
    file.write_text(new, encoding="utf-8")
    print(f"{summary} Previous version: backups\\{backup.name}.")

    name = NAME_PATTERN.search(new)
    created = created_files(name["val"]) if name else []
    if created:
        print(f"\nFiles created while running ({len(created)}):")
        for path in created:
            print(f"   {path.parent.name}\\{path.name}")
        print("Deleting them also clears the finished hunts (they start again).")
        if yes("Delete them?"):
            for path in created:
                path.unlink(missing_ok=True)
            print("Deleted.")
    print("\nWhen opened, configure_positions.py will ask for what is to be done again.\n")


# ============================================================
# CHOICE OF THE SCRIPT (one per browser)
# ============================================================
def status(text):
    """"ready" or "N setting(s) missing"."""
    try:
        missing_count = len(missing(tidy_up(text)))
    except (SyntaxError, ValueError, TypeError, AttributeError):
        return "unreadable configuration"
    return f"{missing_count} setting(s) missing" if missing_count else "ready"


def folder_scripts():
    """Booster scripts of the folder: (file, NAME, EXECUTABLE, status)."""
    scripts = []
    for file in sorted(DIRECTORY.glob("kyara_booster*.py")):
        text = file.read_text(encoding="utf-8", errors="replace")
        name, executable = NAME_PATTERN.search(text), EXECUTABLE_PATTERN.search(text)
        if name:
            scripts.append((file, name["val"],
                            executable and executable["val"].strip('"') or "to detect",
                            status(text)))
    return scripts


def create_script(names_taken):
    """Copy of kyara_booster.py for another browser, empty configuration."""
    if not DEFAULT_FILE.exists():
        print(f"{DEFAULT_FILE.name} not found: cannot make a copy of it.")
        return None
    print("Name of the new script, for example the browser's:")
    print("   brave, chrome, edge, firefox, opera2…")
    name = re.sub(r"[^a-z0-9_-]", "", ask("Name: ").lower().replace(" ", "_"))
    file = DIRECTORY / f"kyara_booster_{name}.py"
    if not name:
        print("Empty name: cancelled.")
        return None
    if name in {taken.lower() for taken in names_taken} or file.exists():
        print(f"\"{name}\" is already used: choose another name.")
        return None

    text = DEFAULT_FILE.read_text(encoding="utf-8")
    start, end = text.find(SECTION_START), text.find(SECTION_END)
    if start < 0 or end < start:
        print(f"Configuration part of {DEFAULT_FILE.name} not found: cancelled.")
        return None
    # The code of kyara_booster.py, with a new configuration (everything to zero).
    text = text[:start] + DEFAULT_CONFIGURATION + text[end:]
    text = NAME_PATTERN.sub(lambda _: f'NAME = "{name}"', text, count=1)
    compile(text, str(file), "exec")
    file.write_text(text, encoding="utf-8")
    print(f"Created: {file.name} (NAME \"{name}\", everything to set).")
    print("For the positions, put the mouse on THIS browser: it is detected")
    print("by itself, with its screen.")
    print(f"To run it afterwards: python {file.name}\n")
    return file


def choose_script():
    """Asks which script (so which browser) to configure."""
    scripts = folder_scripts()
    print("=== Script to configure ===")
    print("One script per browser. Which one to configure?")
    for rank, (file, name, executable, script_status) in enumerate(scripts, 1):
        print(f"   {rank}  {file.name:<28} browser: {executable:<12} ({script_status})")
    new = len(scripts) + 1
    print(f"   {new}  New script for another browser")
    reply = ask("Choice (Enter = 1): ", "1")
    print()
    if reply.isdigit() and 1 <= int(reply) <= len(scripts):
        return scripts[int(reply) - 1][0]
    if reply == str(new):
        return create_script([name for _, name, _, _ in scripts])
    print("Unknown choice: cancelled.")
    return None


# ============================================================
# MENU
# ============================================================
ACTIONS = {
    "1": ("Configure everything: packs then positions (recommended the 1st time)", action_all),
    "2": ("Packs and rotation (which ones to open, in which order)", action_packs),
    "3": ("Positions (mouse + G key)", action_positions),
    "4": ("Hunt for a card", action_hunt),
    "5": ("Accounts (several Kyara accounts on this browser)", action_accounts),
    "6": ("Opening steps (add, delete, waits)", action_steps),
    "7": ("Settings (name, browser, pauses, mouse speed…)", action_settings),
    "8": ("Reset (coordinates or everything)", None),
    "9": ("Free mode (show / copy a position)", None),
}


def summary(file, text):
    accounts = read(text, "ACCOUNTS")
    print(f"--- {file.name}: NAME \"{read(text, 'NAME')}\", "
          f"browser {read(text, 'EXECUTABLE') or 'to detect'}   |   {status(text)}")
    print(f"    Packs to open: {', '.join(read(text, 'ROTATION')) or 'none'}"
          f"   |   Hunt: {describe_hunt(read(text, 'HUNT'))}")
    print(f"    Accounts: {', '.join(accounts) if accounts else 'none'}")


def menu(file):
    session = Session(file)
    try:
        session.save(tidy_up(session.text))
    except (SyntaxError, ValueError, TypeError, AttributeError) as error:
        print(f"The configuration of {file.name} is unreadable ({error}).")
        print("Fix it in the file, or put it back to default:")
        reset_mode(file)
        return

    if show_missing(session.text):
        if yes("Set them now?", default=True):
            print()
            session.save(complete(session.text))
        else:
            print()

    while True:
        summary(file, session.text)
        for key, (label, _) in ACTIONS.items():
            print(f"   {key}  {label}")
        choice = ask("Choice (Enter = quit): ")
        print()
        if not choice:
            break
        if choice not in ACTIONS:
            print("Unknown choice.\n")
            continue
        if choice == "8":
            reset_mode(file)
            session = Session(file)
            session.save(tidy_up(session.text))
            continue
        if choice == "9":
            free_mode()
            continue

        session.save(ACTIONS[choice][1](session.text))
        if choice not in ("1", "3") and show_missing(session.text, "Still missing:"):
            if yes("Set them now?", default=True):
                print()
                session.save(complete(session.text))

    if show_missing(session.text, "Warning, still missing:"):
        print("The script will refuse to start as long as this is not set.")
        print("Run  python configure_positions.py  again: it will ask for it.")
    if session.text != session.original:
        print(f"Run the script again so that it takes the new configuration:")
        print(f"   python {file.name}")


def main():
    arguments = sys.argv[1:]
    if "free" in arguments:
        free_mode()
        return
    reset = "reset" in arguments
    arguments = [argument for argument in arguments if argument != "reset"]
    file = Path(arguments[0]) if arguments else choose_script()
    if file is None:
        return
    if not file.is_absolute():
        file = DIRECTORY / file
    if not file.exists():
        print(f"File not found: {file}")
        return
    if reset:
        reset_mode(file)
    else:
        menu(file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        flush_terminal_keyboard()
        print("\nStopped.")
