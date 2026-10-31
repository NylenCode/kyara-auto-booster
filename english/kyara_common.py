"""
Tools used by kyara_booster.py: capture, reading the 10/10 counter,
detection of the presence popup, clicks. Nothing to set here: all the
configuration is at the top of kyara_booster.py.
"""

import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import random
import re
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

import mss
import pyautogui
import pytesseract
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat

from coordination import request_turn, report_counter, end_turn


TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if not TESSERACT_PATH.exists():
    raise FileNotFoundError(f"Tesseract not found: {TESSERACT_PATH}")

pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)

SCRIPT_DIR = Path(__file__).resolve().parent
# Files created while running, kept apart from the scripts: check captures
# (replaced each time) and finished hunts.
DEBUG_DIR = SCRIPT_DIR / "debug"
HUNTS_DIR = SCRIPT_DIR / "hunts"
DEBUG_DIR.mkdir(exist_ok=True)
HUNTS_DIR.mkdir(exist_ok=True)

# Cursor movement: duration (in seconds) picked at random in this range,
# with acceleration then slowing down. Increase to slow down.
MOVE_DURATION = (0.5, 0.9)
# Below this, the cursor would almost jump at once: never faster.
MIN_MOVE_DURATION = 0.3
# Short pause once on the target, before the click.
PAUSE_BEFORE_CLICK = 0.15

# Prints each OCR pass (useful to tune the areas).
VERBOSE_OCR = False

# --- Main method: comparing glyphs (no OCR) ---
# The counter font is monospaced: "10/10" gives 5 glyphs whose first two
# are identical to the last two; "9/10" gives only 4.
# Max gap (pixels) between two glyphs of the same text; beyond that, it is
# the colored indicator on the left or another interface element.
MAX_GLYPH_GAP = 3
# Likeness (correlation of the gray levels, -1 to 1) of two glyphs, measured
# on real captures: the same digit gives 0.87 to 1.00, two different digits
# 0.81 at most ("3" and "5"; slashed zero and "5": 0.78). At least
# SAME_SIMILARITY: same digit. Less than DIFFERENT_SIMILARITY: different
# digits. In between: doubt, OCR.
SAME_SIMILARITY = 0.85
DIFFERENT_SIMILARITY = 0.83
# Turned by 180°, the slashed zero stays nearly the same (0.72 to 0.78 on real
# captures), not the "6" (0.32): this decides when the OCR reads one of the
# two, the only way without a "0" in the denominator (20/25, 6/15).
ZERO_SYMMETRY = 0.52
# Thresholds tried in turn (above Otsu): a stricter threshold separates
# glyphs stuck together by anti-aliasing ("6/" or "10").
THRESHOLD_HARDENINGS = (0, 30, 60)

# --- Fallback method: OCR with votes ---
# Full counter: the number before the "/" is the same as after (10/10, or
# 20/20 with a subscription that adds 10 capacity). The slashed zero of the
# font is often read "6", "8" or "9": 16/16 is therefore 10/10.
# Without the slash (read "1", "7" or lost), the reading counts as half a vote.
READING_PATTERN = re.compile(r"(\d{2})/(\d{2})")
READING_PATTERN_NO_SLASH = re.compile(r"(\d{2})[17]?(\d{2})")
# Possible capacities, to recognize the denominator read (the "20" of "3/20"):
# 10, 20 with a subscription, 15 and 25 with the bonus of an event…
POSSIBLE_CAPACITIES = tuple(range(10, 55, 5))
OCR_CONFIG = "-c tessedit_char_whitelist=0123456789/"
OCR_PSM = (7, 6)
THRESHOLD_OFFSETS = (0, -30, 30)

# Without any change, the counter value is printed again every N seconds.
PERIODIC_DISPLAY = 60

# Re-centering: if the counter is unreadable N times in a row, it is looked
# for in a band of this size around the expected position.
UNREADABLE_BEFORE_RECENTER = 2
DELAY_BETWEEN_RECENTERS = 10
# "Counter not found" is printed again only once every N seconds.
NOT_FOUND_REMINDER = 300

UNIFORM_DETAIL = "uniform image"


def number_read(text):
    """"16" -> "10": the slashed zero (2nd digit) read 6, 8 or 9 becomes 0 again."""
    return text[0] + ("0" if text[1] in "0689" else text[1])


def full_vote(compact, capacity=0):
    """
    Vote of an OCR reading for "full counter": 1, 0.5 without slash, else 0.
    capacity = 0: any number, the same on both sides.
    """
    for pattern, vote in ((READING_PATTERN, 1), (READING_PATTERN_NO_SLASH, 0.5)):
        m = pattern.fullmatch(compact)
        if not m:
            continue
        numerator, denominator = number_read(m[1]), number_read(m[2])
        if (numerator == denominator and int(numerator) in POSSIBLE_CAPACITIES
                and (not capacity or int(numerator) == capacity)):
            return vote
    return 0
SEARCH_WIDTH = 600
SEARCH_HEIGHT = 75

# Score to reach to stop the OCR passes early.
DECISIVE_SCORE = 3
MIN_SCORE = 2


# ============================================================
# CAPTURE
# ============================================================
_grabber = None


def capture_area(region):
    """
    Captures (x, y, width, height) in screen coordinates (negatives included).
    The browser window is read directly, even if another window goes in
    front of it; otherwise, the screen is captured.
    """
    global _grabber
    x, y, width, height = (int(v) for v in region)

    if _window is not None:
        image = _window.capture((x, y, width, height))
        if image is not None:
            return image

    if _grabber is None:
        _grabber = mss.MSS()
    capture = _grabber.grab(
        {"left": x, "top": y, "width": width, "height": height}
    )
    return Image.frombytes("RGB", capture.size, capture.rgb)


# ============================================================
# BROWSER WINDOW
# ============================================================
# The window is read with PrintWindow: the script sees it even when hidden
# behind Discord or another window. To click, it comes to the front for
# the time of the action, then the windows are put back as before.
EXECUTABLES = {"brave": "brave.exe", "opera": "opera.exe"}
# Window lost (closed, minimized): searched again every N seconds.
WINDOW_SEARCH_DELAY = 10
# A capture of the window is reused for N seconds (counter + popup).
WINDOW_CACHE_DURATION = 0.25
# Minimum share of the screen the window must cover to be followed
# (its invisible border sticks out a few pixels onto the next screen).
MIN_SCREEN_SHARE = 0.25

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32")
_kernel32 = ctypes.WinDLL("kernel32")
_dwmapi = ctypes.WinDLL("dwmapi")

_user32.GetForegroundWindow.restype = wt.HWND
_user32.GetWindow.restype = wt.HWND
_user32.GetWindow.argtypes = (wt.HWND, wt.UINT)
_user32.GetAncestor.restype = wt.HWND
_user32.GetAncestor.argtypes = (wt.HWND, wt.UINT)
_user32.WindowFromPoint.restype = wt.HWND
_user32.WindowFromPoint.argtypes = (wt.POINT,)
_user32.GetWindowDC.restype = wt.HDC
_user32.GetWindowDC.argtypes = (wt.HWND,)
_user32.ReleaseDC.argtypes = (wt.HWND, wt.HDC)
_user32.PrintWindow.argtypes = (wt.HWND, wt.HDC, wt.UINT)
_user32.SetWindowPos.argtypes = (
    wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT
)
_user32.GetWindowLongW.argtypes = (wt.HWND, ctypes.c_int)
_gdi32.CreateCompatibleDC.restype = wt.HDC
_gdi32.CreateCompatibleDC.argtypes = (wt.HDC,)
_gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
_gdi32.CreateCompatibleBitmap.argtypes = (wt.HDC, ctypes.c_int, ctypes.c_int)
_gdi32.SelectObject.restype = wt.HGDIOBJ
_gdi32.SelectObject.argtypes = (wt.HDC, wt.HGDIOBJ)
_gdi32.DeleteObject.argtypes = (wt.HGDIOBJ,)
_gdi32.DeleteDC.argtypes = (wt.HDC,)
_gdi32.GetDIBits.argtypes = (
    wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT
)
_kernel32.OpenProcess.restype = wt.HANDLE
_kernel32.CloseHandle.argtypes = (wt.HANDLE,)

PW_RENDERFULLCONTENT = 2
GW_HWNDPREV = 3
GA_ROOT = 2
HWND_TOPMOST = wt.HWND(-1)
HWND_NOTOPMOST = wt.HWND(-2)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
DWMWA_CLOAKED = 14


class _BitmapHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


def _rectangle(hwnd):
    rect = wt.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def _process(hwnd):
    pid = wt.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _executable(pid):
    handle = _kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(512)
        size = wt.DWORD(512)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value).lower()
        return ""
    finally:
        _kernel32.CloseHandle(handle)


def _shown(hwnd):
    """Window really visible on screen (neither minimized nor hidden by Windows)."""
    if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
        return False
    cloaked = ctypes.c_int(0)
    _dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return not cloaked.value


def _intersection(a, b):
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, width) * max(0, height)


def _activate(hwnd):
    """Gives the keyboard focus back to a window (best effort: Windows may refuse)."""
    current = _user32.GetForegroundWindow()
    if not hwnd or current == hwnd or not _user32.IsWindow(hwnd):
        return
    current_thread = _user32.GetWindowThreadProcessId(current, None) if current else 0
    my_thread = _kernel32.GetCurrentThreadId()
    attached = bool(current_thread) and current_thread != my_thread and _user32.AttachThreadInput(
        my_thread, current_thread, True
    )
    try:
        _user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            _user32.AttachThreadInput(my_thread, current_thread, False)


class BrowserWindow:
    """Browser window placed on `area` (the screen where it is shown)."""

    def __init__(self, browser, area):
        self.prefix = f"[{browser.upper()}]"
        self.executable = EXECUTABLES.get(browser, f"{browser}.exe")
        x, y, width, height = area
        self.area = (x, y, x + width, y + height)
        self.hwnd = None
        self._search = float("-inf")
        self._lost_reported = False
        self._image = None
        self._image_rect = None
        self._image_date = float("-inf")

    def _surface_on_area(self, hwnd):
        """Surface of the window on its screen, 0 if it covers too little of it."""
        rect = _rectangle(hwnd)
        surface = _intersection(rect, self.area) if rect else 0
        area_size = (self.area[2] - self.area[0]) * (self.area[3] - self.area[1])
        return surface if surface >= MIN_SCREEN_SHARE * area_size else 0

    def _find(self):
        candidates = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def callback(hwnd, _):
            if _shown(hwnd) and _user32.GetWindowTextLengthW(hwnd):
                surface = self._surface_on_area(hwnd)
                if surface and _executable(_process(hwnd)) == self.executable:
                    candidates.append((surface, hwnd))
            return True

        _user32.EnumWindows(callback, 0)
        return max(candidates)[1] if candidates else None

    def handle(self):
        """The followed window, or None if it is closed or minimized."""
        if self.hwnd and _user32.IsWindow(self.hwnd) and _shown(self.hwnd):
            if self._surface_on_area(self.hwnd):
                return self.hwnd
            # Moved to another screen: like a lost one, it will be searched again.
            print(f"{self.prefix} The window left its screen.")
            self.hwnd = None
            self._lost_reported = False
            self._search = float("-inf")
        if time.monotonic() - self._search < WINDOW_SEARCH_DELAY:
            return None
        self._search = time.monotonic()

        self.hwnd = self._find()
        if self.hwnd:
            length = _user32.GetWindowTextLengthW(self.hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(self.hwnd, title, length + 1)
            print(f"{self.prefix} Followed window: \"{title.value}\" "
                  "(read even if another window goes in front of it).")
            self._lost_reported = False
        elif not self._lost_reported:
            print(f"{self.prefix} Window {self.executable} not found on its screen "
                  "(closed or minimized?): capturing the screen instead.")
            self._lost_reported = True
        return self.hwnd

    def _capture_window(self, hwnd):
        rect = _rectangle(hwnd)
        if not rect:
            return None, None
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        if width <= 0 or height <= 0:
            return None, None

        window_dc = _user32.GetWindowDC(hwnd)
        memory_dc = _gdi32.CreateCompatibleDC(window_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(window_dc, width, height)
        previous = _gdi32.SelectObject(memory_dc, bitmap)
        try:
            if not _user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
                return None, None
            header = _BitmapHeader()
            header.biSize = ctypes.sizeof(header)
            header.biWidth, header.biHeight = width, -height
            header.biPlanes, header.biBitCount = 1, 32
            buffer = ctypes.create_string_buffer(width * height * 4)
            _gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
        finally:
            _gdi32.SelectObject(memory_dc, previous)
            _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(memory_dc)
            _user32.ReleaseDC(hwnd, window_dc)

        image = Image.frombuffer(
            "RGBA", (width, height), buffer, "raw", "BGRA", 0, 1
        ).convert("RGB")
        # All-black image: the browser drew nothing, the screen will do better.
        if max(maxi for _, maxi in image.getextrema()) < 8:
            return None, None
        return image, rect

    def capture(self, region):
        """Region (x, y, width, height) of the screen read in the window, or None."""
        hwnd = self.handle()
        if not hwnd:
            return None
        if time.monotonic() - self._image_date > WINDOW_CACHE_DURATION:
            self._image, self._image_rect = self._capture_window(hwnd)
            self._image_date = time.monotonic()
        if self._image is None:
            return None

        x, y, width, height = region
        result = Image.new("RGB", (width, height))
        result.paste(self._image, (self._image_rect[0] - x, self._image_rect[1] - y))
        return result

    def under_cursor(self, position):
        """True if a click at this position really lands on the browser."""
        hwnd = self.handle()
        if not hwnd:
            return True  # unknown window: previous behavior, without any check
        below = _user32.WindowFromPoint(wt.POINT(*position))
        root = _user32.GetAncestor(below, GA_ROOT) if below else None
        return bool(root) and _process(root) == _process(hwnd)

    def _covered(self, hwnd):
        """True if a window shown above it overlaps the browser."""
        rect = _rectangle(hwnd)
        above = _user32.GetWindow(hwnd, GW_HWNDPREV)
        while above:
            if (
                _shown(above)
                and not _user32.GetWindowLongW(above, GWL_EXSTYLE) & WS_EX_TRANSPARENT
            ):
                other = _rectangle(above)
                if other and _intersection(rect, other):
                    return True
            above = _user32.GetWindow(above, GW_HWNDPREV)
        return False

    @contextmanager
    def foreground(self):
        """
        Brings the browser in front of the other windows during the action, then
        puts back the window order, the keyboard focus and the cursor as before.
        Even when visible, the browser takes the focus on click: everything is
        therefore put back as soon as another window had the focus, hidden or not.
        """
        hwnd = self.handle()
        if not hwnd:
            yield
            return

        focus = _user32.GetForegroundWindow()
        covered = self._covered(hwnd)
        if not covered and focus and _process(focus) == _process(hwnd):
            yield  # the browser already has the focus: nothing to put back
            return

        on_top = _user32.GetWindow(hwnd, GW_HWNDPREV)
        cursor = pyautogui.position()
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if covered:
            print(f"{self.prefix} Window hidden: brought to the front for the time of the action.")
            _user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            _user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            time.sleep(0.3)  # time for the screen to redraw
        try:
            yield
        finally:
            if on_top and _user32.IsWindow(on_top):
                _user32.SetWindowPos(hwnd, on_top, 0, 0, 0, 0, flags)
            _activate(focus)
            pyautogui.moveTo(*cursor, duration=0.3, tween=pyautogui.easeInOutQuad)
            print(f"{self.prefix} Windows put back as before.")


_window = None


def follow_window(browser, area):
    """Turns on direct reading of the browser window for this script."""
    global _window
    _window = BrowserWindow(browser, area)
    _window.handle()
    return _window


@contextmanager
def browser_in_front():
    if _window is None:
        yield
    else:
        with _window.foreground():
            yield


def screen_off(area):
    """True if the whole screen is black (screen off, unplugged, PC locked)."""
    try:
        image = capture_area(area)
    except Exception:
        return True
    gray = ImageOps.grayscale(image).reduce(8)
    stat = ImageStat.Stat(gray)
    return stat.stddev[0] < 2 and stat.mean[0] < 20


# ============================================================
# NORMALIZATION
# ============================================================
def normalize_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def otsu_threshold(gray_image):
    """Optimal binarization threshold (Otsu's method) computed on the histogram."""
    histogram = gray_image.histogram()
    total = sum(histogram)
    total_sum = sum(i * n for i, n in enumerate(histogram))

    background_sum = background_weight = 0
    best_threshold, best_variance = 127, -1.0

    for i, n in enumerate(histogram):
        background_weight += n
        if background_weight == 0:
            continue
        text_weight = total - background_weight
        if text_weight == 0:
            break
        background_sum += i * n
        background_mean = background_sum / background_weight
        text_mean = (total_sum - background_sum) / text_weight
        variance = background_weight * text_weight * (background_mean - text_mean) ** 2
        if variance > best_variance:
            best_variance, best_threshold = variance, i

    return best_threshold


# ============================================================
# GLYPHS
# ============================================================
def split_glyphs(image, hardening=0, with_position=False, with_boxes=False):
    """
    Cuts the counter text into glyphs (boolean matrices).
    Returns None if the cut is not clean.

    hardening: threshold stricter than Otsu's, to erase the half-tone
    pixels that stick two neighboring glyphs together.
    with_position: also returns the frame of the text (x0, x1, y0, y1).
    with_boxes: also returns the frame of each glyph (x0, x1, y0, y1).
    """
    gray = ImageOps.grayscale(image)
    width, height = gray.size
    threshold = otsu_threshold(gray)
    pixels = gray.load()

    light = sum(gray.histogram()[threshold + 1:])
    light_text = light < width * height / 2

    if light_text:
        text_threshold = min(254, threshold + hardening)
        mask = [
            [pixels[x, y] > text_threshold for x in range(width)]
            for y in range(height)
        ]
    else:
        text_threshold = max(1, threshold - hardening)
        mask = [
            [pixels[x, y] <= text_threshold for x in range(width)]
            for y in range(height)
        ]
    columns = [sum(mask[y][x] for y in range(height)) for x in range(width)]

    blocks = []
    x = 0
    while x < width:
        if columns[x]:
            start = x
            while x < width and columns[x]:
                x += 1
            blocks.append((start, x))
        else:
            x += 1

    groups = []
    for block in blocks:
        if groups and block[0] - groups[-1][-1][1] <= MAX_GLYPH_GAP:
            groups[-1].append(block)
        else:
            groups.append([block])

    if not groups:
        return None

    # The text is the group with the most glyphs.
    group = max(groups, key=lambda g: (len(g), g[-1][1] - g[0][0]))
    if not 3 <= len(group) <= 5:
        return None

    widths = sorted(end - start for start, end in group)
    median = widths[len(widths) // 2]

    # Two glyphs stuck together (anti-aliasing): cut at the emptiest columns.
    cut = []
    for start, end in group:
        count = round((end - start) / (median + 1))
        if (end - start) <= median * 1.6 or count < 2:
            cut.append((start, end))
            continue
        cuts = []
        for i in range(1, count):
            expected = start + (end - start) * i // count
            near = range(max(start + 1, expected - 2), min(end - 1, expected + 3))
            cuts.append(min(near, key=lambda c: columns[c]))
        bounds = [start] + cuts + [end]
        cut.extend(zip(bounds[:-1], bounds[1:]))
    group = cut

    if len(group) not in (4, 5):
        return None
    widths = sorted(end - start for start, end in group)
    if widths[0] < median * 0.5 or widths[-1] > median * 1.6:
        return None

    glyphs = []
    tops, bottoms = [], []
    for start, end in group:
        lines = [y for y in range(height) if any(mask[y][start:end])]
        glyphs.append([mask[y][start:end] for y in range(lines[0], lines[-1] + 1)])
        tops.append(lines[0])
        bottoms.append(lines[-1] + 1)

    if with_boxes:
        return glyphs, [(start, end, top, bottom) for (start, end), top, bottom in zip(group, tops, bottoms)]
    if with_position:
        return glyphs, (group[0][0], group[-1][1], min(tops), max(bottoms))
    return glyphs


def is_slash(glyph):
    """True if the glyph is shaped like a "/" (top-right and bottom-left filled)."""
    height, width = len(glyph), len(glyph[0])
    half_h, half_w = height // 2, width // 2

    def count(y0, y1, x0, x1):
        return sum(glyph[y][x] for y in range(y0, y1) for x in range(x0, x1))

    diagonal = count(0, half_h, half_w, width) + count(half_h, height, 0, half_w)
    other = count(0, half_h, 0, half_w) + count(half_h, height, half_w, width)
    return diagonal > 2 * other


def locate_counter(image, size):
    """
    Looks for "x/10" in a large image by sliding a window the size of the
    counter area over it. Returns the center of the text (in the image)
    or None.
    """
    window_width, window_height = size
    centers = []
    for y in range(0, image.height - window_height + 1, 8):
        for x in range(0, image.width - window_width + 1, 10):
            window = image.crop((x, y, x + window_width, y + window_height))
            if ImageStat.Stat(ImageOps.grayscale(window)).stddev[0] < 3:
                continue
            for hardening in THRESHOLD_HARDENINGS:
                result = split_glyphs(window, hardening, with_position=True)
                if result is None:
                    continue
                glyphs, (x0, x1, y0, y1) = result
                if is_slash(glyphs[-3]):
                    centers.append((x + (x0 + x1) / 2, y + (y0 + y1) / 2))
                break

    if not centers:
        return None
    xs = sorted(c[0] for c in centers)
    ys = sorted(c[1] for c in centers)
    return xs[len(xs) // 2], ys[len(ys) // 2]


def _center(pixels):
    """Gray levels centered and normed: their dot product is a correlation."""
    mean = sum(pixels) / len(pixels)
    centered = [p - mean for p in pixels]
    norm = sum(c * c for c in centered) ** 0.5 or 1
    return [c / norm for c in centered]


def similarity(gray, box_a, box_b, width, top, bottom):
    """
    Likeness (-1 to 1) of two glyphs: correlation of their gray levels, in
    windows of the same size centered on each one, keeping the best shift
    within ±1 pixel (the same character is not drawn pixel for pixel the same
    at two positions of the screen). The half-tones of the anti-aliasing
    count: much steadier than in black and white.
    """
    def values(box, dx=0, dy=0):
        left = (box[0] + box[1]) // 2 - width // 2 + dx
        return _center(gray.crop((left, top + dy, left + width, bottom + dy)).tobytes())

    a = values(box_a)
    return max(
        sum(x * y for x, y in zip(a, values(box_b, dx, dy)))
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )


def symmetry(gray, box):
    """Likeness (-1 to 1) of a glyph with itself turned by 180°."""
    left, right, top, bottom = box

    def score(dx, dy):
        window = gray.crop((left - 1, top - 1, right + 1 + dx, bottom + 1 + dy))
        turned = _center(window.rotate(180).tobytes())
        return sum(x * y for x, y in zip(_center(window.tobytes()), turned))

    return max(score(dx, dy) for dx in (0, 1) for dy in (0, 1))


def analyze_glyphs(image, capacity=None, reading=""):
    """
    Returns (full, description, numerator).

    full is True/False if the glyphs allow a conclusion, None if the OCR is
    needed. Full: the number before the "/" has the same glyphs as the one
    after (10/10, 25/25), whatever the capacity. Only one of the two digits
    clearly different: not full, without OCR (20/25 differs only by the 2nd
    digit, 15/25 only by the 1st). If the glyphs say full but the quick OCR
    reading reads another number, the full OCR decides.

    Numerator (text, None if a doubt remains): each digit is compared with
    those of the denominator ("10", "20"), which give their shape in the
    font: the slashed zero, which the OCR reads "6", is recognized this way.
    The other digits come from the quick OCR reading (reading, e.g. "13/20");
    a "0" or a "6" there is checked by its symmetry.
    """
    gray = ImageOps.autocontrast(ImageOps.grayscale(image))
    if capacity:
        digits = str(capacity)
    else:
        m = re.search(r"/(\d{2})", reading)
        digits = number_read(m[1]) if m else ""
    read = reading.split("/")[0] if "/" in reading else ""

    description = "unreadable glyphs"
    for hardening in THRESHOLD_HARDENINGS:
        result = split_glyphs(image, hardening, with_boxes=True)
        if result is None:
            continue
        glyphs, boxes = result
        slash = len(glyphs) - 3
        if not is_slash(glyphs[slash]):
            continue
        width = max(end - start for start, end, _, _ in boxes) + 2
        top, bottom = min(b[2] for b in boxes) - 1, max(b[3] for b in boxes) + 1

        def sim(i, j):
            return similarity(gray, boxes[i], boxes[j], width, top, bottom)

        # Each digit before the "/": the denominator one it is identical to,
        # else the OCR one (if it is not a digit ruled out).
        numerator = ""
        for k in range(slash):
            likenesses = [sim(k, slash + 1 + j) for j in range(2)]
            identical = [j for j, s in enumerate(likenesses) if s >= SAME_SIMILARITY]
            if identical and len(digits) == 2:
                numerator += digits[identical[0]]
            elif len(read) == slash and not any(
                    len(digits) == 2 and read[k] == digits[j] and s < DIFFERENT_SIMILARITY
                    for j, s in enumerate(likenesses)):
                if read[k] in "06":
                    numerator += "0" if symmetry(gray, boxes[k]) >= ZERO_SYMMETRY else "6"
                else:
                    numerator += read[k]
            else:
                numerator = None
                break

        if slash == 1:
            # A single digit before the "/": never full (2-digit capacity).
            return False, f"4 glyphs (x/{digits or '?'})", numerator

        sim_1, sim_0 = sim(0, 3), sim(1, 4)
        description = f"5 glyphs, similarities {sim_1:.2f}/{sim_0:.2f}"
        if sim_1 < DIFFERENT_SIMILARITY or sim_0 < DIFFERENT_SIMILARITY:
            return False, description, numerator
        read_elsewhere = re.fullmatch(r"\d{2}/\d{2}", reading) and not full_vote(reading)
        if sim_1 >= SAME_SIMILARITY and sim_0 >= SAME_SIMILARITY and not read_elsewhere:
            return True, description, digits or None
        return None, description, numerator

    return None, description, None


# ============================================================
# COUNTER DETECTION
# ============================================================
class CounterDetector:
    """
    Reads the counter of a browser.

    - Glyphs: 5 glyphs with the number repeated = full (10/10, 20/20),
      4 glyphs = a single digit before the "/", not full.
      Instant and not fooled by the slashed zero of the font.
    - OCR fallback if the cut is not clean: upscaling, Otsu threshold,
      black text on white, white margin, several passes with votes.
    - Cache: if the image has not changed, the previous result is reused
      without running the OCR again.
    - Stability: full is only confirmed after N full readings in a row.
    - Capacity: 10, 20 with a subscription… 0 = read on the counter (denominator
      read again at each change: accounts with or without a subscription).
    """

    def __init__(self, browser, center, size=(100, 45), stable_readings=2,
                 capacity=0):
        self.browser = browser
        # Max capacity of the counter (10, 20…); 0 = read on screen.
        self.capacity = capacity
        self.capacity_read = capacity or None
        # Other capacity read once while it is set: to be confirmed.
        self._capacity_to_confirm = None
        self.prefix = f"[{browser.upper()}]"
        self.expected_center = center
        self.size = size
        self._place(center)
        self.stable_readings = stable_readings
        self.debug_image = DEBUG_DIR / f"debug_{browser}.png"
        self.debug_image_processed = DEBUG_DIR / f"debug_{browser}_processed.png"
        self.debug_image_search = DEBUG_DIR / f"debug_{browser}_search.png"

        self._signature = None
        self._last_result = (False, "?", "")
        self._shown_value = None
        self._last_display = 0.0
        self._unreadable = 0
        self._last_recenter = 0.0
        self._last_not_found_message = -1e9
        self.in_a_row = 0
        self.readable = True
        # Area of the whole browser screen, to recognize a screen that is off
        # (filled in by main_loop).
        self.screen_area = None
        self.screen_off = False

    def _place(self, center):
        width, height = self.size
        self.region = (
            int(center[0]) - width // 2,
            int(center[1]) - height // 2,
            width,
            height,
        )

    def reset(self):
        """To call after an opening: the counter must be read from scratch."""
        self._signature = None
        self.in_a_row = 0

    def counter_visible(self):
        """True if the counter is at its place: still on the home page."""
        image = capture_area(self.region)
        for hardening in THRESHOLD_HARDENINGS:
            glyphs = split_glyphs(image, hardening)
            if glyphs is not None and is_slash(glyphs[-3]):
                return True
        return False

    def change_capacity(self, capacity):
        """Capacity of the logged-in account (0 = read on screen): counter read from scratch."""
        if capacity != self.capacity:
            self.capacity = capacity
            self.capacity_read = capacity or None
            self._capacity_to_confirm = None
            self.reset()

    def recenter(self):
        """
        Looks for the counter ("x/10") in a wide band around the expected
        position, and centers the area on it again. The counter shifts when a
        badge appears or disappears next to it.
        """
        self._last_recenter = time.monotonic()
        cx, cy = self.expected_center
        band = (
            cx - SEARCH_WIDTH // 2,
            cy - SEARCH_HEIGHT // 2,
            SEARCH_WIDTH,
            SEARCH_HEIGHT,
        )
        image = capture_area(band)
        image.save(self.debug_image_search)

        center = locate_counter(image, self.size)
        if center is None:
            # Message limited to one every few minutes.
            if time.monotonic() - self._last_not_found_message >= NOT_FOUND_REMINDER:
                print(
                    f"{self.prefix} Counter not found around {self.expected_center} "
                    f"(image: {self.debug_image_search}). New try every "
                    f"{DELAY_BETWEEN_RECENTERS} s."
                )
                self._last_not_found_message = time.monotonic()
            return False

        x, y = band[0] + center[0], band[1] + center[1]
        self._place((x, y))
        self._signature = None
        print(
            f"{self.prefix} Counter found again at ({int(x)}, {int(y)}): "
            f"area re-centered on {self.region}."
        )
        return True

    @staticmethod
    def _crop(image):
        """
        Keeps the counter text, without the colored indicator on the left nor
        the line on the right, which the OCR read as a digit ("16/206").
        """
        for hardening in THRESHOLD_HARDENINGS:
            result = split_glyphs(image, hardening, with_position=True)
            if result is not None:
                x0, x1, y0, y1 = result[1]
                margin = 4
                return image.crop((max(0, x0 - margin), max(0, y0 - margin),
                                   min(image.width, x1 + margin), min(image.height, y1 + margin)))
        return image

    def _prepare(self, image):
        gray = ImageOps.grayscale(self._crop(image))
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = gray.resize(
            (gray.width * 5, gray.height * 5), Image.Resampling.LANCZOS
        )
        gray = ImageEnhance.Sharpness(gray).enhance(2.0)

        threshold = otsu_threshold(gray)
        light = sum(gray.histogram()[threshold + 1:])
        # The text is the minority part: we want it black on a white background.
        if light < gray.width * gray.height / 2:
            gray = ImageOps.invert(gray)
            threshold = 255 - threshold
        return gray, threshold

    def _quick_reading(self, image):
        """A single OCR pass, only for display."""
        gray, threshold = self._prepare(image)
        binary = ImageOps.expand(
            gray.point(lambda p: 255 if p > threshold else 0), border=30, fill=255
        )
        binary.save(self.debug_image_processed)
        try:
            text = pytesseract.image_to_string(
                binary, config=f"--oem 3 --psm 7 {OCR_CONFIG}"
            )
        except Exception:
            return "?"
        return re.sub(r"[^0-9/]", "", text)

    def _read_ocr(self, image):
        gray, base_threshold = self._prepare(image)

        full_score = 0.0
        other_votes = {}
        readings = []
        first_binary = None

        for offset in THRESHOLD_OFFSETS:
            threshold = max(10, min(245, base_threshold + offset))
            binary = gray.point(lambda p, s=threshold: 255 if p > s else 0)
            binary = ImageOps.expand(binary, border=30, fill=255)
            if first_binary is None:
                first_binary = binary

            for psm in OCR_PSM:
                try:
                    text = pytesseract.image_to_string(
                        binary, config=f"--oem 3 --psm {psm} {OCR_CONFIG}"
                    )
                except Exception as error:
                    print(f"{self.prefix} [OCR ERROR] {error}")
                    continue

                compact = re.sub(r"[^0-9/]", "", text)
                readings.append(compact or "∅")

                vote = full_vote(compact, self.capacity and self.capacity_read)
                if vote:
                    full_score += vote
                elif re.fullmatch(r"\d{1,2}/\d{1,2}", compact):
                    other_votes[compact] = other_votes.get(compact, 0) + 1

                if VERBOSE_OCR:
                    print(
                        f"{self.prefix} [OCR threshold={threshold} psm={psm}] "
                        f"{text.strip()!r} -> {compact!r}"
                    )

                best_other = max(other_votes.values(), default=0)
                if full_score >= DECISIVE_SCORE or best_other >= DECISIVE_SCORE:
                    break
            else:
                continue
            break

        if first_binary is not None:
            first_binary.save(self.debug_image_processed)

        best_other = max(other_votes.values(), default=0)
        full = full_score >= MIN_SCORE and full_score > best_other
        return full, " | ".join(readings)

    def read(self):
        """Returns True when the counter is read full (10/10, 20/20) in a stable way."""
        if (
            self._unreadable >= UNREADABLE_BEFORE_RECENTER
            and time.monotonic() - self._last_recenter >= DELAY_BETWEEN_RECENTERS
        ):
            try:
                self.recenter()
            except Exception as error:
                print(f"{self.prefix} [RECENTER ERROR] {error}")

        try:
            image = capture_area(self.region)
        except Exception as error:
            print(f"{self.prefix} [CAPTURE ERROR] {error}")
            self.in_a_row = 0
            report_counter(self.browser, False, f"capture error: {error}")
            return False

        signature = hashlib.md5(image.tobytes()).digest()

        if signature == self._signature:
            raw_full, value, detail = self._last_result
        else:
            image.save(self.debug_image)
            raw_full, value, detail = self._analyze(image)
            self._signature = signature
            self._last_result = (raw_full, value, detail)

        # Unreadable counter: either it moved, or the whole screen is black
        # (screen off, PC locked). In that case we wait without trying
        # anything, and say it only once.
        off = (
            value == "?"
            and self.screen_area is not None
            and screen_off(self.screen_area)
        )
        if off != self.screen_off:
            if off:
                print(
                    f"{self.prefix} Screen off or black: nothing to read. "
                    "Paused, resumes automatically when it comes back on."
                )
            else:
                print(f"{self.prefix} Screen visible again: reading resumes.")
                self._signature = None
            self.screen_off = off

        self.readable = value != "?"
        if not off:
            self._unreadable = 0 if self.readable else self._unreadable + 1
        self.in_a_row = self.in_a_row + 1 if raw_full else 0
        full = self.in_a_row >= self.stable_readings

        # Prints each change of value, and a regular reminder otherwise.
        now = time.monotonic()
        if not off and (
            value != self._shown_value
            or now - self._last_display >= PERIODIC_DISPLAY
        ):
            print(f"{self.prefix} Counter: {value}  ({detail})")
            self._shown_value = value
            self._last_display = now

        report_counter(self.browser, full)
        return full

    def _learn_capacity(self, read):
        """
        Capacity read on screen: "3/20" -> 20. Always checked: if it differs
        from the one already known, set or read (two readings in a row, so
        as not to follow a wrong reading), the script adapts to the counter.
        """
        m = re.search(r"/(\d{2})", read)
        if not m:
            return
        capacity = int(number_read(m[1]))
        if capacity not in POSSIBLE_CAPACITIES or capacity == self.capacity_read:
            self._capacity_to_confirm = None
            return
        if self.capacity_read and self._capacity_to_confirm != capacity:
            self._capacity_to_confirm = capacity
            return
        if self.capacity:
            print(f"{self.prefix} The counter goes up to {capacity}, not {self.capacity_read} "
                  f"as set: the script adapts ({capacity} boosters).")
        else:
            print(f"{self.prefix} Counter capacity: {capacity} boosters.")
        self._capacity_to_confirm = None
        self.capacity_read = capacity

    def _analyze(self, image):
        """Returns (full, value to display, detail)."""
        if ImageStat.Stat(ImageOps.grayscale(image)).stddev[0] < 3:
            # Uniform image (black screen, tab loading…): nothing to read.
            return False, "?", UNIFORM_DETAIL

        # Capacity read again at each change of image (an account with or
        # without a subscription may be logged in), even when it is set.
        read = self._quick_reading(image)
        self._learn_capacity(read)
        total = self.capacity_read or "?"

        full, detail, numerator = analyze_glyphs(image, self.capacity_read, read)
        if full:
            return True, f"{total}/{total}", detail
        if full is False:
            # Numerator read by OCR when the glyphs did not recognize it.
            if numerator is None:
                if read is None:
                    read = self._quick_reading(image)
                numerator = read.split("/")[0] if "/" in read else "?"
            return False, f"{numerator}/{total}", detail

        full, readings = self._read_ocr(image)
        if full:
            return True, f"{total}/{total}", f"{detail}, OCR: {readings}"
        valid = [r for r in readings.split(" | ") if re.fullmatch(r"\d{1,2}/\d{1,2}", r)]
        if valid:
            self._learn_capacity(valid[0])
            # Reading whose denominator is exact: its numerator too, more
            # surely (the slashed zero read "6" affects both).
            exact = [r for r in valid if r.split("/")[1] == str(self.capacity_read)]
            valid = exact or valid
            numerator = analyze_glyphs(image, self.capacity_read, valid[0])[2]
            numerator = numerator or valid[0].split("/")[0]
        value = f"{numerator}/{self.capacity_read or '?'}" if valid else "?"
        return False, value, f"{detail}, OCR: {readings}"


# ============================================================
# PRESENCE POPUP
# ============================================================
# Title of the game popup « Tu es toujours là ? » ("Are you still there?").
POPUP_TITLE_WORDS = ("toujours", "encore", "still")


def distance(a, b):
    """Number of letters to change to go from a to b (Levenshtein)."""
    previous = list(range(len(b) + 1))
    for i, letter_a in enumerate(a, 1):
        current = [i]
        for j, letter_b in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (letter_a != letter_b),
            ))
        previous = current
    return previous[-1]


def is_red(pixel):
    """Color of the « Je suis là » ("I'm here") button (orange-red, even darkened)."""
    r, g, b = pixel[:3]
    # Bright: (255, 85, 51); darkened by the popup overlay: (102, 31, 18).
    return r >= 70 and r > 2 * g and r > 2 * b


def red_blocks_mask(image):
    """
    Mask (half resolution) of solid red blocks of at least ~14 x 14 px,
    like the « Je suis là » button. Thin red borders disappear.
    Computed with Pillow operations: a few milliseconds.
    """
    small = image.reduce(2)
    r, g, b = small.split()

    def double(channel):
        return channel.point(lambda v: min(255, 2 * v))

    def positive(channel):
        return channel.point(lambda v: 255 if v > 0 else 0)

    red = r.point(lambda v: 255 if v >= 70 else 0)
    red = ImageChops.multiply(red, positive(ImageChops.subtract(r, double(g))))
    red = ImageChops.multiply(red, positive(ImageChops.subtract(r, double(b))))
    return red.filter(ImageFilter.MinFilter(7))


class PopupWatcher:
    """
    Looks for the « Tu es toujours là ? » ("Are you still there?") popup on the
    whole browser screen (it may be centered or at the bottom right) and
    clicks its button, where it really is.

    OCR of the whole screen is slow: it only runs every `interval`
    seconds… or right away when a new solid red block (the button)
    appears, which a quick test checks at each pass.
    """

    def __init__(self, browser, area, interval=10):
        self.browser = browser
        self.prefix = f"[{browser.upper()}]"
        self.area = area
        self.interval = interval
        self.debug_image = DEBUG_DIR / f"debug_popup_{browser}.png"
        self._last = 0.0
        self._red_signature = None

    def _check_again_in(self, seconds):
        self._last = time.monotonic() - self.interval + seconds

    def _locate(self, image):
        """Returns (x, y) of the button in the image, None if no popup."""
        gray = ImageOps.autocontrast(ImageOps.grayscale(image))
        data = pytesseract.image_to_data(
            gray, config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT
        )
        words = [
            (
                normalize_text(text),
                data["left"][i],
                data["top"][i],
                data["width"][i],
                data["height"][i],
            )
            for i, text in enumerate(data["text"])
            if normalize_text(text)
        ]

        # Title: « toujours », one misread letter tolerated. « Tu es » before it
        # is not required: the OCR sometimes sticks it into « Tes ».
        def neighbor(left, right):
            return (
                0 <= right[1] - (left[1] + left[3]) <= 40
                and abs(right[2] - left[2]) <= max(left[4], right[4])
            )

        titles = [
            word for word in words
            if any(distance(word[0], title) <= 1 for title in POPUP_TITLE_WORDS)
        ]
        if not titles:
            return None

        # The text is not enough (it may show elsewhere, in another
        # window): the solid red button right below it is needed too.
        for _, tx, ty, tw, th in titles:
            position = self._red_button(image, tx, ty, tw, th)
            if position:
                return position

        # « toujours » alone is a common word: report it only if it really
        # looks like the title (« tu es » / « tes » / "you are" just before).
        for title in titles:
            if any(w[0] in ("es", "tu", "tes", "tues", "you", "are") and neighbor(w, title)
                   for w in words):
                return "not_found"
        return None

    @staticmethod
    def _red_button(image, tx, ty, tw, th):
        """Center of the red block (« Je suis là » button) below the title, or None."""
        width, height = image.size
        pixels = image.load()
        x_min, x_max = max(0, tx - 250), min(width, tx + tw + 250)
        red_lines = []
        for y in range(ty + th, min(height, ty + th + 150)):
            xs = [x for x in range(x_min, x_max) if is_red(pixels[x, y])]
            if len(xs) >= 30:
                red_lines.append((y, xs))

        # The button is the first block of at least 10 red lines in a row
        # (the popup borders are only one or two lines).
        block = []
        for y, xs in red_lines:
            if block and y != block[-1][0] + 1:
                if len(block) >= 10:
                    break
                block = []
            block.append((y, xs))
        if 10 <= len(block) <= 80:
            ys = [y for y, _ in block]
            xs = [x for _, line in block for x in line]
            return sum(xs) // len(xs), (ys[0] + ys[-1]) // 2
        return None

    def check(self, urgent=False):
        """urgent=True shortens the interval (unreadable counter: popup likely)."""
        try:
            image = capture_area(self.area)
            mask = red_blocks_mask(image)
        except Exception as error:
            print(f"{self.prefix} [POPUP ERROR] {error}")
            return False

        # New red block on screen (the popup button?): OCR right away.
        signature = hashlib.md5(mask.tobytes()).digest()
        new_red = (
            signature != self._red_signature and mask.getbbox() is not None
        )
        self._red_signature = signature

        delay = min(4, self.interval) if urgent else self.interval
        if not new_red and time.monotonic() - self._last < delay:
            return False
        self._last = time.monotonic()

        try:
            position = self._locate(image)
        except Exception as error:
            print(f"{self.prefix} [POPUP ERROR] {error}")
            return False

        if position is None:
            return False

        image.save(self.debug_image)
        if position == "not_found":
            print(
                f"{self.prefix} Popup text seen, but no red button "
                f"below it: ignored. Image: {self.debug_image}"
            )
            return False

        target = (self.area[0] + position[0], self.area[1] + position[1])

        # The click uses the mouse: the lock is needed, but without waiting
        # for priority (it is very short).
        if not request_turn(self.browser, priority=True, reason="popup"):
            self._check_again_in(2)
            return False

        try:
            print(f"{self.prefix} Presence popup detected.")
            with browser_in_front():
                click(self.browser, target, "« Je suis là » button", wait=1.5)
        finally:
            end_turn(self.browser, hand_over=False)
        # Checks again quickly that the popup is really gone.
        self._check_again_in(3)
        return True


# ============================================================
# CLICKS
# ============================================================
def click(browser, position, description="", wait=0.5, double=False):
    """Glides the cursor to the target (no teleporting), then clicks."""
    x, y = position
    action = "Double-click" if double else "Click"
    if _window is not None and not _window.under_cursor(position):
        print(f"[{browser.upper()}] {action} cancelled: {description or position} "
              f"-> ({x}, {y}), another window is in front of the browser.")
        time.sleep(wait)
        return
    print(f"[{browser.upper()}] {action}: {description or position} -> ({x}, {y})")

    duration = max(MIN_MOVE_DURATION, random.uniform(*MOVE_DURATION))
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    time.sleep(PAUSE_BEFORE_CLICK)

    if double:
        pyautogui.doubleClick(interval=0.12)
    else:
        pyautogui.click()
    time.sleep(wait)


# One mouse wheel notch, in Windows units (pyautogui.scroll sends these units).
WHEEL_NOTCH = 120
# Notches sent upwards to be sure to start again from the top of the page.
PAGE_RISE = 60


def scroll(browser, position, notches, description=""):
    """
    Goes all the way up the page, then scrolls down `notches` wheel notches,
    mouse on `position`: the page always ends up at the same place.
    """
    x, y = position
    if _window is not None and not _window.under_cursor(position):
        print(f"[{browser.upper()}] Scroll cancelled: {description or position}, "
              "another window is in front of the browser.")
        return
    print(f"[{browser.upper()}] Scroll: {notches} notch(es) down "
          f"for {description or position}")

    duration = max(MIN_MOVE_DURATION, random.uniform(*MOVE_DURATION))
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    for _ in range(PAGE_RISE // 10):
        pyautogui.scroll(10 * WHEEL_NOTCH)
    time.sleep(1)
    for _ in range(notches):
        pyautogui.scroll(-WHEEL_NOTCH)
        time.sleep(0.1)
    # Scrolling is animated: wait for it to finish before clicking.
    time.sleep(1)


# ============================================================
# MAIN LOOP
# ============================================================
# Boosters opened by the "×10" button of the game, by the "×5" for the rest
# of a counter at 15 or 25, and pause between two openings in a row.
BOOSTERS_PER_OPENING = 10
BOOSTERS_LEFT = 5
PAUSE_BETWEEN_OPENINGS = 4


def batches_to_open(capacity, button_5):
    """Boosters of each opening to empty the counter: 25 -> [10, 10, 5]."""
    batches = [BOOSTERS_PER_OPENING] * (capacity // BOOSTERS_PER_OPENING)
    if button_5 and capacity % BOOSTERS_PER_OPENING >= BOOSTERS_LEFT:
        batches.append(BOOSTERS_LEFT)
    return batches or [BOOSTERS_PER_OPENING]


def main_loop(browser, detector, popup, sequence, interval=2,
              pause_after_opening=5, each_pass=None, button_5=False):
    """
    Continuous detection; opening only when the lock is obtained.
    Waiting for one's turn never blocks the reading of the counter.
    `each_pass`: function called at each pass (e.g. following the account).
    `button_5`: true if the "×5" button is placed. `sequence` receives the
    number of boosters to open.
    """
    from coordination import release_at_startup

    prefix = f"[{browser.upper()}]"
    release_at_startup(browser)
    detector.screen_area = popup.area
    follow_window(browser, popup.area)

    try:
        print(f"{prefix} Tesseract: {pytesseract.get_tesseract_version()}")
    except Exception as error:
        print(f"[TESSERACT ERROR] {error}")
        return

    print(f"{prefix} Counter area: {detector.region}")
    print(f"{prefix} Diagnostic: {detector.debug_image}")
    print(f"{prefix} Ctrl+C to stop (or mouse in the top-left corner).")

    try:
        while True:
            try:
                if not detector.screen_off:
                    popup.check(urgent=not detector.readable)
                    if each_pass:
                        each_pass()

                if detector.read() and request_turn(browser):
                    print(f"{prefix} Full counter confirmed and mouse free: opening.")
                    # The game opens 10 boosters at a time: several openings
                    # in a row to empty the counter (25: 10, 10, then 5).
                    capacity = detector.capacity_read or 0
                    batches = batches_to_open(capacity, button_5)
                    if capacity % BOOSTERS_PER_OPENING and not button_5:
                        print(f"{prefix} ×5 button not placed (menu 3 of the assistant): "
                              "the 5 boosters left stay on the counter.")
                    try:
                        with browser_in_front():
                            for number, batch in enumerate(batches, 1):
                                if number > 1:
                                    time.sleep(PAUSE_BETWEEN_OPENINGS)
                                    popup.check(urgent=True)
                                    print(f"{prefix} Counter at {capacity}: "
                                          f"opening {number}/{len(batches)} ({batch} boosters).")
                                sequence(batch)
                    finally:
                        end_turn(browser)
                    detector.reset()
                    time.sleep(pause_after_opening)
                    continue

            except pyautogui.FailSafeException:
                raise
            except Exception as error:
                print(f"{prefix} [ERROR] {type(error).__name__}: {error}")
                time.sleep(5)

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{prefix} Stop requested.")
    except pyautogui.FailSafeException:
        print(f"\n{prefix} PyAutoGUI safety stop triggered.")
    finally:
        end_turn(browser, hand_over=False)
        print(f"{prefix} Script stopped.")
