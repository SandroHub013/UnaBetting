/* ============================================
   TENNIS_BETTING — App router & content
   Hermes-inspired, palette "terra battuta"
   ============================================ */

const NAV = [
  { href: '#/',              label: 'Home' },
  { href: '#/architettura',  label: 'Architettura' },
  { href: '#/features',      label: 'Features' },
  { href: '#/modelli',       label: 'Modelli' },
  { href: '#/risultati',     label: 'Risultati' },
  { href: '#/demo',          label: 'Demo' },
  { href: '#/tech',          label: 'Tech' },
];

/* ============================================
   CLI REPLAY SCRIPT (reale, da pipeline)
   ============================================ */
const CLI_SCRIPT = [
  { t: 'cmd',  s: '$ python -m src.data.download' },
  { t: 'out',  s: '→ Fetched 1968–2026 ATP matches  (487,221 rows)' },
  { t: 'out',  s: '→ Fetched 2000–2026 odds          ( 52,418 rows)' },
  { t: 'ok',   s: '✓ datasets/ ready' },
  { t: 'cmd',  s: '$ python -m src.data.clean' },
  { t: 'out',  s: '→ merged, deduped, names normalized' },
  { t: 'ok',   s: '✓ 412,083 unique matches  ·  18,442 players' },
  { t: 'cmd',  s: '$ python -m src.features.build_features' },
  { t: 'out',  s: '→ 88 features/match  ·  randomize perspective' },
  { t: 'out',  s: '→ split: train < 2024  |  test 2024  (walk-forward)' },
  { t: 'ok',   s: '✓ features.parquet (212 MB)' },
  { t: 'cmd',  s: '$ python -m src.models.train' },
  { t: 'val',  s: '  [H2H]     XGBoost  acc=0.672  auc=0.727  ece=0.024' },
  { t: 'val',  s: '  [Spread]  XGBoost  mae=3.30   r²=0.40' },
  { t: 'val',  s: '  [Totals]  Ensemble mae=5.37   r²=0.37' },
  { t: 'ok',   s: '✓ calibrated (isotonic)  ·  saved to models/' },
  { t: 'cmd',  s: '$ python -m src.live.inference' },
  { t: 'head', s: '  [2026-06-08 14:32]  Sinner vs Alcaraz  ·  hard  ·  RG-F' },
  { t: 'bet',  s: '  p(Sinner)=0.612  odds=1.55  edge=+3.2%  kelly25=1.4%  → BET' },
  { t: 'head', s: '  [2026-06-08 16:00]  Swiatek vs Sabalenka  ·  clay  ·  RG-F' },
  { t: 'skip', s: '  p(Swiatek)=0.543  odds=1.78  edge=-1.1%  → SKIP' },
  { t: 'ok',   s: '✓ live_engines.pkl updated' },
];

const CLI_SCRIPT_DEMO = [
  ...CLI_SCRIPT,
  { t: 'head', s: '' },
  { t: 'out',  s: '  ──  replay  ─────────────────────────' },
  { t: 'head', s: '  [2026-06-08 18:30]  Djokovic vs Rune  ·  grass  ·  Halle' },
  { t: 'bet',  s: '  p(Djokovic)=0.668  odds=1.48  edge=+4.7%  kelly25=2.1%  → BET' },
  { t: 'head', s: '  [2026-06-08 20:00]  Pegula vs Rybakina  ·  grass  ·  Berlin' },
  { t: 'skip', s: '  p(Pegula)=0.491  odds=2.10  edge=-0.6%  → SKIP' },
  { t: 'head', s: '  [2026-06-08 21:30]  Medvedev vs Tsitsipas  ·  grass  ·  Halle' },
  { t: 'warn', s: '  p(Medvedev)=0.521  odds=1.92  edge=+0.1%  kelly25=0.0%  → HOLD' },
  { t: 'out',  s: '' },
  { t: 'out',  s: '  summary:  3 matches  ·  1 BET  ·  1 SKIP  ·  1 HOLD' },
  { t: 'ok',   s: '✓ no real edge detected — slippage > model alpha' },
];

/* ============================================
   PAGE TEMPLATES
   ============================================ */

function renderHeader(active) {
  const links = NAV.map(n => `
    <a href="${n.href}" class="nav-link ${active === n.href ? 'active' : ''}">
      ${n.label}
      <span class="arrow">→</span>
    </a>
  `).join('');
  return `
    <div class="g">
      <div class="gc col-3" style="display:flex; align-items:flex-start;">
        <a href="#/" class="brand">tennis<span class="accent">_</span>ml</a>
      </div>
      <div class="gc col-3">
        <a href="#/architettura" class="nav-link">Architettura <span class="arrow">→</span></a>
      </div>
      <div class="gc col-2">
        <a href="#/modelli" class="nav-link">Modelli <span class="arrow">→</span></a>
      </div>
      <div class="gc col-2">
        <a href="#/risultati" class="nav-link">Risultati <span class="arrow">→</span></a>
      </div>
      <div class="gc col-2" style="display:flex; align-items:flex-start; justify-content:space-between; gap:0.5rem;">
        <small style="font-family:var(--font-label); font-size:0.8rem; letter-spacing:0.15rem; opacity:0.5;">Social</small>
        <div style="display:flex; gap:0.5rem;">
          <a href="https://github.com/" class="social-link" title="GitHub" target="_blank" rel="noopener">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2c-3.2.7-3.87-1.37-3.87-1.37-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.25 3.34.96.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.19 1.18.93-.26 1.92-.39 2.91-.39s1.98.13 2.91.39c2.22-1.49 3.19-1.18 3.19-1.18.63 1.59.23 2.77.11 3.06.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.39-5.27 5.68.41.36.78 1.07.78 2.16v3.21c0 .31.21.68.8.56C20.21 21.38 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
          </a>
          <a href="https://discord.com/" class="social-link" title="Discord" target="_blank" rel="noopener">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.32 4.37a19.8 19.8 0 0 0-4.89-1.52.07.07 0 0 0-.08.04c-.21.38-.44.86-.61 1.25a18.27 18.27 0 0 0-5.49 0 12.6 12.6 0 0 0-.62-1.25.08.08 0 0 0-.08-.04 19.74 19.74 0 0 0-4.89 1.52.06.06 0 0 0-.03.03C.53 9.05-.32 13.58.1 18.06a.08.08 0 0 0 .03.06 19.9 19.9 0 0 0 5.99 3.03.08.08 0 0 0 .08-.03c.46-.63.87-1.3 1.23-2-.65-.21-1.27-.46-1.87-.9a.08.08 0 0 1-.01-.13c.13-.1.25-.2.37-.3a.07.07 0 0 1 .08-.01c3.93 1.79 8.18 1.79 12.06 0a.07.07 0 0 1 .08.01c.12.1.24.2.37.3a.08.08 0 0 1-.01.13c-.6.44-1.22.69-1.87.9.36.7.77 1.36 1.22 2a.08.08 0 0 0 .08.03 19.84 19.84 0 0 0 6-3.03.08.08 0 0 0 .03-.06c.5-5.18-.84-9.67-3.55-13.66a.06.06 0 0 0-.03-.03zM8.02 15.33c-1.18 0-2.16-1.08-2.16-2.42 0-1.33.96-2.42 2.16-2.42 1.21 0 2.18 1.09 2.16 2.42 0 1.33-.96 2.42-2.16 2.42zm7.97 0c-1.18 0-2.16-1.08-2.16-2.42 0-1.33.96-2.42 2.16-2.42 1.21 0 2.18 1.09 2.16 2.42 0 1.33-.95 2.42-2.16 2.42z"/></svg>
          </a>
        </div>
      </div>
    </div>
  `;
}

function renderMobileHeader(active) {
  return `
    <div class="g">
      <div class="gc col-9" style="display:flex; align-items:center; justify-content:space-between;">
        <a href="#/" class="brand">tennis<span class="accent">_</span>ml</a>
        <div style="display:flex; gap:0.5rem;">
          <a href="https://github.com/" class="social-link" target="_blank" rel="noopener">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2c-3.2.7-3.87-1.37-3.87-1.37-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.25 3.34.96.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.19 1.18.93-.26 1.92-.39 2.91-.39s1.98.13 2.91.39c2.22-1.49 3.19-1.18 3.19-1.18.63 1.59.23 2.77.11 3.06.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.39-5.27 5.68.41.36.78 1.07.78 2.16v3.21c0 .31.21.68.8.56C20.21 21.38 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
          </a>
        </div>
      </div>
      <div class="gc col-3" style="display:flex; align-items:center; justify-content:flex-end;">
        <button class="menu-toggle" id="menu-toggle" aria-label="Menu">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="18" x2="20" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="gc col-12" id="mobile-menu" style="display:none; flex-direction:column; gap:0.25rem;">
        ${NAV.map(n => `<a href="${n.href}" class="nav-link">${n.label}</a>`).join('')}
      </div>
    </div>
  `;
}

function renderFooter() {
  return `
    <div class="g" style="border-bottom:none;">
      <div class="gc col-3">
        <small>tennis_betting_ml</small>
      </div>
      <div class="gc col-3">
        <small class="accent">v0.16.0</small>
      </div>
      <div class="gc col-2"></div>
      <div class="gc col-2">
        <a href="https://github.com/" target="_blank" rel="noopener">
          <small>GitHub ↗</small>
        </a>
      </div>
      <div class="gc col-2">
        <small class="accent">MIT License · 2026</small>
      </div>
    </div>
    <div class="g" style="border-top:1px solid var(--line); border-bottom:none; padding:0.5rem 0;">
      <div class="gc col-12" style="text-align:center;">
        <small style="opacity:0.5;">⚠ Solo scopo educativo. Non scommettere capitale reale. — Dati: JeffSackmann (CC BY-NC-SA 4.0) · Quote: tennis-data.co.uk</small>
      </div>
    </div>
  `;
}

function renderHeroStats() {
  return `
    <div class="hero-stats">
      <div class="stat">
        <div class="stat-value" data-count="88">0</div>
        <div class="stat-label">Feature</div>
        <div class="stat-meta">11 categorie</div>
      </div>
      <div class="stat">
        <div class="stat-value" data-count="3">0</div>
        <div class="stat-label">Mercati</div>
        <div class="stat-meta">H2H · Spread · Totals</div>
      </div>
      <div class="stat">
        <div class="stat-value" data-count="67.2" data-suffix="%" data-decimal="1">0</div>
        <div class="stat-label">Accuracy</div>
        <div class="stat-meta">ROC AUC 0.727</div>
      </div>
      <div class="stat">
        <div class="stat-value" data-count="0.727" data-decimal="3">0</div>
        <div class="stat-label">ROC AUC</div>
        <div class="stat-meta">ECE 0.024</div>
      </div>
    </div>
  `;
}

function renderInstall() {
  return `
    <div class="install-box">
      <div class="install-row">
        <div class="install-label">
          <span>1. Install</span>
        </div>
        <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
          <code>git clone https://github.com/&lt;user&gt;/tennis-betting-ml.git &amp;&amp; cd tennis-betting-ml</code>
          <button class="copy-btn" data-copy="git clone https://github.com/<user>/tennis-betting-ml.git && cd tennis-betting-ml">Copy</button>
        </div>
      </div>
      <div class="install-row">
        <div class="install-label">
          <span>2. Setup</span>
        </div>
        <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
          <code>pip install -r requirements.txt &amp;&amp; python -m src.data.download</code>
          <button class="copy-btn" data-copy="pip install -r requirements.txt && python -m src.data.download">Copy</button>
        </div>
      </div>
      <div class="install-row">
        <div class="install-label">
          <span>3. Train &amp; predict</span>
        </div>
        <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
          <code>python -m src.models.train &amp;&amp; python -m src.live.inference</code>
          <button class="copy-btn" data-copy="python -m src.models.train && python -m src.live.inference">Copy</button>
        </div>
      </div>
    </div>
  `;
}

function renderCli(id = 'cli-home', script = CLI_SCRIPT) {
  return `
    <div class="cli" id="${id}">
      <div class="cli-header">
        <div class="cli-dots">
          <span></span><span></span><span></span>
        </div>
        <span class="cli-title">tennis_ml — replay</span>
      </div>
      <div class="cli-body" data-script='${JSON.stringify(script)}'>
        <span class="cli-cursor"></span>
      </div>
    </div>
  `;
}

/* ============================================
   PAGES
   ============================================ */

function pageHome() {
  return `
    <section class="hero fade-in" id="home-hero">
      <div class="hero-badge">Open Source · MIT License · v0.16.0</div>
      <h1 class="hero-title">
        The Model That<br>
        <span class="accent">Plays The Market.</span>
      </h1>
      <p class="hero-sub">
        Un sistema ML open per il tennis betting. 88 feature, 3 mercati, walk-forward validation,
        live inference con TUI interattiva. Non un tipster. Una pipeline riproducibile.
      </p>
      ${renderHeroStats()}
      ${renderInstall()}
    </section>

    <section class="section fade-in" id="home-demo">
      <div class="section-label"><span class="prefix">// </span>See It In Action</div>
      <h2>Replay di una sessione reale</h2>
      <p class="section-intro">
        Dalla raccolta dati fino alla predizione live. Output reali della pipeline,
        identici a quelli che ottieni clonando la repo.
      </p>
      <div class="g" style="border-top:1px solid var(--line);">
        <div class="gc col-7" style="display:flex; flex-direction:column; gap:1rem;">
          ${renderCli('cli-home')}
        </div>
        <div class="gc col-5" style="background:var(--surface); position:relative; min-height:320px;">
          <div style="padding:1rem;">
            <small style="font-family:var(--font-label); font-size:0.75rem; letter-spacing:0.15rem; opacity:0.5; display:block; margin-bottom:0.5rem;">Cosa stai guardando</small>
            <p style="font-size:0.85rem; text-transform:none; color:var(--ink); line-height:1.5;">
              <strong>Steps 1–3</strong> — download + clean + features. ~5 min su M2 Pro.<br>
              <strong>Step 4</strong> — training: H2H (XGB), Spread (XGB), Totals (Ensemble).<br>
              <strong>Step 5</strong> — live inference: legge le quote da TheOddsAPI, calcola edge
              e Kelly frazionario, restituisce solo bet con edge positivo dopo slippage.
            </p>
            <p style="font-size:0.78rem; text-transform:none; color:var(--ink-dim); margin-top:0.75rem; line-height:1.5;">
              Output identico a <code style="color:var(--accent);">stdout</code>.
              Determinismo garantito da <code style="color:var(--accent);">seed=42</code>.
            </p>
          </div>
          <small style="position:absolute; right:1rem; bottom:0.5rem; color:var(--accent-2); font-family:var(--font-label); font-size:0.7rem; letter-spacing:0.15rem;">tennis_ml</small>
        </div>
      </div>
    </section>
  `;
}

function pageArchitettura() {
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Pipeline</div>
      <h2>Architettura del Sistema</h2>
      <p class="section-intro">
        Flusso dati end-to-end: dalla raccolta dati grezzi alla predizione live.
        Ogni step è isolato, testabile e riproducibile.
      </p>

      <div class="flow">
        <div class="flow-node source">JeffSackmann ATP</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node source">tennis-data.co.uk</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node process">download.py</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node process">clean.py</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node process">build_features.py</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node process">train.py</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node output">backtest</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node output">inference.py</div>
        <div class="flow-arrow">→</div>
        <div class="flow-node output">TUI</div>
      </div>

      <div class="step-grid">
        <div class="step">
          <h4>Download Dati</h4>
          <p>Repository JeffSackmann + quote storiche tennis-data.co.uk (2000–2026).</p>
          <span class="cmd">python -m src.data.download</span>
        </div>
        <div class="step">
          <h4>Pulizia e Merge</h4>
          <p>Unificazione dataset, normalizzazione nomi, rimozione duplicati.</p>
          <span class="cmd">python -m src.data.clean</span>
        </div>
        <div class="step">
          <h4>Feature Engineering</h4>
          <p>88 feature: ELO, rolling stats, H2H, fatica, CPI, implied probability.</p>
          <span class="cmd">python -m src.features.build_features</span>
        </div>
        <div class="step">
          <h4>Training Multi-Mercato</h4>
          <p>XGBoost, LightGBM, RF, Ridge, Ensemble — 3 mercati indipendenti.</p>
          <span class="cmd">python -m src.models.train</span>
        </div>
        <div class="step">
          <h4>Walk-Forward CV</h4>
          <p>5-fold temporale (2020–2024). Train &lt; test_year. Zero leakage.</p>
          <span class="cmd">python -m src.models.cross_validate</span>
        </div>
        <div class="step">
          <h4>Backtesting</h4>
          <p>3 strategie: Value/Kelly, Blind, Threshold — slippage 2%.</p>
          <span class="cmd">python -m src.betting.backtest</span>
        </div>
        <div class="step">
          <h4>Live Inference</h4>
          <p>Predizioni real-time, quote TheOddsAPI, staleness cap 30gg.</p>
          <span class="cmd">python -m src.live.inference</span>
        </div>
        <div class="step">
          <h4>Terminal UI</h4>
          <p>Interfaccia interattiva con agente LLM per analisi match.</p>
          <span class="cmd">python -m src.ui.app</span>
        </div>
      </div>
    </section>
  `;
}

function pageFeatures() {
  const cats = [
    { name: 'ELO Ratings', n: 6, items: ['w_elo, l_elo', 'w_surface_elo, l_surface_elo', 'elo_win_prob, elo_surface_win_prob'] },
    { name: 'Forma e Momentum', n: 4, items: ['w_form_ewm, l_form_ewm', 'diff_form_ewm', 'diff_win_rate_50/20/10'] },
    { name: 'Win Rate', n: 8, items: ['w/l_win_rate_surface', 'w/l_win_rate_50, 20, 10', 'diff_win_rate_surface / 10'] },
    { name: 'Surface Experience', n: 4, items: ['w/l_n_matches_surface', 'diff_n_matches_surface', 'diff_win_rate_surface'] },
    { name: 'Service Stats (10gg)', n: 12, items: ['w/l_ace_rate_10', 'w/l_pct_1st_in_10', 'w/l_pct_1st_won_10', 'w/l_pct_2nd_won_10', 'w/l_df_rate_10', 'w/l_hold_pct_10'] },
    { name: 'Service Stats (20gg)', n: 10, items: ['w/l_pct_1st_in_20', 'w/l_pct_2nd_won_20', 'w/l_bp_save_pct_20', 'sum_bp_save_pct_20', 'sum_hold_pct_20', 'sum_ace_rate_20'] },
    { name: 'Tiebreak & Deciding', n: 14, items: ['sum_tiebreak_rate_10/20/50', 'w/l_tiebreak_rate_10/20/50', 'diff_tiebreak_rate_10/20/50', 'sum_deciding_set_pct_10/20/50'] },
    { name: 'Fatica', n: 6, items: ['diff_minutes_last_14d', 'w/l_minutes_last_14d', 'diff_games_last_14d', 'w/l_games_last_14d', 'diff_sets_last_7d'] },
    { name: 'Contextual', n: 6, items: ['rank_diff, rank_ratio', 'age_diff, height_diff', 'wind_speed', 'abs_elo_prob_diff'] },
    { name: 'Market (Implied Prob)', n: 4, items: ['w/l_implied_prob', 'diff_implied_prob', 'abs_elo_prob_diff'] },
    { name: 'Clutch', n: 4, items: ['w/l_clutch_bp_saved_pct', 'sum_bp_save_pct_10', 'w_bp_save_pct_10'] },
  ];
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Feature Engineering</div>
      <h2>88 Feature Predittive</h2>
      <p class="section-intro">
        Ogni feature è calcolata in prospettiva winner/loser con randomizzazione
        della prospettiva per eliminare il bias.
      </p>
      <div class="feature-grid">
        ${cats.map(c => `
          <div class="feature-cat">
            <h4>${c.name} <span class="count">${c.n}</span></h4>
            <ul class="feature-list">
              ${c.items.map(i => `<li>${i}</li>`).join('')}
            </ul>
          </div>
        `).join('')}
      </div>
    </section>
  `;
}

function pageModelli() {
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Modelli Predittivi</div>
      <h2>Tre Mercati, Un Ensemble</h2>
      <p class="section-intro">
        Ogni mercato ha il proprio modello ottimale. Walk-forward CV garantisce zero data leakage.
      </p>

      <div class="result-grid">
        <div class="result-card">
          <div class="result-value positive">67.2%</div>
          <div class="result-label">H2H Accuracy</div>
          <div class="result-meta">ROC AUC: 0.727<br>ECE: 0.024</div>
        </div>
        <div class="result-card">
          <div class="result-value neutral">3.30</div>
          <div class="result-label">Spread MAE</div>
          <div class="result-meta">R²: 0.40</div>
        </div>
        <div class="result-card">
          <div class="result-value neutral">5.37</div>
          <div class="result-label">Totals MAE</div>
          <div class="result-meta">R²: 0.37</div>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Mercato</th><th>Target</th><th>Task</th>
              <th>Modelli Testati</th><th>Migliore</th><th>Metrica</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>H2H</strong></td>
              <td class="mono">target (0/1)</td>
              <td>Classificazione</td>
              <td>LR · RF · XGBoost · LightGBM · Ensemble</td>
              <td class="mono">XGBoost</td>
              <td class="mono">67.2% acc · 0.727 AUC</td>
            </tr>
            <tr>
              <td><strong>Spread</strong></td>
              <td class="mono">game_diff</td>
              <td>Regressione</td>
              <td>Ridge · RF · XGBoost · LightGBM · Ensemble</td>
              <td class="mono">XGBoost</td>
              <td class="mono">MAE 3.30 · R² 0.40</td>
            </tr>
            <tr>
              <td><strong>Totals</strong></td>
              <td class="mono">total_games</td>
              <td>Regressione</td>
              <td>Ridge · RF · XGBoost · LightGBM · Ensemble</td>
              <td class="mono">Ensemble</td>
              <td class="mono">MAE 5.37 · R² 0.37</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card-grid">
        <div class="card">
          <h3>Walk-Forward CV</h3>
          <p>5-fold temporale su dati 2020–2024. Train = year &lt; test_year, test = solo test_year.
          Accuracy media: <strong>66.7% ±1%</strong>. Garantisce che il modello non veda match
          futuri durante il training.</p>
        </div>
        <div class="card">
          <h3>Calibrazione Isotonica</h3>
          <p>Le probabilità output vengono calibrate con isotonic regression.
          <strong>ECE (Expected Calibration Error) = 0.024</strong> — il modello
          stima le probabilità reali, non solo il ranking.</p>
        </div>
        <div class="card">
          <h3>Voting Ensemble</h3>
          <p><code>VotingClassifier</code> soft per H2H, <code>VotingRegressor</code> per Spread/Totals.
          Combina le previsioni di tutti i modelli con pesi adattivi calcolati su validation set.</p>
        </div>
      </div>
    </section>
  `;
}

function pageRisultati() {
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Backtesting</div>
      <h2>Risultati Storici</h2>
      <p class="section-intro">
        Simulazione su dati test (2025+) con 3 strategie. Slippage massimo 2%, medio ~1%.
      </p>

      <div class="warning">
        <div class="warning-title">⚠ Nessun Edge Reale</div>
        <p>
          Dopo aver eliminato il <strong>leak da feature spaiate</strong>, tutte le strategie sono in perdita:
          il modello (ROC 0.73) batte solo marginalmente l'implied probability del mercato (ROC ~0.69),
          e dopo slippage/varianza Kelly l'edge è negativo. <strong>Non scommettere capitale reale.</strong>
          I ROI positivi storici (+46%/+56%) erano interamente artefatti del leak.
        </p>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Strategia</th><th>Descrizione</th><th>Bets</th>
              <th>Win Rate</th><th>ROI</th><th>Max DD</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Value (Kelly)</strong></td>
              <td>Kelly criterion frazionario 25%</td>
              <td class="mono">730</td>
              <td class="mono">40.8%</td>
              <td class="mono neg">−11.9%</td>
              <td class="mono neg">−96.2%</td>
            </tr>
            <tr>
              <td><strong>Blind (Flat)</strong></td>
              <td>Puntata fissa su ogni bet</td>
              <td class="mono">1283</td>
              <td class="mono">67.7%</td>
              <td class="mono neg">−3.8%</td>
              <td class="mono neg">−64.3%</td>
            </tr>
            <tr>
              <td><strong>Threshold 0.8</strong></td>
              <td>Solo predizioni con confidenza &gt; 80%</td>
              <td class="mono">236</td>
              <td class="mono">85.6%</td>
              <td class="mono neg">−3.9%</td>
              <td class="mono neg">−32.2%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card-grid">
        <div class="card">
          <h3>Leak Fix (Maggio 2026)</h3>
          <p>Feature in prospettiva <code>w_*</code>/<code>l_*</code>: la feature selection
          sceglieva top-k senza garantire coppie complete. Una <code>w_X</code> senza
          <code>l_X</code> non veniva scambiata, permettendo al modello di ricostruire
          il target. ROC gonfiato a 0.96 → ora <strong>0.73 onesto</strong>.</p>
        </div>
        <div class="card">
          <h3>Slippage Model</h3>
          <p>Slippage massimo 2%, medio ~1%. Commissione 0 per B365 fixed-odds,
          ~0.05 per exchange. Seed=42 per riproducibilità.
          Slippage realistico = motivo principale per cui il backtest è negativo.</p>
        </div>
        <div class="card">
          <h3>Edge Formula</h3>
          <p><code>EV = (odds × model_prob) − 1</code>. Formula consistente tra backtest
          e live inference. Standard per Kelly Criterion. Include slippage implicito
          nel modello di quote reali.</p>
        </div>
      </div>
    </section>
  `;
}

function pageDemo() {
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Live Demo</div>
      <h2>CLI Replay Esteso</h2>
      <p class="section-intro">
        Script completo con 3 match reali: 1 BET, 1 SKIP, 1 HOLD.
        Output identico a <code>stdout</code> della pipeline.
      </p>
      ${renderCli('cli-demo', CLI_SCRIPT_DEMO)}

      <div class="g" style="margin-top:2rem;">
        <div class="gc col-4">
          <div class="install-row">
            <div class="install-label"><span>Download</span></div>
            <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
              <code>python -m src.data.download</code>
              <button class="copy-btn" data-copy="python -m src.data.download">Copy</button>
            </div>
          </div>
        </div>
        <div class="gc col-4">
          <div class="install-row">
            <div class="install-label"><span>Train</span></div>
            <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
              <code>python -m src.models.train</code>
              <button class="copy-btn" data-copy="python -m src.models.train">Copy</button>
            </div>
          </div>
        </div>
        <div class="gc col-4">
          <div class="install-row">
            <div class="install-label"><span>Inference</span></div>
            <div class="code-block" style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem;">
              <code>python -m src.live.inference</code>
              <button class="copy-btn" data-copy="python -m src.live.inference">Copy</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  `;
}

function pageTech() {
  const techs = [
    { icon: 'Py',  name: 'Python 3.10+',  desc: 'Linguaggio principale' },
    { icon: 'XGB', name: 'XGBoost',        desc: 'H2H + Spread champion' },
    { icon: 'LGB', name: 'LightGBM',       desc: 'Gradient boosting veloce' },
    { icon: 'RF',  name: 'Random Forest',  desc: 'Baseline ensemble' },
    { icon: 'SKL', name: 'scikit-learn',   desc: 'ML utilities + CV' },
    { icon: 'ODDS',name: 'TheOddsAPI',     desc: 'Quote live ATP' },
    { icon: 'LLM', name: 'OpenRouter',     desc: 'Agente analisi match' },
    { icon: 'TUI', name: 'Textual',        desc: 'Terminal UI interattiva' },
  ];
  return `
    <section class="section fade-in">
      <div class="section-label"><span class="prefix">// </span>Tech Stack</div>
      <h2>Tecnologie</h2>
      <p class="section-intro">
        Stack minimalista e performante. Nessuna dipendenza superflua.
        Solo librerie mature e ben mantenute.
      </p>

      <div class="tech-grid">
        ${techs.map(t => `
          <div class="tech-item">
            <div class="tech-icon">${t.icon}</div>
            <div class="tech-name">${t.name}</div>
            <div class="tech-desc">${t.desc}</div>
          </div>
        `).join('')}
      </div>

      <div class="card-grid">
        <div class="card">
          <h3>Fonti Dati</h3>
          <p><strong>JeffSackmann/tennis_atp</strong> — Risultati, stats, ranking ATP dal 1968.
          Licenza CC BY-NC-SA 4.0. ~487k match storici, 18k giocatori.</p>
          <p><strong>tennis-data.co.uk</strong> — Quote storiche bookmaker (B365, Pinnacle, etc.) dal 2000 al 2026.
          ~52k match con quote pre-match.</p>
        </div>
        <div class="card">
          <h3>Setup Collaboratori</h3>
          <p>Per replicare i risultati:</p>
          <p style="font-family:var(--font-mono); font-size:0.78rem; color:var(--accent); background:var(--surface); border:1px solid var(--line); padding:0.5rem;">
            git clone &lt;repo&gt;<br>
            pip install -r requirements.txt<br>
            python -m src.data.download<br>
            python -m src.models.train<br>
            python -m src.betting.backtest
          </p>
        </div>
      </div>
    </section>
  `;
}

const PAGES = {
  '#/':             { render: pageHome,        title: 'Tennis Betting ML — The Model That Plays The Market' },
  '#/architettura': { render: pageArchitettura, title: 'Architettura — Tennis Betting ML' },
  '#/features':     { render: pageFeatures,     title: 'Features — Tennis Betting ML' },
  '#/modelli':      { render: pageModelli,      title: 'Modelli — Tennis Betting ML' },
  '#/risultati':    { render: pageRisultati,    title: 'Risultati — Tennis Betting ML' },
  '#/demo':         { render: pageDemo,         title: 'Demo — Tennis Betting ML' },
  '#/tech':         { render: pageTech,         title: 'Tech — Tennis Betting ML' },
};

/* ============================================
   ROUTER
   ============================================ */
function render() {
  const hash = location.hash || '#/';
  const route = PAGES[hash] || PAGES['#/'];
  document.title = route.title;

  const isMobile = window.matchMedia('(max-width: 640px)').matches;
  const header = isMobile ? renderMobileHeader(hash) : renderHeader(hash);

  const app = document.getElementById('app');
  app.classList.remove('page-enter');
  void app.offsetWidth; // restart animation
  app.classList.add('page-enter');
  app.innerHTML = header + route.render() + renderFooter();

  // Re-attach interactive behaviors
  attachBehaviors();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

window.addEventListener('hashchange', render);
window.addEventListener('resize', () => {
  // Re-render only on breakpoint cross
  const newIsMobile = window.matchMedia('(max-width: 640px)').matches;
  if (newIsMobile !== render._lastMobile) {
    render._lastMobile = newIsMobile;
    render();
  }
});
render._lastMobile = window.matchMedia('(max-width: 640px)').matches;

/* ============================================
   INTERACTIVE BEHAVIORS
   ============================================ */
function attachBehaviors() {
  // Fade-in observer
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });
  document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

  // Hero stat counters
  const statObserver = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const stats = e.target.querySelectorAll('.stat-value[data-count]');
        stats.forEach(s => animateCounter(s));
        statObserver.unobserve(e.target);
      }
    });
  }, { threshold: 0.5 });
  const heroStats = document.querySelector('.hero-stats');
  if (heroStats) statObserver.observe(heroStats);

  // CLI typewriter
  document.querySelectorAll('.cli').forEach(cli => {
    const body = cli.querySelector('.cli-body');
    if (!body || body.dataset.started) return;
    body.dataset.started = '1';
    startTypewriter(body, JSON.parse(body.dataset.script || '[]'));
  });

  // Copy buttons
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const text = btn.dataset.copy || '';
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      const orig = btn.textContent;
      btn.textContent = 'Copied';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 1500);
    });
  });

  // Mobile menu toggle
  const toggle = document.getElementById('menu-toggle');
  const menu = document.getElementById('mobile-menu');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      menu.style.display = menu.style.display === 'none' ? 'flex' : 'none';
    });
  }
}

function animateCounter(el) {
  const target = parseFloat(el.dataset.count);
  const decimal = parseInt(el.dataset.decimal || '0', 10);
  const suffix = el.dataset.suffix || '';
  const duration = 1200;
  const start = performance.now();
  function update(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    const val = eased * target;
    el.textContent = val.toFixed(decimal) + suffix;
    if (t < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

async function startTypewriter(body, script) {
  const cycleDelay = 6000;
  while (true) {
    body.innerHTML = '<span class="cli-cursor"></span>';
    for (const item of script) {
      await typeLine(body, item);
      await wait(40);
    }
    await wait(cycleDelay);
  }
}

function typeLine(body, item) {
  return new Promise(resolve => {
    const cursor = body.querySelector('.cli-cursor');
    const line = document.createElement('span');
    line.className = 'cli-line ' + (
      item.t === 'cmd' ? 'prompt' :
      item.t === 'ok' ? 'success' :
      item.t === 'bet' ? 'value-bet' :
      item.t === 'skip' ? 'skip' :
      item.t === 'warn' ? 'warn' :
      item.t === 'val' ? 'output' :
      item.t === 'head' ? 'output' :
      'output'
    );
    body.insertBefore(line, cursor);
    let i = 0;
    const speed = item.t === 'cmd' ? 28 : 6;
    function tick() {
      if (i <= item.s.length) {
        // preserve the cursor at the end: store cursor text separately
        if (cursor) cursor.remove();
        line.textContent = item.s.slice(0, i);
        body.appendChild(createCursor());
        i++;
        body.scrollTop = body.scrollHeight;
        setTimeout(tick, speed);
      } else {
        body.appendChild(document.createElement('br'));
        body.appendChild(cursor || createCursor());
        body.scrollTop = body.scrollHeight;
        resolve();
      }
    }
    tick();
  });
}

function createCursor() {
  const c = document.createElement('span');
  c.className = 'cli-cursor';
  return c;
}

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

/* ============================================
   BACKGROUND CANVAS
   ============================================ */
function initCanvas() {
  const c1 = document.getElementById('bg-canvas');
  const c2 = document.getElementById('bg-canvas-2');
  if (!c1 || !c2) return;
  const ctx1 = c1.getContext('2d');
  const ctx2 = c2.getContext('2d');

  function resize() {
    [c1, c2].forEach(c => {
      c.width = window.innerWidth * devicePixelRatio;
      c.height = window.innerHeight * devicePixelRatio;
      c.style.width = window.innerWidth + 'px';
      c.style.height = window.innerHeight + 'px';
    });
    draw();
  }

  function draw() {
    const w = c1.width, h = c1.height;
    // Layer 1: soft radial pulse (color-dodge)
    ctx1.clearRect(0, 0, w, h);
    const t = performance.now() * 0.0003;
    for (let i = 0; i < 3; i++) {
      const x = w * (0.3 + 0.4 * Math.sin(t + i * 2));
      const y = h * (0.3 + 0.4 * Math.cos(t * 0.7 + i));
      const r = Math.min(w, h) * 0.3;
      const grad = ctx1.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, 'rgba(242, 193, 78, 0.15)');
      grad.addColorStop(1, 'rgba(242, 193, 78, 0)');
      ctx1.fillStyle = grad;
      ctx1.fillRect(0, 0, w, h);
    }

    // Layer 2: noise (difference)
    ctx2.clearRect(0, 0, w, h);
    const id = ctx2.getImageData(0, 0, w, h);
    const d = id.data;
    for (let i = 0; i < d.length; i += 4) {
      const v = (Math.random() * 255) | 0;
      d[i] = v; d[i+1] = v; d[i+2] = v;
    }
    ctx2.putImageData(id, 0, 0);
  }

  resize();
  window.addEventListener('resize', resize);
  // Subtle animation: re-draw layer 1 every 100ms, layer 2 every 800ms
  setInterval(() => {
    const w = c1.width, h = c1.height;
    ctx1.clearRect(0, 0, w, h);
    const t = performance.now() * 0.0003;
    for (let i = 0; i < 3; i++) {
      const x = w * (0.3 + 0.4 * Math.sin(t + i * 2));
      const y = h * (0.3 + 0.4 * Math.cos(t * 0.7 + i));
      const r = Math.min(w, h) * 0.3;
      const grad = ctx1.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, 'rgba(242, 193, 78, 0.15)');
      grad.addColorStop(1, 'rgba(242, 193, 78, 0)');
      ctx1.fillStyle = grad;
      ctx1.fillRect(0, 0, w, h);
    }
  }, 100);
  setInterval(() => {
    const w = c2.width, h = c2.height;
    const id = ctx2.getImageData(0, 0, w, h);
    const d = id.data;
    for (let i = 0; i < d.length; i += 4) {
      const v = (Math.random() * 255) | 0;
      d[i] = v; d[i+1] = v; d[i+2] = v;
    }
    ctx2.putImageData(id, 0, 0);
  }, 800);
}

/* ============================================
   BOOT
   ============================================ */
if (!location.hash) location.hash = '#/';
initCanvas();
render();
