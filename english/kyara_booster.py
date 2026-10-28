"""
Automatic opening of Kyara boosters — fully configurable version.

Everything is set in the CONFIGURATION part below (see also README.txt).
The positions fill themselves in with configure_positions.py.

Several browsers at the same time: copy this file (e.g. kyara_booster_2.py)
and change NAME, EXECUTABLE, SCREEN_AREA and the positions. The copies that
are running detect at the same time but open each in turn (a single mouse).
"""

# ============================================================
# CONFIGURATION
# ============================================================

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


# ============================================================
# END OF CONFIGURATION — nothing to change below
# ============================================================

import re
import time
from datetime import datetime

import pyautogui
import pytesseract
from PIL import ImageChops, ImageOps, ImageStat

import kyara_common
from kyara_common import (
    POSSIBLE_CAPACITIES,
    HUNTS_DIR,
    DEBUG_DIR,
    CounterDetector,
    PopupWatcher,
    main_loop,
    capture_area,
    click,
    MIN_MOVE_DURATION,
    scroll,
    distance,
    normalize_text,
)

PREFIX = f"[{NAME.upper()}]"
REVEAL_IMAGE = DEBUG_DIR / f"debug_{NAME}_reveal.png"

# « Tout révéler » button: band searched around the fallback position,
# only white text kept (the gray text next to it and the border bother the OCR).
BAND_HALF_WIDTH, BAND_TOP, BAND_HEIGHT = 500, 31, 90
BUTTON_TEXT_THRESHOLD = 160
MAX_BUTTON_WAIT = 8
# Before reading the cards, wait until the screen stops moving (animation).
MAX_GRID_WAIT = 6

pyautogui.FAILSAFE = CORNER_STOP
pyautogui.PAUSE = 0.15
kyara_common.MOVE_DURATION = MOVE_DURATION
kyara_common.EXECUTABLES[NAME] = EXECUTABLE.lower()

# Accounts: avatar read in a square of 2 x AVATAR_RADIUS around AVATAR,
# recognized if its color (hue, without the brightness) is close enough.
AVATAR_RADIUS = 20
MAX_ACCOUNT_GAP = 0.1
# The avatar is checked again every N seconds (account change).
ACCOUNT_CHECK = 10

# Logged-in account (None: unknown or no accounts).
current_account = None
last_account_check = float("-inf")
unknown_avatar_reported = False
# Next pack of the rotation, per account (None: without account).
rotation_positions = {}
# Counter detector, to give it the capacity of the logged-in account.
counter_detector = None


# ============================================================
# CONFIGURATION CHECK
# ============================================================
def check_configuration():
    errors = []
    used = set()

    def check_packs(names, where):
        used.update(names)
        for name in names:
            if name not in PACKS:
                errors.append(f"{where}: pack \"{name}\" missing from PACKS.")

    def check_hunt(hunt, where):
        if not isinstance(hunt, dict) or not hunt.get("card") or not hunt.get("pack"):
            errors.append(f"{where}: the hunt must have a \"card\" and a \"pack\".")
            return
        check_packs([hunt["pack"]], where)
        if "then" in hunt:
            if not hunt["then"]:
                errors.append(f"{where}: \"then\" is empty.")
            check_packs(hunt["then"], where)

    if not EXECUTABLE.strip():
        errors.append("browser (EXECUTABLE) to set.")
    if SCREEN_AREA[2] <= 0 or SCREEN_AREA[3] <= 0:
        errors.append("browser screen (SCREEN_AREA) to set.")
    if tuple(COUNTER_CENTER) == (0, 0):
        errors.append("counter position (COUNTER_CENTER) to set.")
    if not ROTATION:
        errors.append("packs to open (ROTATION) to set: none chosen.")
    check_packs(ROTATION, "ROTATION")
    if HUNT:
        check_hunt(HUNT, "HUNT")
    if ACCOUNTS:
        if tuple(AVATAR) == (0, 0):
            errors.append("avatar position (AVATAR) to set.")
        for name, account in ACCOUNTS.items():
            where = f"account \"{name}\""
            color = account.get("color")
            if not (isinstance(color, (tuple, list)) and len(color) == 3):
                errors.append(f"{where}: \"color\" must be (red, green, blue).")
            rotation = account.get("rotation", ROTATION)
            if not rotation:
                errors.append(f"{where}: empty rotation.")
            check_packs(rotation, where)
            if account.get("hunt"):
                check_hunt(account["hunt"], where)
            capacity = account.get("capacity", 0)
            if capacity and capacity not in POSSIBLE_CAPACITIES:
                errors.append(f"{where}: \"capacity\": 0 (read on the counter) or "
                              f"{', '.join(map(str, POSSIBLE_CAPACITIES))}.")

    # (0, 0): position not placed yet with configure_positions.py.
    for name in sorted(used & PACKS.keys()):
        if tuple(PACKS[name]["position"]) == (0, 0):
            errors.append(f"position of the pack \"{name}\" to set.")
    for name, setting in PACKS.items():
        notches = setting.get("scroll", 0)
        if not isinstance(notches, int) or notches < 0:
            errors.append(f"PACKS: \"scroll\" of the pack \"{name}\" must be "
                          "a whole number of notches (0 or more).")
    for step in SEQUENCE:
        if step[0] not in ("pack", "click", "double_click", "reveal_all",
                           "read_cards", "wait"):
            errors.append(f"SEQUENCE: unknown step \"{step[0]}\".")
        elif step[0] in ("click", "double_click") and tuple(step[2]) == (0, 0):
            errors.append(f"position of the button \"{step[1]}\" to set.")
        elif step[0] == "reveal_all" and tuple(step[1]) == (0, 0):
            errors.append("position of the « Tout révéler » (Reveal all) button to set.")
    if MAX_CAPACITY and MAX_CAPACITY not in POSSIBLE_CAPACITIES:
        errors.append(f"MAX_CAPACITY: 0 (read on the counter) or "
                      f"{', '.join(map(str, POSSIBLE_CAPACITIES))}.")
    if not (MIN_MOVE_DURATION <= MOVE_DURATION[0] <= MOVE_DURATION[1]):
        errors.append(f"MOVE_DURATION: (min, max) with min at least "
                      f"{MIN_MOVE_DURATION} and max at least min (default (0.5, 0.9)).")
    if errors:
        print(f"{PREFIX} [CONFIGURATION] Some settings are missing to start:")
    for error in errors:
        print(f"{PREFIX} [CONFIGURATION]    - {error}")
    return not errors


# ============================================================
# ACCOUNTS
# ============================================================
def chromaticity(color):
    """Share of red, green and blue: the same, darkened or not."""
    total = sum(color) or 1
    return [component / total for component in color]


def color_gap(a, b):
    return sum((x - y) ** 2 for x, y in zip(chromaticity(a), chromaticity(b))) ** 0.5


def read_account():
    """Name of the account whose avatar is shown, or None if it is not recognized."""
    x, y = AVATAR
    image = capture_area(
        (x - AVATAR_RADIUS, y - AVATAR_RADIUS, 2 * AVATAR_RADIUS, 2 * AVATAR_RADIUS)
    )
    color = ImageStat.Stat(image.convert("RGB")).mean
    if sum(color) < 30:  # black screen or page loading
        return None
    gap, name = min((color_gap(color, account["color"]), name)
                    for name, account in ACCOUNTS.items())
    return name if gap <= MAX_ACCOUNT_GAP else None


def account_settings():
    """(rotation, hunt, account) of the logged-in account, otherwise the general settings."""
    if ACCOUNTS and current_account in ACCOUNTS:
        account = ACCOUNTS[current_account]
        return account.get("rotation", ROTATION), account.get("hunt"), current_account
    return ROTATION, HUNT, None


def account_capacity(account=None):
    """Counter capacity for this account (otherwise MAX_CAPACITY); 0 = read on screen."""
    return (ACCOUNTS or {}).get(account, {}).get("capacity", MAX_CAPACITY)


def capacity_text(capacity):
    return f"counter /{capacity}" if capacity else "counter read by itself"


def update_account():
    global current_account, unknown_avatar_reported
    if not ACCOUNTS:
        return
    seen = read_account()
    if seen is None:
        # Normal outside the home page or under a popup: the last account stays.
        if current_account is None and not unknown_avatar_reported:
            print(f"{PREFIX} Avatar not recognized: general settings meanwhile "
                  f"({describe(ROTATION, HUNT, None)}).")
            unknown_avatar_reported = True
        return
    if seen != current_account:
        current_account = seen
        print(f"{PREFIX} Logged-in account: {seen} ({describe(*account_settings())}, "
              f"{capacity_text(account_capacity(seen))}).")
        if counter_detector:
            counter_detector.change_capacity(account_capacity(seen))


def follow_account():
    """Called at each pass: checks the avatar every N seconds."""
    global last_account_check
    if not ACCOUNTS or time.monotonic() - last_account_check < ACCOUNT_CHECK:
        return
    last_account_check = time.monotonic()
    update_account()


# ============================================================
# HUNT FOR A CARD
# ============================================================
def hunt_file(hunt, account):
    name = normalize_text(hunt["card"])
    if account:
        name = f"{normalize_text(account)} {name}"
    return HUNTS_DIR / f"hunt_{name.replace(' ', '_')}.txt"


def hunt_going_on(hunt, account):
    return bool(hunt) and not hunt_file(hunt, account).exists()


def describe(rotation, hunt, account):
    """What the script does with these settings, in one sentence."""
    then = " / ".join(hunt.get("then", rotation) if hunt else rotation)
    if hunt_going_on(hunt, account):
        return (f"hunt for {hunt['card']}: pack {hunt['pack']} until "
                f"getting it, then {then}")
    if hunt:
        return (f"rotation {then}, hunt for {hunt['card']} done "
                f"({hunt_file(hunt, account).name})")
    return f"rotation {then}"


def card_pattern(card):
    """
    Pattern that recognizes the start of the name (names are cut, "Rimur…"),
    even with a stray letter stuck in front or a misread first letter.
    """
    word = normalize_text(card).split()[0]

    def loose(text):
        # Letters the OCR often mixes up.
        return "".join(
            {"i": "[il1]", "l": "[il1]", "o": "[o0]", "m": "(?:m|rn)"}.get(c, re.escape(c))
            for c in text
        )

    if len(word) <= 4:
        return re.compile(rf"^{loose(word)}")
    return re.compile(f"{loose(word[:4])}|{loose(word[1:5])}")


def difference(image_a, image_b):
    """Average gap between two captures (0 = identical)."""
    gap = ImageChops.difference(ImageOps.grayscale(image_a), ImageOps.grayscale(image_b))
    return ImageStat.Stat(gap).mean[0]


def wait_stable_screen():
    """Waits until the screen stops moving (end of the cards animation)."""
    previous = capture_area(SCREEN_AREA)
    start = time.monotonic()
    while time.monotonic() - start < MAX_GRID_WAIT:
        time.sleep(1)
        image = capture_area(SCREEN_AREA)
        if difference(image, previous) < 1:
            return image
        previous = image
    return previous


def read_cards(card):
    """Reads the screen of the turned cards; returns (image, words where the card is read)."""
    image = wait_stable_screen()
    gray = ImageOps.grayscale(image)
    words = set()
    # Two preparations: white text alone, then stretched contrast. Enlarged,
    # because the card names are small.
    for prepared in (gray.point(lambda v: 0 if v >= 160 else 255),
                     ImageOps.autocontrast(gray)):
        prepared = prepared.resize((prepared.width * 2, prepared.height * 2))
        text = pytesseract.image_to_string(prepared, config="--oem 3 --psm 11")
        words.update(normalize_text(text).split())
    pattern = card_pattern(card)
    return image, sorted(word for word in words if pattern.search(word))


def step_read_cards(pack, hunt, account):
    """Looks for the card of the hunt; creates the end-of-hunt file if found."""
    if not hunt_going_on(hunt, account) or pack != hunt["pack"]:
        # Kept to check the screen of the turned cards.
        capture_area(SCREEN_AREA).save(REVEAL_IMAGE)
        return

    image, found = read_cards(hunt["card"])
    image.save(REVEAL_IMAGE)
    if not found:
        print(f"{PREFIX} No {hunt['card']} in these cards. "
              f"Image: {REVEAL_IMAGE}")
        return

    file = hunt_file(hunt, account)
    capture = file.with_suffix(".png")
    image.save(capture)
    file.write_text(
        f"{hunt['card']} obtained on {datetime.now():%Y-%m-%d at %H:%M}"
        + (f" (account {account})" if account else "")
        + f" (read: {', '.join(found)}).\n",
        encoding="utf-8",
    )
    print(f"{PREFIX} " + "*" * 50)
    print(f"{PREFIX} {hunt['card'].upper()} OBTAINED! Switching to: "
          f"{describe(*account_settings()) if account else describe(ROTATION, HUNT, None)}.")
    print(f"{PREFIX} Capture: {capture}")
    print(f"{PREFIX} " + "*" * 50)


# ============================================================
# « TOUT RÉVÉLER » (REVEAL ALL) BUTTON
# ============================================================
def locate_reveal_button(fallback):
    """Screen center of the « Tout révéler » button, or None if it is not shown."""
    x0 = fallback[0] - BAND_HALF_WIDTH
    y0 = fallback[1] - BAND_TOP
    width, height = 2 * BAND_HALF_WIDTH, BAND_HEIGHT
    image = capture_area((x0, y0, width, height))
    gray = ImageOps.grayscale(image).point(
        lambda v: 0 if v >= BUTTON_TEXT_THRESHOLD else 255
    )
    gray = gray.resize((width * 2, height * 2))
    data = pytesseract.image_to_data(
        gray, config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT
    )
    words = [
        (normalize_text(text), i)
        for i, text in enumerate(data["text"])
        if normalize_text(text)
    ]
    # The game is in French: the button reads « Tout révéler ».
    for word, i in words:
        if distance(word, "reveler") > 1:
            continue
        left = data["left"][i]
        # The button starts at the « Tout » right before it, if it is read.
        for other, j in words:
            if distance(other, "tout") <= 1 and 0 < left - data["left"][j] < 120:
                left = data["left"][j]
        right = data["left"][i] + data["width"][i]
        middle_y = data["top"][i] + data["height"][i] / 2
        return x0 + round((left + right) / 4), y0 + round(middle_y / 2)
    return None


def step_reveal_all(fallback, wait):
    """Clicks « Tout révéler » and checks that the button is gone."""
    start = time.monotonic()
    position = None
    while time.monotonic() - start < MAX_BUTTON_WAIT:
        position = locate_reveal_button(fallback)
        if position:
            break
        time.sleep(0.5)

    if not position:
        print(f"{PREFIX} « Tout révéler » button not found: fallback position.")
        click(NAME, fallback, "Reveal all", wait, double=True)
        return

    for _ in range(3):
        click(NAME, position, "Reveal all", 1.5)
        if not locate_reveal_button(fallback):
            break
        print(f"{PREFIX} « Tout révéler » still shown: new click.")
    time.sleep(max(0, wait - 1.5))


# ============================================================
# OPENING
# ============================================================
def choose_pack():
    """(pack, hunt, account): pack to open according to the account, the hunt and the rotation."""
    update_account()
    rotation, hunt, account = account_settings()
    if hunt_going_on(hunt, account):
        return hunt["pack"], hunt, account
    then = hunt.get("then", rotation) if hunt else rotation
    position = rotation_positions.get(account, 0)
    rotation_positions[account] = position + 1
    return then[position % len(then)], hunt, account


def open_boosters():
    pack, hunt, account = choose_pack()
    print(f"{PREFIX} Start of the opening: {pack}"
          + (f" (account {account})." if account else "."))

    for step in SEQUENCE:
        action = step[0]
        if action == "pack":
            setting = PACKS[pack]
            if setting.get("scroll", 0):
                scroll(NAME, setting["position"], setting["scroll"], pack)
            click(NAME, setting["position"], pack, step[1],
                  double=setting.get("double_click", False))
        elif action in ("click", "double_click"):
            _, description, position, wait = step
            click(NAME, position, description, wait, double=action == "double_click")
        elif action == "reveal_all":
            step_reveal_all(step[1], step[2])
        elif action == "read_cards":
            try:
                step_read_cards(pack, hunt, account)
            except Exception as error:
                print(f"{PREFIX} [CARDS ERROR] {error}")
        elif action == "wait":
            time.sleep(step[1])

    print(f"{PREFIX} Opening done.")


# ============================================================
# START
# ============================================================
def capital(text):
    """First letter in capital, the rest as it is ("Shonen Mix")."""
    return text[:1].upper() + text[1:]


def main():
    global counter_detector
    print("=" * 60)
    print(f" KYARA AUTOMATION - {NAME.upper()} ({EXECUTABLE})")
    print("=" * 60)
    if not check_configuration():
        print(f"{PREFIX} Run  python configure_positions.py  : it will ask you "
              "for what is missing. Then run this script again.")
        return

    if ACCOUNTS:
        print(f"{PREFIX} Accounts recognized by their avatar:")
        for name, account in ACCOUNTS.items():
            print(f"{PREFIX}    {name}: "
                  f"{describe(account.get('rotation', ROTATION), account.get('hunt'), name)}, "
                  f"{capacity_text(account_capacity(name))}.")
        print(f"{PREFIX}    other / not recognized: {describe(ROTATION, HUNT, None)}, "
              f"{capacity_text(MAX_CAPACITY)}.")
    else:
        print(f"{PREFIX} {capital(describe(ROTATION, HUNT, None))}, "
              f"{capacity_text(MAX_CAPACITY)}.")

    detector = CounterDetector(
        NAME, COUNTER_CENTER, COUNTER_SIZE, stable_readings=STABLE_READINGS,
        capacity=account_capacity(current_account),
    )
    counter_detector = detector
    popup = PopupWatcher(NAME, SCREEN_AREA, POPUP_INTERVAL)

    main_loop(NAME, detector, popup, open_boosters, INTERVAL,
              pause_after_opening=PAUSE_AFTER_OPENING,
              each_pass=follow_account)


if __name__ == "__main__":
    main()
