# Analyse d'écart & Feuille de route — 12 Features du Framework

> Référence : diagramme « Features » (workflow E/E Architect Design en 12 étapes).
> Objectif de ce document : cartographier chaque feature par rapport au code C existant
> (`src/`, `inc/`) et à la chaîne de documentation Python (`tools/scripts/`), identifier
> les manques, et proposer un plan d'implémentation — avec un focus détaillé sur la
> **feature #6 (sélection de stratégie de mapping au runtime)**.

Légende d'état :
- ✅ **Implémenté** — présent et fonctionnel dans le core.
- 🟡 **Partiel** — mécanique présente mais incomplète, figée en dur, ou hors du core C.
- ⛔ **Manquant** — à construire.

---

## 1. Tableau de synthèse

| # | Feature | État | Où c'est (ou devrait être) | Écart principal |
|---|---------|:----:|----------------------------|-----------------|
| 1 | System/Object definition/Creation | ✅ | `EEC_architecture.c`, `EEC_component_loader.c`, `validate_ecu_json.py` | RAS. Création System/Component/Sensor/Actuator/ECU + validation JSON OK. |
| 2 | EE Object library | ✅ | `library/` (ecus, systems, components, sensors, actuators, bundles, platform.json) | RAS. Infrastructure (ECU, dashboard…) présente. |
| 3 | Import/Export (+ CAN DBC) | ✅ | `EEC_library.c`, `EEC_export.c` (JSON) ; `EEC_dbc.c` (export + import DBC dans le core C) | RAS. Export DBC câblé dans `main.c` ; import activable via `EEC_IMPORT_DBC`. Round-trip couvert par `qa/test_dbc_roundtrip.c`. |
| 4 | ECU IO Needs reservation | ✅ | `EEC_estimation.c` (buckets par interface, propositions SMALL/MEDIUM/LARGE + mix) | RAS. Estimation par type d'IO présente. |
| 5 | System/Function repartition (Zonal/Central) | ✅ | `EEC_zone.c/.h` (modèle zones + mode) ; `EEC_connect.c` (routage zonal) ; `main.c` | Mode CENTRAL/ZONAL sur `EEC_Architecture_t`, `EEC_Zone_t`, API CreateZone/AssignSystemToZone, chargement `EEC_ZONES=<json>`, export `zones.json`, règle de vérif zones. |
| 6 | IO Mapping strategy selection | ✅ | `EEC_connect.c` (`EEC_Architecture_AutoMap` dispatcher) ; `main.c` | Sélecteur runtime via `EEC_MAP_STRATEGY` (smart/order/zone/strict), défaut smart. |
| 7 | IO Mapping system↔ECU | ✅ | `EEC_connect.c` (SmartMap 7 niveaux, strict per-signal, MapToEcu) | RAS. Moteur de mapping complet. |
| 8 | Network Topology | ✅ | `EEC_main_helpers.c` (7 bus : Tractor/Powertrain/ISOBUS/Diag/Hydraulics/LIN/Eth), `EEC_connect.c` | Bus + affectation ECU présents. Manque éventuel : import d'une topologie commune + adresses ECU pilotées par données. |
| 9 | Rules Verifications | ✅ | `EEC_verify.c` (21 règles V1–V13, B1–B8 : électrique, sécurité, câblage, naming) | RAS. |
| 10 | Save Json Architecture | ✅ | `EEC_export.c` (`exported_architecture.json`, `exported_physical_architecture.json`) | RAS. |
| 11 | Generate Doc | ✅ | ~44 générateurs `tools/scripts/*.py` (pinout, topologie, dataflow, connector view, system view, signal dictionary) | RAS. « CAN database » dépend de #3 (DBC). |
| 12 | Export Doc Package to Polarion | ✅ | `push_document_to_polarion.py`, `push_requirements_to_polarion.py`, `polarion_config*.json`, `package_release.py` | RAS (connecteur ReqIF/REST à configurer côté client). |

**Bilan :** 12/12 ✅, 0 🟡, 0 ⛔. Toutes les features du workflow sont implémentées
dans le core. Extension en cours de cadrage : ingestion du fichier machine-config
(.mc) pour dériver automatiquement les systèmes/variants présents (voir groundwork).

---

## 2. Feuille de route des 3 manques

### Priorité recommandée
1. **#6 — Sélecteur de stratégie de mapping au runtime** (rapide, forte valeur, débloque la démo)
2. **#5 — Modèle Zonal/Central** (s'appuie sur #6)
3. **#3 — DBC import/export dans le core C** (plus volumineux, autonome)

---

## 3. ⭐ Focus feature #6 — IO Mapping strategy selection (runtime)

### 3.1 Problème actuel
Les 4 stratégies existent déjà et sont fonctionnelles :

| Stratégie | Fonction | État dans `main.c` |
|-----------|----------|--------------------|
| 1. SmartMap (score 7 niveaux) | `EEC_Architecture_AutoMapSmart` | active |
| 2. Registration-order | `EEC_Architecture_AutoMapAll` | commentée |
| 3. Zone routing | `EEC_System_connect_to_ecus` (sous-tableaux d'ECU) | commentée |
| 4. Strict per-signal | `EEC_System_connect_to_ecus_strict` | commentée |

Le choix se fait **en éditant/recompilant `main.c`** (commenter/décommenter des blocs).
Il n'existe pas de point de sélection unique piloté par une valeur (argument, variable
d'environnement, ou champ JSON).

### 3.2 Objectif
Sélectionner la stratégie **sans recompiler**, via un unique paramètre, avec une trace
indiquant la stratégie retenue — tout en gardant les 4 fonctions existantes intactes.

### 3.3 Conception proposée

**a) Nouvel enum + dispatcher** (nouveau fichier léger, ou ajout à `EEC_connect.h`) :

```c
/** @brief Stratégie de mapping IO sélectionnable au runtime. */
typedef enum EEC_MapStrategy_e {
    EEC_MAP_STRATEGY_SMART = 0,   /**< Score-sorted 7 niveaux (défaut). */
    EEC_MAP_STRATEGY_ORDER,       /**< Ordre d'enregistrement. */
    EEC_MAP_STRATEGY_ZONE,        /**< Routage par zone (location ECU). */
    EEC_MAP_STRATEGY_STRICT       /**< Règles strictes par signal. */
} EEC_MapStrategy_t;

/** @brief Convertit un nom ("smart"|"order"|"zone"|"strict") en enum. */
EEC_MapStrategy_t EEC_MapStrategy_FromString(const char *name);

/** @brief Applique la stratégie choisie ; renvoie le nb de signaux mappés ou -1. */
int EEC_Architecture_AutoMap(EEC_Architecture_t *arch,
                             EEC_Ecu_t *const *ecus, uint32_t ecu_count,
                             EEC_MapStrategy_t strategy, FILE *trace);
```

**b) Implémentation du dispatcher** (`EEC_connect.c`) : un simple `switch` qui délègue
aux fonctions existantes. Pour `ZONE`, réutiliser la logique de découpage par
`location` d'ECU déjà esquissée dans le bloc commenté de `main.c`. Pour `STRICT`,
appliquer une policy par défaut (ou chargée depuis JSON en phase 2).

**c) Sélection de la source** dans `main.c` (par ordre de priorité) :
1. Variable d'environnement `EEC_MAP_STRATEGY` (ex. `smart`, `order`, `zone`, `strict`).
2. À défaut, valeur par défaut `EEC_MAP_STRATEGY_SMART`.

> Remarque : le core reste sans dépendance externe. La lecture d'un champ
> `"mapping_strategy"` dans un JSON de configuration d'architecture peut être ajoutée
> en phase 2 si souhaité.

**d) Trace** : écrire une ligne d'en-tête dans `automap_trace.txt` :
`[STRATEGY] selected = SMART (source: env EEC_MAP_STRATEGY)`.

### 3.4 Découpage en tâches
- [ ] T1. Ajouter `EEC_MapStrategy_t` + prototypes dans `EEC_connect.h`.
- [ ] T2. Implémenter `EEC_MapStrategy_FromString` + `EEC_Architecture_AutoMap` (switch) dans `EEC_connect.c`.
- [ ] T3. Remplacer le bloc « STRATEGY 1..4 » de `main.c` par un appel unique au dispatcher piloté par env var.
- [ ] T4. Émettre la ligne `[STRATEGY]` dans la trace.
- [ ] T5. Compiler (`run.ps1 -SkipRun`), lancer les 4 valeurs, comparer `automap_trace.txt`.
- [ ] T6. (option) documenter la variable dans `README.md` / `DEVELOPMENT.md`.

### 3.5 Effort & risques
- **Effort :** faible (réutilisation des 4 fonctions ; ~1 fichier .h + ~1 fonction .c + refactor de `main.c`).
- **Risque :** faible — aucune modification de la logique de mapping existante ; le défaut reproduit le comportement actuel (SmartMap).
- **Compat :** rétrocompatible (sans env var → comportement identique à aujourd'hui).

---

## 4. Feature #5 — Zonal/Central repartition (IMPLÉMENTÉ)

- **Modèle :** `EEC_ArchMode_t` (`CENTRAL` défaut / `ZONAL`) + `EEC_Zone_t` (nom + liste
  d'ECU) sur `EEC_Architecture_t` ; champ `zone` sur `EEC_System_t`.
  - `CENTRAL` → tous les systèmes routables sur l'ensemble des ECU (comportement historique).
  - `ZONAL` → chaque système assigné n'est mappé que sur les ECU de sa zone.
- **API (`EEC_zone.c/.h`) :** `SetMode`, `CreateZone`, `Zone_AddEcu`,
  `AssignSystemToZone`, `FindZone/FindEcu/FindSystem`.
- **Data-driven :** `EEC_Architecture_LoadZones` lit un JSON (`mode` + `zones[]` avec
  `ecus`/`systems`), activable dans l'app via `EEC_ZONES=<fichier>` (ex. `library/zones.json`).
  Remplace l'ancien matching par `strstr` sur les noms.
- **Routage :** stratégie `ZONE` de #6 rendue zone-aware ; auto-sélectionnée en mode ZONAL.
- **Export & vérif :** `EEC_Export_zones_json` (→ `exports/zones.json`) et `EEC_Verify_zones`
  (« tout système auto-mappable assigné à exactement une zone ; toute zone a ≥ 1 ECU »).

## 5. Feature #3 — CAN DBC dans le core C (IMPLÉMENTÉ)

- **Export :** `EEC_Export_dbc_bus` / `EEC_Export_dbc_all` (`EEC_dbc.c`) génèrent un
  `.dbc` Vector-compatible (BU_, BO_, SG_ : signé/non-signé, endianness, scale/offset,
  min/max, unités, receivers). Câblé dans `main.c` (un `.dbc` par bus CAN/ISOBUS).
- **Import :** `EEC_Import_dbc` parse les enregistrements BO_/SG_ et recrée messages +
  signaux. Activable dans l'app via la variable d'environnement `EEC_IMPORT_DBC=<fichier>`.
- **Tests :** `qa/test_dbc_roundtrip.c` couvre le round-trip export→import (frames std 11-bit
  et étendues 29-bit, DLC, layout des signaux).
- **Restes optionnels :** commentaires `CM_`, attributs `BA_`, tables de valeurs `VAL_`.

---

*Généré comme support de cadrage — aucune modification de code n'a été effectuée.*
