# Superguide : Pharma Sales Lake sur AWS

Ce guide explique tout, pas à pas, pour refaire le projet sur n'importe quel ordinateur, **sans compte AWS et sans payer**.
Lis les étapes **dans l'ordre** et copie les commandes **exactement**.

---

## 0. L'histoire du projet (à raconter en entretien)

C'est **ton vrai problème de Global Pharma**, reconstruit avec des outils AWS et des données inventées :

- 4 grossistes envoient chaque semaine un fichier de ventes ;
- chacun a **son format** : séparateur, virgule ou point, format de date, encodage ;
- chacun **nomme les médicaments à sa façon**, et un grossiste peut même écrire le même médicament de deux manières (`SUS` et `SUSP`) ;
- les fichiers sont **cumulés** : le fichier de la semaine 38 contient aussi les semaines 27 à 37.

**Ton travail** : construire sur AWS un lac de données qui :
- lit automatiquement chaque fichier dès qu'il arrive ;
- **refuse** un fichier qui contient un nom inconnu, au lieu de le perdre en silence ;
- supprime les doublons ;
- **prouve** avec des tests que le résultat final correspond au dernier fichier.

---

## 1. AWS en 2 minutes

AWS (Amazon Web Services) loue des ordinateurs et des services sur Internet. Voici ceux du projet :

| Service | C'est comme… | Rôle dans le projet |
|---|---|---|
| **S3** | Un disque dur sur Internet, rangé en « buckets » | Recevoir les fichiers, stocker le lac de données |
| **Lambda** | Un petit programme qui se réveille tout seul | Lire, traduire et vérifier chaque nouveau fichier |
| **DynamoDB** | Un cahier de bord très rapide | Noter chaque fichier traité et son statut |
| **SQS** | Une boîte aux lettres | Recevoir les alertes (« nom inconnu ») et les erreurs |
| **IAM** | Les badges d'accès | La Lambda n'a le droit de toucher qu'à ce dont elle a besoin |
| **CloudWatch** | Le journal | Les messages de la Lambda |
| **Athena** | Du SQL sur des fichiers S3 | Interroger les résultats (sur le vrai AWS seulement) |

**LocalStack** est un **faux AWS** qui tourne dans Docker, sur ton PC. C'est gratuit, et il ne faut ni compte ni carte bancaire.
**Terraform** crée toute l'infrastructure à partir de fichiers texte : c'est de l'*Infrastructure as Code*. Le même code fonctionne sur LocalStack et sur le vrai AWS.

---

## 2. Ce qu'il faut installer (une seule fois)

1. **Docker Desktop** : https://www.docker.com/products/docker-desktop
   - Installe-le, redémarre l'ordinateur, puis ouvre Docker Desktop.
   - Attends que la baleine soit **verte** (« Engine running »).
2. **Git** : https://git-scm.com/downloads (clique sur « Next » partout).
3. **VS Code** : https://code.visualstudio.com

Tu n'as **pas besoin** d'installer Python, Terraform ou AWS : tout tourne dans Docker.

---

## 3. Récupérer le projet

Ouvre PowerShell (touche Windows, tape `PowerShell`, Entrée), puis :

```bash
cd $HOME\Downloads
```
```bash
git clone https://github.com/Isac9/pharma-sales-lake-aws.git
```
```bash
cd pharma-sales-lake-aws
```

Toutes les commandes suivantes se tapent **dans ce dossier**.

---

## 4. Démarrer le faux AWS

```bash
docker compose up -d localstack
```

Attends environ 20 secondes. Pour vérifier que tout est prêt :
```bash
curl.exe http://localhost:4566/_localstack/health
```
Tu dois voir `"s3": "available"` (ou `"running"`).

---

## 5. Créer l'infrastructure avec Terraform

**5.1 Préparer Terraform.** Il télécharge le « traducteur » AWS, environ 1 minute :
```bash
docker compose run --rm terraform init
```
Tu dois lire : `Terraform has been successfully initialized!`

**5.2 Voir ce qui va être créé, sans rien créer :**
```bash
docker compose run --rm terraform plan
```
La dernière ligne doit ressembler à `Plan: 18 to add, 0 to change, 0 to destroy`.

**5.3 Créer pour de vrai :**
```bash
docker compose run --rm terraform apply -auto-approve
```
Tu dois lire : `Apply complete!`

Tu viens de créer :
- 2 buckets S3 ;
- 1 Lambda, avec ses droits IAM et son journal ;
- 1 table DynamoDB ;
- 2 files SQS ;
- le déclencheur « nouveau fichier → Lambda ».

---

## 6. Faire tourner le lac de données

**6.1 Créer les fichiers des grossistes.** Ils sont rangés dans `data/landing/` :
```bash
docker compose run --rm tools python -m lake.generate
```

**6.2 Déposer les fichiers dans S3**, comme le feraient les grossistes :
```bash
docker compose run --rm tools python -m lake.upload
```
Pour chaque fichier, la Lambda se déclenche toute seule et tu vois `LOADED`.
La toute première fois, la Lambda met environ 30 secondes à démarrer. C'est normal.

**6.3 Construire la couche « gold »** : dédoublonnage et tests.
```bash
docker compose run --rm tools dbt build --project-dir dbt
```
Tu dois lire : `Done. PASS=11 WARN=0 ERROR=0`.

**6.4 Voir le résultat :**
```bash
docker compose run --rm tools python -m lake.report
```

| Colonne | Signification |
|---|---|
| `rows_all_files` | Lignes si on additionne tous les fichiers (faux) |
| `rows_deduplicated` | Lignes réelles, après dédoublonnage |
| `naive_revenue_m_xof` | Chiffre d'affaires faux, en millions de FCFA |
| `true_revenue_m_xof` | Chiffre d'affaires réel |
| `overstatement_x` | Combien de fois le chiffre naïf est trop gros (environ **6 fois**) |

---

## 7. La démo à savoir faire : « SUS » et « SUSP »

**7.1 Distrimed se met à écrire `SUSP` à partir de la semaine 33 :**
```bash
docker compose run --rm tools python -m lake.generate --new-variant
```
```bash
docker compose run --rm tools python -m lake.upload --wholesaler distrimed
```
Résultat :
```
landing/distrimed/2026-W32.csv   LOADED
landing/distrimed/2026-W33.csv   REJECTED  unknown={"product": {"AMOXICILLINE 250 SUSP": 7, ...}}
```

**7.2 Lire l'alerte dans SQS :**
```bash
docker compose run --rm tools python -m lake.status
```

**7.3 Corriger.** Ouvre `reference/product_aliases.csv` dans VS Code, ajoute ces 4 lignes à la fin, puis enregistre :
```
distrimed,AMOXICILLINE 250 SUSP,P003
distrimed,METRONIDAZOLE 125 SUSP,P005
distrimed,COTRIMOXAZOLE 240 SUSP,P007
distrimed,PARACETAMOL 120 SIROP,P010
```

**7.4 Envoyer la nouvelle table dans S3, puis relivrer les fichiers :**
```bash
docker compose run --rm terraform apply -auto-approve
```
```bash
docker compose run --rm tools python -m lake.upload --wholesaler distrimed
```
Cette fois, tout est `LOADED`. Les fichiers déjà chargés ne sont pas retraités : c'est l'**idempotence**.

**7.5 Revenir aux données normales.** Annule tes 4 lignes avec Ctrl + Z, puis enregistre. Ensuite :
```bash
docker compose run --rm terraform apply -auto-approve
```
```bash
docker compose run --rm tools python -m lake.generate
```
```bash
docker compose run --rm tools python -m lake.upload --wholesaler distrimed
```

---

## 8. Les tests

```bash
docker compose run --rm tools pytest -q
```
Résultat : `12 passed`.

Sur GitHub, à chaque envoi de code, un robot rejoue **tout** le projet : il démarre LocalStack, lance Terraform, la Lambda et dbt. C'est le badge vert « CI » du README.

---

## 9. (Plus tard) Déployer sur le vrai AWS

Quand tu auras un compte AWS :
1. Crée un utilisateur IAM avec une clé d'accès, dans la console AWS. **Ne mets jamais cette clé dans le code ni sur GitHub.**
2. Installe AWS CLI et Terraform sur ton PC, puis tape `aws configure` et colle ta clé.
3. Lance :
```bash
cd infra
```
```bash
terraform init
```
```bash
terraform apply -var localstack=false -var suffix=isac9
```
4. Après ta démo, **détruis tout** pour ne rien payer :
```bash
terraform destroy -var localstack=false -var suffix=isac9
```

---

## 10. Arrêter proprement

```bash
docker compose down
```
LocalStack oublie tout à l'arrêt. La prochaine fois, refais les étapes 4, 5.3 et 6.

Si Terraform se plaint au redémarrage (il croit que les ressources existent encore), efface sa mémoire :
```bash
Remove-Item infra\terraform.tfstate*
```
Ensuite, refais `terraform apply`.

---

## 11. GitHub

Tout est expliqué dans le guide du projet PartnerHub, section 10 : https://github.com/Isac9/partnerhub-data-platform/blob/main/GUIDE.md

Le cycle à retenir :
```bash
git add -A
```
```bash
git commit -m "Describe what you changed"
```
```bash
git push
```
Ensuite, regarde l'onglet **Actions** du dépôt : une coche verte signifie que tout est bon.

---

## 12. Problèmes fréquents

| Message | Solution |
|---|---|
| `failed to connect to the docker API` | Ouvre Docker Desktop et attends la baleine verte. |
| `Could not connect to the endpoint URL` | LocalStack n'est pas lancé : `docker compose up -d localstack`. |
| `NoSuchBucket` ou `ResourceNotFoundException` | LocalStack a redémarré : refais `terraform apply` (étape 5.3). |
| `no result for ... after 300s` | La Lambda a planté : `python -m lake.status` affiche la file d'erreurs. |
| `port is already allocated` | Un autre programme utilise le port 4566 : arrête-le. |

---

## 13. Phrases d'entretien (en anglais)

- *"I built a serverless ingestion pipeline on AWS with Terraform: S3 events trigger a Lambda that parses four wholesaler formats and maps product names to canonical codes."*
- *"A file with an unknown product name is rejected as a whole and raises an SQS alert. A partial load would give totals that look plausible but are too low. This is a problem I actually had at work."*
- *"The files are cumulative: summing them overstates revenue about six times. The gold layer deduplicates, and a dbt test reconciles it with the latest file."*
- *"Ingestion is idempotent: each file's ETag is logged in DynamoDB."*
- *"Everything runs on LocalStack in CI, and the same Terraform code deploys to a real AWS account."*
