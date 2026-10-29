# Kyara Auto Booster

Opens your **Kyara** boosters automatically, as soon as the counter is full.

🇫🇷 **Version française : voir [README.fr.md](README.fr.md) et le dossier [`francais/`](francais/).**

☕ **Like it? Support me with a tip on Ko-fi: [ko-fi.com/nylen9](https://ko-fi.com/nylen9). Thank you!**

---

## What it does

- Watches the booster counter at the top of the page (`3/10`, `7/10`…).
- When it is full (`10/10`, or `20/20` with a subscription), it clicks to open the boosters, then waits again.
- At `20/20` it opens **twice in a row**, because the game button only opens 10 at a time.
- **Reads the counter capacity by itself** (10 or 20) and adapts if it changes.
- **Rotation**: opens your chosen packs in turn (e.g. Isekai, Shonen Mix, Isekai…).
- **Card hunt**: opens a pack until a given card drops, then switches to other packs.
- **Several accounts**: recognizes the logged-in account by its profile picture; each account can have its own packs and its own counter capacity.
- **Several browsers at the same time** (e.g. Opera + Brave): the scripts take turns with the mouse.
- Handles the « Tu es toujours là ? » ("Are you still there?") popup.
- The browser can stay behind other windows; the mouse glides like a real hand.
- **No file to edit by hand**: an assistant (`configure_positions.py`) asks simple questions. You place the mouse on each button and press **G**.

> The game is in French: the program reads the French texts of the game. The program itself (messages, assistant, guide) is fully available in English or French.

## Requirements

- **Windows** (10 or 11)
- **Python 3.10+** and **Tesseract OCR** (in its default folder `C:\Program Files\Tesseract-OCR`): `install.bat` installs them for you.

## Install (once)

1. Download the program: green **Code** button, then **Download ZIP**, and unzip it.
2. Double-click **`install.bat`**. It installs what is missing (Python, the
   Python tools, Tesseract) and keeps what is already there. Windows may ask
   for permission: click **Yes**.

> If Windows shows "Windows protected your PC": click **More info**, then **Run anyway**.

<details>
<summary>By hand, in a terminal</summary>

```bash
winget install -e --id Python.Python.3.13
```

Close and reopen the terminal, then:

```bash
python -m pip install -r requirements.txt
```

```bash
winget install -e --id UB-Mannheim.TesseractOCR
```

</details>

## Quick start

1. Open Kyara in your browser, on the boosters page.
2. Double-click **`configure.bat`** (or `python configure.py` in a terminal).
   Choose your language (**2** = English; it is remembered). The assistant
   opens: choose your packs, then place each position with the mouse and the
   **G** key.
3. Double-click **`run.bat`** to start the program (or `python start.py`).
   A second browser set up in the assistant (e.g. named `brave`): `run.bat brave` in a terminal.

To stop: `Ctrl + C`, or move the mouse to the top-left corner of the screen.

The full step-by-step guide (install, assistant menus, accounts, two browsers, troubleshooting) is in **[english/README.txt](english/README.txt)**.

## Folders

| Folder | Content |
|---|---|
| [`english/`](english/) | English version + guide `README.txt` |
| [`francais/`](francais/) | French version + guide `LISEZ-MOI.txt` |

Both versions work the same way. `configure.py` and `start.py` open the one in
the language you chose; you can also run the scripts directly from their folder.

## Disclaimer

This is an unofficial fan tool, not affiliated with Kyara. Automating a game may go against its terms of use: **use it at your own risk**.

## Support

If this program saves you time, you can support me with a small tip on Ko-fi ☕
**[ko-fi.com/nylen9](https://ko-fi.com/nylen9)**
