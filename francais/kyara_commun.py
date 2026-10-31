"""
Outils utilisés par kyara_booster.py : capture, lecture du compteur 10/10,
détection du popup de présence, clics. Rien à régler ici : toute la
configuration est en haut de kyara_booster.py.
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

from coordination import demander_tour, signaler_compteur, terminer_tour


CHEMIN_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

if not CHEMIN_TESSERACT.exists():
    raise FileNotFoundError(f"Tesseract introuvable : {CHEMIN_TESSERACT}")

pytesseract.pytesseract.tesseract_cmd = str(CHEMIN_TESSERACT)

DOSSIER_SCRIPT = Path(__file__).resolve().parent
# Fichiers créés en fonctionnement, rangés à part des scripts : captures de
# contrôle (remplacées à chaque fois) et chasses terminées.
DOSSIER_DEBUG = DOSSIER_SCRIPT / "debug"
DOSSIER_CHASSES = DOSSIER_SCRIPT / "chasses"
DOSSIER_DEBUG.mkdir(exist_ok=True)
DOSSIER_CHASSES.mkdir(exist_ok=True)

# Déplacement du curseur : durée (en secondes) tirée au hasard dans cet
# intervalle, avec accélération puis ralentissement. Augmenter pour ralentir.
DUREE_MOUVEMENT = (0.5, 0.9)
# En dessous, le curseur sauterait presque d'un coup : jamais plus rapide.
DUREE_MIN_MOUVEMENT = 0.3
# Petite pause une fois arrivé sur la cible, avant le clic.
PAUSE_AVANT_CLIC = 0.15

# Affiche chaque passe OCR (utile pour régler les zones).
OCR_VERBEUX = False

# --- Méthode principale : comparaison des glyphes (sans OCR) ---
# La police du compteur est à chasse fixe : « 10/10 » donne 5 glyphes dont les
# deux premiers sont identiques aux deux derniers ; « 9/10 » n'en donne que 4.
# Écart max (pixels) entre deux glyphes d'un même texte ; au-delà, c'est
# l'indicateur coloré à gauche ou un autre élément d'interface.
ECART_MAX_GLYPHES = 3
# Ressemblance (corrélation des niveaux de gris, -1 à 1) de deux glyphes,
# mesurée sur les vraies captures : un même chiffre donne 0.87 à 1.00, deux
# chiffres différents 0.74 au plus (« 1 » et « 2 » ; « 6 » et zéro barré :
# 0.70). Au moins SIMILARITE_MEME : même chiffre. Moins de
# SIMILARITE_DIFFERENTE : chiffres différents. Entre les deux : doute, OCR.
SIMILARITE_MEME = 0.82
SIMILARITE_DIFFERENTE = 0.78
# Seuils essayés tour à tour (au-dessus d'Otsu) : un seuil plus strict
# sépare les glyphes collés par l'anticrénelage (« 6/ » ou « 10 »).
DURCISSEMENTS_SEUIL = (0, 30, 60)

# --- Méthode de secours : OCR avec vote ---
# Compteur plein : le nombre avant le « / » est le même qu'après (10/10, ou
# 20/20 avec un abonnement qui ajoute 10 de capacité). Le zéro barré de la
# police est souvent lu « 6 », « 8 » ou « 9 » : 16/16 vaut donc 10/10.
# Sans barre (lue « 1 », « 7 » ou perdue), la lecture compte pour une demi-voix.
MOTIF_LECTURE = re.compile(r"(\d{2})/(\d{2})")
MOTIF_LECTURE_SANS_BARRE = re.compile(r"(\d{2})[17]?(\d{2})")
# Capacités possibles, pour reconnaître le dénominateur lu (« 20 » de « 3/20 ») :
# 10, 20 avec un abonnement, 15 et 25 avec le bonus d'un événement…
CAPACITES_POSSIBLES = tuple(range(10, 55, 5))
CONFIG_OCR = "-c tessedit_char_whitelist=0123456789/"
PSM_OCR = (7, 6)
DECALAGES_SEUIL = (0, -30, 30)

# Sans changement, la valeur du compteur est réaffichée toutes les N secondes.
AFFICHAGE_PERIODIQUE = 60

# Recalage : si le compteur est illisible N fois de suite, il est recherché
# dans une bande de cette taille autour de la position prévue.
ILLISIBLES_AVANT_RECALAGE = 2
DELAI_ENTRE_RECALAGES = 10
# « Compteur introuvable » n'est réaffiché qu'une fois toutes les N secondes.
RAPPEL_INTROUVABLE = 300

DETAIL_UNIFORME = "image uniforme"


def nombre_lu(texte):
    """« 16 » -> « 10 » : le zéro barré (2e chiffre) lu 6, 8 ou 9 redevient 0."""
    return texte[0] + ("0" if texte[1] in "0689" else texte[1])


def voix_plein(compact, capacite=0):
    """
    Voix d'une lecture OCR pour « compteur plein » : 1, 0.5 sans barre, sinon 0.
    capacite = 0 : n'importe quel nombre, le même des deux côtés.
    """
    for motif, voix in ((MOTIF_LECTURE, 1), (MOTIF_LECTURE_SANS_BARRE, 0.5)):
        m = motif.fullmatch(compact)
        if not m:
            continue
        numerateur, denominateur = nombre_lu(m[1]), nombre_lu(m[2])
        if (numerateur == denominateur and int(numerateur) in CAPACITES_POSSIBLES
                and (not capacite or int(numerateur) == capacite)):
            return voix
    return 0
LARGEUR_RECHERCHE = 600
HAUTEUR_RECHERCHE = 75

# Score à atteindre pour arrêter les passes OCR plus tôt.
SCORE_DECISIF = 3
SCORE_MIN = 2


# ============================================================
# CAPTURE
# ============================================================
_captureur = None


def capturer_zone(region):
    """
    Capture (x, y, largeur, hauteur) en coordonnées écran (négatives comprises).
    La fenêtre du navigateur est lue directement, même si une autre fenêtre
    passe devant ; sinon, c'est l'écran qui est capturé.
    """
    global _captureur
    x, y, largeur, hauteur = (int(v) for v in region)

    if _fenetre is not None:
        image = _fenetre.capturer((x, y, largeur, hauteur))
        if image is not None:
            return image

    if _captureur is None:
        _captureur = mss.MSS()
    capture = _captureur.grab(
        {"left": x, "top": y, "width": largeur, "height": hauteur}
    )
    return Image.frombytes("RGB", capture.size, capture.rgb)


# ============================================================
# FENÊTRE DU NAVIGATEUR
# ============================================================
# La fenêtre est lue avec PrintWindow : le script la voit même cachée
# derrière Discord ou une autre fenêtre. Pour cliquer, elle passe au premier
# plan le temps de l'action, puis les fenêtres sont remises comme avant.
EXECUTABLES = {"brave": "brave.exe", "opera": "opera.exe"}
# Fenêtre perdue (fermée, réduite) : nouvelle recherche toutes les N secondes.
DELAI_RECHERCHE_FENETRE = 10
# Une capture de la fenêtre resert pendant N secondes (compteur + popup).
DUREE_CACHE_FENETRE = 0.25
# Part minimale de l'écran que la fenêtre doit couvrir pour être suivie
# (sa bordure invisible dépasse de quelques pixels sur l'écran voisin).
PART_ECRAN_MIN = 0.25

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


class _EnteteBitmap(ctypes.Structure):
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


def _processus(hwnd):
    pid = wt.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _executable(pid):
    poignee = _kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not poignee:
        return ""
    try:
        tampon = ctypes.create_unicode_buffer(512)
        taille = wt.DWORD(512)
        if _kernel32.QueryFullProcessImageNameW(poignee, 0, tampon, ctypes.byref(taille)):
            return os.path.basename(tampon.value).lower()
        return ""
    finally:
        _kernel32.CloseHandle(poignee)


def _affichee(hwnd):
    """Fenêtre réellement visible à l'écran (ni réduite, ni masquée par Windows)."""
    if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
        return False
    masquee = ctypes.c_int(0)
    _dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(masquee), ctypes.sizeof(masquee)
    )
    return not masquee.value


def _intersection(a, b):
    largeur = min(a[2], b[2]) - max(a[0], b[0])
    hauteur = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, largeur) * max(0, hauteur)


def _activer(hwnd):
    """Redonne le focus clavier à une fenêtre (au mieux : Windows peut refuser)."""
    actuelle = _user32.GetForegroundWindow()
    if not hwnd or actuelle == hwnd or not _user32.IsWindow(hwnd):
        return
    fil_actuel = _user32.GetWindowThreadProcessId(actuelle, None) if actuelle else 0
    mon_fil = _kernel32.GetCurrentThreadId()
    attache = bool(fil_actuel) and fil_actuel != mon_fil and _user32.AttachThreadInput(
        mon_fil, fil_actuel, True
    )
    try:
        _user32.SetForegroundWindow(hwnd)
    finally:
        if attache:
            _user32.AttachThreadInput(mon_fil, fil_actuel, False)


class FenetreNavigateur:
    """Fenêtre du navigateur posée sur `zone` (l'écran où il est affiché)."""

    def __init__(self, navigateur, zone):
        self.prefixe = f"[{navigateur.upper()}]"
        self.executable = EXECUTABLES.get(navigateur, f"{navigateur}.exe")
        x, y, largeur, hauteur = zone
        self.zone = (x, y, x + largeur, y + hauteur)
        self.hwnd = None
        self._recherche = float("-inf")
        self._perdue_signalee = False
        self._image = None
        self._rect_image = None
        self._date_image = float("-inf")

    def _surface_sur_zone(self, hwnd):
        """Surface de la fenêtre sur son écran, 0 si elle en couvre trop peu."""
        rect = _rectangle(hwnd)
        surface = _intersection(rect, self.zone) if rect else 0
        aire_zone = (self.zone[2] - self.zone[0]) * (self.zone[3] - self.zone[1])
        return surface if surface >= PART_ECRAN_MIN * aire_zone else 0

    def _chercher(self):
        candidates = []

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def rappel(hwnd, _):
            if _affichee(hwnd) and _user32.GetWindowTextLengthW(hwnd):
                surface = self._surface_sur_zone(hwnd)
                if surface and _executable(_processus(hwnd)) == self.executable:
                    candidates.append((surface, hwnd))
            return True

        _user32.EnumWindows(rappel, 0)
        return max(candidates)[1] if candidates else None

    def handle(self):
        """La fenêtre suivie, ou None si elle est fermée ou réduite."""
        if self.hwnd and _user32.IsWindow(self.hwnd) and _affichee(self.hwnd):
            if self._surface_sur_zone(self.hwnd):
                return self.hwnd
            # Déplacée sur un autre écran : comme perdue, elle sera recherchée.
            print(f"{self.prefixe} La fenêtre a quitté son écran.")
            self.hwnd = None
            self._perdue_signalee = False
            self._recherche = float("-inf")
        if time.monotonic() - self._recherche < DELAI_RECHERCHE_FENETRE:
            return None
        self._recherche = time.monotonic()

        self.hwnd = self._chercher()
        if self.hwnd:
            longueur = _user32.GetWindowTextLengthW(self.hwnd)
            titre = ctypes.create_unicode_buffer(longueur + 1)
            _user32.GetWindowTextW(self.hwnd, titre, longueur + 1)
            print(f"{self.prefixe} Fenêtre suivie : « {titre.value} » "
                  "(lue même si une autre fenêtre passe devant).")
            self._perdue_signalee = False
        elif not self._perdue_signalee:
            print(f"{self.prefixe} Fenêtre {self.executable} introuvable sur son écran "
                  "(fermée ou réduite ?) : capture de l'écran à la place.")
            self._perdue_signalee = True
        return self.hwnd

    def _capturer_fenetre(self, hwnd):
        rect = _rectangle(hwnd)
        if not rect:
            return None, None
        largeur, hauteur = rect[2] - rect[0], rect[3] - rect[1]
        if largeur <= 0 or hauteur <= 0:
            return None, None

        dc_fenetre = _user32.GetWindowDC(hwnd)
        dc_memoire = _gdi32.CreateCompatibleDC(dc_fenetre)
        bitmap = _gdi32.CreateCompatibleBitmap(dc_fenetre, largeur, hauteur)
        ancien = _gdi32.SelectObject(dc_memoire, bitmap)
        try:
            if not _user32.PrintWindow(hwnd, dc_memoire, PW_RENDERFULLCONTENT):
                return None, None
            entete = _EnteteBitmap()
            entete.biSize = ctypes.sizeof(entete)
            entete.biWidth, entete.biHeight = largeur, -hauteur
            entete.biPlanes, entete.biBitCount = 1, 32
            tampon = ctypes.create_string_buffer(largeur * hauteur * 4)
            _gdi32.GetDIBits(dc_memoire, bitmap, 0, hauteur, tampon, ctypes.byref(entete), 0)
        finally:
            _gdi32.SelectObject(dc_memoire, ancien)
            _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(dc_memoire)
            _user32.ReleaseDC(hwnd, dc_fenetre)

        image = Image.frombuffer(
            "RGBA", (largeur, hauteur), tampon, "raw", "BGRA", 0, 1
        ).convert("RGB")
        # Image toute noire : le navigateur n'a rien dessiné, l'écran fera mieux.
        if max(maxi for _, maxi in image.getextrema()) < 8:
            return None, None
        return image, rect

    def capturer(self, region):
        """Région (x, y, largeur, hauteur) de l'écran lue dans la fenêtre, ou None."""
        hwnd = self.handle()
        if not hwnd:
            return None
        if time.monotonic() - self._date_image > DUREE_CACHE_FENETRE:
            self._image, self._rect_image = self._capturer_fenetre(hwnd)
            self._date_image = time.monotonic()
        if self._image is None:
            return None

        x, y, largeur, hauteur = region
        resultat = Image.new("RGB", (largeur, hauteur))
        resultat.paste(self._image, (self._rect_image[0] - x, self._rect_image[1] - y))
        return resultat

    def sous_le_curseur(self, position):
        """Vrai si un clic à cette position tombe bien sur le navigateur."""
        hwnd = self.handle()
        if not hwnd:
            return True  # fenêtre inconnue : comportement d'avant, sans contrôle
        dessous = _user32.WindowFromPoint(wt.POINT(*position))
        racine = _user32.GetAncestor(dessous, GA_ROOT) if dessous else None
        return bool(racine) and _processus(racine) == _processus(hwnd)

    def _recouverte(self, hwnd):
        """Vrai si une fenêtre affichée au-dessus empiète sur le navigateur."""
        rect = _rectangle(hwnd)
        dessus = _user32.GetWindow(hwnd, GW_HWNDPREV)
        while dessus:
            if (
                _affichee(dessus)
                and not _user32.GetWindowLongW(dessus, GWL_EXSTYLE) & WS_EX_TRANSPARENT
            ):
                autre = _rectangle(dessus)
                if autre and _intersection(rect, autre):
                    return True
            dessus = _user32.GetWindow(dessus, GW_HWNDPREV)
        return False

    @contextmanager
    def premier_plan(self):
        """
        Passe le navigateur devant les autres fenêtres pendant l'action, puis
        remet l'ordre des fenêtres, le focus clavier et le curseur comme avant.
        Même visible, le navigateur prend le focus au clic : tout est donc
        remis dès qu'une autre fenêtre avait le focus, cachée ou non.
        """
        hwnd = self.handle()
        if not hwnd:
            yield
            return

        focus = _user32.GetForegroundWindow()
        recouverte = self._recouverte(hwnd)
        if not recouverte and focus and _processus(focus) == _processus(hwnd):
            yield  # le navigateur a déjà le focus : rien à remettre
            return

        au_dessus = _user32.GetWindow(hwnd, GW_HWNDPREV)
        curseur = pyautogui.position()
        drapeaux = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if recouverte:
            print(f"{self.prefixe} Fenêtre cachée : passage au premier plan le temps de l'action.")
            _user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, drapeaux)
            _user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, drapeaux)
            time.sleep(0.3)  # le temps que l'écran se redessine
        try:
            yield
        finally:
            if au_dessus and _user32.IsWindow(au_dessus):
                _user32.SetWindowPos(hwnd, au_dessus, 0, 0, 0, 0, drapeaux)
            _activer(focus)
            pyautogui.moveTo(*curseur, duration=0.3, tween=pyautogui.easeInOutQuad)
            print(f"{self.prefixe} Fenêtres remises comme avant.")


_fenetre = None


def suivre_fenetre(navigateur, zone):
    """Active la lecture directe de la fenêtre du navigateur pour ce script."""
    global _fenetre
    _fenetre = FenetreNavigateur(navigateur, zone)
    _fenetre.handle()
    return _fenetre


@contextmanager
def navigateur_au_premier_plan():
    if _fenetre is None:
        yield
    else:
        with _fenetre.premier_plan():
            yield


def ecran_eteint(zone):
    """Vrai si tout l'écran est noir (écran éteint, débranché, PC verrouillé)."""
    try:
        image = capturer_zone(zone)
    except Exception:
        return True
    gris = ImageOps.grayscale(image).reduce(8)
    stat = ImageStat.Stat(gris)
    return stat.stddev[0] < 2 and stat.mean[0] < 20


# ============================================================
# NORMALISATION
# ============================================================
def normaliser_texte(texte):
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


def seuil_otsu(image_grise):
    """Seuil de binarisation optimal (méthode d'Otsu) calculé sur l'histogramme."""
    histogramme = image_grise.histogram()
    total = sum(histogramme)
    somme_totale = sum(i * n for i, n in enumerate(histogramme))

    somme_fond = poids_fond = 0
    meilleur_seuil, meilleure_variance = 127, -1.0

    for i, n in enumerate(histogramme):
        poids_fond += n
        if poids_fond == 0:
            continue
        poids_texte = total - poids_fond
        if poids_texte == 0:
            break
        somme_fond += i * n
        moyenne_fond = somme_fond / poids_fond
        moyenne_texte = (somme_totale - somme_fond) / poids_texte
        variance = poids_fond * poids_texte * (moyenne_fond - moyenne_texte) ** 2
        if variance > meilleure_variance:
            meilleure_variance, meilleur_seuil = variance, i

    return meilleur_seuil


# ============================================================
# GLYPHES
# ============================================================
def segmenter_glyphes(image, durcissement=0, avec_position=False, avec_boites=False):
    """
    Découpe le texte du compteur en glyphes (matrices de booléens).
    Renvoie None si le découpage n'est pas net.

    durcissement : seuil plus strict que celui d'Otsu, pour effacer les
    pixels de demi-teinte qui collent deux glyphes voisins.
    avec_position : renvoie aussi le cadre du texte (x0, x1, y0, y1).
    avec_boites : renvoie aussi le cadre de chaque glyphe (x0, x1, y0, y1).
    """
    gris = ImageOps.grayscale(image)
    largeur, hauteur = gris.size
    seuil = seuil_otsu(gris)
    pixels = gris.load()

    clairs = sum(gris.histogram()[seuil + 1:])
    texte_clair = clairs < largeur * hauteur / 2

    if texte_clair:
        seuil_texte = min(254, seuil + durcissement)
        masque = [
            [pixels[x, y] > seuil_texte for x in range(largeur)]
            for y in range(hauteur)
        ]
    else:
        seuil_texte = max(1, seuil - durcissement)
        masque = [
            [pixels[x, y] <= seuil_texte for x in range(largeur)]
            for y in range(hauteur)
        ]
    colonnes = [sum(masque[y][x] for y in range(hauteur)) for x in range(largeur)]

    blocs = []
    x = 0
    while x < largeur:
        if colonnes[x]:
            debut = x
            while x < largeur and colonnes[x]:
                x += 1
            blocs.append((debut, x))
        else:
            x += 1

    groupes = []
    for bloc in blocs:
        if groupes and bloc[0] - groupes[-1][-1][1] <= ECART_MAX_GLYPHES:
            groupes[-1].append(bloc)
        else:
            groupes.append([bloc])

    if not groupes:
        return None

    # Le texte est le groupe qui a le plus de glyphes.
    groupe = max(groupes, key=lambda g: (len(g), g[-1][1] - g[0][0]))
    if not 3 <= len(groupe) <= 5:
        return None

    largeurs = sorted(fin - debut for debut, fin in groupe)
    mediane = largeurs[len(largeurs) // 2]

    # Deux glyphes collés (anticrénelage) : on coupe aux colonnes les plus vides.
    decoupe = []
    for debut, fin in groupe:
        nombre = round((fin - debut) / (mediane + 1))
        if (fin - debut) <= mediane * 1.6 or nombre < 2:
            decoupe.append((debut, fin))
            continue
        coupures = []
        for i in range(1, nombre):
            attendu = debut + (fin - debut) * i // nombre
            proches = range(max(debut + 1, attendu - 2), min(fin - 1, attendu + 3))
            coupures.append(min(proches, key=lambda c: colonnes[c]))
        bornes = [debut] + coupures + [fin]
        decoupe.extend(zip(bornes[:-1], bornes[1:]))
    groupe = decoupe

    if len(groupe) not in (4, 5):
        return None
    largeurs = sorted(fin - debut for debut, fin in groupe)
    if largeurs[0] < mediane * 0.5 or largeurs[-1] > mediane * 1.6:
        return None

    glyphes = []
    hauts, bas = [], []
    for debut, fin in groupe:
        lignes = [y for y in range(hauteur) if any(masque[y][debut:fin])]
        glyphes.append([masque[y][debut:fin] for y in range(lignes[0], lignes[-1] + 1)])
        hauts.append(lignes[0])
        bas.append(lignes[-1] + 1)

    if avec_boites:
        return glyphes, [(debut, fin, h, b) for (debut, fin), h, b in zip(groupe, hauts, bas)]
    if avec_position:
        return glyphes, (groupe[0][0], groupe[-1][1], min(hauts), max(bas))
    return glyphes


def est_barre_oblique(glyphe):
    """Vrai si le glyphe a la forme d'un « / » (haut-droite et bas-gauche pleins)."""
    hauteur, largeur = len(glyphe), len(glyphe[0])
    mi_h, mi_l = hauteur // 2, largeur // 2

    def compte(y0, y1, x0, x1):
        return sum(glyphe[y][x] for y in range(y0, y1) for x in range(x0, x1))

    diagonale = compte(0, mi_h, mi_l, largeur) + compte(mi_h, hauteur, 0, mi_l)
    autre = compte(0, mi_h, 0, mi_l) + compte(mi_h, hauteur, mi_l, largeur)
    return diagonale > 2 * autre


def localiser_compteur(image, taille):
    """
    Cherche « x/10 » dans une grande image en y faisant glisser une fenêtre de
    la taille de la zone du compteur. Renvoie le centre du texte (dans l'image)
    ou None.
    """
    largeur_fenetre, hauteur_fenetre = taille
    centres = []
    for y in range(0, image.height - hauteur_fenetre + 1, 8):
        for x in range(0, image.width - largeur_fenetre + 1, 10):
            fenetre = image.crop((x, y, x + largeur_fenetre, y + hauteur_fenetre))
            if ImageStat.Stat(ImageOps.grayscale(fenetre)).stddev[0] < 3:
                continue
            for durcissement in DURCISSEMENTS_SEUIL:
                resultat = segmenter_glyphes(fenetre, durcissement, avec_position=True)
                if resultat is None:
                    continue
                glyphes, (x0, x1, y0, y1) = resultat
                if est_barre_oblique(glyphes[-3]):
                    centres.append((x + (x0 + x1) / 2, y + (y0 + y1) / 2))
                break

    if not centres:
        return None
    xs = sorted(c[0] for c in centres)
    ys = sorted(c[1] for c in centres)
    return xs[len(xs) // 2], ys[len(ys) // 2]


def similarite(gris, boite_a, boite_b, largeur, haut, bas):
    """
    Ressemblance (-1 à 1) de deux glyphes : corrélation de leurs niveaux de
    gris, dans des fenêtres de même taille centrées sur chacun, en gardant le
    meilleur décalage à ±1 pixel près (le même caractère n'est pas rendu
    pixel pour pixel pareil à deux positions de l'écran). Les demi-teintes de
    l'anticrénelage comptent : bien plus stable qu'en noir et blanc.
    """
    def valeurs(boite, dx=0, dy=0):
        gauche = (boite[0] + boite[1]) // 2 - largeur // 2 + dx
        pixels = gris.crop((gauche, haut + dy, gauche + largeur, bas + dy)).tobytes()
        moyenne = sum(pixels) / len(pixels)
        centres = [p - moyenne for p in pixels]
        norme = sum(c * c for c in centres) ** 0.5 or 1
        return [c / norme for c in centres]

    a = valeurs(boite_a)
    return max(
        sum(x * y for x, y in zip(a, valeurs(boite_b, dx, dy)))
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )


def analyser_glyphes(image, capacite=None, lecture=""):
    """
    Renvoie (plein, description, numérateur).

    plein vaut True/False si les glyphes permettent de conclure, None s'il faut
    passer à l'OCR. Plein : le nombre avant le « / » a les mêmes glyphes que
    celui d'après (10/10, 25/25), quelle que soit la capacité. Un seul des deux
    chiffres nettement différent : pas plein, sans OCR (20/25 ne diffère que
    par le 2e chiffre, 15/25 que par le 1er). Si les glyphes disent plein mais
    que la lecture OCR rapide lit un autre nombre, l'OCR complet tranche.

    Numérateur (texte, None s'il reste un doute) : chaque chiffre est comparé
    à ceux du dénominateur (« 10 », « 20 »), qui donnent leur forme dans la
    police : le zéro barré, que l'OCR lit « 6 », est ainsi reconnu. Les autres
    chiffres viennent de la lecture OCR rapide (lecture, ex. « 13/20 »).
    """
    gris = ImageOps.autocontrast(ImageOps.grayscale(image))
    if capacite:
        chiffres = str(capacite)
    else:
        m = re.search(r"/(\d{2})", lecture)
        chiffres = nombre_lu(m[1]) if m else ""
    lu = lecture.split("/")[0] if "/" in lecture else ""

    description = "glyphes illisibles"
    for durcissement in DURCISSEMENTS_SEUIL:
        resultat = segmenter_glyphes(image, durcissement, avec_boites=True)
        if resultat is None:
            continue
        glyphes, boites = resultat
        barre = len(glyphes) - 3
        if not est_barre_oblique(glyphes[barre]):
            continue
        largeur = max(fin - debut for debut, fin, _, _ in boites) + 2
        haut, bas = min(b[2] for b in boites) - 1, max(b[3] for b in boites) + 1

        def sim(i, j):
            return similarite(gris, boites[i], boites[j], largeur, haut, bas)

        # Chaque chiffre avant le « / » : celui du dénominateur auquel il est
        # identique, sinon celui de l'OCR (s'il n'est pas un chiffre écarté).
        numerateur = ""
        for k in range(barre):
            ressemblances = [sim(k, barre + 1 + j) for j in range(2)]
            identiques = [j for j, s in enumerate(ressemblances) if s >= SIMILARITE_MEME]
            if identiques and len(chiffres) == 2:
                numerateur += chiffres[identiques[0]]
            elif len(lu) == barre and not any(
                    len(chiffres) == 2 and lu[k] == chiffres[j] and s < SIMILARITE_DIFFERENTE
                    for j, s in enumerate(ressemblances)):
                numerateur += lu[k]
            else:
                numerateur = None
                break

        if barre == 1:
            # Un seul chiffre avant le « / » : jamais plein (capacité à 2 chiffres).
            return False, f"4 glyphes (x/{chiffres or '?'})", numerateur

        sim_1, sim_0 = sim(0, 3), sim(1, 4)
        description = f"5 glyphes, similarités {sim_1:.2f}/{sim_0:.2f}"
        if sim_1 < SIMILARITE_DIFFERENTE or sim_0 < SIMILARITE_DIFFERENTE:
            return False, description, numerateur
        lu_ailleurs = re.fullmatch(r"\d{2}/\d{2}", lecture) and not voix_plein(lecture)
        if sim_1 >= SIMILARITE_MEME and sim_0 >= SIMILARITE_MEME and not lu_ailleurs:
            return True, description, chiffres or None
        return None, description, None

    return None, description, None


# ============================================================
# DÉTECTION DU COMPTEUR
# ============================================================
class DetecteurCompteur:
    """
    Lit le compteur d'un navigateur.

    - Glyphes : 5 glyphes dont le nombre est répété = plein (10/10, 20/20),
      4 glyphes = un seul chiffre avant le « / », pas plein.
      Instantané et insensible au zéro barré de la police.
    - Secours OCR si le découpage n'est pas net : agrandissement, seuil
      d'Otsu, texte noir sur blanc, marge blanche, plusieurs passes avec vote.
    - Cache : si l'image n'a pas changé, le résultat précédent est réutilisé
      sans relancer l'OCR.
    - Stabilité : le plein n'est confirmé qu'après N lectures pleines consécutives.
    - Capacité : 10, 20 avec abonnement… 0 = lue sur le compteur (dénominateur
      relu à chaque changement : comptes avec ou sans abonnement).
    """

    def __init__(self, navigateur, centre, taille=(100, 45), lectures_stables=2,
                 capacite=0):
        self.navigateur = navigateur
        # Capacité max du compteur (10, 20…) ; 0 = lue à l'écran.
        self.capacite = capacite
        self.capacite_lue = capacite or None
        # Autre capacité lue une fois alors qu'elle est réglée : à confirmer.
        self._capacite_a_confirmer = None
        self.prefixe = f"[{navigateur.upper()}]"
        self.centre_prevu = centre
        self.taille = taille
        self._placer(centre)
        self.lectures_stables = lectures_stables
        self.image_debug = DOSSIER_DEBUG / f"debug_{navigateur}.png"
        self.image_debug_traitee = DOSSIER_DEBUG / f"debug_{navigateur}_traitee.png"
        self.image_debug_recherche = DOSSIER_DEBUG / f"debug_{navigateur}_recherche.png"

        self._signature = None
        self._dernier_resultat = (False, "?", "")
        self._valeur_affichee = None
        self._dernier_affichage = 0.0
        self._illisibles = 0
        self._dernier_recalage = 0.0
        self._dernier_message_introuvable = -1e9
        self.consecutifs = 0
        self.lisible = True
        # Zone de tout l'écran du navigateur, pour reconnaître un écran éteint
        # (renseignée par boucle_principale).
        self.zone_ecran = None
        self.ecran_eteint = False

    def _placer(self, centre):
        largeur, hauteur = self.taille
        self.region = (
            int(centre[0]) - largeur // 2,
            int(centre[1]) - hauteur // 2,
            largeur,
            hauteur,
        )

    def reinitialiser(self):
        """À appeler après une ouverture : le compteur doit être relu à neuf."""
        self._signature = None
        self.consecutifs = 0

    def compteur_visible(self):
        """Vrai si le compteur est à sa place : encore sur la page d'accueil."""
        image = capturer_zone(self.region)
        for durcissement in DURCISSEMENTS_SEUIL:
            glyphes = segmenter_glyphes(image, durcissement)
            if glyphes is not None and est_barre_oblique(glyphes[-3]):
                return True
        return False

    def changer_capacite(self, capacite):
        """Capacité du compte connecté (0 = lue à l'écran) : compteur relu à neuf."""
        if capacite != self.capacite:
            self.capacite = capacite
            self.capacite_lue = capacite or None
            self._capacite_a_confirmer = None
            self.reinitialiser()

    def recaler(self):
        """
        Cherche le compteur (« x/10 ») dans une bande large autour de la position
        prévue, et recentre la zone dessus. Le compteur se décale quand un badge
        apparaît ou disparaît à côté de lui.
        """
        self._dernier_recalage = time.monotonic()
        cx, cy = self.centre_prevu
        bande = (
            cx - LARGEUR_RECHERCHE // 2,
            cy - HAUTEUR_RECHERCHE // 2,
            LARGEUR_RECHERCHE,
            HAUTEUR_RECHERCHE,
        )
        image = capturer_zone(bande)
        image.save(self.image_debug_recherche)

        centre = localiser_compteur(image, self.taille)
        if centre is None:
            # Message limité à un toutes les quelques minutes.
            if time.monotonic() - self._dernier_message_introuvable >= RAPPEL_INTROUVABLE:
                print(
                    f"{self.prefixe} Compteur introuvable autour de {self.centre_prevu} "
                    f"(image : {self.image_debug_recherche}). Nouvel essai toutes "
                    f"les {DELAI_ENTRE_RECALAGES} s."
                )
                self._dernier_message_introuvable = time.monotonic()
            return False

        x, y = bande[0] + centre[0], bande[1] + centre[1]
        self._placer((x, y))
        self._signature = None
        print(
            f"{self.prefixe} Compteur retrouvé en ({int(x)}, {int(y)}) : "
            f"zone recalée sur {self.region}."
        )
        return True

    @staticmethod
    def _recadrer(image):
        """
        Garde le texte du compteur, sans l'indicateur coloré à gauche ni le
        trait à droite, que l'OCR lisait comme un chiffre (« 16/206 »).
        """
        for durcissement in DURCISSEMENTS_SEUIL:
            resultat = segmenter_glyphes(image, durcissement, avec_position=True)
            if resultat is not None:
                x0, x1, y0, y1 = resultat[1]
                marge = 4
                return image.crop((max(0, x0 - marge), max(0, y0 - marge),
                                   min(image.width, x1 + marge), min(image.height, y1 + marge)))
        return image

    def _preparer(self, image):
        gris = ImageOps.grayscale(self._recadrer(image))
        gris = ImageOps.autocontrast(gris, cutoff=1)
        gris = gris.resize(
            (gris.width * 5, gris.height * 5), Image.Resampling.LANCZOS
        )
        gris = ImageEnhance.Sharpness(gris).enhance(2.0)

        seuil = seuil_otsu(gris)
        clairs = sum(gris.histogram()[seuil + 1:])
        # Le texte est la partie minoritaire : on le veut noir sur fond blanc.
        if clairs < gris.width * gris.height / 2:
            gris = ImageOps.invert(gris)
            seuil = 255 - seuil
        return gris, seuil

    def _lecture_rapide(self, image):
        """Une seule passe OCR, uniquement pour l'affichage."""
        gris, seuil = self._preparer(image)
        binaire = ImageOps.expand(
            gris.point(lambda p: 255 if p > seuil else 0), border=30, fill=255
        )
        binaire.save(self.image_debug_traitee)
        try:
            texte = pytesseract.image_to_string(
                binaire, config=f"--oem 3 --psm 7 {CONFIG_OCR}"
            )
        except Exception:
            return "?"
        return re.sub(r"[^0-9/]", "", texte)

    def _lire_ocr(self, image):
        gris, seuil_base = self._preparer(image)

        score_plein = 0.0
        votes_autres = {}
        lectures = []
        premiere_binaire = None

        for decalage in DECALAGES_SEUIL:
            seuil = max(10, min(245, seuil_base + decalage))
            binaire = gris.point(lambda p, s=seuil: 255 if p > s else 0)
            binaire = ImageOps.expand(binaire, border=30, fill=255)
            if premiere_binaire is None:
                premiere_binaire = binaire

            for psm in PSM_OCR:
                try:
                    texte = pytesseract.image_to_string(
                        binaire, config=f"--oem 3 --psm {psm} {CONFIG_OCR}"
                    )
                except Exception as erreur:
                    print(f"{self.prefixe} [ERREUR OCR] {erreur}")
                    continue

                compact = re.sub(r"[^0-9/]", "", texte)
                lectures.append(compact or "∅")

                voix = voix_plein(compact, self.capacite and self.capacite_lue)
                if voix:
                    score_plein += voix
                elif re.fullmatch(r"\d{1,2}/\d{1,2}", compact):
                    votes_autres[compact] = votes_autres.get(compact, 0) + 1

                if OCR_VERBEUX:
                    print(
                        f"{self.prefixe} [OCR seuil={seuil} psm={psm}] "
                        f"{texte.strip()!r} -> {compact!r}"
                    )

                meilleur_autre = max(votes_autres.values(), default=0)
                if score_plein >= SCORE_DECISIF or meilleur_autre >= SCORE_DECISIF:
                    break
            else:
                continue
            break

        if premiere_binaire is not None:
            premiere_binaire.save(self.image_debug_traitee)

        meilleur_autre = max(votes_autres.values(), default=0)
        plein = score_plein >= SCORE_MIN and score_plein > meilleur_autre
        return plein, " | ".join(lectures)

    def lire(self):
        """Renvoie True quand le compteur est lu plein (10/10, 20/20) de façon stable."""
        if (
            self._illisibles >= ILLISIBLES_AVANT_RECALAGE
            and time.monotonic() - self._dernier_recalage >= DELAI_ENTRE_RECALAGES
        ):
            try:
                self.recaler()
            except Exception as erreur:
                print(f"{self.prefixe} [ERREUR RECALAGE] {erreur}")

        try:
            image = capturer_zone(self.region)
        except Exception as erreur:
            print(f"{self.prefixe} [ERREUR CAPTURE] {erreur}")
            self.consecutifs = 0
            signaler_compteur(self.navigateur, False, f"erreur capture : {erreur}")
            return False

        signature = hashlib.md5(image.tobytes()).digest()

        if signature == self._signature:
            plein_brut, valeur, detail = self._dernier_resultat
        else:
            image.save(self.image_debug)
            plein_brut, valeur, detail = self._analyser(image)
            self._signature = signature
            self._dernier_resultat = (plein_brut, valeur, detail)

        # Compteur illisible : soit il s'est déplacé, soit tout l'écran est noir
        # (écran éteint, PC verrouillé). Dans ce cas on attend sans rien
        # tenter, et on le dit une seule fois.
        eteint = (
            valeur == "?"
            and self.zone_ecran is not None
            and ecran_eteint(self.zone_ecran)
        )
        if eteint != self.ecran_eteint:
            if eteint:
                print(
                    f"{self.prefixe} Écran éteint ou noir : rien à lire. "
                    "En pause, reprise automatique quand il se rallume."
                )
            else:
                print(f"{self.prefixe} Écran de nouveau visible : reprise de la lecture.")
                self._signature = None
            self.ecran_eteint = eteint

        self.lisible = valeur != "?"
        if not eteint:
            self._illisibles = 0 if self.lisible else self._illisibles + 1
        self.consecutifs = self.consecutifs + 1 if plein_brut else 0
        plein = self.consecutifs >= self.lectures_stables

        # Affiche chaque changement de valeur, et un rappel régulier sinon.
        maintenant = time.monotonic()
        if not eteint and (
            valeur != self._valeur_affichee
            or maintenant - self._dernier_affichage >= AFFICHAGE_PERIODIQUE
        ):
            print(f"{self.prefixe} Compteur : {valeur}  ({detail})")
            self._valeur_affichee = valeur
            self._dernier_affichage = maintenant

        signaler_compteur(self.navigateur, plein)
        return plein

    def _apprendre_capacite(self, lu):
        """
        Capacité lue à l'écran : « 3/20 » -> 20. Toujours vérifiée : si elle
        diffère de celle déjà connue, réglée ou lue (deux lectures d'affilée,
        pour ne pas suivre une fausse lecture), le script s'adapte au compteur.
        """
        m = re.search(r"/(\d{2})", lu)
        if not m:
            return
        capacite = int(nombre_lu(m[1]))
        if capacite not in CAPACITES_POSSIBLES or capacite == self.capacite_lue:
            self._capacite_a_confirmer = None
            return
        if self.capacite_lue and self._capacite_a_confirmer != capacite:
            self._capacite_a_confirmer = capacite
            return
        if self.capacite:
            print(f"{self.prefixe} Le compteur va jusqu'à {capacite}, pas {self.capacite_lue} "
                  f"comme réglé : le script s'adapte ({capacite} boosters).")
        else:
            print(f"{self.prefixe} Capacité du compteur : {capacite} boosters.")
        self._capacite_a_confirmer = None
        self.capacite_lue = capacite

    def _analyser(self, image):
        """Renvoie (plein, valeur affichable, détail)."""
        if ImageStat.Stat(ImageOps.grayscale(image)).stddev[0] < 3:
            # Image uniforme (écran noir, onglet en chargement…) : rien à lire.
            return False, "?", DETAIL_UNIFORME

        # Capacité relue à chaque changement d'image (un compte avec ou sans
        # abonnement pouvant être connecté), même quand elle est réglée.
        lu = self._lecture_rapide(image)
        self._apprendre_capacite(lu)
        total = self.capacite_lue or "?"

        plein, detail, numerateur = analyser_glyphes(image, self.capacite_lue, lu)
        if plein:
            return True, f"{total}/{total}", detail
        if plein is False:
            # Numérateur lu par OCR quand les glyphes ne l'ont pas reconnu.
            if numerateur is None:
                if lu is None:
                    lu = self._lecture_rapide(image)
                numerateur = lu.split("/")[0] if "/" in lu else "?"
            return False, f"{numerateur}/{total}", detail

        plein, lectures = self._lire_ocr(image)
        if plein:
            return True, f"{total}/{total}", f"{detail}, OCR : {lectures}"
        valides = [l for l in lectures.split(" | ") if re.fullmatch(r"\d{1,2}/\d{1,2}", l)]
        if valides:
            self._apprendre_capacite(valides[0])
            # Lecture dont le dénominateur est exact : son numérateur aussi,
            # plus sûrement (le zéro barré lu « 6 » touche les deux).
            exactes = [l for l in valides if l.split("/")[1] == str(self.capacite_lue)]
            valides = exactes or valides
        valeur = (f"{valides[0].split('/')[0]}/{self.capacite_lue or '?'}"
                  if valides else "?")
        return False, valeur, f"{detail}, OCR : {lectures}"


# ============================================================
# POPUP DE PRÉSENCE
# ============================================================
MOTS_TITRE_POPUP = ("toujours", "encore")


def distance(a, b):
    """Nombre de lettres à changer pour passer de a à b (Levenshtein)."""
    precedente = list(range(len(b) + 1))
    for i, lettre_a in enumerate(a, 1):
        courante = [i]
        for j, lettre_b in enumerate(b, 1):
            courante.append(min(
                precedente[j] + 1,
                courante[j - 1] + 1,
                precedente[j - 1] + (lettre_a != lettre_b),
            ))
        precedente = courante
    return precedente[-1]


def est_rouge(pixel):
    """Couleur du bouton « Je suis là » (rouge-orangé, même assombri)."""
    r, g, b = pixel[:3]
    # Vif : (255, 85, 51) ; assombri par le voile du popup : (102, 31, 18).
    return r >= 70 and r > 2 * g and r > 2 * b


def masque_blocs_rouges(image):
    """
    Masque (demi-résolution) des blocs rouges pleins d'au moins ~14 x 14 px,
    comme le bouton « Je suis là ». Les fines bordures rouges disparaissent.
    Calculé avec les opérations de Pillow : quelques millisecondes.
    """
    petite = image.reduce(2)
    r, g, b = petite.split()

    def double(canal):
        return canal.point(lambda v: min(255, 2 * v))

    def positif(canal):
        return canal.point(lambda v: 255 if v > 0 else 0)

    rouge = r.point(lambda v: 255 if v >= 70 else 0)
    rouge = ImageChops.multiply(rouge, positif(ImageChops.subtract(r, double(g))))
    rouge = ImageChops.multiply(rouge, positif(ImageChops.subtract(r, double(b))))
    return rouge.filter(ImageFilter.MinFilter(7))


class SurveillancePopup:
    """
    Cherche le popup « Tu es toujours là ? » sur tout l'écran du navigateur
    (il peut être centré ou en bas à droite) et clique sur son bouton,
    à l'endroit où il se trouve réellement.

    L'OCR de tout l'écran est lent : il n'est lancé que toutes les
    `intervalle` secondes… ou tout de suite quand un nouveau bloc rouge plein
    (le bouton) apparaît, ce qu'un test rapide vérifie à chaque passage.
    """

    def __init__(self, navigateur, zone, intervalle=10):
        self.navigateur = navigateur
        self.prefixe = f"[{navigateur.upper()}]"
        self.zone = zone
        self.intervalle = intervalle
        self.image_debug = DOSSIER_DEBUG / f"debug_popup_{navigateur}.png"
        self._derniere = 0.0
        self._signature_rouge = None

    def _revoir_dans(self, secondes):
        self._derniere = time.monotonic() - self.intervalle + secondes

    def _localiser(self, image):
        """Renvoie (x, y) du bouton dans l'image, None si pas de popup."""
        gris = ImageOps.autocontrast(ImageOps.grayscale(image))
        donnees = pytesseract.image_to_data(
            gris, config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT
        )
        mots = [
            (
                normaliser_texte(texte),
                donnees["left"][i],
                donnees["top"][i],
                donnees["width"][i],
                donnees["height"][i],
            )
            for i, texte in enumerate(donnees["text"])
            if normaliser_texte(texte)
        ]

        # Titre : « toujours », une lettre mal lue tolérée. « Tu es » devant
        # n'est pas exigé : l'OCR le colle parfois en « Tes ».
        def voisin(gauche, droite):
            return (
                0 <= droite[1] - (gauche[1] + gauche[3]) <= 40
                and abs(droite[2] - gauche[2]) <= max(gauche[4], droite[4])
            )

        titres = [
            mot for mot in mots
            if any(distance(mot[0], titre) <= 1 for titre in MOTS_TITRE_POPUP)
        ]
        if not titres:
            return None

        # Le texte ne suffit pas (il peut s'afficher ailleurs, dans une autre
        # fenêtre) : il faut aussi le bouton rouge plein juste en dessous.
        for _, tx, ty, tl, th in titres:
            position = self._bouton_rouge(image, tx, ty, tl, th)
            if position:
                return position

        # « toujours » seul est un mot courant : le signaler seulement s'il
        # ressemble vraiment au titre (« tu es » / « tes » juste avant).
        for titre in titres:
            if any(m[0] in ("es", "tu", "tes", "tues") and voisin(m, titre) for m in mots):
                return "introuvable"
        return None

    @staticmethod
    def _bouton_rouge(image, tx, ty, tl, th):
        """Centre du bloc rouge (bouton « Je suis là ») sous le titre, ou None."""
        largeur, hauteur = image.size
        pixels = image.load()
        x_min, x_max = max(0, tx - 250), min(largeur, tx + tl + 250)
        lignes_rouges = []
        for y in range(ty + th, min(hauteur, ty + th + 150)):
            xs = [x for x in range(x_min, x_max) if est_rouge(pixels[x, y])]
            if len(xs) >= 30:
                lignes_rouges.append((y, xs))

        # Le bouton est le premier bloc d'au moins 10 lignes rouges consécutives
        # (les bordures du popup ne font qu'une ou deux lignes).
        bloc = []
        for y, xs in lignes_rouges:
            if bloc and y != bloc[-1][0] + 1:
                if len(bloc) >= 10:
                    break
                bloc = []
            bloc.append((y, xs))
        if 10 <= len(bloc) <= 80:
            ys = [y for y, _ in bloc]
            xs = [x for _, ligne in bloc for x in ligne]
            return sum(xs) // len(xs), (ys[0] + ys[-1]) // 2
        return None

    def verifier(self, urgent=False):
        """urgent=True raccourcit l'intervalle (compteur illisible : popup probable)."""
        try:
            image = capturer_zone(self.zone)
            masque = masque_blocs_rouges(image)
        except Exception as erreur:
            print(f"{self.prefixe} [ERREUR POPUP] {erreur}")
            return False

        # Nouveau bloc rouge à l'écran (le bouton du popup ?) : OCR immédiat.
        signature = hashlib.md5(masque.tobytes()).digest()
        nouveau_rouge = (
            signature != self._signature_rouge and masque.getbbox() is not None
        )
        self._signature_rouge = signature

        delai = min(4, self.intervalle) if urgent else self.intervalle
        if not nouveau_rouge and time.monotonic() - self._derniere < delai:
            return False
        self._derniere = time.monotonic()

        try:
            position = self._localiser(image)
        except Exception as erreur:
            print(f"{self.prefixe} [ERREUR POPUP] {erreur}")
            return False

        if position is None:
            return False

        image.save(self.image_debug)
        if position == "introuvable":
            print(
                f"{self.prefixe} Texte du popup vu, mais sans bouton rouge "
                f"dessous : ignoré. Image : {self.image_debug}"
            )
            return False

        cible = (self.zone[0] + position[0], self.zone[1] + position[1])

        # Le clic utilise la souris : il faut le verrou, mais sans attendre
        # la priorité (c'est très court).
        if not demander_tour(self.navigateur, prioritaire=True, raison="popup"):
            self._revoir_dans(2)
            return False

        try:
            print(f"{self.prefixe} Popup de présence détecté.")
            with navigateur_au_premier_plan():
                cliquer(self.navigateur, cible, "bouton « Je suis là »", attente=1.5)
        finally:
            terminer_tour(self.navigateur, passer_la_main=False)
        # Revérifie vite que le popup a bien disparu.
        self._revoir_dans(3)
        return True


# ============================================================
# CLICS
# ============================================================
def cliquer(navigateur, position, description="", attente=0.5, double=False):
    """Fait glisser le curseur jusqu'à la cible (sans téléportation), puis clique."""
    x, y = position
    action = "Double-clic" if double else "Clic"
    if _fenetre is not None and not _fenetre.sous_le_curseur(position):
        print(f"[{navigateur.upper()}] {action} annulé : {description or position} "
              f"-> ({x}, {y}), une autre fenêtre est devant le navigateur.")
        time.sleep(attente)
        return
    print(f"[{navigateur.upper()}] {action} : {description or position} -> ({x}, {y})")

    duree = max(DUREE_MIN_MOUVEMENT, random.uniform(*DUREE_MOUVEMENT))
    pyautogui.moveTo(x, y, duration=duree, tween=pyautogui.easeInOutQuad)
    time.sleep(PAUSE_AVANT_CLIC)

    if double:
        pyautogui.doubleClick(interval=0.12)
    else:
        pyautogui.click()
    time.sleep(attente)


# Un cran de molette, en unités Windows (pyautogui.scroll envoie ces unités).
CRAN_MOLETTE = 120
# Crans envoyés vers le haut pour être sûr de repartir du haut de la page.
REMONTEE_PAGE = 60


def defiler(navigateur, position, crans, description=""):
    """
    Remonte tout en haut de la page, puis descend de `crans` crans de molette,
    souris sur `position` : la page se retrouve toujours au même endroit.
    """
    x, y = position
    if _fenetre is not None and not _fenetre.sous_le_curseur(position):
        print(f"[{navigateur.upper()}] Molette annulée : {description or position}, "
              "une autre fenêtre est devant le navigateur.")
        return
    print(f"[{navigateur.upper()}] Molette : {crans} cran(s) vers le bas "
          f"pour {description or position}")

    duree = max(DUREE_MIN_MOUVEMENT, random.uniform(*DUREE_MOUVEMENT))
    pyautogui.moveTo(x, y, duration=duree, tween=pyautogui.easeInOutQuad)
    for _ in range(REMONTEE_PAGE // 10):
        pyautogui.scroll(10 * CRAN_MOLETTE)
    time.sleep(1)
    for _ in range(crans):
        pyautogui.scroll(-CRAN_MOLETTE)
        time.sleep(0.1)
    # Le défilement est animé : attendre qu'il soit fini avant de cliquer.
    time.sleep(1)


# ============================================================
# BOUCLE PRINCIPALE
# ============================================================
# Nombre de boosters ouverts par le bouton du jeu, et pause entre deux
# ouvertures d'affilée (compteur à 20 ou 25 : deux ouvertures).
BOOSTERS_PAR_OUVERTURE = 10
PAUSE_ENTRE_OUVERTURES = 4

def boucle_principale(navigateur, detecteur, popup, sequence, intervalle=2,
                      pause_apres_ouverture=5, a_chaque_tour=None):
    """
    Détection en continu ; ouverture seulement quand le verrou est obtenu.
    Attendre son tour ne bloque jamais la lecture du compteur.
    `a_chaque_tour` : fonction appelée à chaque passage (ex. suivi du compte).
    """
    from coordination import liberer_au_demarrage

    prefixe = f"[{navigateur.upper()}]"
    liberer_au_demarrage(navigateur)
    detecteur.zone_ecran = popup.zone
    suivre_fenetre(navigateur, popup.zone)

    try:
        print(f"{prefixe} Tesseract : {pytesseract.get_tesseract_version()}")
    except Exception as erreur:
        print(f"[ERREUR TESSERACT] {erreur}")
        return

    print(f"{prefixe} Zone compteur : {detecteur.region}")
    print(f"{prefixe} Diagnostic : {detecteur.image_debug}")
    print(f"{prefixe} Ctrl+C pour arrêter (ou souris dans le coin haut-gauche).")

    try:
        while True:
            try:
                if not detecteur.ecran_eteint:
                    popup.verifier(urgent=not detecteur.lisible)
                    if a_chaque_tour:
                        a_chaque_tour()

                if detecteur.lire() and demander_tour(navigateur):
                    print(f"{prefixe} Compteur plein confirmé et souris libre : ouverture.")
                    # Le bouton du jeu ouvre 10 boosters : à 20/20, deux ouvertures
                    # d'affilée pour vider le compteur.
                    ouvertures = max(1, (detecteur.capacite_lue or 0) // BOOSTERS_PAR_OUVERTURE)
                    try:
                        with navigateur_au_premier_plan():
                            for numero in range(1, ouvertures + 1):
                                if numero > 1:
                                    time.sleep(PAUSE_ENTRE_OUVERTURES)
                                    popup.verifier(urgent=True)
                                    print(f"{prefixe} Compteur à {detecteur.capacite_lue} : "
                                          f"ouverture {numero}/{ouvertures}.")
                                sequence()
                    finally:
                        terminer_tour(navigateur)
                    detecteur.reinitialiser()
                    time.sleep(pause_apres_ouverture)
                    continue

            except pyautogui.FailSafeException:
                raise
            except Exception as erreur:
                print(f"{prefixe} [ERREUR] {type(erreur).__name__}: {erreur}")
                time.sleep(5)

            time.sleep(intervalle)

    except KeyboardInterrupt:
        print(f"\n{prefixe} Arrêt demandé.")
    except pyautogui.FailSafeException:
        print(f"\n{prefixe} Arrêt de sécurité PyAutoGUI déclenché.")
    finally:
        terminer_tour(navigateur, passer_la_main=False)
        print(f"{prefixe} Script arrêté.")
