# Le fil : notice technique

Appli web privée pour deux personnes (Luka et Jules) : fil de discussion, fichiers, outils, rédaction, mots magiques.

- **Adresse** : https://luka-chappuis.github.io/le-fil/ (GitHub Pages, branche `main`, racine du dépôt)
- **Serveur** : Supabase, projet « Fil Luka-Jules » (id `eonjswzamgpzszaidfxu`, région Paris), organisation « Cordeau »

## Organisation des fichiers

- `source/src/index.html` : l'appli entière (HTML, CSS, JavaScript), à modifier ici.
- `source/public/` : service worker (`sw.js`), manifeste d'installation, icônes.
- `source/build.js` : assemble le site dans `dist/site` (intègre la bibliothèque Supabase et les photos chiffrées).
  Ensuite, copier le contenu de `dist/site` à la racine du dépôt et pousser sur `main`.
- `source/decor-chiffre.json` : photos d'origine (images-émojis et mots magiques), chiffrées.
  La clé n'est lisible que par les deux membres connectés (table `decor_cle`). Ni la clé ni les photos en clair ne sont dans ce dépôt.
- `source/test/essai.py` : essais d'interface (Playwright, serveur Supabase simulé, site servi sur http://localhost:8765).
- `source/test/essai_v8.py` : essais des fonctions de la v8 (photos, réponses, modification, « écrit… », recherche, envoi différé, mode sombre).

Pour reconstruire : `cd source && npm install && node build.js`.
À chaque version, changer le nom du cache dans `public/sw.js` (`le-fil-vN`) pour forcer la mise à jour sur les appareils.

## Côté serveur (Supabase)

Tables (toutes protégées par des règles d'accès : seuls les deux membres y accèdent) :
`members`, `messages`, `reactions`, `reads` (« Vu »), `tasks` (liste à deux), `push_subscriptions` (appareils abonnés aux notifications),
`mots_magiques` (mot et chemin de l'image), `reglages`, `decor_cle`.
Colonnes ajoutées en v8 sur `messages` : `reply_to` (message cité), `edited_at` (rempli par la base à chaque modification), `client_id` (identifiant unique choisi par l'appareil, évite les doublons quand un message en attente repart).
Modification : sur ses propres messages, seuls le texte (`body`) et le fichier (`file_path`, `file_name`, `file_size`, `file_type`) peuvent changer. Le déclencheur `messages_limiter_modification` n'accepte un nouveau fichier que pour un message qui en avait déjà un, déposé dans son propre dossier ; l'appli supprime ensuite l'ancien fichier du stockage.
Stockage : compartiment privé `fichiers` (fichiers envoyés dans `<id membre>/…`, images des mots magiques dans `<id membre>/magie/…`).

Fonctions :
- `inscription` : création de compte, fermée une fois les deux membres inscrits.
- `assistant` : rédaction (corriger, reformuler, traduire, demande libre) avec Claude. La clé `ANTHROPIC_API_KEY` est un secret Supabase.
- `notifier` : notifications même appli fermée. Appelée par la base à chaque nouveau message ; ses clés sont dans le coffre-fort Supabase.

## Fonctions de l'appli

Messages en temps réel, fichiers jusqu'à 20 Mo, réactions, « Vu », émojis et images-émojis, notifications (son au choix),
outils en haut (calculatrice, prix et marges avec commission, convertisseur avec monnaies BCE, liste à deux, rédaction),
mots magiques gérés dans Réglages (roue dentée) : la photo passe au premier plan quelques secondes.

Ajouts v8 : photos affichées dans le fil (agrandies au clic, réduites à 2560 px avant l'envoi), réponse à un message précis,
modification de ses messages, et sur une photo ou un fichier : « Modifier » propose le texte ou l'image / le fichier (remplacement) (un texte envoyé avec un seul fichier devient sa légende), « Jules écrit… » (diffusion temps réel, rien n'est enregistré), recherche (loupe),
messages vocaux (micro), mode sombre en option (Réglages, clair par défaut, choix gardé par appareil), pastille de non-lus sur l'icône, messages écrits hors connexion
gardés sur l'appareil et envoyés au retour du réseau.
