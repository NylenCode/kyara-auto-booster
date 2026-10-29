# Kyara Auto Booster

Ouvre tes boosters **Kyara** tout seul, dès que le compteur est plein.

🇬🇧 **English version: see [README.md](README.md) and the [`english/`](english/) folder.**

☕ **Ça te plaît ? Soutiens-moi avec un tip sur Ko-fi : [ko-fi.com/nylen9](https://ko-fi.com/nylen9). Merci !**

---

## Ce qu'il fait

- Surveille le compteur de boosters en haut de la page (`3/10`, `7/10`…).
- Quand il est plein (`10/10`, ou `20/20` avec un abonnement), il clique pour ouvrir les boosters, puis attend à nouveau.
- À `20/20`, il ouvre **deux fois de suite**, car le bouton du jeu n'en ouvre que 10 à la fois.
- **Lit tout seul la capacité du compteur** (10 ou 20) et s'adapte si elle change.
- **Rotation** : ouvre tes packs choisis à tour de rôle (ex. Isekai, Shonen Mix, Isekai…).
- **Chasse à la carte** : ouvre un pack jusqu'à obtenir une carte, puis passe à d'autres packs.
- **Plusieurs comptes** : reconnaît le compte connecté à sa photo de profil ; chaque compte peut avoir ses packs et la capacité de son compteur.
- **Plusieurs navigateurs en même temps** (ex. Opera + Brave) : les scripts se passent la souris chacun leur tour.
- Gère le popup « Tu es toujours là ? ».
- Le navigateur peut rester derrière d'autres fenêtres ; la souris glisse comme une vraie main.
- **Aucun fichier à modifier à la main** : un assistant (`configurer_positions.py`) pose des questions simples. Tu mets la souris sur chaque bouton et tu appuies sur **G**.

## Il faut

- **Windows** (10 ou 11)
- **Python 3.10+** et **Tesseract OCR** (dans son dossier par défaut `C:\Program Files\Tesseract-OCR`) : `install.bat` les installe pour toi.

## Installation (une seule fois)

1. Télécharge le programme : bouton vert **Code**, puis **Download ZIP**, et décompresse-le.
2. Double-clique sur **`install.bat`**. Il installe ce qui manque (Python, les
   outils Python, Tesseract) et garde ce qui est déjà là. Windows peut demander
   l'autorisation : clique sur **Oui**.

> Si Windows affiche « Windows a protégé votre ordinateur » : clique sur **Informations complémentaires**, puis **Exécuter quand même**.

<details>
<summary>À la main, dans un terminal</summary>

```bash
winget install -e --id Python.Python.3.13
```

Ferme et rouvre le terminal, puis :

```bash
python -m pip install -r requirements.txt
```

```bash
winget install -e --id UB-Mannheim.TesseractOCR
```

</details>

## Démarrage rapide

1. Ouvre Kyara dans ton navigateur, sur la page des boosters.
2. Double-clique sur **`configure.bat`** (ou `python configure.py` dans un terminal).
   Choisis ta langue (**1** = Français ; elle est retenue). L'assistant
   s'ouvre : choisis tes packs, puis place chaque position avec la souris et
   la touche **G**.
3. Double-clique sur **`run.bat`** pour lancer le programme (ou `python start.py`).
   Un 2e navigateur réglé dans l'assistant (ex. nommé `brave`) : `run.bat brave` dans un terminal.

Pour arrêter : `Ctrl + C`, ou mets la souris tout en haut à gauche de l'écran.

Le mode d'emploi complet (installation, menus de l'assistant, comptes, deux navigateurs, problèmes) est dans **[francais/LISEZ-MOI.txt](francais/LISEZ-MOI.txt)**.

## Dossiers

| Dossier | Contenu |
|---|---|
| [`francais/`](francais/) | Version française + mode d'emploi `LISEZ-MOI.txt` |
| [`english/`](english/) | Version anglaise + guide `README.txt` |

Les deux versions marchent pareil. `configure.py` et `start.py` ouvrent celle de
la langue choisie ; tu peux aussi lancer les scripts directement depuis leur dossier.

## Avertissement

Outil de fan non officiel, sans lien avec Kyara. Automatiser un jeu peut aller contre ses conditions d'utilisation : **à utiliser à tes risques**.

## Soutien

Si ce programme te fait gagner du temps, tu peux me soutenir avec un petit tip sur Ko-fi ☕
**[ko-fi.com/nylen9](https://ko-fi.com/nylen9)**
