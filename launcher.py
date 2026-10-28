"""
Shared by configure.py and start.py: language choice (remembered), then the
program of that language, in its folder (francais/ or english/).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGUAGE_FILE = ROOT / ".language"

# code: (name shown, folder, assistant)
LANGUAGES = {
    "fr": ("Français", "francais", "configurer_positions.py"),
    "en": ("English", "english", "configure_positions.py"),
}
ANSWERS = {"1": "fr", "fr": "fr", "f": "fr", "2": "en", "en": "en", "e": "en"}

START_HINT = {
    "fr": "Pour lancer le programme :  python start.py\n"
          "(un 2e navigateur, ex. brave :  python start.py brave)",
    "en": "To start the program:  python start.py\n"
          "(a 2nd browser, e.g. brave:  python start.py brave)",
}


def saved_language():
    try:
        code = LANGUAGE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return code if code in LANGUAGES else None


def choose_language():
    """Asks the language; Enter = the last one chosen. Remembers the answer."""
    saved = saved_language()
    print("\nLangue / Language :")
    for number, code in enumerate(LANGUAGES, 1):
        default = "   <- Entrée / Enter" if code == saved else ""
        print(f"  {number}  {LANGUAGES[code][0]}{default}")
    while True:
        answer = input("> ").strip().lower()
        if not answer and saved:
            return saved
        code = ANSWERS.get(answer)
        if code:
            LANGUAGE_FILE.write_text(code, encoding="utf-8")
            return code
        print("Tape 1 ou 2 / Type 1 or 2")


def run(code, script, arguments=()):
    """Runs a script of the language folder and waits for its end."""
    folder = ROOT / LANGUAGES[code][1]
    if not (folder / script).exists():
        print({"fr": f"Introuvable : {LANGUAGES[code][1]}\\{script}",
               "en": f"Not found: {LANGUAGES[code][1]}\\{script}"}[code])
        return 1
    process = subprocess.Popen([sys.executable, script, *arguments], cwd=folder)
    while True:
        try:
            return process.wait()
        except KeyboardInterrupt:
            # Ctrl+C also reaches the script: let it stop cleanly (it gives
            # the mouse back to the other scripts).
            continue
