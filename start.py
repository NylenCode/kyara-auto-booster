"""
Lance le programme dans la langue choisie avec configure.py.
Starts the program in the language chosen with configure.py.

    python start.py            kyara_booster.py
    python start.py brave      kyara_booster_brave.py (2e navigateur / 2nd browser)
"""

import sys

from launcher import choose_language, run, saved_language

try:
    code = saved_language() or choose_language()
except (KeyboardInterrupt, EOFError):
    sys.exit(0)

script = sys.argv[1] if len(sys.argv) > 1 else "kyara_booster.py"
if not script.endswith(".py"):
    script = f"kyara_booster_{script}.py"
sys.exit(run(code, script))
