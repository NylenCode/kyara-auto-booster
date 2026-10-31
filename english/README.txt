=====================================================================
  KYARA AUTO BOOSTER — USER GUIDE
=====================================================================

WHAT IS IT?
  A small program that opens your Kyara boosters by itself.
  It watches the counter at the top of the page ("3/10", "7/10"…).
  As soon as it is full (10/10, or 20/20 with a subscription), it
  clicks for you to open the boosters, then it waits again.

  You have nothing to write in the files: an "assistant" asks you
  questions and sets everything for you.

  The game is in French: the program reads the French texts of the
  game (the « Tout révéler » button, the « Tu es toujours là ? »
  popup). Nothing to change for that.


CONTENTS
  1. Open the terminal ............ the window where commands are typed
  2. Install (only once) .......... 3 things to install
  3. Set up ....................... the assistant, the first time
  4. Start and stop
  5. The assistant menu, choice by choice
  6. Two browsers at the same time
  7. A problem?
  8. For the curious: setting by hand (not needed)


=====================================================================
 1. OPEN THE TERMINAL
=====================================================================
  The terminal is a black (or blue) window where commands are typed.
  It must be opened IN THIS FOLDER.

  The easiest (Windows 11):
    1. Open this folder (the one where this README file is).
    2. Right-click in an empty space of the folder (not on a file).
    3. Click "Open in Terminal".

  On Windows 10: hold the Shift key, right-click in an empty space,
  then "Open PowerShell window here".

  Another way, if you do not see these options:
    click in the address bar at the top of the folder (where the path
    is written), delete everything, type  cmd  then press Enter.

  To type a command: write it (or copy-paste it), then press Enter.

  Tips:
    - Up arrow = brings back the previous command.
    - Closing the terminal window stops the program.


=====================================================================
 2. INSTALL (only once per computer)
=====================================================================
  THE EASIEST: double-click install.bat (in the main folder of the
  program, the one above this one). It installs the 3 things below by
  itself, and keeps what is already installed.

  BY HAND: 3 things must be installed. Type these commands one by one in
  the terminal, waiting for each one to finish.

  If you are asked to accept terms: type  Y  then Enter.
  If Windows asks for permission: click Yes.

  STEP 1 — Python (runs the program)
      winget install -e --id Python.Python.3.13
    Then CLOSE the terminal and OPEN IT AGAIN (this is important).

  STEP 2 — The Python tools (mouse, screenshots)
      python -m pip install pyautogui pytesseract mss pillow
    At the end, you should see "Successfully installed"
    (or "Requirement already satisfied": that is fine too).

  STEP 3 — Tesseract (reads the text shown on screen)
      winget install -e --id UB-Mannheim.TesseractOCR
    If an installation window opens: do not change the folder
    offered, just click Next until the end.

  CHECK — type:
      python -c "import pyautogui, pytesseract, mss, PIL; print('OK')"
    If it shows OK, everything is ready.

  Without winget (installing by hand):
    - Python: https://www.python.org/downloads/
      On the first window, TICK "Add python.exe to PATH".
    - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
      (64-bit Windows installer, keep the folder offered).


=====================================================================
 3. SET UP (the first time)
=====================================================================
  1. Open Kyara in your browser (Opera, Brave, Chrome…), on the
     boosters page.
  2. In the terminal, type:
         python configure_positions.py
  3. It asks which "script" to set up. One script = one browser.
     The first time, just press Enter.
  4. It sees that nothing is set yet and shows the list of what is
     missing. At "Set them now?", press Enter (= yes).
  5. It shows the list of the game boosters, with a number:
         1  Shonen Mix      4  Seinen          7  Mecha
         2  Shonen          5  Shojo           8  Waifus
         3  Isekai          6  Sport           9  Husbandos
     Type the NUMBERS of the packs to open, separated by commas.
     Examples:
         3          -> always Isekai
         3, 1       -> one Isekai, then one Shonen Mix, etc.
     No need to write the names.
  6. Then it shows you the places to click, one by one.
     For each one:
         - put the mouse on it, in the browser;
         - press the  G  key of the keyboard.
     That is all: the position is saved.
         G   = save the place where the mouse is
         N   = skip (keep the old place)
         Esc = stop (what is done is kept)
     You can click normally in the browser in between: only the G
     key saves.
  7. When everything is set, it shows "Everything is set: the script
     can start." The menu comes back: press Enter to quit.

  If something is still missing (for example a button skipped with
  N), it says so when quitting. Simply open the assistant again later:
  it will only ask again for what is missing.

  Good to know during step 6:
    - THE COUNTER ("1/10", "5/10", "10/10"…), at the top of the page:
      it is the most important. Put the TIP of the mouse right on the
      number that changes, just before the "/".
          1/10    -> tip on the 1
          5/10    -> tip on the 5
          10/10   -> tip BETWEEN the 1 and the 0 of the first 10
          20/20   -> tip BETWEEN the 2 and the 0 of the first 20
                     (with a subscription, the counter goes up to 20)
      Not on the "/10", not next to the text: otherwise the program
      does not read the counter and never opens anything.
    - The buttons of the opening screen (« Ouvrir 10 boosters »,
      « Tout révéler »…) are only visible during an opening.
      If you have none going on, skip them with N.
    - If a pack is only visible when scrolling down the page (Sport,
      Seinen, Mecha…): first go all the way up with the mouse wheel,
      then scroll down to the pack, put the mouse on it and press G.
      The program remembers how far down you went.


=====================================================================
 4. START AND STOP
=====================================================================
  START — in the terminal, type:
      python kyara_booster.py
  Leave the window open: the program works as long as it is open.
  You can use your computer at the same time.

  STOP — as you like:
    - press Ctrl + C in the terminal;
    - or put the mouse in the very top-left corner of the screen;
    - or close the terminal window.

  GOOD TO KNOW
    - After changing a setting, stop then start the program again.
    - The browser can be hidden behind other windows: it still works.
      To click, it brings it in front for a second, then puts
      everything back as before.
    - The browser must NOT be minimized in the taskbar.
    - The « Tu es toujours là ? » ("Are you still there?") popup is
      handled by itself.
    - If a setting is missing, the program says which one at start and
      refuses to click at random. Then run the assistant
      (python configure_positions.py): it will ask for what is missing.


=====================================================================
 5. THE ASSISTANT MENU, CHOICE BY CHOICE
=====================================================================
  To open the menu:  python configure_positions.py
  Type the number wanted, then Enter. Enter alone = quit.
  Each change is saved right away.
  At the top of the menu, it says whether the script is "ready" or how
  many settings are missing. After each choice, if something is
  missing (for example the position of a pack you just added), it
  offers to set it right away.

  ---------------------------------------------------------------
  1  CONFIGURE EVERYTHING
  ---------------------------------------------------------------
     The packs, then all the places to click (see part 3).
     It is the right choice the first time.

  ---------------------------------------------------------------
  2  PACKS AND ROTATION — which packs to open, in which order
  ---------------------------------------------------------------
     It shows the numbered list of the game boosters. Type the
     numbers, separated by commas. They take turns in a loop.
       6          -> always Sport
       6, 3       -> Sport, Isekai, Sport, Isekai…
       3, 3, 6    -> two Isekai, then one Sport, etc.
     Enter without writing anything = change nothing.
     A new booster released in the game, missing from the list: type
     its name instead of the number. It then asks whether a
     double-click is needed to open it: answer  n  (no) unless one
     click is not enough.
     Only the position of the chosen packs is asked.

  ---------------------------------------------------------------
  3  POSITIONS — the places to click
  ---------------------------------------------------------------
     Mouse on the element asked, then G key (see part 3).
     To do again if the clicks land next to the target (browser
     moved, page zoom changed…).

  ---------------------------------------------------------------
  4  HUNT FOR A CARD — open a pack until getting a card
  ---------------------------------------------------------------
     Example: "open Isekai until getting Rimuru, then open
     Shonen Mix".
     It asks you:
       - the card wanted (e.g. Rimuru);
       - the pack to open to get it (its number, e.g. 3 for Isekai);
       - the packs to open afterwards (numbers; Enter = your usual
         packs).
     After each opening, it reads the cards obtained. When the card
     is there, it switches by itself to the next packs, and keeps a
     picture of the cards in the "hunts" folder.
     To stop a hunt: type  none  as the card name.

  ---------------------------------------------------------------
  5  ACCOUNTS — if you have several Kyara accounts on this browser
  ---------------------------------------------------------------
     The program recognizes which account is logged in thanks to the
     color of its profile picture (top right), and each account can
     have its own packs and its own counter (subscribed or not).
     Example:
         account "A"    -> Isekai and Shonen Mix, counter /20 (subscribed)
         account "Logo" -> Isekai until Rimuru, then Shonen Mix,
                           counter /10 (not subscribed)
     How to do it, for EACH account:
       1. In the browser, log in on this account.
       2. In the menu: 5, then 1.
       3. Put the mouse in the middle of the profile picture, press G.
       4. Give the account a name, then its packs (and its hunt if you
          want), then the capacity of its counter:
          0 = read by itself, 10 = not subscribed, 20 = subscribed.
     Then switch account in the browser and start again.
     Afterwards, you can switch account whenever you want, even while
     the program is running: it adapts by itself.

  ---------------------------------------------------------------
  6  STEPS — what the program does when the counter is full
  ---------------------------------------------------------------
     It shows the numbered list of the steps. To change it:
         a        add a step (it asks the questions)
         d 3      delete step no. 3
         w 3 5    wait 5 seconds after step no. 3
         m 3 1    move step no. 3 to first place
         Enter    finish
     Example: if a page takes time to load, increase the wait of the
     step right before it (w …).

  ---------------------------------------------------------------
  7  SETTINGS — speed, pauses, name…
  ---------------------------------------------------------------
     By default, the mouse GLIDES to the button in 0.5 to 0.9
     second, like a real hand. It never jumps at once onto the button.
     First, it asks "Put everything back to default at once?":
     y = yes (the name and the browser do not change), Enter = no.
     Then, one question per setting, with its default value:
         Enter = keep    d = put the default value back
     Example: for a slower mouse, at "duration of a mouse movement",
     type  0.8 1.2
     Too fast (less than 0.3 second): refused, the mouse would almost
     jump at once.

     MAX CAPACITY OF THE COUNTER (subscriptions)
     Without a subscription, the counter goes up to 10 ("10/10"). A
     subscription that adds +10 capacity makes it go up to 20
     ("20/20"). An event can add +5 more (lightning next to the
     counter): 15/15 or 25/25.
         0   = automatic (default, recommended): the program reads
               the number after the "/" itself. Also works with
               several accounts, subscribed or not.
         10  = no subscription
         20  = subscription with +10 capacity
         15, 25 = the same, with the +5 bonus of an event
     With several accounts, each account can have its own capacity
     (menu 5); this setting is used for the others.
     The program still checks the counter: if you set 10 but the
     counter goes up to 20 (or the other way round), it adapts by
     itself and writes it in the window:
         "The counter goes up to 20, not 10 as set: the script
          adapts (20 boosters)."
     In every case, it opens when the counter is full.
     At 20/20, the game button only opens 10 boosters: the program
     therefore does the opening TWICE in a row (20/20 -> 10/20 -> 0/20,
     25/25 -> 15/25 -> 5/25). At 15/15, only once (15/15 -> 5/15).
     The 2nd time, it takes the next pack of your rotation.
     The shorter recharge time of a subscription needs no setting:
     the program just watches the counter.

  ---------------------------------------------------------------
  8  RESET
  ---------------------------------------------------------------
     Only touches the script chosen at the start. Two possibilities:

     1 = CLEAR THE POSITIONS ONLY
         The places to click are cleared. Everything else is kept
         (packs, hunt, accounts, settings).
         Then: menu 3 to place them again with G.
         Useful when the clicks land next to the target.

     2 = CLEAR EVERYTHING
         Everything becomes empty again, like a new script: no pack
         chosen, no more hunt, no more accounts, positions cleared.
         Only these stay: the name of the script, its browser and its
         screen.
         Useful when everything is mixed up and you want a clean start.

     EXAMPLE with the Brave script:
                           before            after 1          after 2
         browser           Brave             Brave            Brave
         packs             Shonen Mix        Shonen Mix       none
         hunt              Rimuru            Rimuru           none
         positions         placed            cleared          cleared

     In both cases, the script no longer starts until it is done
     again. Open the assistant again: it sees what is missing and asks
     you for it (positions only after 1; packs then positions after 2).

     It always asks for confirmation (y = yes). Enter = cancel.
     Regrets? The previous version is kept in the "backups" folder
     (e.g. kyara_booster_brave.py.bak): put this file back next to the
     scripts, in place of the script, and remove ".bak" from its name.

  ---------------------------------------------------------------
  9  FREE MODE — just see a position
  ---------------------------------------------------------------
     Each press on G shows where the mouse is and copies it (Ctrl+V
     to paste it). Esc to stop. Rarely useful.


=====================================================================
 6. TWO BROWSERS AT THE SAME TIME
=====================================================================
  Example: Opera AND Brave, each one with its Kyara account.

  1. Open Kyara in the second browser.
  2. Type  python configure_positions.py
  3. Choose "New script for another browser".
  4. Give it a name, for example  brave
  5. The new script is empty: the assistant asks for the packs, then
     the positions. Place them with G in THIS browser.
  6. Open TWO terminals, and run one script in each:
         python kyara_booster.py           (the first browser)
         python kyara_booster_brave.py     (the second one)

  They do not get in each other's way: when both are full, they open
  each in turn (there is only one mouse).


=====================================================================
 7. A PROBLEM?
=====================================================================
  "'python' is not recognized"
      Python is not installed, or the terminal was not opened again
      after the installation. Close and open the terminal again.
      Otherwise, try  py  instead of  python.

  "No module named …"
      Step 2 of the installation was not done.

  "Tesseract not found"
      Step 3 of the installation was not done, or Tesseract was
      installed in another folder than the one offered.

  "can't open file …"
      The terminal is not opened in this folder (see part 1).

  "Some settings are missing to start"
      The program lists what is missing. Run
          python configure_positions.py
      and answer yes to "Set them now?".

  The clicks land next to the target
      Place the positions again: menu 3.

  "Counter not found" or "The window left its screen"
      The browser was moved. Put it back where it was, or place the
      positions again (menu 3).
      For the counter, put the tip of the mouse right on the number
      just before the "/" (the 5 of "5/10"; for "10/10", between the
      1 and the 0 of the first 10; for "20/20", between the 2 and
      the 0).

  "Pack page never opened: opening cancelled"
      The click on the pack changed nothing, even after 3 tries. The
      pack may have moved on the page: place its position again (menu 3).

  "Window … not found"
      The browser is closed or minimized in the taskbar.
      Open it in full.

  "Waiting: … is opening"
      Normal: another script is using the mouse.

  It stays stuck "waiting" for nothing
      Type:  python coordination.py reset

  Everything is mixed up, nothing works any more
      Menu 8, then 2 (clear everything), then open the assistant again.


=====================================================================
 8. FOR THE CURIOUS: SETTING BY HAND (not needed)
=====================================================================
  The assistant does all this for you. This part is only useful if you
  want to change the file yourself.

  THE FILES OF THE FOLDER
    kyara_booster.py          the program (its settings are at the top)
    kyara_booster_xxx.py      the copies for other browsers
    configure_positions.py    the assistant
    kyara_common.py           internal tools (do not touch)
    coordination.py           sharing of the mouse (do not touch)
  The files created by the scripts are stored in 3 subfolders
  (created by themselves), so as not to clutter the scripts folder:
    debug\                    captures to check (counter, popup, cards
                              obtained). Only one of each kind: they
                              are replaced each time, the folder does
                              not grow. Can be deleted.
    hunts\                    hunt_<card>.txt / .png: finished hunt.
                              Delete the file to start it again.
    backups\                  *.bak: previous version of each script,
                              kept by the assistant at each change

  CHANGING THE SETTINGS
    Open kyara_booster.py with Notepad. The settings are at the very
    top, each one explained. Only change the values, keeping the
    quotes, commas and brackets. Then start the program again.

    NAME              name shown (different for each script)
    EXECUTABLE        browser program: "opera.exe",
                      "brave.exe", "chrome.exe", "msedge.exe"…
                      "" = not detected yet
    SCREEN_AREA       browser screen (filled in by the assistant)
                      (0, 0, 0, 0) = not detected yet
    COUNTER_CENTER    place of the "x/10" counter: on the number
                      right before the "/" (10/10: between the 1 and the 0)
    MAX_CAPACITY      counter capacity: 0 = read by itself
                      (recommended), 10 = no subscription, 20 = subscription
    PACKS             all the game boosters and the place to click on
                      them. "scroll": 3 = scroll down 3 notches first.
    ROTATION          packs to open, in order, in a loop
                      [] = none chosen
    HUNT              e.g. {"card": "Rimuru", "pack": "Isekai",
                            "then": ["Shonen Mix"]}
                      None = no hunt
    AVATAR, ACCOUNTS  accounts recognized by their profile picture
                      (None = no accounts; see menu 5).
                      "capacity": 20 = counter of this account (optional)
    SEQUENCE          the steps of the opening (see menu 6)
    POPUP_INTERVAL    delay between two checks of the popup
    CORNER_STOP       True = mouse in the top-left corner stops everything
    MOVE_DURATION     mouse speed (min, max), in seconds
                      default (0.5, 0.9); at least 0.3

    A position is written (x, y): x = from left to right, y = from top
    to bottom. On a screen placed to the left of the main screen, x is
    negative: that is normal. (0, 0) = position not placed yet.

  ASSISTANT SHORTCUTS
    python configure_positions.py kyara_booster_brave.py
        goes directly to this script, without the choice question
    python configure_positions.py reset
        goes directly to the reset
    python configure_positions.py free
        goes directly to the free mode


=====================================================================
 SUPPORT
=====================================================================
  If this program saves you time, you can support me with a small
  tip on Ko-fi — thank you! ☕
      https://ko-fi.com/nylen9
