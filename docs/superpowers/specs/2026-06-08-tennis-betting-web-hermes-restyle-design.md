# Tennis Betting — Hermes-Style Site Restyle

**Data:** 2026-06-08
**Path sito:** `docs/web/`
**Tipo:** Sito statico SPA (HTML + CSS + JS, no build)

## Obiettivo

Restyling completo del sito `docs/web/index.html` (attualmente one-pager dark con accent verde) ispirato allo stile visivo di [Hermes Agent](https://hermes-agent.nousresearch.com/), adattato al tema tennis (palette "terra battuta"). Il sito deve presentare in modo professionale il sistema ML: pipeline, 88 feature, 3 modelli, risultati backtest, demo CLI.

## Decisioni approvate

1. **Struttura:** Multi-pagina SPA con router hash
2. **Palette:** Court/terra battuta (non Hermes fedele)
3. **Font:** Identici a Hermes via CDN (Fontsource)
4. **Demo TUI:** Replay sessione CLI reale (typewriter)

## Architettura file

```
docs/web/
├── index.html          # shell + router hash, contiene tutte le route
├── style.css           # tutti gli stili (palette, font, animazioni)
├── app.js              # router, typewriter, observer, page rendering
├── pages/              # contenuti HTML delle singole pagine (template strings in app.js)
└── assets/
    └── og-image.png    # opzionale, social card
```

Tutto inline per semplicità: `index.html` carica `<link>` CSS e `<script type="module">` JS. Nessun bundler.

## Palette "Terra Battuta"

| Token | Valore | Uso |
|-------|--------|-----|
| `--bg` | `#EFE7D2` | Sfondo base (sabbia chiara) |
| `--surface` | `#F7F1E0` | Card / pannelli |
| `--surface-2` | `#E5DCC0` | Hover, sezioni alternate |
| `--line` | `rgba(26,26,18,0.20)` | Bordi (border-current/20) |
| `--ink` | `#1A1A12` | Testo primario |
| `--ink-dim` | `#5A5240` | Testo secondario |
| `--accent` | `#2E6B3F` | Verde erba (primario) |
| `--accent-2` | `#C75A2A` | Argilla (secondario) |
| `--warning` | `#C0392B` | Warning / perdita |
| `--highlight` | `#F2C14E` | Highlight / value bet |
| `--black-overlay` | `rgba(26,26,18,1)` | Mix-blend overlay |

## Tipografia

Tutti i font caricati da `cdn.jsdelivr.net/npm/@fontsource/` (o fallback).

| Ruolo | Font | Peso | Tracking |
|-------|------|------|----------|
| Display hero | Sigurd | Variable | tight |
| Headline | Rules Expanded | Bold | tight |
| Label / nav | Mondwest | Regular | 0.1875rem |
| Body | Collapse | Regular 400 / Bold 700 | normal |
| Mono / CLI | Courier Prime | Regular / Bold | normal |
| Numeri display | Rules Compressed | Medium | tight |

Fallback: `system-ui, -apple-system, "Segoe UI", sans-serif`.

## Layout system

**Griglia 12 colonne** (`.g` / `.gc`) con gap 1px tramite `border-current/20`. Padding container `max-width: 1600px` con `p-8`. Ogni `.gc` ha padding `p-4`.

**Header sticky** con logo "tennis_ml" (mono accent), nav links uppercase Mondwest, icone social a destra (GitHub, README).

**Footer** a 5 celle: nome progetto + versione, "v0.16.0", link "Nous Research ↗", "MIT License · 2026".

## Effetti full-screen (anima Hermes)

Layer `pointer-events: none` impilati sotto il contenuto (z-1, z-2, z-99, z-100, z-101, z-201):

```css
.bg-overlay-multiply  { background: var(--black-overlay); mix-blend-mode: multiply; z-index: 1; }
.bg-overlay-difference { background: #FFF; mix-blend-mode: difference; z-index: 100; }
.bg-filler            { opacity: 0.06; mix-blend-mode: difference; z-index: 2; }  /* canvas/noise */
.bg-radial-accent     { radial-gradient top-left verde; mix-blend-mode: lighten; opacity: 0.22; z-index: 99; }
.bg-canvas-color-dodge { <canvas> animate pattern; mix-blend-mode: color-dodge; z-index: 101; }
.bg-canvas-difference  { <canvas> noise; mix-blend-mode: difference; z-index: 201; }
```

## Pagine (route hash)

### `#/` Home
- Hero: badge `Open Source • MIT License` (Mondwest)
- Headline: "The Model That **Plays The Market**." (mix-blend plus-lighter sulla seconda riga)
- Sub: "An open ML system for tennis betting — 88 features, 3 markets, walk-forward validation. Not a tipster. A reproducible pipeline."
- Install box (Courier Prime, due righe: `git clone...` + `pip install -r requirements.txt && python -m src.models.train`)
- **Demo CLI** (sezione "See It in Action"): riquadro `border-4 border-double` con header (3 dot + label "tennis_ml") e corpo 320px typewriter con sessione reale

### `#/architettura`
- Section label: `// Pipeline`
- H2: Architettura del Sistema
- Flow diagram orizzontale (arch-node) stile pipeline: `JeffSackmann ATP` → `tennis-data.co.uk` → `download.py` → `clean.py` → `build_features.py` → `train.py` → `backtest.py` → `inference.py` → `TUI`
- Griglia 8 step numerati (counter increment) con titolo + descrizione + comando CLI in Courier

### `#/features`
- Section label: `// Feature Engineering`
- H2: 88 Feature Predittive
- 11 card in griglia (auto-fit 280px), ognuna con titolo (h4 mono accent), conteggio (.feature-count), lista mono dim

### `#/modelli`
- Section label: `// Modelli Predittivi`
- H2: Tre Mercati, Un Ensemble
- 3 result-card grandi: H2H 67.2% (verde), Spread MAE 3.30 (accent-2), Totals MAE 5.37 (highlight)
- Tabella modelli (H2H/Spread/Totals) con colonne: Mercato, Target, Task, Modelli Testati, Migliore, Metrica
- 3 card: Walk-Forward CV, Calibrazione Isotonica, Voting Ensemble

### `#/risultati`
- Section label: `// Backtesting`
- H2: Risultati Storici
- Tabella backtest: Value (Kelly) / Blind (Flat) / Threshold 0.8
- **Warning box** prominente: "Nessun edge reale. Dopo aver eliminato il leak... Non scommettere capitale reale."
- 3 card: Leak Fix Maggio 2026, Slippage Model, Edge Formula

### `#/demo`
- CLI replay esteso: stessa struttura home ma con script più lungo + scroll interno + bottone "Replay" che riavvia l'animazione
- Sotto: 3 comandi rapidi con copy button (Download, Train, Inference)

### `#/tech`
- Section label: `// Tech Stack`
- H2: Tecnologie
- Griglia tech-item (8 celle): Python, XGBoost, LightGBM, scikit-learn, Random Forest, TheOddsAPI, OpenRouter, Textual
- 2 card: Fonti Dati (JeffSackmann + tennis-data.co.uk), Setup Collaboratori

## Demo CLI — Script typewriter

Animazione char-by-char (~30ms/carattere) in riquadro `border-4 border-double` con cursore blink. Auto-loop dopo pausa 4s.

```bash
$ python -m src.data.download
✓ Fetched 1968-2026 ATP matches (487,221 rows)
✓ Fetched 2000-2026 odds (52,418 rows)

$ python -m src.data.clean
✓ Merged datasets: 412,083 unique matches
✓ Normalized player names: 18,442

$ python -m src.features.build_features
✓ Built 88 features per match
✓ Walk-forward split: train<2024 / test 2024

$ python -m src.models.train
[H2H]     XGBoost  acc=0.672  auc=0.727  ece=0.024
[Spread]  XGBoost  mae=3.30   r2=0.40
[Totals]  Ensemble mae=5.37   r2=0.37
✓ Calibrated isotonic regression

$ python -m src.live.inference
[2026-06-08 14:32] Sinner vs Alcaraz | hard | RG-F
  p(Sinner) = 0.612  | odds 1.55 | edge +3.2%
  kelly 25% = 1.4% bankroll  → BET
[2026-06-08 16:00] Swiatek vs Sabalenka | clay | RG-F
  p(Swiatek) = 0.543 | odds 1.78 | edge -1.1%
  → SKIP (no value)
```

## Animazioni

1. **Typewriter CLI** — funzione `type(text, el, speed=30)` con cancellazione progressiva, supporta linee multiple
2. **Fade-in sezioni** — IntersectionObserver aggiunge classe `.visible` con `transform: translateY(12px) → 0`
3. **Cursore blink** — `@keyframes blink` opacity 1/0 1s
4. **Hover card** — `opacity 0 → 0.05` su overlay 250ms
5. **Smooth scroll** — `scrollIntoView({behavior: 'smooth'})` su nav links

## Router hash

```js
const routes = { '#/': renderHome, '#/architettura': renderArch, ... };
window.addEventListener('hashchange', () => routes[location.hash]());
```

Default: `#/`. Nav link `href="#/architettura"`. `<main id="app">` viene svuotato e re-popolato ad ogni cambio. Mantiene scroll position tra pagine.

## Responsive

- Desktop: griglia piena, font scalati
- Tablet (< 1024px): collapse colonne a 1
- Mobile (< 640px): hero font 2.5rem, nav in hamburger, card impilate

## Accessibilità

- `lang="it"` su `<html>`
- Skip link "Salta al contenuto"
- Contrasto testo verificato (ink #1A1A12 su bg #EFE7D2 = 12.8:1 ✓)
- Focus-visible ring `outline: 1px solid var(--ink)`
- Reduced motion: `@media (prefers-reduced-motion: reduce)` disabilita typewriter/animazioni

## Test/Verifica

Aprire `docs/web/index.html` in browser. Checklist:
- [ ] Tutte le 7 route caricano
- [ ] Typewriter CLI gira in loop senza bloccare UI
- [ ] Hover effects su card visibili
- [ ] Mobile responsive (DevTools 375px, 768px, 1280px)
- [ ] Font Hermes caricati da CDN
- [ ] Console pulita (no errori)
- [ ] Link interni tra pagine funzionano (es. da home → features)
- [ ] Copy button su CLI install/demo copia il testo corretto

## Non-goal

- Niente backend, niente build step, niente dipendenze npm
- Niente multi-language (italiano + qualche termine EN per il mood tecnico)
- Niente dark mode toggle (la palette terra battuta è fissa)
- Niente immagini/photo (lo stile Hermes è testuale + canvas)
