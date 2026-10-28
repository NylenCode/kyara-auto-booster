"""
Coordination entre plusieurs copies de kyara_booster.py (une par navigateur).

- La DÉTECTION n'est jamais bloquée : chaque script lit son compteur en continu.
- L'OUVERTURE est exclusive (une seule souris) : un verrou partagé dit qui ouvre.
- Celui qui vient d'ouvrir laisse passer les autres : si l'un d'eux est à
  plein, il ouvre ; sinon chacun continue sa détection.

Les noms sont libres (NOM dans chaque script), mais doivent être différents.

Usage en ligne de commande :
    python coordination.py          -> affiche l'état
    python coordination.py reset    -> remet l'état à zéro
"""

import json
import msvcrt
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ---------- CONFIGURATION ----------
DOSSIER_LOCAL = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
)

# Dossier propre à ce programme.
DOSSIER = DOSSIER_LOCAL / "KyaraBoosterConfigurable"
FICHIER_ETAT = DOSSIER / "etat.json"
FICHIER_VERROU = DOSSIER / "etat.lock"

# Un « compteur plein » signalé reste valable ce nombre de secondes.
VALIDITE_PRET = 20
# Si un script plante en pleine ouverture, son verrou expire après ce délai.
DUREE_MAX_TOUR = 300

DOSSIER.mkdir(parents=True, exist_ok=True)

dernieres_detections = {}
dernier_message_attente = {}


# ---------- ACCÈS AU FICHIER D'ÉTAT ----------
def _etat_vide():
    return {
        "proprietaire": None,
        "raison": None,
        "depuis": 0.0,
        # Dernier script à avoir ouvert : il laisse passer les autres.
        "dernier": None,
        "pret": {},
    }


@contextmanager
def _etat_verrouille():
    """Lit, laisse modifier puis réécrit l'état, sous verrou inter-processus."""
    with open(FICHIER_VERROU, "a+b") as verrou:
        verrou.seek(0)
        debut = time.monotonic()
        while True:
            try:
                msvcrt.locking(verrou.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() - debut > 10:
                    raise TimeoutError(f"Verrou bloqué : {FICHIER_VERROU}")
                time.sleep(0.05)

        try:
            try:
                etat = json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))
                if not isinstance(etat, dict):
                    raise ValueError
            except (OSError, ValueError):
                etat = _etat_vide()

            base = _etat_vide()
            base.update(etat)
            base["pret"] = dict(etat.get("pret") or {})
            etat = base

            # Verrou orphelin (script planté) : on le libère.
            if (
                etat["proprietaire"]
                and time.time() - etat["depuis"] > DUREE_MAX_TOUR
            ):
                print(
                    f"[COORDINATION] Verrou de {etat['proprietaire'].upper()} "
                    "expiré : libéré."
                )
                etat["proprietaire"] = None
                etat["raison"] = None

            yield etat

            FICHIER_ETAT.write_text(
                json.dumps(etat, indent=2), encoding="utf-8"
            )
        finally:
            verrou.seek(0)
            msvcrt.locking(verrou.fileno(), msvcrt.LK_UNLCK, 1)


def _verifier_nom(nom):
    nom = str(nom).lower().strip()
    if not nom:
        raise ValueError("Nom de script vide : remplir NOM dans la configuration.")
    return nom


def _autres_prets(etat, nom):
    maintenant = time.time()
    return [
        autre for autre, date in etat["pret"].items()
        if autre != nom and maintenant - date < VALIDITE_PRET
    ]


# ---------- API ----------
def signaler_compteur(nom, detecte, texte_ocr=""):
    """Publie l'état du compteur (lu par les autres scripts) et l'affiche s'il change."""
    nom = _verifier_nom(nom)

    with _etat_verrouille() as etat:
        etat["pret"][nom] = time.time() if detecte else 0.0

    if dernieres_detections.get(nom) != detecte:
        etat_txt = "DÉTECTÉ" if detecte else "NON détecté"
        print(f"[{nom.upper()}] Compteur plein {etat_txt}.")
        if texte_ocr:
            print(f"[{nom.upper()}] Lecture : {texte_ocr}")
        dernieres_detections[nom] = detecte


def demander_tour(nom, prioritaire=False, raison="ouverture"):
    """
    Tente de prendre la souris, sans jamais attendre.

    Renvoie True si le script peut agir maintenant, False sinon
    (il continue alors sa détection et redemandera au prochain passage).

    prioritaire=True ignore la priorité des autres (clic de popup, très court).
    """
    nom = _verifier_nom(nom)

    with _etat_verrouille() as etat:
        proprietaire = etat["proprietaire"]

        if proprietaire == nom:
            return True

        if proprietaire is None:
            autres = _autres_prets(etat, nom)
            if not prioritaire and etat["dernier"] == nom and autres:
                motif = f"priorité à {autres[0].upper()} (compteur plein)"
            else:
                etat["proprietaire"] = nom
                etat["raison"] = raison
                etat["depuis"] = time.time()
                dernier_message_attente.pop(nom, None)
                return True
        else:
            motif = f"{proprietaire.upper()} ouvre"

    if dernier_message_attente.get(nom) != motif:
        print(f"[{nom.upper()}] En attente : {motif}. Détection continue.")
        dernier_message_attente[nom] = motif
    return False


def terminer_tour(nom, passer_la_main=True):
    """
    Libère la souris. Avec passer_la_main=True (fin d'ouverture), les autres
    scripts deviennent prioritaires : ils ouvriront dès que leur compteur sera plein.
    """
    nom = _verifier_nom(nom)

    with _etat_verrouille() as etat:
        if etat["proprietaire"] != nom:
            return
        etat["proprietaire"] = None
        etat["raison"] = None
        etat["depuis"] = 0.0
        if passer_la_main:
            etat["dernier"] = nom
        # Le compteur vient d'être consommé : ne plus se déclarer prêt.
        etat["pret"][nom] = 0.0

    if passer_la_main:
        print(
            f"[COORDINATION] {nom.upper()} a terminé. "
            "Les autres peuvent ouvrir s'ils sont pleins."
        )


def liberer_au_demarrage(nom):
    """Efface un verrou laissé par une exécution précédente du même script."""
    nom = _verifier_nom(nom)
    with _etat_verrouille() as etat:
        if etat["proprietaire"] == nom:
            print(f"[COORDINATION] Ancien verrou de {nom.upper()} libéré.")
            etat["proprietaire"] = None
            etat["raison"] = None
        etat["pret"][nom] = 0.0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        FICHIER_ETAT.write_text(json.dumps(_etat_vide(), indent=2), encoding="utf-8")
        print(f"État remis à zéro : {FICHIER_ETAT}")
    else:
        with _etat_verrouille() as etat:
            print(json.dumps(etat, indent=2))
