"""
Choix de la langue, puis l'assistant de configuration.
Language choice, then the setup assistant.

    python configure.py            langue, puis assistant / language, then assistant
    python configure.py reset      les arguments vont à l'assistant / arguments go to the assistant
"""

import sys

from launcher import LANGUAGES, START_HINT, choose_language, run

try:
    code = choose_language()
except (KeyboardInterrupt, EOFError):
    sys.exit(0)

run(code, LANGUAGES[code][2], sys.argv[1:])
print()
print(START_HINT[code])
