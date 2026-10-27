# Verser les collections de votre musée dans TRACES

TRACES présente aux visiteurs des objets de musée liés à l'enfance, leur pose
une question sur leurs propres souvenirs et enregistre leur témoignage. Les
souvenirs s'accumulent ainsi autour de chaque objet.

L'installation réunit aujourd'hui **230 œuvres de cinq institutions** : la
Maison des collections de la Ville de Mons, Abby, Le Fresnoy, le Huis van
Alijn et le MUMONS. Tous les textes existent en **français, néerlandais et
anglais**.

Ce guide explique comment votre musée peut y ajouter ses propres œuvres. Il
s'adresse d'abord aux équipes des musées ; la dernière partie décrit les
commandes à lancer par l'équipe technique.

## En bref

| Étape | Qui | Quoi |
| --- | --- | --- |
| 1 | Le musée | Choisit ses œuvres et remplit le modèle de tableur `template_collection.xlsx` |
| 2 | Le musée | Rassemble les images et vidéos, et les envoie avec le tableur |
| 3 | L'équipe technique | Intègre les œuvres et prépare les traductions dans les deux autres langues |
| 4 | Le musée | Relit les traductions dans un classeur Excel |
| 5 | L'équipe technique | Intègre les corrections et met le kiosque à jour |

Le musée n'a rien à installer : tout se fait dans Excel.

## 1. Choisir les œuvres

Les partenaires actuels ont fourni entre 4 et 99 œuvres chacun. Quelques
repères :

- **Un lien avec l'enfance** : jouets, école, photographies de famille,
  vêtements, archives (actes, lettres), fêtes, objets du quotidien…
- **Des images de bonne qualité** : les œuvres sont affichées en grand, sur un
  écran de 44 pouces.
- **Des droits d'utilisation** : les images et les textes sont affichés dans
  l'installation **et publiés dans ce dépôt GitHub, qui est public**. Le
  musée doit pouvoir autoriser ces deux usages.
- **Des personnes reconnaissables** : pour une photographie de personnes
  vivantes identifiables, assurez-vous que leur accord le permet.

Chaque œuvre est associée à **une des 12 questions** posées au visiteur juste
après l'avoir découverte. Choisissez pour chaque œuvre la question qui lui
correspond le mieux :

| N° | Question posée au visiteur |
| --- | --- |
| 1 | Et vous ? Comment était votre enfance ? Était-elle heureuse, triste, ennuyeuse ? Quel est le premier souvenir qui vous vient à l'esprit quand vous pensez à votre enfance ? |
| 2 | Si vous aviez un espace très limité pour conserver des souvenirs, quels sont les 3 souvenirs que vous garderiez ? |
| 3 | Et vous ? Conservez-vous un objet spécial ou symbolique de votre enfance, hérité de vos parents ? Pouvez-vous nous raconter son histoire ? |
| 4 | Enfant, vous souvenez-vous de vous être réveillé la nuit à cause d'un cauchemar ? Ou au contraire, y a-t-il un rêve agréable et marquant dont vous vous souvenez encore ? |
| 5 | Aviez-vous des animaux de compagnie quand vous étiez enfant ? Quel est votre meilleur souvenir d'enfance avec un animal ? |
| 6 | Quel était votre jeu préféré quand vous étiez enfant ? |
| 7 | Avez-vous un souvenir d'enfance lié à une lettre — écrite, envoyée ou reçue — qui vous a marqué ? Pouvez-vous nous raconter votre histoire ? |
| 8 | Savez-vous pourquoi vos parents ont choisi votre prénom ? Quelle est l'histoire derrière ce choix ? |
| 9 | Avez-vous un souvenir d'enfance lié à un vêtement particulier ou à un uniforme que vous portiez quand vous étiez petit ? |
| 10 | Quel est votre meilleur souvenir d'enfance lié à une fête comme la Saint-Nicolas ou Noël ? |
| 11 | Quel est le premier souvenir d'enfance marquant, lié à des retrouvailles avec des êtres chers, qui vous vient à l'esprit ? |
| 12 | Et vous, quand vous étiez enfant et que vous aviez besoin d'être réconforté ou protégé, vos parents ou grands-parents invoquaient-ils un saint, un proche ou un personnage particulier, réel ou imaginaire ? Aviez-vous une figure protectrice ? Qui était-ce ? |

## 2. Remplir le tableur

Ouvrez `template_collection.xlsx` et remplissez la feuille **« Œuvres »**,
une ligne par œuvre à partir de la ligne 3. La ligne 1 rappelle le contenu de
chaque colonne et la ligne 2 contient les en-têtes : ne les modifiez pas. La
feuille « Exemple » montre une ligne remplie.

| Colonne | Obligatoire | Contenu | Exemple |
| --- | --- | --- | --- |
| Database ID | non | **À laisser vide** : TRACES attribue les identifiants | |
| Museum ID | oui | Numéro d'inventaire de l'objet chez vous | `INV.1987.042` |
| Origin | oui | Nom de votre institution, identique sur toutes les lignes | `Musée de l'Exemple` |
| Language | oui | Langue des textes de la ligne : `fr`, `nl` ou `en` | `fr` |
| Type of object | oui | Une catégorie de la feuille « Types » (liste déroulante) | `Toy or game` |
| Date /period | oui | Date ou période, sous une forme lisible | `1935`, `1870-1880`, `19e siècle` |
| Title | oui | Titre affiché au visiteur | `Ours en peluche` |
| Author | non | Auteur, artiste ou fabricant | |
| Name | non | Personnes liées à l'objet (modèle, destinataire…) | |
| Storage place | non | Ville ou lieu de conservation | `Mons` |
| Keywords | oui | Mots-clés sur la forme **et** le contenu, séparés par des virgules | `ours, peluche, jouet, tissu usé` |
| Emotions | oui | 2 à 4 émotions de la feuille « Émotions », séparées par des virgules | `Joie, Confiance` |
| Explanation | oui | Texte de présentation lu par le visiteur | 3 à 8 phrases |
| Question | oui | Numéro de la question associée (1 à 12, voir plus haut) | `3` |
| Media | oui | Noms des fichiers images ou vidéos, séparés par des virgules | `INV_1987_042_face.jpg` |

Quelques conseils :

- **Une seule langue par ligne.** Écrivez chaque œuvre dans la langue où vous
  êtes le plus à l'aise ; les lignes peuvent être dans des langues
  différentes. Les deux autres langues sont préparées pour vous (étape 3).
- **Le texte « Explanation »** est lu à l'écran, debout, par un public
  familial : phrases courtes, pas de jargon. Décrivez concrètement ce que
  montre l'objet et son histoire. Ce texte sert aussi à rapprocher les œuvres
  qui se ressemblent.
- **Les émotions** viennent de la roue des émotions de Plutchik : joie,
  confiance, tristesse, sérénité… (« nostalgie », par exemple, n'en fait pas
  partie). Les libellés français, néerlandais ou anglais de la feuille
  « Émotions » sont tous acceptés. Elles servent à proposer au visiteur des
  œuvres qui se répondent.
- **Un type d'objet absent de la liste** est accepté, mais il sera créé et
  traduit à part : préférez une catégorie existante quand c'est possible.

**Objets portant un texte** (lettre, acte, inscription, étiquette) : utilisez
aussi la feuille facultative **« Transcriptions »**. Recopiez le texte tel
qu'il est écrit sur l'objet (orthographe d'origine), avec une courte
explication pour le visiteur, et reprenez le même Museum ID que dans
« Œuvres ».

## 3. Préparer les médias

| Média | Format attendu | Remarques |
| --- | --- | --- |
| Images | JPG ou TIF, au moins 1 500 px sur le grand côté | Converties et réduites à 2 000 px par nos soins. Une image par vue ; la **première** de la colonne Media sert de vignette |
| Vidéos | MP4 (codec H.264), **moins de 100 Mo** par fichier | Un extrait de 30 secondes à 3 minutes suffit. Une vignette est extraite automatiquement |

Deux points importants pour les vidéos :

- **Elles sont jouées sans le son**, en boucle et sans boutons de lecture.
  Si la parole compte, fournissez une version sous-titrée (sous-titres
  incrustés dans l'image).
- Les formats MOV et les fichiers bruts d'appareil photo (NEF, CR2…) ne sont
  pas pris en charge : exportez-les en MP4 ou en JPG.

Inutile de renommer vos fichiers : indiquez simplement leur nom exact dans la
colonne Media. Envoyez le tableur et un dossier contenant tous les médias
(par WeTransfer, SharePoint ou une clé USB).

## 4. Relire les traductions

Nous traduisons vos textes dans les deux autres langues avec
[DeepL](https://www.deepl.com), puis nous vous envoyons le classeur de
relecture `review_translations.xlsx`. Une traduction automatique ne suffit
pas pour un texte affiché au public : **votre relecture est indispensable**.

Dans le classeur :

- chaque feuille correspond à un type de texte (Titres, Descriptions, mots-clés,
  Transcriptions…) ; la colonne `id` est l'identifiant TRACES de chaque œuvre.
  Le classeur contient les textes de tous les partenaires : **nous vous
  indiquons les identifiants de vos œuvres**, ne relisez que ces lignes ;
- **corrigez uniquement les cellules jaunes**. Celles qui portent le
  commentaire « Traduction automatique (DeepL) — à relire » n'ont encore été
  relues par personne ;
- les cellules grises (identifiant, texte d'origine) ne doivent pas être
  modifiées, et les lignes ne doivent être ni ajoutées, ni supprimées, ni
  déplacées.

Ce qu'il faut vérifier : le sens, le vocabulaire propre à votre domaine, les
noms propres, les titres (faut-il les traduire ou les garder tels quels ?) et
le registre : vouvoiement ou tutoiement, cohérent avec le reste de vos
textes.

Selon le calendrier, les traductions automatiques peuvent être mises en
service en attendant votre relecture ; vos corrections les remplacent alors à
la mise à jour suivante.

## 5. Mise en service

L'équipe technique intègre vos corrections, vérifie la base, puis met à jour
le kiosque sans perdre les témoignages déjà recueillis
(procédure : [`docs/update-collection.md`](../docs/update-collection.md)).

Vos œuvres apparaissent alors dans le parcours. Les témoignages que les
visiteurs laissent à leur sujet sont relus par l'équipe du lieu d'exposition
avant d'être montrés aux visiteurs suivants. **Les témoignages des visiteurs
restent sur l'ordinateur de l'installation** : ils ne sont jamais publiés
dans ce dépôt.

### Ce que deviennent vos données

Les images, vidéos et textes de vos œuvres sont publiés dans ce dépôt GitHub
public. Ils ne sont pas couverts par la licence du code : **ils restent votre
propriété** et ne peuvent pas être réutilisés sans votre accord.

---

## Pour l'équipe technique

### Prérequis

- Python 3.9 ou plus récent, puis :
  `pip install openpyxl pillow deepl sentence-transformers sqlite-vec numpy`
- [ffmpeg](https://ffmpeg.org) pour les vignettes des vidéos
- Une clé d'API DeepL. Le plan gratuit (« Developer ») offre un **crédit
  unique de 1 000 000 de caractères, qui ne se renouvelle pas** ; au-delà, il
  faut passer à un plan payant. Une collection de 100 œuvres demande entre
  50 000 et 200 000 caractères selon la longueur des notices : le crédit
  gratuit couvre donc plusieurs collections. `--dry-run` donne le chiffre
  exact sans rien consommer, et le script affiche le crédit restant à chaque
  passage. La clé se passe par la variable d'environnement `DEEPL_AUTH_KEY`
  (sous Windows PowerShell : `$env:DEEPL_AUTH_KEY = "votre-clé"`).

Les textes envoyés à DeepL sont les notices publiques des œuvres, jamais les
témoignages.

### Intégrer une nouvelle collection

Depuis le dossier `database/` :

```bash
# 1. médias : conversion et noms normalisés, dans un dossier de travail HORS du dépôt
python prepare_media.py "<dossier livré par le musée>" "<dossier de travail>"
#    puis copier les images et vidéos (pas le CSV) dans ../assets/

# 2. œuvres : vérifier d'abord (--dry-run n'écrit rien), puis importer
python import_collection.py pp1_collection.db "<tableur du musée>.xlsx" --assets ../assets --dry-run
python import_collection.py pp1_collection.db "<tableur du musée>.xlsx" --assets ../assets

# 3. traductions : estimer le volume, puis traduire vers le classeur de relecture
python translate_collection.py pp1_collection.db review_translations.xlsx --dry-run
python translate_collection.py pp1_collection.db review_translations.xlsx

# 4. charger les traductions en base
python import_translations.py pp1_collection.db review_translations.xlsx

# 5. vecteurs sémantiques (obligatoire : sans vecteur, le serveur du kiosque ne démarre pas)
python compute_embeddings.py pp1_collection.db

# 6. contrôle final : doit afficher « BASE PRÊTE À DÉPLOYER »
python check_collection.py --db pp1_collection.db --images ../assets
```

Puis committer `database/pp1_collection.db`, `database/review_translations.xlsx`
et les nouveaux fichiers de `assets/`, et déployer sur le kiosque avec
[`docs/update-collection.md`](../docs/update-collection.md).

Le rapport de `import_collection.py` signale chaque problème du tableur
(type ou émotion inconnus, média introuvable, colonne obligatoire vide…) et
liste les identifiants attribués, à communiquer au musée pour la relecture.
Faites corriger le tableur et relancez : l'import ne crée jamais de doublon.
Pour modifier des œuvres déjà intégrées, ajoutez `--update`, toujours avec le
tableur du musée concerné (jamais `PP1-Collection_Database.xlsx`, refusé) ;
une valeur non reconnue n'écrase jamais la valeur existante.
`--origin "<nom du musée>"` limite l'import à un musée.

`translate_collection.py --ids 235-260` limite la traduction à certaines
œuvres ; `--keep-titles` recopie les titres sans les traduire (titres de
films, noms propres).

### Au retour de la relecture

```bash
python import_translations.py pp1_collection.db review_translations_corrige.xlsx
python compute_embeddings.py pp1_collection.db        # si des descriptions françaises ont changé
python check_collection.py --db pp1_collection.db --images ../assets
```

Remplacer ensuite `review_translations.xlsx` par le classeur corrigé avant de
committer. Le classeur étant unique, ne l'envoyer qu'à un musée à la fois. Une ligne dont le texte d'origine a changé depuis la traduction
est laissée de côté (avec un avertissement) : relancer alors
`translate_collection.py`.

### Contenu du dossier

| Fichier | Rôle |
| --- | --- |
| `pp1_collection.db` | La base SQLite de référence, lue par le serveur du kiosque |
| `template_collection.xlsx` | Le modèle de tableur à envoyer aux musées |
| `PP1-Collection_Database.xlsx` | Le tableur source des 230 œuvres actuelles (même format) |
| `review_translations.xlsx` | Le classeur de relecture : source de vérité de tous les textes FR / NL / EN |
| `prepare_media.py` | Conversion et renommage des médias livrés par un musée |
| `import_collection.py` | Import des œuvres d'un tableur dans la base |
| `translate_collection.py` | Traductions DeepL vers le classeur de relecture |
| `import_translations.py` | Import du classeur de relecture dans la base |
| `compute_embeddings.py` | Vecteurs sémantiques des descriptions (choix des œuvres proposées) |
| `check_collection.py` | Contrôle avant déploiement : médias, vecteurs, traductions |
| `schema.sql`, `SCHEMA.md` | Le schéma de la base et sa documentation technique |

Les anciens scripts de migration (V3 à V11) ont été appliqués à la base puis
retirés du dépôt ; ils restent consultables dans l'historique Git. Leur
historique est résumé dans [`SCHEMA.md`](SCHEMA.md).
