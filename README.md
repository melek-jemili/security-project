# DemoApp — atelier « Secure Web »

Application minimaliste à lancer **en local uniquement** :

- `vulnerable/app.py` — port **5000** — exemples volontaires de SQLi, XSS réfléchi, XSS stocké et CSRF.
- `secure/app.py` — port **5001** — version corrigée des fonctionnalités historiques.

La version vulnérable écoute uniquement sur `127.0.0.1`. Ne l'exposez pas au
réseau et n'y ajoutez pas de hook BeEF ni de service tiers. Les exemples utilisent
des comptes et des données fictifs. L'application s'ouvre sur la page de connexion ;
après connexion, le catalogue est accessible. Les produits sont stockés dans la
table SQLite `products`.

## Installation

```powershell
cd C:\Users\EXTRA\Downloads\securedemo\securedemo
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Lancement

```powershell
cd vulnerable
python app.py
```

Ouvrir `http://127.0.0.1:5000` (redirection vers `/login`). La base SQLite est réinitialisée au démarrage
avec les comptes fictifs `admin / SuperSecret123` et `melek / motdepasse1`.

## Déploiement sur Render

Le dépôt inclut `render.yaml` pour créer un **Web Service** Flask (pas un Static
Site). Dans Render, créez un Blueprint depuis le dépôt et utilisez les valeurs
du fichier. Elles installent les dépendances puis démarrent la version corrigée
avec Gunicorn. `SECRET_KEY` est générée automatiquement par Render.

La version vulnérable est volontairement réservée aux démonstrations locales ;
ne l'exposez pas publiquement. Les données SQLite écrites par l'application
hébergée ne sont pas garanties après un redémarrage ou un nouveau déploiement.

## Démonstrations

1. **SQL Injection — `/login`**  
   La requête de connexion vulnérable concatène directement les champs reçus.
   Une saisie SQL dans le nom d'utilisateur permet d'illustrer un contournement ;
   la version `secure` utilise des requêtes paramétrées.

2. **XSS réfléchi — `/search`**  
   La page réaffiche la recherche sans échappement HTML. Observez le rendu avec
   un marqueur inoffensif dans cet environnement local.

3. **XSS stocké — `/product/<id>`**  
   Un commentaire de produit est enregistré puis affiché sans échappement.
   Pour l'atelier, utilisez uniquement du contenu inoffensif. Aucun hook BeEF,
   vol de données ou appel externe n'est fourni.

4. **CSRF — `/csrf-demo`**  
   Après connexion, le formulaire modifie la préférence de produit du compte
   sans jeton CSRF. Le tableau de bord permet de constater ce changement sans
   conséquence. Cette page locale illustre l'action vulnérable, pas un site tiers :
   en situation réelle, la possibilité d'une requête cross-site dépend aussi des
   attributs des cookies et du navigateur.

## Correctifs à retenir

- **SQLi :** utiliser des requêtes paramétrées, jamais la concaténation.
- **XSS :** conserver l'échappement automatique des templates et valider le
  contenu selon son contexte d'affichage.
- **CSRF :** valider un jeton imprévisible côté serveur pour chaque requête
  modifiant l'état ; configurer également les cookies de session avec `SameSite`.
- **Mots de passe :** les hacher et ne jamais renvoyer les erreurs SQL brutes.
