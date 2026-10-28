"""
Assistant qui règle toute la configuration de kyara_booster.py, sans ouvrir
le fichier.

    python configurer_positions.py
        Demande quel script configurer (un script par navigateur, ou un
        nouveau pour un autre navigateur), puis ouvre le menu :
          1. tout configurer : packs puis positions ;
          2. packs et rotation (ex. « Sport » ou « Sport, Isekai ») ;
          3. positions : souris dessus et touche G (les crans de molette
             pour les packs plus bas dans la page sont comptés aussi) ;
             le navigateur (EXECUTABLE) et son écran (ZONE_ECRAN) sont
             détectés au passage ;
          4. chasse à une carte ;
          5. comptes : plusieurs comptes Kyara reconnus à leur avatar,
             chacun avec ses packs et sa chasse ;
          6. étapes de l'ouverture (ajouter, supprimer, déplacer, attentes) ;
          7. réglages (nom, navigateur, pauses, vitesse de la souris) ;
          8. remise à zéro ;  9. mode libre.
        Chaque changement est enregistré tout de suite ; la version d'avant
        est gardée dans sauvegardes/kyara_booster.py.bak.

    python configurer_positions.py kyara_booster_2.py
        Pareil, directement pour ce script (sans la question du choix).

    python configurer_positions.py reset
        Remise à zéro du script choisi (une confirmation est demandée) :
        1. coordonnées à zéro : toutes les positions à (0, 0), le reste gardé ;
        2. tout par défaut : la configuration d'origine (nom, navigateur et
           écran gardés ; sur un autre écran, positions à replacer).
        Pour une copie : python configurer_positions.py reset kyara_booster_2.py

    python configurer_positions.py libre
        Mode libre : chaque appui sur G affiche la position et la copie dans
        le presse-papiers (Ctrl+V pour la coller où tu veux).

Touches (marchent même quand le navigateur est au premier plan) :
    G       valider la position de la souris
    N       passer (garder la valeur actuelle)
    Échap   arrêter
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

DOSSIER = Path(__file__).resolve().parent
FICHIER_PAR_DEFAUT = DOSSIER / "kyara_booster.py"
# Rangement : mêmes sous-dossiers que kyara_commun.py, plus les anciennes
# versions des scripts (.bak).
DOSSIER_DEBUG = DOSSIER / "debug"
DOSSIER_CHASSES = DOSSIER / "chasses"
DOSSIER_SAUVEGARDES = DOSSIER / "sauvegardes"


def chemin_sauvegarde(fichier):
    """sauvegardes/<script>.bak (dossier créé au besoin)."""
    DOSSIER_SAUVEGARDES.mkdir(exist_ok=True)
    return DOSSIER_SAUVEGARDES / (fichier.name + ".bak")

TOUCHE_G, TOUCHE_N, TOUCHE_ECHAP = 0x47, 0x4E, 0x1B

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

# Molette : crochet souris global (marche quel que soit le programme devant).
WH_MOUSE_LL, WM_MOUSEWHEEL, PM_REMOVE = 14, 0x020A, 1
CRAN_MOLETTE = 120


class _InfoSouris(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


_ProcSouris = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = (ctypes.c_int, _ProcSouris, ctypes.c_void_p, wt.DWORD)
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
_user32.PeekMessageW.argtypes = (
    ctypes.POINTER(wt.MSG), wt.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
)
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_kernel32.GetModuleHandleW.argtypes = (ctypes.c_wchar_p,)

# Positions à remplir, cherchées dans la partie configuration du script :
# (motif, texte à afficher, est un pack). Le groupe « pos » est la position
# « (x, y) » ; pour un pack, le groupe « mol » est son réglage de molette.
POSITION = r"(?P<pos>\(-?\d+, -?\d+\))"
MOLETTE = r'(?P<mol>, "molette": (?P<crans>\d+))?'
ELEMENTS = (
    (rf"^COMPTEUR_CENTRE = {POSITION}",
     lambda m: "le compteur « x/10 » en haut de la page Kyara : pointe de la souris "
               "sur le nombre juste devant le « / » (le 5 de « 5/10 » ; "
               "« 10/10 » : entre le 1 et le 0 ; « 20/20 » : entre le 2 et le 0)", False),
    (rf'^\s*"(?P<nom>[^"]+)": \{{"position": {POSITION}, "double_clic": (?:True|False){MOLETTE}',
     lambda m: f"le pack « {m['nom']} » sur la page d'accueil", True),
    (rf"^AVATAR = {POSITION}",
     lambda m: "l'avatar du compte connecté (en haut à droite, au centre)", False),
    (rf'^\s*\("(?:clic|double_clic)", "(?P<nom>[^"]+)", {POSITION}',
     lambda m: f"le bouton « {m['nom']} »", False),
    (rf'^\s*\("tout_reveler", {POSITION}',
     lambda m: "le bouton « Tout révéler » (écran des cartes à retourner)", False),
)
NON_DEFINIE = "(0, 0)"
MOTIF_EXECUTABLE = re.compile(r'^EXECUTABLE = (?P<val>"[^"]*")', re.MULTILINE)
MOTIF_NOM = re.compile(r'^NOM = "(?P<val>[^"]*)"', re.MULTILINE)
MOTIF_ZONE = re.compile(r"^ZONE_ECRAN = (?P<val>\(-?\d+, -?\d+, \d+, \d+\))", re.MULTILINE)


# Configuration d'origine de kyara_booster.py (pour « reset »), de
# « 1. Navigateur » jusqu'à la ligne « FIN DE LA CONFIGURATION » exclue.
CONFIGURATION_DEFAUT = '''\
# ---------- 1. Navigateur ----------
# Nom affiché dans le terminal. Doit être différent pour chaque copie lancée.
NOM = "principal"
# Programme du navigateur : "opera.exe", "brave.exe", "chrome.exe",
# "msedge.exe", "firefox.exe"… (rempli par configurer_positions.py).
# "" = pas encore détecté.
EXECUTABLE = ""
# Écran où le navigateur est affiché : (x, y, largeur, hauteur)
# (rempli par configurer_positions.py). Écran principal : (0, 0, 1920, 1080).
# (0, 0, 0, 0) = pas encore détecté.
ZONE_ECRAN = (0, 0, 0, 0)

# ---------- 2. Compteur de boosters (x/10) ----------
# Compteur « x/10 » en haut de la page Kyara : pointe de la souris sur le
# nombre juste devant le « / » (le 5 de « 5/10 » ; « 10/10 » : entre le 1
# et le 0 du premier 10). S'il bouge un peu,
# le script le retrouve tout seul (recalage automatique).
# (0, 0) = position pas encore placée (vaut pour toutes les positions).
COMPTEUR_CENTRE = (0, 0)
# Taille de la zone lue autour du centre (largeur, hauteur). Laisser tel quel.
COMPTEUR_TAILLE = (100, 45)
# Nombre de lectures « compteur plein » d'affilée avant d'ouvrir (évite une
# fausse lecture).
LECTURES_STABLES = 2
# Capacité max du compteur de boosters : 10 sans abonnement, 20 avec un
# abonnement qui ajoute 10 de capacité (« x/20 »). 0 = lue toute seule sur
# le compteur (conseillé : marche aussi avec plusieurs comptes, abonnés ou
# non). Dans tous les cas, le script ouvre quand le compteur est plein.
CAPACITE_MAX = 0
# Pause entre deux lectures du compteur, en secondes.
INTERVALLE = 2
# Pause après une ouverture, en secondes.
PAUSE_APRES_OUVERTURE = 5

# ---------- 3. Packs ----------
# Le plus simple : configurer_positions.py demande les packs voulus et leur
# ordre (ex. « Sport » seul, ou « Sport, Isekai »), puis leurs positions.
# Tous les boosters du jeu sont listés ; seuls ceux qui sont utilisés
# (ROTATION, chasse, comptes) ont besoin d'une position.
# Pour un booster ajouté au jeu plus tard : copier une ligne, changer le nom.
# "double_clic": True si un simple clic ne suffit pas pour ce pack.
# "molette": 3  pour un pack visible seulement en descendant la page : le
#               script remonte en haut de la page puis descend de 3 crans de
#               molette avant de cliquer (compté par configurer_positions.py).
#               Sans "molette", pas de défilement.
PACKS = {
    "Shonen Mix": {"position": (0, 0), "double_clic": False},
    "Shonen": {"position": (0, 0), "double_clic": False},
    "Isekai": {"position": (0, 0), "double_clic": True},
    "Seinen": {"position": (0, 0), "double_clic": False},
    "Shojo": {"position": (0, 0), "double_clic": False},
    "Sport": {"position": (0, 0), "double_clic": False},
    "Mecha": {"position": (0, 0), "double_clic": False},
    "Waifus": {"position": (0, 0), "double_clic": False},
    "Husbandos": {"position": (0, 0), "double_clic": False},
}

# Packs à ouvrir, dans l'ordre, en boucle ([] = pas encore choisis) :
#   ["Isekai", "Shonen Mix"]  -> Isekai, puis Shonen Mix, puis Isekai…
#   ["Shonen Mix"]            -> toujours Shonen Mix
#   ["Isekai", "Isekai", "Shonen Mix"] -> deux Isekai pour un Shonen Mix
ROTATION = []

# Chasse à une carte (facultatif) : ouvrir un pack jusqu'à obtenir une carte,
# puis passer à une autre rotation. None = pas de chasse.
#   CHASSE = {"carte": "Rimuru", "pack": "Isekai", "ensuite": ["Shonen Mix"]}
# La carte est cherchée sur l'écran des cartes retournées (étape "lire_cartes"
# de la SEQUENCE). Seul le début du nom compte : les noms y sont tronqués.
# Une fois trouvée, un fichier chasse_<carte>.txt est créé dans le dossier
# « chasses » : le supprimer pour reprendre la chasse.
CHASSE = None

# Plusieurs comptes Kyara sur ce navigateur (facultatif) : le compte connecté
# est reconnu à la couleur de son avatar (en haut à droite) et chaque compte
# a ses packs, sa chasse et son compteur (abonné ou non). Le plus simple :
# configurer_positions.py, choix « Comptes », une fois par compte en étant
# connecté dessus.
# AVATAR = centre de l'avatar. COMPTES = None : pas de comptes (ROTATION et
# CHASSE servent pour tout le monde). Exemple :
#   COMPTES = {
#       "A": {"couleur": (78, 65, 29), "rotation": ["Isekai", "Shonen Mix"],
#             "chasse": None},
#       "Logo": {"couleur": (48, 33, 74), "rotation": ["Shonen Mix"],
#                "chasse": {"carte": "Rimuru", "pack": "Isekai"}, "capacite": 20},
#   }
# « couleur » est lue par configurer_positions.py. Avec une chasse, le compte
# ouvre le pack de la chasse jusqu'à la carte, puis passe à sa « rotation ».
# « capacite » (facultatif) : CAPACITE_MAX pour ce compte seulement (20 =
# compte abonné, 10 = sans abonnement, 0 = lue sur le compteur).
AVATAR = (0, 0)
COMPTES = None

# ---------- 4. Séquence d'ouverture ----------
# Les étapes faites quand le compteur est plein (10/10, 20/20), dans l'ordre :
#   ("pack", attente)                       clic sur le pack choisi (voir PACKS)
#   ("clic", "nom", (x, y), attente)        clic simple
#   ("double_clic", "nom", (x, y), attente) double-clic
#   ("tout_reveler", (x, y), attente)       cherche le bouton « Tout révéler »
#                                           et clique dessus ; (x, y) sert si
#                                           le bouton n'est pas trouvé
#   ("lire_cartes",)                        cherche la carte de la chasse
#                                           (rien si pas de chasse en cours)
#   ("attendre", secondes)                  simple pause
# « attente » = secondes d'attente après l'étape (chargement de la page…).
SEQUENCE = [
    ("pack", 2),
    ("clic", "Ouvrir 10 boosters", (0, 0), 2),
    ("clic", "Valider l'ouverture", (0, 0), 3),
    ("tout_reveler", (0, 0), 3),
    ("lire_cartes",),
    ("clic", "Retour au début", (0, 0), 2),
]

# ---------- 5. Popup « Tu es toujours là ? » ----------
# Le popup est cherché sur tout ZONE_ECRAN ; le clic se fait sur son bouton.
# Vérification complète toutes les N secondes (un test rapide tourne en plus
# à chaque passage et la déclenche dès que le bouton rouge apparaît).
INTERVALLE_POPUP = 10

# ---------- 6. Souris ----------
# Mettre la souris dans le coin haut-gauche de l'écran principal arrête le script.
ARRET_COIN_ECRAN = True
# Durée d'un déplacement de souris, en secondes (min, max) : la souris glisse
# jusqu'au bouton, jamais de saut d'un coup. Au moins 0.3 (sinon refusé).
DUREE_MOUVEMENT = (0.5, 0.9)


'''

# ============================================================
# CLAVIER, FENÊTRE, ÉCRAN
# ============================================================
def appuyee(touche):
    return _user32.GetAsyncKeyState(touche) & 0x8000


def pomper_messages():
    """Laisse passer les messages Windows (nécessaire au crochet de la molette)."""
    message = wt.MSG()
    while _user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        pass


def attendre_touche():
    """Attend G, N ou Échap (où que soit le focus) et renvoie la touche."""
    while True:
        for touche in (TOUCHE_G, TOUCHE_N, TOUCHE_ECHAP):
            if appuyee(touche):
                while appuyee(touche):  # attendre le relâchement
                    pomper_messages()
                    time.sleep(0.02)
                return touche
        pomper_messages()
        time.sleep(0.02)


def vider_clavier_terminal():
    """Évite que les « g » tapés se retrouvent dans le terminal à la fin."""
    while msvcrt.kbhit():
        msvcrt.getwch()


def copier(texte):
    subprocess.run(["clip"], input=texte.encode("utf-8"), check=False)


def programme_sous(position):
    """Nom du programme de la fenêtre sous la souris (ex. "opera.exe"), ou None."""
    fenetre = _user32.WindowFromPoint(wt.POINT(*position))
    racine = _user32.GetAncestor(fenetre, 2) if fenetre else None
    if not racine:
        return None
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(racine, ctypes.byref(pid))
    poignee = _kernel32.OpenProcess(0x1000, False, pid.value)
    if not poignee:
        return None
    try:
        tampon = ctypes.create_unicode_buffer(512)
        taille = ctypes.c_ulong(512)
        if _kernel32.QueryFullProcessImageNameW(poignee, 0, tampon, ctypes.byref(taille)):
            return Path(tampon.value).name.lower()
        return None
    finally:
        _kernel32.CloseHandle(poignee)


def ecran_sous(position):
    """(x, y, largeur, hauteur) de l'écran qui contient la position."""
    x, y = position
    with mss.MSS() as captureur:
        for ecran in captureur.monitors[1:]:
            if (ecran["left"] <= x < ecran["left"] + ecran["width"]
                    and ecran["top"] <= y < ecran["top"] + ecran["height"]):
                return ecran["left"], ecran["top"], ecran["width"], ecran["height"]
    return None


def texte_position(position):
    return f"({position[0]}, {position[1]})"


class SuiviMolette:
    """
    Compte les crans de molette depuis le haut de la page, pour chaque
    programme (seuls ceux tournés au-dessus du navigateur comptent pour lui).
    Remonter plus haut que le haut ne compte pas : la page ne bouge plus.
    """

    def __init__(self):
        self.niveaux = {}           # programme -> unités de molette vers le bas
        self._crochet = None
        self._procedure = _ProcSouris(self._recevoir)

    def _recevoir(self, code, wparam, lparam):
        if code == 0 and wparam == WM_MOUSEWHEEL:
            try:
                info = ctypes.cast(lparam, ctypes.POINTER(_InfoSouris)).contents
                delta = ctypes.c_short(info.mouseData >> 16).value   # > 0 = vers le haut
                programme = programme_sous((info.pt.x, info.pt.y))
                if programme:
                    self.niveaux[programme] = max(0, self.niveaux.get(programme, 0) - delta)
            except Exception:
                pass
        return _user32.CallNextHookEx(None, code, wparam, lparam)

    def __enter__(self):
        self._crochet = _user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._procedure, _kernel32.GetModuleHandleW(None), 0
        )
        return self

    def __exit__(self, *_):
        if self._crochet:
            _user32.UnhookWindowsHookEx(self._crochet)
            self._crochet = None

    def crans(self, programme):
        return round(self.niveaux.get(programme, 0) / CRAN_MOLETTE)


# ============================================================
# MODE LIBRE
# ============================================================
def mode_libre():
    print("Mode libre : pose la souris sur un élément et appuie sur G.")
    print("La position est copiée : colle-la avec Ctrl+V. Échap pour arrêter.")
    print("Les crans de molette sont comptés depuis le haut de la page : remonte")
    print("d'abord tout en haut si la page a déjà défilé.\n")
    with SuiviMolette() as molette:
        while True:
            touche = attendre_touche()
            if touche == TOUCHE_ECHAP:
                break
            if touche != TOUCHE_G:
                continue
            position = tuple(pyautogui.position())
            programme = programme_sous(position)
            copier(texte_position(position))
            print(f"{texte_position(position)}  copié"
                  f"   (programme : {programme or '?'}, écran : {ecran_sous(position)}, "
                  f"molette : {molette.crans(programme)} cran(s))")
    vider_clavier_terminal()


# ============================================================
# LECTURE ET ÉCRITURE DE LA CONFIGURATION
# ============================================================
def _decalage(texte, ligne, colonne):
    """Rang dans le texte d'une (ligne, colonne en octets UTF-8) donnée par ast."""
    lignes = texte.splitlines(keepends=True)
    avant = sum(len(texte_ligne) for texte_ligne in lignes[:ligne - 1])
    return avant + len(lignes[ligne - 1].encode("utf-8")[:colonne].decode("utf-8"))


def affectation(texte, nom):
    """(début, fin, valeur) de la valeur de « NOM = … » dans le script, ou None."""
    for noeud in ast.parse(texte).body:
        if (isinstance(noeud, ast.Assign) and len(noeud.targets) == 1
                and isinstance(noeud.targets[0], ast.Name) and noeud.targets[0].id == nom):
            valeur = noeud.value
            return (_decalage(texte, valeur.lineno, valeur.col_offset),
                    _decalage(texte, valeur.end_lineno, valeur.end_col_offset),
                    ast.literal_eval(valeur))
    return None


def lire(texte, nom, defaut=None):
    trouve = affectation(texte, nom)
    return trouve[2] if trouve else defaut


def ecrire_valeur(valeur, retrait=0):
    """Valeur écrite comme dans la configuration (une ligne par pack, par étape…)."""
    interieur = " " * (retrait + 4)
    if isinstance(valeur, dict) and any(isinstance(v, dict) for v in valeur.values()):
        lignes = [f"{interieur}{ecrire_valeur(cle)}: {ecrire_valeur(v, retrait + 4)},"
                  for cle, v in valeur.items()]
        return "{\n" + "\n".join(lignes) + "\n" + " " * retrait + "}"
    if isinstance(valeur, list) and valeur and all(isinstance(v, tuple) for v in valeur):
        lignes = [f"{interieur}{ecrire_valeur(v)}," for v in valeur]
        return "[\n" + "\n".join(lignes) + "\n" + " " * retrait + "]"
    if isinstance(valeur, dict):
        return "{" + ", ".join(f"{ecrire_valeur(cle)}: {ecrire_valeur(v)}"
                               for cle, v in valeur.items()) + "}"
    if isinstance(valeur, list):
        return "[" + ", ".join(ecrire_valeur(v) for v in valeur) + "]"
    if isinstance(valeur, tuple):
        return ("(" + ", ".join(ecrire_valeur(v) for v in valeur)
                + ("," if len(valeur) == 1 else "") + ")")
    if isinstance(valeur, str):
        return json.dumps(valeur, ensure_ascii=False)
    return repr(valeur)


def remplacer(texte, nom, valeur):
    debut, fin, _ = affectation(texte, nom)
    return texte[:debut] + ecrire_valeur(valeur) + texte[fin:]


def pack_propre(reglage):
    """Réglage d'un pack, clés dans l'ordre attendu par l'assistant."""
    propre = {"position": tuple(reglage.get("position", (0, 0))),
              "double_clic": bool(reglage.get("double_clic", False))}
    if reglage.get("molette"):
        propre["molette"] = reglage["molette"]
    return propre


def ecrire_packs(texte, packs):
    return remplacer(texte, "PACKS", {nom: pack_propre(r) for nom, r in packs.items()})


def mettre_en_forme(texte):
    """
    PACKS et SEQUENCE réécrits dans la forme lue par l'assistant ; les
    boosters du jeu absents de PACKS y sont ajoutés (position à placer).
    """
    packs = {nom: {"position": (0, 0), "double_clic": double}
             for nom, double in BOOSTERS_DU_JEU.items()}
    packs.update(lire(texte, "PACKS"))
    # Ordre du jeu d'abord, puis les packs ajoutés à la main.
    ordre = [nom for nom in BOOSTERS_DU_JEU] + [nom for nom in packs if nom not in BOOSTERS_DU_JEU]
    texte = ecrire_packs(texte, {nom: packs[nom] for nom in ordre})
    return remplacer(texte, "SEQUENCE", [tuple(etape) for etape in lire(texte, "SEQUENCE")])


class Session:
    """Script en cours de configuration ; sauvegarde .bak au premier changement."""

    def __init__(self, fichier):
        self.fichier = fichier
        self.original = fichier.read_text(encoding="utf-8")
        self.texte = self.original
        self.sauvegarde_faite = False

    def enregistrer(self, nouveau):
        if nouveau == self.texte:
            return
        compile(nouveau, str(self.fichier), "exec")  # sécurité : le script reste valide
        sauvegarde = chemin_sauvegarde(self.fichier)
        if not self.sauvegarde_faite:
            sauvegarde.write_text(self.original, encoding="utf-8")
            self.sauvegarde_faite = True
        self.fichier.write_text(nouveau, encoding="utf-8")
        self.texte = nouveau
        print(f"Enregistré dans {self.fichier.name} "
              f"(version d'avant : sauvegardes\\{sauvegarde.name}).\n")


# ============================================================
# QUESTIONS
# ============================================================
# Mots tapés par erreur à la place d'un nom de pack.
MOTS_COMMANDES = {"reset", "libre", "menu", "quitter", "q", "aide"}

# Boosters du jeu, dans l'ordre de la page, et s'il faut un double-clic.
BOOSTERS_DU_JEU = {
    "Shonen Mix": False, "Shonen": False, "Isekai": True,
    "Seinen": False, "Shojo": False, "Sport": False,
    "Mecha": False, "Waifus": False, "Husbandos": False,
}


def demander(question, defaut=""):
    vider_clavier_terminal()
    return input(question).strip() or defaut


def oui(question, defaut=False):
    reponse = demander(question + (" (O/n) : " if defaut else " (o/N) : ")).lower()
    return defaut if not reponse else reponse.startswith(("o", "y"))


def nombre(texte):
    """« 2 », « 2.5 » ou « 2,5 » -> 2 ou 2.5 (ValueError sinon, ou si négatif)."""
    valeur = float(texte.replace(",", "."))
    if valeur < 0:
        raise ValueError("nombre négatif")
    return int(valeur) if valeur.is_integer() else valeur


def liste_packs(reponse, packs):
    """
    « 6, 3 » ou « Sport, isekai » -> ["Sport", "Isekai"] : numéro de la liste
    des boosters, ou nom (un pack connu garde son écriture, accents ignorés).
    """
    noms = list(packs)
    connus = {texte_normalise(nom): nom for nom in noms}
    resultat = []
    for morceau in reponse.replace('"', "").split(","):
        morceau = morceau.strip()
        if morceau.isdigit() and 1 <= int(morceau) <= len(noms):
            resultat.append(noms[int(morceau) - 1])
        elif morceau:
            resultat.append(connus.get(texte_normalise(morceau), morceau))
    return resultat


def afficher_boosters(packs):
    """Liste numérotée des boosters, sur trois colonnes."""
    noms = list(packs)
    lignes = (len(noms) + 2) // 3
    for ligne in range(lignes):
        cases = [f"{rang + 1:>3}  {noms[rang]:<14}"
                 for rang in range(ligne, len(noms), lignes)]
        print("".join(cases).rstrip())


def est_commande(reponse):
    if reponse.lower() in MOTS_COMMANDES:
        print(f"« {reponse} » est une commande, pas un nom de pack : rien n'a changé.")
        print("Pour la remise à zéro, c'est le choix 8 du menu.\n")
        return True
    return False


def ajouter_packs(packs, noms):
    """Ajoute à `packs` les packs nouveaux (position à placer ensuite avec G)."""
    for nom in noms:
        if nom not in packs:
            double = oui(f"« {nom} » est un nouveau pack. Faut-il un double-clic pour l'ouvrir ?")
            packs[nom] = {"position": (0, 0), "double_clic": double}


def texte_normalise(texte):
    """Comme normaliser_texte de kyara_commun : sans accents, minuscules."""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


def fichier_chasse(chasse, compte):
    """Même nom que dans kyara_booster.py : chasse_[<compte>_]<carte>.txt."""
    nom = texte_normalise(chasse["carte"])
    if compte:
        nom = f"{texte_normalise(compte)} {nom}"
    return DOSSIER_CHASSES / f"chasse_{nom.replace(' ', '_')}.txt"


def decrire_chasse(chasse):
    if not chasse:
        return "aucune"
    texte = f"{chasse['carte']} dans {chasse['pack']}"
    if chasse.get("ensuite"):
        texte += f", puis {', '.join(chasse['ensuite'])}"
    return texte


def demander_chasse(packs, actuelle, rotation_apres):
    """Questions de la chasse ; renvoie la chasse voulue (dict ou None)."""
    print(f"Chasse actuelle : {decrire_chasse(actuelle)}")
    carte = demander("Carte à chasser (Entrée = garder, « aucune » = pas de chasse) : ")
    if not carte:
        return actuelle
    if carte.lower() in ("aucune", "aucun", "non", "none", "rien"):
        return None
    afficher_boosters(packs)
    pack = demander(f"Pack à ouvrir jusqu'à obtenir {carte} (numéro ou nom) : ")
    if not pack or est_commande(pack):
        print("Pas de pack : chasse inchangée.")
        return actuelle
    chasse = {"carte": carte, "pack": liste_packs(pack, packs)[0]}
    ensuite = demander(f"Packs à ouvrir une fois {carte} obtenu, dans l'ordre "
                       f"(numéros ou noms ; Entrée = {', '.join(rotation_apres) or 'aucun'}) : ")
    if ensuite and not est_commande(ensuite):
        chasse["ensuite"] = liste_packs(ensuite, packs)
    ajouter_packs(packs, [chasse["pack"], *chasse.get("ensuite", [])])
    return chasse


def proposer_reprise(chasse, compte):
    """Si la carte est déjà marquée obtenue, propose de reprendre la chasse."""
    if not chasse:
        return
    fichier = fichier_chasse(chasse, compte)
    if fichier.exists() and oui(f"{chasse['carte']} est déjà marqué obtenu ({fichier.name}). "
                                "Reprendre la chasse (supprimer ce fichier) ?"):
        fichier.unlink()
        fichier.with_suffix(".png").unlink(missing_ok=True)
        print("Chasse reprise.")


def packs_utilises(texte):
    """Packs utilisés ailleurs que dans ROTATION : {pack: par quoi}."""
    utilises = {}

    def noter(chasse, par):
        for nom in [chasse.get("pack"), *chasse.get("ensuite", [])]:
            if nom:
                utilises.setdefault(nom, par)

    if lire(texte, "CHASSE"):
        noter(lire(texte, "CHASSE"), "la chasse")
    for compte, reglage in (lire(texte, "COMPTES") or {}).items():
        for nom in reglage.get("rotation", []):
            utilises.setdefault(nom, f"le compte « {compte} »")
        if reglage.get("chasse"):
            noter(reglage["chasse"], f"la chasse du compte « {compte} »")
    return utilises


# ============================================================
# 2. PACKS ET ROTATION
# ============================================================
def action_packs(texte):
    """Demande les packs à ouvrir et leur ordre, puis réécrit PACKS et ROTATION."""
    packs, rotation = lire(texte, "PACKS"), lire(texte, "ROTATION")
    print("=== Packs à ouvrir ===")
    afficher_boosters(packs)
    print(f"Actuellement : {', '.join(rotation) or 'aucun pack choisi'}")
    print("Tape les NUMÉROS des packs à ouvrir, dans l'ordre, séparés par des")
    print("virgules. Ils sont ouverts en boucle dans cet ordre. Exemples :")
    print("   6          -> toujours le n°6 (Sport)")
    print("   6, 3       -> Sport, puis Isekai, puis Sport… (en alternance)")
    print("   3, 3, 6    -> deux Isekai, puis un Sport, etc.")
    print("Un booster qui n'est pas dans la liste : tape son nom.")
    reponse = demander("Packs" + (" (Entrée = ne rien changer)" if rotation else "") + " : ")
    if not reponse or est_commande(reponse):
        if not rotation:
            print("Aucun pack choisi : le script ne pourra pas démarrer.")
        print()
        return texte

    rotation = liste_packs(reponse, packs)
    ajouter_packs(packs, rotation)
    print(f"Packs à ouvrir : {', '.join(rotation)}\n")
    return remplacer(ecrire_packs(texte, packs), "ROTATION", rotation)


# ============================================================
# 3. POSITIONS (touche G)
# ============================================================
def trouver_elements(texte, tous=False):
    """
    Positions de la configuration, dans l'ordre du fichier. Sans `tous`,
    seulement celles qui servent (packs utilisés, avatar si comptes).
    """
    fin = texte.find("FIN DE LA CONFIGURATION")
    configuration = texte[:fin if fin >= 0 else len(texte)]
    avec_comptes = bool(lire(texte, "COMPTES"))
    utilises = set(lire(texte, "ROTATION") or []) | set(packs_utilises(texte))
    trouves = []
    for motif, libelle, est_pack in ELEMENTS:
        if motif.startswith("^AVATAR") and not avec_comptes and not tous:
            continue
        for m in re.finditer(motif, configuration, re.MULTILINE):
            if est_pack and m["nom"] not in utilises and not tous:
                continue
            # Pack : endroit du réglage de molette (à remplacer, ou à ajouter).
            molette = None
            if est_pack:
                debut, fin = m.span("mol") if m["mol"] else (m.end(), m.end())
                molette = (debut, fin, int(m["crans"] or 0))
            trouves.append((m.start("pos"), m.end("pos"), libelle(m), m["pos"], molette))
    return sorted(trouves)


def a_definir(texte):
    return [libelle for _, _, libelle, actuelle, _ in trouver_elements(texte)
            if actuelle == NON_DEFINIE]


def navigateur_inconnu(texte):
    """Vrai si le navigateur ou son écran n'ont pas encore été détectés."""
    zone = lire(texte, "ZONE_ECRAN", (0, 0, 0, 0))
    return not lire(texte, "EXECUTABLE") or zone[2] <= 0 or zone[3] <= 0


def manques(texte):
    """Ce qui manque pour que le script démarre, en clair."""
    liste = []
    if not lire(texte, "ROTATION"):
        liste.append("les packs à ouvrir (aucun choisi)")
    if navigateur_inconnu(texte):
        liste.append("le navigateur et son écran (détectés tout seuls à la première position)")
    for libelle in a_definir(texte):
        de = "du " + libelle[3:] if libelle.startswith("le ") else "de " + libelle
        liste.append(f"la position {de}")
    return liste


def afficher_manques(texte, titre="Il manque des réglages pour que le script démarre :"):
    liste = manques(texte)
    if liste:
        print(titre)
        for element in liste:
            print(f"   - {element}")
    return liste


def completer(texte):
    """Fait régler, dans l'ordre, tout ce qui manque."""
    if not lire(texte, "ROTATION"):
        texte = action_packs(texte)
    if manques(texte):
        texte = action_positions(texte, seulement_a_definir=True)
    if not afficher_manques(texte, "Il manque encore :"):
        print("Tout est réglé : le script peut démarrer.\n")
    else:
        print()
    return texte


def action_positions(texte, seulement_a_definir=False):
    elements = trouver_elements(texte)
    if seulement_a_definir:
        a_placer = [element for element in elements if element[3] == NON_DEFINIE]
        # Navigateur inconnu, positions déjà placées : un G suffit à le détecter.
        if not a_placer and elements and navigateur_inconnu(texte):
            a_placer = elements[:1]
        elements = a_placer
    if not elements:
        print("Aucune position à placer.\n")
        return texte

    print("=== Positions ===")
    print(f"{len(elements)} position(s) à placer. Pour chaque élément : pose la souris")
    print("dessus, puis   G = valider    N = garder la valeur actuelle    Échap = arrêter")
    print("Tu peux cliquer normalement pour changer de page (ouvrir un pack…) :")
    print("seule la touche G enregistre. Inutile de valider une vraie ouverture :")
    print("passe un bouton avec N si sa page n'est pas affichée.")
    print("Pack plus bas dans la page : descends jusqu'à lui avec la molette, puis G.")
    print("Les crans sont comptés depuis le haut de la page : si elle a déjà")
    print("défilé, remonte d'abord tout en haut avec la molette.\n")

    remplacements = []          # (debut, fin, nouveau texte)
    navigateur = ecran = None
    with SuiviMolette() as suivi:
        for numero, (debut, fin, libelle, actuelle, molette) in enumerate(elements, 1):
            etat = "à définir" if actuelle == NON_DEFINIE else f"actuel : {actuelle}"
            if molette and molette[2]:
                etat += f", molette {molette[2]} cran(s)"
            print(f"[{numero}/{len(elements)}] {libelle}  ({etat})")
            touche = attendre_touche()
            if touche == TOUCHE_ECHAP:
                print("   Arrêt : les positions déjà validées sont enregistrées.")
                break
            if touche == TOUCHE_N:
                print("   Gardée.")
                continue

            position = tuple(pyautogui.position())
            nouvelle = texte_position(position)
            remplacements.append((debut, fin, nouvelle))
            copier(nouvelle)
            if molette:
                crans = suivi.crans(programme_sous(position))
                remplacements.append(
                    (molette[0], molette[1], f', "molette": {crans}' if crans else "")
                )
                print(f"   -> {nouvelle}, molette : {crans} cran(s)"
                      + ("" if crans else " (pack visible sans descendre)"))
            else:
                print(f"   -> {nouvelle}")
            # Navigateur et écran : ceux du premier élément validé.
            if navigateur is None:
                navigateur = programme_sous(position)
                ecran = ecran_sous(position)

    vider_clavier_terminal()

    for motif, valeur, nom in (
        (MOTIF_EXECUTABLE, navigateur and f'"{navigateur}"', "EXECUTABLE"),
        (MOTIF_ZONE, ecran and "({}, {}, {}, {})".format(*ecran), "ZONE_ECRAN"),
    ):
        m = motif.search(texte)
        if m and valeur and m["val"] != valeur:
            remplacements.append((m.start("val"), m.end("val"), valeur))
            print(f"{nom} détecté : {valeur}")

    for debut, fin, valeur in sorted(remplacements, reverse=True):
        texte = texte[:debut] + valeur + texte[fin:]
    return texte


def action_tout(texte):
    return action_positions(action_packs(texte))


# ============================================================
# 4. CHASSE
# ============================================================
def action_chasse(texte):
    packs = lire(texte, "PACKS")
    print("=== Chasse à une carte ===")
    print("Ouvrir un pack jusqu'à obtenir une carte précise (lue sur l'écran des")
    print("cartes retournées), puis passer à d'autres packs.")
    if lire(texte, "COMPTES"):
        print("Avec des comptes, chaque compte a sa propre chasse (menu 5) : celle-ci")
        print("ne sert que quand le compte connecté n'est pas reconnu.")
    chasse = demander_chasse(packs, lire(texte, "CHASSE"), lire(texte, "ROTATION"))
    proposer_reprise(chasse, None)
    print(f"Chasse : {decrire_chasse(chasse)}\n")
    return remplacer(ecrire_packs(texte, packs), "CHASSE", chasse)


# ============================================================
# 5. COMPTES
# ============================================================
# Comme dans kyara_booster.py : carré lu autour de l'avatar, écart de teinte.
AVATAR_RAYON = 20
ECART_COMPTE_MAX = 0.1


def couleur_sous(position):
    """Couleur moyenne (r, v, b) de l'avatar autour de la position."""
    x, y = position
    with mss.MSS() as captureur:
        image = captureur.grab({"left": x - AVATAR_RAYON, "top": y - AVATAR_RAYON,
                                "width": 2 * AVATAR_RAYON, "height": 2 * AVATAR_RAYON})
    pixels = image.rgb
    nombre_pixels = len(pixels) // 3
    return tuple(round(sum(pixels[i::3]) / nombre_pixels) for i in range(3))


def ecart_couleurs(a, b):
    def part(couleur):
        total = sum(couleur) or 1
        return [composante / total for composante in couleur]
    return sum((x - y) ** 2 for x, y in zip(part(a), part(b))) ** 0.5


def decrire_compte(reglage):
    texte = f"packs {', '.join(reglage.get('rotation', []))}"
    if reglage.get("chasse"):
        texte += f", chasse à {decrire_chasse(reglage['chasse'])}"
    capacite = reglage.get("capacite", 0)
    texte += f", compteur /{capacite}" if capacite else ", compteur lu tout seul"
    return texte


def demander_capacite(defaut):
    """Capacité du compteur d'un compte : 0 (lue toute seule), 10, 20…"""
    print("Compteur de ce compte : 0 = lu tout seul (conseillé), 10 = sans abonnement,")
    print("20 = abonnement +10 de capacité (compteur « x/20 »).")
    while True:
        reponse = demander(f"Capacité du compteur pour ce compte (Entrée = {defaut}) : ")
        if not reponse:
            return defaut
        if reponse.isdigit() and int(reponse) in (0, 10, 20, 30, 40, 50):
            return int(reponse)
        print("Réponds 0, 10 ou 20.")


def ajouter_compte(texte):
    packs, comptes = lire(texte, "PACKS"), lire(texte, "COMPTES") or {}
    avatar = lire(texte, "AVATAR", (0, 0))
    print("Dans le navigateur, connecte-toi sur le compte voulu (page d'accueil).")
    print("Pose la souris au centre de son avatar (en haut à droite) et appuie")
    print("sur G.   Échap = annuler")
    if attendre_touche() != TOUCHE_G:
        vider_clavier_terminal()
        print("Annulé.\n")
        return texte
    position = tuple(pyautogui.position())
    couleur = couleur_sous(position)
    print(f"   -> avatar en {texte_position(position)}, couleur {couleur}")
    if (comptes and tuple(avatar) != (0, 0)
            and max(abs(position[0] - avatar[0]), abs(position[1] - avatar[1])) > 15):
        print("   Attention : l'avatar n'est plus au même endroit que pour les autres")
        print("   comptes. Refais-les aussi (choix 1, connecté sur chacun).")

    # Compte déjà enregistré avec cette couleur : proposé par défaut.
    proche = min(((ecart_couleurs(couleur, r["couleur"]), nom) for nom, r in comptes.items()),
                 default=None)
    defaut = proche[1] if proche and proche[0] <= ECART_COMPTE_MAX else ""
    nom = demander("Nom de ce compte (ex. principal, logo)"
                   + (f" (Entrée = {defaut})" if defaut else "") + " : ", defaut)
    if not nom:
        print("Pas de nom : annulé.\n")
        return texte
    nom = {connu.lower(): connu for connu in comptes}.get(nom.lower(), nom)
    for autre, reglage in comptes.items():
        if autre != nom and ecart_couleurs(couleur, reglage["couleur"]) < 2 * ECART_COMPTE_MAX:
            print(f"   Attention : avatar de couleur proche de « {autre} » : les deux "
                  "risquent d'être confondus.")

    ancien = comptes.get(nom, {})
    rotation = ancien.get("rotation") or lire(texte, "ROTATION")
    afficher_boosters(packs)
    while True:
        reponse = demander("Packs à ouvrir pour ce compte, dans l'ordre (numéros ou noms"
                           + (f" ; Entrée = {', '.join(rotation)}" if rotation else "") + ") : ")
        if reponse and not est_commande(reponse):
            rotation = liste_packs(reponse, packs)
        if rotation:
            break
        print("Choisis au moins un pack (par exemple 1).")
    ajouter_packs(packs, rotation)
    print("Chasse à une carte pour ce compte : la carte est cherchée à chaque")
    print("ouverture de son pack ; une fois obtenue, le compte passe à ses packs.")
    chasse = demander_chasse(packs, ancien.get("chasse"), rotation)
    proposer_reprise(chasse, nom)
    capacite = demander_capacite(ancien.get("capacite", lire(texte, "CAPACITE_MAX", 0)))

    comptes[nom] = {"couleur": couleur, "rotation": rotation, "chasse": chasse,
                    "capacite": capacite}
    texte = ecrire_packs(texte, packs)
    texte = remplacer(texte, "AVATAR", position)
    if not lire(texte, "ROTATION"):
        # Packs d'un compte non reconnu : ceux du premier compte.
        texte = remplacer(texte, "ROTATION", rotation)
    print(f"Compte « {nom} » : {decrire_compte(comptes[nom])}.")
    print("Autre compte : change de compte dans le navigateur, puis choix 1 à nouveau.\n")
    return remplacer(texte, "COMPTES", comptes)


def action_comptes(texte):
    while True:
        comptes = lire(texte, "COMPTES") or {}
        print("=== Comptes (plusieurs comptes Kyara sur ce navigateur) ===")
        print("Le compte connecté est reconnu à la couleur de son avatar, et chaque")
        print("compte a ses packs, sa chasse et son compteur (abonné ou non).")
        print("À faire une fois par compte.")
        for nom, reglage in comptes.items():
            print(f"   - {nom} : {decrire_compte(reglage)}")
        if not comptes:
            print("   Aucun compte : les mêmes packs pour tout le monde.")
        print("   1  Ajouter ou modifier le compte connecté")
        if comptes:
            print("   2  Supprimer un compte")
            print("   3  Ne plus utiliser les comptes")
        print("   Entrée  retour au menu")
        choix = demander("Choix : ")
        if choix == "1":
            texte = ajouter_compte(texte)
        elif choix == "2" and comptes:
            nom = demander(f"Compte à supprimer ({', '.join(comptes)}) : ")
            nom = {connu.lower(): connu for connu in comptes}.get(nom.lower())
            if nom:
                del comptes[nom]
                texte = remplacer(texte, "COMPTES", comptes or None)
                print(f"Compte « {nom} » supprimé.\n")
            else:
                print("Compte inconnu.\n")
        elif choix == "3" and comptes:
            if oui("Supprimer tous les comptes ?"):
                texte = remplacer(texte, "COMPTES", None)
                print("Comptes supprimés : mêmes packs pour tout le monde.\n")
        else:
            print()
            return texte


# ============================================================
# 6. ÉTAPES DE L'OUVERTURE
# ============================================================
# Rang de l'attente dans chaque type d'étape.
RANG_ATTENTE = {"pack": 1, "clic": 3, "double_clic": 3, "tout_reveler": 2, "attendre": 1}


def decrire_etape(etape):
    action = etape[0]
    if action == "pack":
        return "clic sur le pack choisi (selon la rotation)"
    if action in ("clic", "double_clic"):
        sorte = "clic" if action == "clic" else "double-clic"
        return f"{sorte} « {etape[1]} » en {texte_position(etape[2])}"
    if action == "tout_reveler":
        return f"Tout révéler (cherché à l'écran, secours {texte_position(etape[1])})"
    if action == "lire_cartes":
        return "lecture des cartes retournées (chasse + capture)"
    if action == "attendre":
        return "pause"
    return f"étape inconnue « {action} »"


def numero(texte, sequence, fin=False):
    rang = int(texte) - 1
    if not 0 <= rang < len(sequence) + (1 if fin else 0):
        raise ValueError("numéro inexistant")
    return rang


def ajouter_etape(sequence):
    print("Type d'étape :  1 clic   2 double-clic   3 pause   4 Tout révéler")
    print("                5 lecture des cartes   6 clic sur le pack choisi")
    sorte = demander("Type : ")
    if sorte in ("1", "2"):
        nom = demander("Nom du bouton (affiché dans le terminal) : ")
        if not nom:
            return
        attente = nombre(demander("Attente après le clic, en secondes (Entrée = 2) : ", "2"))
        etape = ("clic" if sorte == "1" else "double_clic", nom, (0, 0), attente)
    elif sorte == "3":
        etape = ("attendre", nombre(demander("Durée de la pause, en secondes : ")))
    elif sorte == "4":
        etape = ("tout_reveler", (0, 0), 3)
    elif sorte == "5":
        etape = ("lire_cartes",)
    elif sorte == "6":
        etape = ("pack", 2)
    else:
        print("Type inconnu.")
        return
    place = demander(f"Place dans la liste (1 à {len(sequence) + 1}, Entrée = à la fin) : ")
    rang = numero(place, sequence, fin=True) if place else len(sequence)
    sequence.insert(rang, etape)
    if (0, 0) in etape:
        print("Sa position sera demandée avec G.")


def action_etapes(texte):
    sequence = [tuple(etape) for etape in lire(texte, "SEQUENCE")]
    while True:
        print("=== Étapes de l'ouverture (faites quand le compteur est plein, dans l'ordre) ===")
        for rang, etape in enumerate(sequence, 1):
            attente = (f", puis {etape[RANG_ATTENTE[etape[0]]]} s"
                       if etape[0] in RANG_ATTENTE else "")
            print(f"   {rang:>2}  {decrire_etape(etape)}{attente}")
        print("Commandes :   a = ajouter une étape      s 3 = supprimer l'étape 3")
        print("              t 3 5 = attente de 5 s après l'étape 3")
        print("              d 3 1 = déplacer l'étape 3 en 1re place")
        print("              Entrée = terminer")
        commande = demander("Commande : ").lower().split()
        if not commande:
            break
        try:
            if commande[0] == "a":
                ajouter_etape(sequence)
            elif commande[0] == "s":
                print(f"Supprimée : {decrire_etape(sequence.pop(numero(commande[1], sequence)))}")
            elif commande[0] == "t":
                rang = numero(commande[1], sequence)
                etape = list(sequence[rang])
                etape[RANG_ATTENTE[etape[0]]] = nombre(commande[2])
                sequence[rang] = tuple(etape)
            elif commande[0] == "d":
                etape = sequence.pop(numero(commande[1], sequence))
                sequence.insert(numero(commande[2], sequence, fin=True), etape)
            else:
                print("Commande inconnue.")
        except (IndexError, ValueError, KeyError):
            print("Commande mal écrite, numéro inexistant ou étape sans attente.")
        print()
    if not any(etape[0] == "pack" for etape in sequence):
        print("Attention : aucune étape « clic sur le pack choisi » : aucun pack ne")
        print("sera cliqué.")
    print()
    return remplacer(texte, "SEQUENCE", sequence)


# ============================================================
# 7. RÉGLAGES
# ============================================================
# (nom, description, valeur par défaut ; None = aucune).
REGLAGES = (
    ("NOM", "nom affiché dans le terminal (différent pour chaque script)", None),
    ("EXECUTABLE", "programme du navigateur, ex. opera.exe (détecté avec les positions)", None),
    ("INTERVALLE", "pause entre deux lectures du compteur, en secondes", 2),
    ("LECTURES_STABLES", "lectures « compteur plein » d'affilée avant d'ouvrir", 2),
    ("CAPACITE_MAX", "capacité max du compteur de boosters : 0 = lue toute seule sur "
                     "le compteur (conseillé), 10 = sans abonnement, 20 = abonnement "
                     "+10 de capacité (pour les comptes sans réglage à eux : "
                     "menu Comptes)", 0),
    ("PAUSE_APRES_OUVERTURE", "pause après une ouverture, en secondes", 5),
    ("INTERVALLE_POPUP", "délai maximum entre deux vérifications du popup, en secondes", 10),
    ("DUREE_MOUVEMENT", "durée d'un mouvement de souris en secondes, min et max : la souris "
                        "glisse jusqu'au bouton (plus grand = plus lent, minimum 0,3)",
     (0.5, 0.9)),
    ("ARRET_COIN_ECRAN", "souris tout en haut à gauche = arrêt d'urgence (o/n)", True),
)
DUREE_MIN_MOUVEMENT = 0.3


def convertir(reponse, actuelle, nom):
    """Valeur tapée -> valeur du même type que l'actuelle (ValueError sinon)."""
    if isinstance(actuelle, bool):
        if reponse.lower().startswith(("o", "y")):
            return True
        if reponse.lower().startswith("n"):
            return False
        raise ValueError("répondre o ou n")
    if isinstance(actuelle, str):
        valeur = reponse.strip('"').strip()
        if nom == "EXECUTABLE":
            valeur = valeur.lower()
            if not valeur.endswith(".exe"):
                valeur += ".exe"
        if not valeur:
            raise ValueError("valeur vide")
        return valeur
    if isinstance(actuelle, (tuple, list)):
        # « 0,5 ; 0,9 » ou « 0.5 0.9 » (virgule décimale) ou « 0.5, 0.9 ».
        morceaux = (re.split(r"[;\s]+", reponse) if re.search(r"[;\s]", reponse)
                    else reponse.split(","))
        valeurs = tuple(nombre(morceau) for morceau in morceaux if morceau)
        if len(valeurs) != len(actuelle):
            raise ValueError(f"{len(actuelle)} nombres attendus")
        if nom == "DUREE_MOUVEMENT":
            if valeurs[0] < DUREE_MIN_MOUVEMENT:
                raise ValueError(f"trop rapide : au moins {afficher_valeur(DUREE_MIN_MOUVEMENT)}")
            if valeurs[1] < valeurs[0]:
                raise ValueError("le max doit être au moins égal au min")
        return valeurs
    valeur = nombre(reponse)
    if isinstance(actuelle, int) and not isinstance(valeur, int):
        raise ValueError("nombre entier attendu")
    if valeur == 0 and nom == "LECTURES_STABLES":
        raise ValueError("au moins 1")
    if nom == "CAPACITE_MAX" and valeur not in (0, 10, 20, 30, 40, 50):
        raise ValueError("0 (automatique), 10, 20, 30, 40 ou 50")
    return valeur


def afficher_valeur(valeur):
    if isinstance(valeur, bool):
        return "o" if valeur else "n"
    if isinstance(valeur, (tuple, list)):
        return " ; ".join(afficher_valeur(v) for v in valeur)
    if isinstance(valeur, float):
        return str(valeur).replace(".", ",")
    return str(valeur)


def action_reglages(texte):
    print("=== Réglages ===")
    print("Par défaut : ceux des scripts d'origine (souris qui glisse en 0,5 à")
    print("0,9 seconde, jamais de saut d'un coup).")
    if oui("Tout remettre par défaut d'un coup ?"):
        for nom, _, defaut in REGLAGES:
            if defaut is not None and affectation(texte, nom) is not None:
                texte = remplacer(texte, nom, defaut)
        print("Réglages remis par défaut (le nom et le navigateur sont gardés).\n")
        return texte

    print("Pour chaque réglage :   Entrée = garder    d = valeur par défaut")
    for nom, description, defaut in REGLAGES:
        if affectation(texte, nom) is None:
            continue
        actuelle = lire(texte, nom)
        par_defaut = "" if defaut is None else f"   (défaut : {afficher_valeur(defaut)})"
        reponse = demander(f"\n{description}\n   {nom} = {afficher_valeur(actuelle)}"
                           f"{par_defaut}  -> ")
        if not reponse:
            continue
        if reponse.lower() == "d" and defaut is not None:
            valeur = defaut
        else:
            try:
                valeur = convertir(reponse, actuelle, nom)
            except ValueError as erreur:
                print(f"   Refusé ({erreur}) : valeur gardée.")
                continue
        texte = remplacer(texte, nom, valeur)
        print(f"   {nom} = {afficher_valeur(valeur)}")
    print()
    return texte


# ============================================================
# 8. REMISE À ZÉRO
# ============================================================
DEBUT_SECTION = "# ---------- 1."
FIN_SECTION = "# ============================================================\n# FIN DE LA CONFIGURATION"


def positions_a_zero(texte):
    """Toutes les positions à (0, 0), réglages de molette retirés."""
    for debut, fin, _, _, molette in sorted(trouver_elements(texte, tous=True), reverse=True):
        if molette:
            texte = texte[:molette[0]] + texte[molette[1]:]
        texte = texte[:debut] + NON_DEFINIE + texte[fin:]
    return texte


def fichiers_crees(nom):
    """Fichiers créés en fonctionnement : captures debug et chasses terminées."""
    motifs = ((DOSSIER_DEBUG, f"debug_{nom}.png"), (DOSSIER_DEBUG, f"debug_{nom}_*.png"),
              (DOSSIER_DEBUG, f"debug_popup_{nom}.png"),
              (DOSSIER_CHASSES, "chasse_*.txt"), (DOSSIER_CHASSES, "chasse_*.png"))
    return sorted({chemin for dossier, motif in motifs for chemin in dossier.glob(motif)})


def mode_reset(fichier):
    original = fichier.read_text(encoding="utf-8")
    print(f"=== Remise à zéro de {fichier.name} ===")
    print("   1  Coordonnées à zéro : toutes les positions passent à (0, 0) et les")
    print("      réglages de molette sont retirés. Packs, rotation, chasse, comptes")
    print("      et réglages sont gardés. À replacer ensuite (menu 3).")
    print("   2  Tout à zéro : toute la configuration (packs choisis, chasse,")
    print("      comptes, positions, étapes, réglages) revient à celle d'un fichier")
    print("      neuf : aucun pack choisi, positions à (0, 0). Gardés : le nom,")
    print("      le navigateur et son écran.")
    print("   Entrée  annuler")
    choix = demander("Choix : ")

    if choix == "1":
        try:
            nouveau = positions_a_zero(original)
        except (SyntaxError, ValueError):
            print("Configuration illisible : utilise plutôt le choix 2.")
            return
        resume = "Coordonnées remises à (0, 0)."
    elif choix == "2":
        debut, fin = original.find(DEBUT_SECTION), original.find(FIN_SECTION)
        if debut < 0 or fin < debut:
            print("Partie configuration introuvable (repères effacés ?) : rien n'est fait.")
            print("Reprends une copie neuve de kyara_booster.py.")
            return
        nouveau = original[:debut] + CONFIGURATION_DEFAUT + original[fin:]
        # Gardés : le nom (unique par script), le navigateur et son écran.
        gardes = []
        for motif in (MOTIF_NOM, MOTIF_EXECUTABLE, MOTIF_ZONE):
            actuel = motif.search(original[debut:fin])
            if actuel:
                nouveau = motif.sub(lambda _: actuel[0], nouveau, count=1)
                gardes.append(actuel[0])
        resume = ("Configuration remise à zéro"
                  + (f" (gardés : {', '.join(gardes)})" if gardes else "") + ".")
    else:
        print("Annulé : rien n'a changé.\n")
        return

    compile(nouveau, str(fichier), "exec")  # sécurité : le script reste valide
    if not oui(f"{resume.rstrip('.')} : confirmer ?"):
        print("Annulé : rien n'a changé.\n")
        return
    sauvegarde = chemin_sauvegarde(fichier)
    sauvegarde.write_text(original, encoding="utf-8")
    fichier.write_text(nouveau, encoding="utf-8")
    print(f"{resume} Ancienne version : sauvegardes\\{sauvegarde.name}.")

    nom = MOTIF_NOM.search(nouveau)
    crees = fichiers_crees(nom["val"]) if nom else []
    if crees:
        print(f"\nFichiers créés pendant le fonctionnement ({len(crees)}) :")
        for chemin in crees:
            print(f"   {chemin.parent.name}\\{chemin.name}")
        print("Les supprimer efface aussi les chasses terminées (elles reprennent).")
        if oui("Les supprimer ?"):
            for chemin in crees:
                chemin.unlink(missing_ok=True)
            print("Supprimés.")
    print("\nÀ l'ouverture, configurer_positions.py demandera ce qui est à refaire.\n")


# ============================================================
# CHOIX DU SCRIPT (un par navigateur)
# ============================================================
def etat(texte):
    """« prêt » ou « il manque N réglage(s) »."""
    try:
        nombre_manques = len(manques(mettre_en_forme(texte)))
    except (SyntaxError, ValueError, TypeError, AttributeError):
        return "configuration illisible"
    return f"il manque {nombre_manques} réglage(s)" if nombre_manques else "prêt"


def scripts_du_dossier():
    """Scripts de booster du dossier : (fichier, NOM, EXECUTABLE, état)."""
    scripts = []
    for fichier in sorted(DOSSIER.glob("kyara_booster*.py")):
        texte = fichier.read_text(encoding="utf-8", errors="replace")
        nom, executable = MOTIF_NOM.search(texte), MOTIF_EXECUTABLE.search(texte)
        if nom:
            scripts.append((fichier, nom["val"],
                            executable and executable["val"].strip('"') or "à détecter",
                            etat(texte)))
    return scripts


def creer_script(noms_pris):
    """Copie de kyara_booster.py pour un autre navigateur, configuration vide."""
    if not FICHIER_PAR_DEFAUT.exists():
        print(f"{FICHIER_PAR_DEFAUT.name} introuvable : impossible d'en faire une copie.")
        return None
    print("Nom du nouveau script, par exemple celui du navigateur :")
    print("   brave, chrome, edge, firefox, opera2…")
    nom = re.sub(r"[^a-z0-9_-]", "", demander("Nom : ").lower().replace(" ", "_"))
    fichier = DOSSIER / f"kyara_booster_{nom}.py"
    if not nom:
        print("Nom vide : annulé.")
        return None
    if nom in {pris.lower() for pris in noms_pris} or fichier.exists():
        print(f"« {nom} » est déjà utilisé : choisis un autre nom.")
        return None

    texte = FICHIER_PAR_DEFAUT.read_text(encoding="utf-8")
    debut, fin = texte.find(DEBUT_SECTION), texte.find(FIN_SECTION)
    if debut < 0 or fin < debut:
        print(f"Partie configuration de {FICHIER_PAR_DEFAUT.name} introuvable : annulé.")
        return None
    # Le code de kyara_booster.py, avec une configuration neuve (tout à zéro).
    texte = texte[:debut] + CONFIGURATION_DEFAUT + texte[fin:]
    texte = MOTIF_NOM.sub(lambda _: f'NOM = "{nom}"', texte, count=1)
    compile(texte, str(fichier), "exec")
    fichier.write_text(texte, encoding="utf-8")
    print(f"Créé : {fichier.name} (NOM « {nom} », tout est à régler).")
    print("Pour les positions, pose la souris sur CE navigateur : il est détecté")
    print("tout seul, avec son écran.")
    print(f"Pour le lancer ensuite : python {fichier.name}\n")
    return fichier


def choisir_script():
    """Demande quel script (donc quel navigateur) configurer."""
    scripts = scripts_du_dossier()
    print("=== Script à configurer ===")
    print("Un script par navigateur. Lequel configurer ?")
    for rang, (fichier, nom, executable, etat_script) in enumerate(scripts, 1):
        print(f"   {rang}  {fichier.name:<28} navigateur : {executable:<12} ({etat_script})")
    nouveau = len(scripts) + 1
    print(f"   {nouveau}  Nouveau script pour un autre navigateur")
    reponse = demander("Choix (Entrée = 1) : ", "1")
    print()
    if reponse.isdigit() and 1 <= int(reponse) <= len(scripts):
        return scripts[int(reponse) - 1][0]
    if reponse == str(nouveau):
        return creer_script([nom for _, nom, _, _ in scripts])
    print("Choix inconnu : annulé.")
    return None


# ============================================================
# MENU
# ============================================================
ACTIONS = {
    "1": ("Tout configurer : packs puis positions (conseillé la 1re fois)", action_tout),
    "2": ("Packs et rotation (lesquels ouvrir, dans quel ordre)", action_packs),
    "3": ("Positions (souris + touche G)", action_positions),
    "4": ("Chasse à une carte", action_chasse),
    "5": ("Comptes (plusieurs comptes Kyara sur ce navigateur)", action_comptes),
    "6": ("Étapes de l'ouverture (ajouter, supprimer, attentes)", action_etapes),
    "7": ("Réglages (nom, navigateur, pauses, vitesse de la souris…)", action_reglages),
    "8": ("Remise à zéro (coordonnées ou tout)", None),
    "9": ("Mode libre (afficher / copier une position)", None),
}


def resume(fichier, texte):
    comptes = lire(texte, "COMPTES")
    print(f"--- {fichier.name} : NOM « {lire(texte, 'NOM')} », "
          f"navigateur {lire(texte, 'EXECUTABLE') or 'à détecter'}   |   {etat(texte)}")
    print(f"    Packs à ouvrir : {', '.join(lire(texte, 'ROTATION')) or 'aucun'}"
          f"   |   Chasse : {decrire_chasse(lire(texte, 'CHASSE'))}")
    print(f"    Comptes : {', '.join(comptes) if comptes else 'aucun'}")


def menu(fichier):
    session = Session(fichier)
    try:
        session.enregistrer(mettre_en_forme(session.texte))
    except (SyntaxError, ValueError, TypeError, AttributeError) as erreur:
        print(f"La configuration de {fichier.name} est illisible ({erreur}).")
        print("Corrige-la dans le fichier, ou remets-la par défaut :")
        mode_reset(fichier)
        return

    if afficher_manques(session.texte):
        if oui("On les règle maintenant ?", defaut=True):
            print()
            session.enregistrer(completer(session.texte))
        else:
            print()

    while True:
        resume(fichier, session.texte)
        for touche, (libelle, _) in ACTIONS.items():
            print(f"   {touche}  {libelle}")
        choix = demander("Choix (Entrée = quitter) : ")
        print()
        if not choix:
            break
        if choix not in ACTIONS:
            print("Choix inconnu.\n")
            continue
        if choix == "8":
            mode_reset(fichier)
            session = Session(fichier)
            session.enregistrer(mettre_en_forme(session.texte))
            continue
        if choix == "9":
            mode_libre()
            continue

        session.enregistrer(ACTIONS[choix][1](session.texte))
        if choix not in ("1", "3") and afficher_manques(session.texte, "Il manque encore :"):
            if oui("On les règle maintenant ?", defaut=True):
                print()
                session.enregistrer(completer(session.texte))

    if afficher_manques(session.texte, "Attention, il manque encore :"):
        print("Le script refusera de démarrer tant que ce n'est pas réglé.")
        print("Relance  python configurer_positions.py  : il le demandera.")
    if session.texte != session.original:
        print(f"Relance le script pour qu'il prenne la nouvelle configuration :")
        print(f"   python {fichier.name}")


def main():
    arguments = sys.argv[1:]
    if "libre" in arguments:
        mode_libre()
        return
    reset = "reset" in arguments
    arguments = [argument for argument in arguments if argument != "reset"]
    fichier = Path(arguments[0]) if arguments else choisir_script()
    if fichier is None:
        return
    if not fichier.is_absolute():
        fichier = DOSSIER / fichier
    if not fichier.exists():
        print(f"Fichier introuvable : {fichier}")
        return
    if reset:
        mode_reset(fichier)
    else:
        menu(fichier)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        vider_clavier_terminal()
        print("\nArrêté.")
