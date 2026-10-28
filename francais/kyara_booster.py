"""
Ouverture automatique de boosters Kyara — version entièrement configurable.

Tout se règle dans la partie CONFIGURATION ci-dessous (voir aussi LISEZ-MOI.txt).
Les positions se remplissent toutes seules avec configurer_positions.py.

Plusieurs navigateurs en même temps : copier ce fichier (ex. kyara_booster_2.py)
et changer NOM, EXECUTABLE, ZONE_ECRAN et les positions. Les copies lancées
détectent en même temps mais ouvrent chacune leur tour (une seule souris).
"""

# ============================================================
# CONFIGURATION
# ============================================================

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


# ============================================================
# FIN DE LA CONFIGURATION — rien à modifier en dessous
# ============================================================

import re
import time
from datetime import datetime

import pyautogui
import pytesseract
from PIL import ImageChops, ImageOps, ImageStat

import kyara_commun
from kyara_commun import (
    CAPACITES_POSSIBLES,
    DOSSIER_CHASSES,
    DOSSIER_DEBUG,
    DetecteurCompteur,
    SurveillancePopup,
    boucle_principale,
    capturer_zone,
    cliquer,
    DUREE_MIN_MOUVEMENT,
    defiler,
    distance,
    normaliser_texte,
)

PREFIXE = f"[{NOM.upper()}]"
IMAGE_REVELATION = DOSSIER_DEBUG / f"debug_{NOM}_revelation.png"

# Bouton « Tout révéler » : bande cherchée autour de la position de secours,
# texte blanc seul gardé (le texte gris à côté et la bordure gênent l'OCR).
DEMI_LARGEUR_BANDE, HAUT_BANDE, HAUTEUR_BANDE = 500, 31, 90
SEUIL_TEXTE_BOUTON = 160
ATTENTE_MAX_BOUTON = 8
# Avant de lire les cartes, attente que l'écran ne bouge plus (animation).
ATTENTE_MAX_GRILLE = 6

pyautogui.FAILSAFE = ARRET_COIN_ECRAN
pyautogui.PAUSE = 0.15
kyara_commun.DUREE_MOUVEMENT = DUREE_MOUVEMENT
kyara_commun.EXECUTABLES[NOM] = EXECUTABLE.lower()

# Comptes : avatar lu dans un carré de 2 x AVATAR_RAYON autour de AVATAR,
# reconnu si sa couleur (teinte, sans la luminosité) est assez proche.
AVATAR_RAYON = 20
ECART_COMPTE_MAX = 0.1
# L'avatar est revérifié toutes les N secondes (changement de compte).
VERIFICATION_COMPTE = 10

# Compte connecté (None : inconnu ou pas de comptes).
compte_actuel = None
derniere_verification_compte = float("-inf")
avatar_inconnu_signale = False
# Prochain pack de la rotation, par compte (None : sans compte).
positions_rotation = {}
# Détecteur du compteur, pour lui donner la capacité du compte connecté.
detecteur_compteur = None


# ============================================================
# VÉRIFICATION DE LA CONFIGURATION
# ============================================================
def verifier_configuration():
    erreurs = []
    utilises = set()

    def verifier_packs(noms, ou):
        utilises.update(noms)
        for nom in noms:
            if nom not in PACKS:
                erreurs.append(f"{ou} : pack « {nom} » absent de PACKS.")

    def verifier_chasse(chasse, ou):
        if not isinstance(chasse, dict) or not chasse.get("carte") or not chasse.get("pack"):
            erreurs.append(f"{ou} : la chasse doit avoir une « carte » et un « pack ».")
            return
        verifier_packs([chasse["pack"]], ou)
        if "ensuite" in chasse:
            if not chasse["ensuite"]:
                erreurs.append(f"{ou} : « ensuite » est vide.")
            verifier_packs(chasse["ensuite"], ou)

    if not EXECUTABLE.strip():
        erreurs.append("navigateur (EXECUTABLE) à définir.")
    if ZONE_ECRAN[2] <= 0 or ZONE_ECRAN[3] <= 0:
        erreurs.append("écran du navigateur (ZONE_ECRAN) à définir.")
    if tuple(COMPTEUR_CENTRE) == (0, 0):
        erreurs.append("position du compteur (COMPTEUR_CENTRE) à définir.")
    if not ROTATION:
        erreurs.append("packs à ouvrir (ROTATION) à définir : aucun choisi.")
    verifier_packs(ROTATION, "ROTATION")
    if CHASSE:
        verifier_chasse(CHASSE, "CHASSE")
    if COMPTES:
        if tuple(AVATAR) == (0, 0):
            erreurs.append("position de l'avatar (AVATAR) à définir.")
        for nom, compte in COMPTES.items():
            ou = f"compte « {nom} »"
            couleur = compte.get("couleur")
            if not (isinstance(couleur, (tuple, list)) and len(couleur) == 3):
                erreurs.append(f"{ou} : « couleur » doit être (rouge, vert, bleu).")
            rotation = compte.get("rotation", ROTATION)
            if not rotation:
                erreurs.append(f"{ou} : rotation vide.")
            verifier_packs(rotation, ou)
            if compte.get("chasse"):
                verifier_chasse(compte["chasse"], ou)
            capacite = compte.get("capacite", 0)
            if capacite and capacite not in CAPACITES_POSSIBLES:
                erreurs.append(f"{ou} : « capacite » : 0 (lue sur le compteur) ou "
                               f"{', '.join(map(str, CAPACITES_POSSIBLES))}.")

    # (0, 0) : position pas encore placée avec configurer_positions.py.
    for nom in sorted(utilises & PACKS.keys()):
        if tuple(PACKS[nom]["position"]) == (0, 0):
            erreurs.append(f"position du pack « {nom} » à définir.")
    for nom, reglage in PACKS.items():
        crans = reglage.get("molette", 0)
        if not isinstance(crans, int) or crans < 0:
            erreurs.append(f"PACKS : « molette » du pack « {nom} » doit être "
                           "un nombre entier de crans (0 ou plus).")
    for etape in SEQUENCE:
        if etape[0] not in ("pack", "clic", "double_clic", "tout_reveler",
                            "lire_cartes", "attendre"):
            erreurs.append(f"SEQUENCE : étape « {etape[0]} » inconnue.")
        elif etape[0] in ("clic", "double_clic") and tuple(etape[2]) == (0, 0):
            erreurs.append(f"position du bouton « {etape[1]} » à définir.")
        elif etape[0] == "tout_reveler" and tuple(etape[1]) == (0, 0):
            erreurs.append("position du bouton « Tout révéler » à définir.")
    if CAPACITE_MAX and CAPACITE_MAX not in CAPACITES_POSSIBLES:
        erreurs.append(f"CAPACITE_MAX : 0 (lue sur le compteur) ou "
                       f"{', '.join(map(str, CAPACITES_POSSIBLES))}.")
    if not (DUREE_MIN_MOUVEMENT <= DUREE_MOUVEMENT[0] <= DUREE_MOUVEMENT[1]):
        erreurs.append(f"DUREE_MOUVEMENT : (min, max) avec min au moins "
                       f"{DUREE_MIN_MOUVEMENT} et max au moins min (défaut (0.5, 0.9)).")
    if erreurs:
        print(f"{PREFIXE} [CONFIGURATION] Il manque des réglages pour démarrer :")
    for erreur in erreurs:
        print(f"{PREFIXE} [CONFIGURATION]    - {erreur}")
    return not erreurs


# ============================================================
# COMPTES
# ============================================================
def chromaticite(couleur):
    """Part de rouge, de vert et de bleu : la même, assombrie ou non."""
    total = sum(couleur) or 1
    return [composante / total for composante in couleur]


def ecart_couleurs(a, b):
    return sum((x - y) ** 2 for x, y in zip(chromaticite(a), chromaticite(b))) ** 0.5


def lire_compte():
    """Nom du compte dont l'avatar est affiché, ou None s'il n'est pas reconnu."""
    x, y = AVATAR
    image = capturer_zone(
        (x - AVATAR_RAYON, y - AVATAR_RAYON, 2 * AVATAR_RAYON, 2 * AVATAR_RAYON)
    )
    couleur = ImageStat.Stat(image.convert("RGB")).mean
    if sum(couleur) < 30:  # écran noir ou page en chargement
        return None
    ecart, nom = min((ecart_couleurs(couleur, compte["couleur"]), nom)
                     for nom, compte in COMPTES.items())
    return nom if ecart <= ECART_COMPTE_MAX else None


def reglages_compte():
    """(rotation, chasse, compte) du compte connecté, sinon les réglages généraux."""
    if COMPTES and compte_actuel in COMPTES:
        compte = COMPTES[compte_actuel]
        return compte.get("rotation", ROTATION), compte.get("chasse"), compte_actuel
    return ROTATION, CHASSE, None


def capacite_compte(compte=None):
    """Capacité du compteur pour ce compte (sinon CAPACITE_MAX) ; 0 = lue à l'écran."""
    return (COMPTES or {}).get(compte, {}).get("capacite", CAPACITE_MAX)


def texte_capacite(capacite):
    return f"compteur /{capacite}" if capacite else "compteur lu tout seul"


def mettre_a_jour_compte():
    global compte_actuel, avatar_inconnu_signale
    if not COMPTES:
        return
    vu = lire_compte()
    if vu is None:
        # Normal hors de l'accueil ou sous un popup : le dernier compte reste.
        if compte_actuel is None and not avatar_inconnu_signale:
            print(f"{PREFIXE} Avatar non reconnu : réglages généraux en attendant "
                  f"({decrire(ROTATION, CHASSE, None)}).")
            avatar_inconnu_signale = True
        return
    if vu != compte_actuel:
        compte_actuel = vu
        print(f"{PREFIXE} Compte connecté : {vu} ({decrire(*reglages_compte())}, "
              f"{texte_capacite(capacite_compte(vu))}).")
        if detecteur_compteur:
            detecteur_compteur.changer_capacite(capacite_compte(vu))


def suivre_compte():
    """Appelée à chaque passage : vérifie l'avatar toutes les N secondes."""
    global derniere_verification_compte
    if not COMPTES or time.monotonic() - derniere_verification_compte < VERIFICATION_COMPTE:
        return
    derniere_verification_compte = time.monotonic()
    mettre_a_jour_compte()


# ============================================================
# CHASSE À UNE CARTE
# ============================================================
def fichier_chasse(chasse, compte):
    nom = normaliser_texte(chasse["carte"])
    if compte:
        nom = f"{normaliser_texte(compte)} {nom}"
    return DOSSIER_CHASSES / f"chasse_{nom.replace(' ', '_')}.txt"


def chasse_en_cours(chasse, compte):
    return bool(chasse) and not fichier_chasse(chasse, compte).exists()


def decrire(rotation, chasse, compte):
    """Ce que fait le script avec ces réglages, en une phrase."""
    suite = " / ".join(chasse.get("ensuite", rotation) if chasse else rotation)
    if chasse_en_cours(chasse, compte):
        return (f"chasse à {chasse['carte']} : pack {chasse['pack']} jusqu'à "
                f"l'obtenir, puis {suite}")
    if chasse:
        return (f"rotation {suite}, chasse à {chasse['carte']} terminée "
                f"({fichier_chasse(chasse, compte).name})")
    return f"rotation {suite}"


def motif_carte(carte):
    """
    Motif qui reconnaît le début du nom (les noms sont tronqués, « Rimur… »),
    même avec une lettre parasite collée devant ou une première lettre mal lue.
    """
    mot = normaliser_texte(carte).split()[0]

    def souple(texte):
        # Lettres que l'OCR confond souvent.
        return "".join(
            {"i": "[il1]", "l": "[il1]", "o": "[o0]", "m": "(?:m|rn)"}.get(c, re.escape(c))
            for c in texte
        )

    if len(mot) <= 4:
        return re.compile(rf"^{souple(mot)}")
    return re.compile(f"{souple(mot[:4])}|{souple(mot[1:5])}")


def difference(image_a, image_b):
    """Écart moyen entre deux captures (0 = identiques)."""
    ecart = ImageChops.difference(ImageOps.grayscale(image_a), ImageOps.grayscale(image_b))
    return ImageStat.Stat(ecart).mean[0]


def attendre_ecran_stable():
    """Attend que l'écran ne bouge plus (fin de l'animation des cartes)."""
    precedente = capturer_zone(ZONE_ECRAN)
    debut = time.monotonic()
    while time.monotonic() - debut < ATTENTE_MAX_GRILLE:
        time.sleep(1)
        image = capturer_zone(ZONE_ECRAN)
        if difference(image, precedente) < 1:
            return image
        precedente = image
    return precedente


def lire_cartes(carte):
    """Lit l'écran des cartes retournées ; renvoie (image, mots où la carte est lue)."""
    image = attendre_ecran_stable()
    gris = ImageOps.grayscale(image)
    mots = set()
    # Deux préparations : texte blanc seul, puis contraste étiré. Agrandies,
    # car les noms des cartes sont petits.
    for preparee in (gris.point(lambda v: 0 if v >= 160 else 255),
                     ImageOps.autocontrast(gris)):
        preparee = preparee.resize((preparee.width * 2, preparee.height * 2))
        texte = pytesseract.image_to_string(preparee, config="--oem 3 --psm 11")
        mots.update(normaliser_texte(texte).split())
    motif = motif_carte(carte)
    return image, sorted(mot for mot in mots if motif.search(mot))


def etape_lire_cartes(pack, chasse, compte):
    """Cherche la carte de la chasse ; crée le fichier de fin de chasse si trouvée."""
    if not chasse_en_cours(chasse, compte) or pack != chasse["pack"]:
        # Gardée pour vérifier l'écran des cartes retournées.
        capturer_zone(ZONE_ECRAN).save(IMAGE_REVELATION)
        return

    image, trouve = lire_cartes(chasse["carte"])
    image.save(IMAGE_REVELATION)
    if not trouve:
        print(f"{PREFIXE} Pas de {chasse['carte']} dans ces cartes. "
              f"Image : {IMAGE_REVELATION}")
        return

    fichier = fichier_chasse(chasse, compte)
    capture = fichier.with_suffix(".png")
    image.save(capture)
    fichier.write_text(
        f"{chasse['carte']} obtenu le {datetime.now():%d/%m/%Y à %H:%M}"
        + (f" (compte {compte})" if compte else "")
        + f" (lu : {', '.join(trouve)}).\n",
        encoding="utf-8",
    )
    print(f"{PREFIXE} " + "*" * 50)
    print(f"{PREFIXE} {chasse['carte'].upper()} OBTENU ! Passage à : "
          f"{decrire(*reglages_compte()) if compte else decrire(ROTATION, CHASSE, None)}.")
    print(f"{PREFIXE} Capture : {capture}")
    print(f"{PREFIXE} " + "*" * 50)


# ============================================================
# BOUTON « TOUT RÉVÉLER »
# ============================================================
def localiser_bouton_reveler(secours):
    """Centre écran du bouton « Tout révéler », ou None s'il n'est pas affiché."""
    x0 = secours[0] - DEMI_LARGEUR_BANDE
    y0 = secours[1] - HAUT_BANDE
    largeur, hauteur = 2 * DEMI_LARGEUR_BANDE, HAUTEUR_BANDE
    image = capturer_zone((x0, y0, largeur, hauteur))
    gris = ImageOps.grayscale(image).point(
        lambda v: 0 if v >= SEUIL_TEXTE_BOUTON else 255
    )
    gris = gris.resize((largeur * 2, hauteur * 2))
    donnees = pytesseract.image_to_data(
        gris, config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT
    )
    mots = [
        (normaliser_texte(texte), i)
        for i, texte in enumerate(donnees["text"])
        if normaliser_texte(texte)
    ]
    for mot, i in mots:
        if distance(mot, "reveler") > 1:
            continue
        gauche = donnees["left"][i]
        # Le bouton commence au « Tout » juste avant, s'il est lu.
        for autre, j in mots:
            if distance(autre, "tout") <= 1 and 0 < gauche - donnees["left"][j] < 120:
                gauche = donnees["left"][j]
        droite = donnees["left"][i] + donnees["width"][i]
        milieu_y = donnees["top"][i] + donnees["height"][i] / 2
        return x0 + round((gauche + droite) / 4), y0 + round(milieu_y / 2)
    return None


def etape_tout_reveler(secours, attente):
    """Clique sur « Tout révéler » et vérifie que le bouton a disparu."""
    debut = time.monotonic()
    position = None
    while time.monotonic() - debut < ATTENTE_MAX_BOUTON:
        position = localiser_bouton_reveler(secours)
        if position:
            break
        time.sleep(0.5)

    if not position:
        print(f"{PREFIXE} Bouton « Tout révéler » non trouvé : position de secours.")
        cliquer(NOM, secours, "Tout révéler", attente, double=True)
        return

    for _ in range(3):
        cliquer(NOM, position, "Tout révéler", 1.5)
        if not localiser_bouton_reveler(secours):
            break
        print(f"{PREFIXE} « Tout révéler » encore affiché : nouveau clic.")
    time.sleep(max(0, attente - 1.5))


# ============================================================
# OUVERTURE
# ============================================================
def choisir_pack():
    """(pack, chasse, compte) : pack à ouvrir selon le compte, la chasse et la rotation."""
    mettre_a_jour_compte()
    rotation, chasse, compte = reglages_compte()
    if chasse_en_cours(chasse, compte):
        return chasse["pack"], chasse, compte
    suite = chasse.get("ensuite", rotation) if chasse else rotation
    position = positions_rotation.get(compte, 0)
    positions_rotation[compte] = position + 1
    return suite[position % len(suite)], chasse, compte


def ouvrir_boosters():
    pack, chasse, compte = choisir_pack()
    print(f"{PREFIXE} Début de l'ouverture : {pack}"
          + (f" (compte {compte})." if compte else "."))

    for etape in SEQUENCE:
        action = etape[0]
        if action == "pack":
            reglage = PACKS[pack]
            if reglage.get("molette", 0):
                defiler(NOM, reglage["position"], reglage["molette"], pack)
            cliquer(NOM, reglage["position"], pack, etape[1],
                    double=reglage.get("double_clic", False))
        elif action in ("clic", "double_clic"):
            _, description, position, attente = etape
            cliquer(NOM, position, description, attente, double=action == "double_clic")
        elif action == "tout_reveler":
            etape_tout_reveler(etape[1], etape[2])
        elif action == "lire_cartes":
            try:
                etape_lire_cartes(pack, chasse, compte)
            except Exception as erreur:
                print(f"{PREFIXE} [ERREUR CARTES] {erreur}")
        elif action == "attendre":
            time.sleep(etape[1])

    print(f"{PREFIXE} Ouverture terminée.")


# ============================================================
# LANCEMENT
# ============================================================
def main():
    global detecteur_compteur
    print("=" * 60)
    print(f" AUTOMATISATION KYARA - {NOM.upper()} ({EXECUTABLE})")
    print("=" * 60)
    if not verifier_configuration():
        print(f"{PREFIXE} Lance  python configurer_positions.py  : il te demandera "
              "ce qui manque. Puis relance ce script.")
        return

    if COMPTES:
        print(f"{PREFIXE} Comptes reconnus à l'avatar :")
        for nom, compte in COMPTES.items():
            print(f"{PREFIXE}    {nom} : "
                  f"{decrire(compte.get('rotation', ROTATION), compte.get('chasse'), nom)}, "
                  f"{texte_capacite(capacite_compte(nom))}.")
        print(f"{PREFIXE}    autre / pas reconnu : {decrire(ROTATION, CHASSE, None)}, "
              f"{texte_capacite(CAPACITE_MAX)}.")
    else:
        print(f"{PREFIXE} {decrire(ROTATION, CHASSE, None).capitalize()}, "
              f"{texte_capacite(CAPACITE_MAX)}.")

    detecteur = DetecteurCompteur(
        NOM, COMPTEUR_CENTRE, COMPTEUR_TAILLE, lectures_stables=LECTURES_STABLES,
        capacite=capacite_compte(compte_actuel),
    )
    detecteur_compteur = detecteur
    popup = SurveillancePopup(NOM, ZONE_ECRAN, INTERVALLE_POPUP)

    boucle_principale(NOM, detecteur, popup, ouvrir_boosters, INTERVALLE,
                      pause_apres_ouverture=PAUSE_APRES_OUVERTURE,
                      a_chaque_tour=suivre_compte)


if __name__ == "__main__":
    main()
