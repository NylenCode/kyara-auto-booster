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
- **Python 3.10+**
- **Tesseract OCR**, installed in its default folder (`C:\Program Files\Tesseract-OCR`)

## Install

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

## Quick start

1. Open Kyara in your browser, on the boosters page.
2. Open a terminal in the `english/` folder and run the assistant:

   ```bash
   python configure_positions.py
   ```

   Choose your packs, then place each position with the mouse and the **G** key.
3. Start the program:

   ```bash
   python kyara_booster.py
   ```

To stop: `Ctrl + C`, or move the mouse to the top-left corner of the screen.

The full step-by-step guide (install, assistant menus, accounts, two browsers, troubleshooting) is in **[english/README.txt](english/README.txt)**.

## Folders

| Folder | Content |
|---|---|
| [`english/`](english/) | English version + guide `README.txt` |
| [`francais/`](francais/) | French version + guide `LISEZ-MOI.txt` |

Both versions work the same way; pick the one in your language.

## Disclaimer

This is an unofficial fan tool, not affiliated with Kyara. Automating a game may go against its terms of use: **use it at your own risk**.

## Support

If this program saves you time, you can support me with a small tip on Ko-fi ☕
**[ko-fi.com/nylen9](https://ko-fi.com/nylen9)**
