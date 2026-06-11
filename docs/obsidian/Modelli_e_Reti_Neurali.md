---
tags:
  - machine-learning
  - neural-networks
  - ensemble
---

# Modelli Predittivi: Alberi e Reti Neurali

Adesso che il progetto si è sganciato dal puro betting, la sperimentazione predittiva segue una rotta basata su un approccio ibrido (Ensemble).

## 1. Baseline: Gradient Boosted Trees (XGBoost/LightGBM)
Sui dati rigorosamente tabulari descritti in [[Feature_Engineering]], XGBoost rappresenta lo standard aureo.
*   **Fix dell'Overfitting**: La profondità (`max_depth`) è tenuta bassa per evitare di memorizzare il forte rumore intrinseco ai dati del tennis (XGB `max_depth: 3`).
*   **Tuning con Optuna**: I parametri LightGBM in `config/config.yaml` non sono più scelti a mano ma derivano da una ricerca bayesiana (`src/models/optuna_tuning.py`, 50 trial, minimizzazione del log-loss su validation): `n_estimators: 106`, `max_depth: 7`, `learning_rate: 0.039`, `num_leaves: 27`, `subsample: 0.825`, `colsample_bytree: 0.657`.
*   **Calibrazione Isotonica**: Applichiamo la calibrazione per far sì che le probabilità in output (es. 0.8) riflettano la reale incidenza di vittoria storica, ed è fondamentale che la cross-validation (`cross_validate.py`) includa questa calibrazione altrimenti le metriche (Log-Loss) risultano fuorvianti.

## 2. Reti Neurali (PyTorch) — `src/models/pytorch_ensemble.py`
Il valore delle Reti Neurali è sbloccato dai **Player Embeddings**: ogni giocatore viene mappato in un vettore N-dimensionale (`nn.Embedding`) che la rete impara dinamicamente. Due architetture coesistono:

*   **`TennisEmbeddingNet`** (feed-forward): concatena l'embedding del Giocatore 1, del Giocatore 2 **e la loro differenza esplicita `p1 - p2`** con le feature numeriche. La differenza modella direttamente il matchup invece di lasciarlo dedurre alla rete (input dim = `3 * embedding_dim + num_numerical`).
*   **`TennisTransformerNet`** (in uso di default in `train.py`): architettura ispirata a TCDformer. Tratta `[p1_emb, p2_emb, emb_diff, feature_proj]` come una sequenza di 4 token, somma i `token_type_embeddings`, e li passa in un `TransformerEncoder` (multi-head self-attention, GELU) per catturare le relazioni stile/contesto prima dei Dense Layer.

> Nota: nessuno strato LSTM è implementato — le dinamiche di "momentum" sono affidate all'attention del Transformer e alle feature di forma (`form_ewm`).

## 3. L'Ensemble Architetturale — `PreFittedEnsemble`
Il layer predittivo finale combina i modelli invece di sceglierne uno. Per evitare il collo di bottiglia di `VotingClassifier` (che ri-clona e ri-fitta ogni stimatore, riaddestrando tutto da zero), si usa `PreFittedEnsemble`:
1. Prende i modelli **già fittati e calibrati** (LR, RF, XGB, LGB).
2. Calcola la **media delle `predict_proba`** (soft voting) — o la media delle `predict` per i target di regressione.
3. Nessun doppio addestramento: l'ensemble è O(predict) invece di O(re-fit).
