/* MISSION_CONTROL — IDE-style frontend. Vanilla JS, no build step. */
'use strict';

/* ================= I18N ================= */
const LANGS = [['it', '🇮🇹 Italiano'], ['en', '🇬🇧 English'], ['es', '🇪🇸 Español'],
               ['fr', '🇫🇷 Français'], ['de', '🇩🇪 Deutsch']];
const I18N = {
  it: {
    act_cockpit: 'Cockpit dati', act_os: 'UnaBettingOS — memoria agentica', act_graph: 'Knowledge graph 3D',
    act_browser: 'Browser web agentico', act_explorer: 'Esplora progetto', act_pipeline: 'Pipeline',
    act_loops: 'Loop autoevolutivi', act_docs: 'Documentazione', act_config: 'Config',
    t_cockpit: 'Cockpit', t_os: 'UnaBettingOS', t_graph: 'Knowledge graph', t_browser: 'Browser web',
    t_explorer: 'Esplora progetto', t_pipeline: 'Pipeline', t_loops: 'Loop autoevolutivi',
    t_docs: 'Documentazione', t_config: 'Config',
    s_data_actions: 'Dati & azioni', s_memory: 'Memoria & conoscenza', s_live: 'Live',
    s_pipeline_dm: 'Pipeline dati/modello', s_shortcuts: 'Scorciatoie', s_brain: 'Cervello',
    s_runlogs: 'Log run (reports/loops)', s_root: 'Radice', s_obsidian: 'Obsidian',
    overview: 'Overview', signals: 'Segnali', bets: 'Bet', quotes: 'Quote',
    bankroll: 'Bankroll', profit: 'Profit', winrate: 'Win rate', open_bets: 'Bet aperte',
    decisions: 'Decisioni', model: 'Modello', accuracy: 'Accuracy', vs_market: 'vs Mercato',
    last_train: 'Train', match: 'Match', when: 'Quando', edge: 'Edge', odds: 'Quota',
    stake: 'Stake €', status: 'Status', record: 'Record', yield_: 'Yield',
    sec_bank: 'Banca', sec_model: 'Modello', sub_honest: 'onesta, leak-free', sub_market: 'favorito B365 — da battere', sub_train: 'TennisLoopNightly 07:13',
    c_edgedist: 'Distribuzione edge — ultime {n} decisioni', c_today: 'Match nel feed (ultimo snapshot)', c_traj: 'Traiettoria modello — accuracy & log loss', c_permodel: 'Accuracy per modello (run corrente)',
    tournament: 'Torneo', surface: 'Sup.', side: 'Side', conf: 'Conf.', player: 'Puntata su', book: 'Book', takenodds: 'Quota presa', outcome: 'Esito', modelprob: 'p modello', bankroll_after: 'Bankroll €', profit_eur: 'Profit €',
    allstatus: 'tutti gli status', st_pending: 'pending', st_won: 'vinta', st_lost: 'persa',
    betmatch_ph: 'Match (es. Sinner vs Alcaraz)', betplayer_ph: 'Puntata su (giocatore)', betodds_ph: 'Quota', betstake_ph: 'Stake €', betnotes_ph: 'Note / bookmaker (opzionale)', bet_add: '+ registra', equity: 'Equity curve — bankroll dopo ogni bet risolta', bet_won: '✓ vinta', bet_lost: '✗ persa', undo: '↩',
    f_edgepos: 'solo edge > 0', f_lowconf: 'escludi low-conf', f_clvpos: 'solo CLV positivo',
    ready: 'pronto', running: 'in esecuzione:', finished: 'terminato (exit', errw: 'errore', copyout: 'copia output', copied: 'output copiato', copyfail: 'copia fallita', file_open_failed: 'Impossibile aprire', loading: 'carico…', links_l: 'Link:', nodata: 'nessun dato', rows_l: 'righe', choosematch: '— scegli match —', snap_l: 'snapshot:', nosnap: 'nessuno snapshot',
    q_today: 'quali sono i match di oggi?', q_sig: 'ultimi segnali del modello?', q_model: 'com’è messo il modello?', q_bank: 'stato del bankroll?', q_vault: 'cerca nel vault: perché il backtest dava 85%?', q_graphelo: 'interroga il grafo: EloRating', q_remember: 'ricorda che: ', q_recall: 'cosa ti ho chiesto di ricordare?',
    note_os: '<b>UnaBettingOS</b> — centro di memoria agentica. Modello locale <b>qwen3.5:9b</b> via Ollama. Collegato a: dati live, vault Obsidian, knowledge graph, memoria persistente.', note_memfile: 'La memoria vive in docs/obsidian/UnaBettingOS_Memoria.md — versionata con git.', note_cold: 'Nota: la prima risposta a freddo carica il modello in VRAM (~1-2 min); poi resta caldo.',
    scanlive: '⚡ scan match live', note_scan: 'scarica quote fresche (the-odds-api, consuma crediti) e fa girare modello + news. Risultati nel tab Segnali.', stopb: '■ stop', note_ponly: 'Output nel tab "Pipeline". Solo comandi whitelisted: il resto passa dai terminali.',
    note_browser: 'Browser agentico: apri URL, leggi il contenuto, segui i link. Anche l\'agente UnaBettingOS può navigare (tool browse_web).', brurl_ph: 'url o dominio…', brback: 'indietro', note_graph: 'Il grafo del progetto (graphify): nodi-stella colorati per community, 3D. Trascina per ruotare, scroll per zoom, click su un nodo per il focus.',
    l_exp: 'EXPERIMENTS.md', l_nightly: 'loop notturno', l_weekly: 'loop settimanale', l_metrics: 'storico metriche', loops_none: 'nessuna run ancora',
    term_label: 'TERMINALE', vibe_hint: 'agente a scelta, in tmux (la sessione sopravvive alla chiusura del tab)',
    upd_title: 'Aggiornamento disponibile', upd_btn: 'Aggiorna ora', upd_later: 'Più tardi', upd_doing: 'aggiornamento…', upd_done: 'Aggiornato ✓ — riavvia l\'app per applicare', upd_fail: 'Aggiornamento fallito', upd_restart: 'Riavvia app',
    chat_intro: "Sono <b>UnaBettingOS</b> — memoria e intelligenza agentica dell'app (qwen3.5:9b, locale). Dati live, vault Obsidian, knowledge graph e memoria persistente: chiedimi dei match, del modello, della storia del progetto — o dimmi \"ricorda che…\".",
    chat_ph: 'scrivi… (Invio per inviare)', open_graph: 'apri il grafo 3D', go: 'vai',
    filter: '⌕ filtra…', register_bet: 'Registra una bet', save: 'Salva',
  },
  en: {
    act_cockpit: 'Data cockpit', act_os: 'UnaBettingOS — agentic memory', act_graph: '3D knowledge graph',
    act_browser: 'Agentic web browser', act_explorer: 'Project explorer', act_pipeline: 'Pipeline',
    act_loops: 'Self-evolving loops', act_docs: 'Documentation', act_config: 'Config',
    t_cockpit: 'Cockpit', t_os: 'UnaBettingOS', t_graph: 'Knowledge graph', t_browser: 'Web browser',
    t_explorer: 'Project explorer', t_pipeline: 'Pipeline', t_loops: 'Self-evolving loops',
    t_docs: 'Documentation', t_config: 'Config',
    s_data_actions: 'Data & actions', s_memory: 'Memory & knowledge', s_live: 'Live',
    s_pipeline_dm: 'Data/model pipeline', s_shortcuts: 'Shortcuts', s_brain: 'Brain',
    s_runlogs: 'Run logs (reports/loops)', s_root: 'Root', s_obsidian: 'Obsidian',
    overview: 'Overview', signals: 'Signals', bets: 'Bets', quotes: 'Odds',
    bankroll: 'Bankroll', profit: 'Profit', winrate: 'Win rate', open_bets: 'Open bets',
    decisions: 'Decisions', model: 'Model', accuracy: 'Accuracy', vs_market: 'vs Market',
    last_train: 'Train', match: 'Match', when: 'When', edge: 'Edge', odds: 'Odds',
    stake: 'Stake €', status: 'Status', record: 'Record', yield_: 'Yield',
    sec_bank: 'Bank', sec_model: 'Model', sub_honest: 'honest, leak-free', sub_market: 'B365 favourite — to beat', sub_train: 'TennisLoopNightly 07:13',
    c_edgedist: 'Edge distribution — last {n} decisions', c_today: 'Matches in feed (latest snapshot)', c_traj: 'Model trajectory — accuracy & log loss', c_permodel: 'Accuracy per model (current run)',
    tournament: 'Tournament', surface: 'Surf.', side: 'Side', conf: 'Conf.', player: 'Bet on', book: 'Book', takenodds: 'Taken odds', outcome: 'Outcome', modelprob: 'model p', bankroll_after: 'Bankroll €', profit_eur: 'Profit €',
    allstatus: 'all statuses', st_pending: 'pending', st_won: 'won', st_lost: 'lost',
    betmatch_ph: 'Match (e.g. Sinner vs Alcaraz)', betplayer_ph: 'Bet on (player)', betodds_ph: 'Odds', betstake_ph: 'Stake €', betnotes_ph: 'Notes / bookmaker (optional)', bet_add: '+ log', equity: 'Equity curve — bankroll after each settled bet', bet_won: '✓ won', bet_lost: '✗ lost', undo: '↩',
    f_edgepos: 'edge > 0 only', f_lowconf: 'exclude low-conf', f_clvpos: 'positive CLV only',
    ready: 'ready', running: 'running:', finished: 'finished (exit', errw: 'error', copyout: 'copy output', copied: 'output copied', copyfail: 'copy failed', file_open_failed: 'Unable to open', loading: 'loading…', links_l: 'Links:', nodata: 'no data', rows_l: 'rows', choosematch: '— choose match —', snap_l: 'snapshot:', nosnap: 'no snapshot',
    q_today: 'what are today’s matches?', q_sig: 'latest model signals?', q_model: 'how is the model doing?', q_bank: 'bankroll status?', q_vault: 'search the vault: why did the backtest show 85%?', q_graphelo: 'query the graph: EloRating', q_remember: 'remember that: ', q_recall: 'what did I ask you to remember?',
    note_os: '<b>UnaBettingOS</b> — agentic memory hub. Local model <b>qwen3.5:9b</b> via Ollama. Wired to: live data, Obsidian vault, knowledge graph, persistent memory.', note_memfile: 'Memory lives in docs/obsidian/UnaBettingOS_Memoria.md — git-versioned.', note_cold: 'Note: the first cold reply loads the model into VRAM (~1-2 min); then it stays warm.',
    scanlive: '⚡ scan live matches', note_scan: 'fetches fresh odds (the-odds-api, uses credits) and runs model + news. Results in the Signals tab.', stopb: '■ stop', note_ponly: 'Output in the "Pipeline" tab. Whitelisted commands only: everything else goes through the terminals.',
    note_browser: 'Agentic browser: open a URL, read the content, follow links. UnaBettingOS can browse too (browse_web tool).', brurl_ph: 'url or domain…', brback: 'back', note_graph: 'The project graph (graphify): star nodes colored by community, 3D. Drag to rotate, scroll to zoom, click a node to focus.',
    l_exp: 'EXPERIMENTS.md', l_nightly: 'nightly loop', l_weekly: 'weekly loop', l_metrics: 'metrics history', loops_none: 'no runs yet',
    term_label: 'TERMINAL', vibe_hint: 'pick an agent in tmux (the session survives closing the tab)',
    upd_title: 'Update available', upd_btn: 'Update now', upd_later: 'Later', upd_doing: 'updating…', upd_done: 'Updated ✓ — restart the app to apply', upd_fail: 'Update failed', upd_restart: 'Restart app',
    chat_intro: "I'm <b>UnaBettingOS</b> — the app's agentic memory & intelligence (qwen3.5:9b, local). Live data, Obsidian vault, knowledge graph and persistent memory: ask me about matches, the model, the project's history — or say \"remember that…\".",
    chat_ph: 'type… (Enter to send)', open_graph: 'open the 3D graph', go: 'go',
    filter: '⌕ filter…', register_bet: 'Log a bet', save: 'Save',
  },
  es: {
    act_cockpit: 'Panel de datos', act_os: 'UnaBettingOS — memoria agéntica', act_graph: 'Grafo 3D',
    act_browser: 'Navegador web agéntico', act_explorer: 'Explorador del proyecto', act_pipeline: 'Pipeline',
    act_loops: 'Bucles autoevolutivos', act_docs: 'Documentación', act_config: 'Config',
    t_cockpit: 'Panel', t_os: 'UnaBettingOS', t_graph: 'Grafo de conocimiento', t_browser: 'Navegador',
    t_explorer: 'Explorador', t_pipeline: 'Pipeline', t_loops: 'Bucles', t_docs: 'Documentación', t_config: 'Config',
    s_data_actions: 'Datos y acciones', s_memory: 'Memoria y conocimiento', s_live: 'En vivo',
    s_pipeline_dm: 'Pipeline datos/modelo', s_shortcuts: 'Atajos', s_brain: 'Cerebro',
    s_runlogs: 'Logs (reports/loops)', s_root: 'Raíz', s_obsidian: 'Obsidian',
    overview: 'Resumen', signals: 'Señales', bets: 'Apuestas', quotes: 'Cuotas',
    bankroll: 'Bankroll', profit: 'Beneficio', winrate: 'Aciertos', open_bets: 'Apuestas abiertas',
    decisions: 'Decisiones', model: 'Modelo', accuracy: 'Precisión', vs_market: 'vs Mercado',
    last_train: 'Train', match: 'Partido', when: 'Cuándo', edge: 'Edge', odds: 'Cuota',
    stake: 'Stake €', status: 'Estado', record: 'Récord', yield_: 'Yield',
    sec_bank: 'Banca', sec_model: 'Modelo', sub_honest: 'honesta, sin fugas', sub_market: 'favorito B365 — a batir', sub_train: 'TennisLoopNightly 07:13',
    c_edgedist: 'Distribución de edge — últimas {n} decisiones', c_today: 'Partidos en el feed (último snapshot)', c_traj: 'Trayectoria del modelo — accuracy y log loss', c_permodel: 'Accuracy por modelo (run actual)',
    tournament: 'Torneo', surface: 'Sup.', side: 'Lado', conf: 'Conf.', player: 'Apuesta a', book: 'Casa', takenodds: 'Cuota tomada', outcome: 'Resultado', modelprob: 'p modelo', bankroll_after: 'Bankroll €', profit_eur: 'Beneficio €',
    allstatus: 'todos los estados', st_pending: 'pendiente', st_won: 'ganada', st_lost: 'perdida',
    betmatch_ph: 'Partido (ej. Sinner vs Alcaraz)', betplayer_ph: 'Apuesta a (jugador)', betodds_ph: 'Cuota', betstake_ph: 'Stake €', betnotes_ph: 'Notas / casa (opcional)', bet_add: '+ registrar', equity: 'Curva de equity — bankroll tras cada apuesta resuelta', bet_won: '✓ ganada', bet_lost: '✗ perdida', undo: '↩',
    f_edgepos: 'solo edge > 0', f_lowconf: 'excluir low-conf', f_clvpos: 'solo CLV positivo',
    ready: 'listo', running: 'ejecutando:', finished: 'terminado (exit', errw: 'error', copyout: 'copiar salida', copied: 'salida copiada', copyfail: 'copia fallida', file_open_failed: 'No se pudo abrir', loading: 'cargando…', links_l: 'Enlaces:', nodata: 'sin datos', rows_l: 'filas', choosematch: '— elige partido —', snap_l: 'snapshot:', nosnap: 'sin snapshot',
    q_today: '¿qué partidos hay hoy?', q_sig: '¿últimas señales del modelo?', q_model: '¿cómo está el modelo?', q_bank: '¿estado del bankroll?', q_vault: 'busca en el vault: ¿por qué el backtest daba 85%?', q_graphelo: 'consulta el grafo: EloRating', q_remember: 'recuerda que: ', q_recall: '¿qué te pedí recordar?',
    note_os: '<b>UnaBettingOS</b> — centro de memoria agéntica. Modelo local <b>qwen3.5:9b</b> vía Ollama. Conectado a: datos en vivo, vault Obsidian, grafo de conocimiento, memoria persistente.', note_memfile: 'La memoria vive en docs/obsidian/UnaBettingOS_Memoria.md — versionada con git.', note_cold: 'Nota: la primera respuesta en frío carga el modelo en VRAM (~1-2 min); luego queda caliente.',
    scanlive: '⚡ escanear partidos en vivo', note_scan: 'descarga cuotas frescas (the-odds-api, consume créditos) y ejecuta modelo + news. Resultados en la pestaña Señales.', stopb: '■ parar', note_ponly: 'Salida en la pestaña "Pipeline". Solo comandos en whitelist: el resto va por los terminales.',
    note_browser: 'Navegador agéntico: abre una URL, lee el contenido, sigue enlaces. UnaBettingOS también puede navegar (herramienta browse_web).', brurl_ph: 'url o dominio…', brback: 'atrás', note_graph: 'El grafo del proyecto (graphify): nodos-estrella coloreados por comunidad, 3D. Arrastra para rotar, scroll para zoom, clic en un nodo para enfocar.',
    l_exp: 'EXPERIMENTS.md', l_nightly: 'bucle nocturno', l_weekly: 'bucle semanal', l_metrics: 'historial de métricas', loops_none: 'aún sin runs',
    term_label: 'TERMINAL', vibe_hint: 'elige un agente en tmux (la sesión sobrevive al cierre de la pestaña)',
    upd_title: 'Actualización disponible', upd_btn: 'Actualizar ahora', upd_later: 'Más tarde', upd_doing: 'actualizando…', upd_done: 'Actualizado ✓ — reinicia la app para aplicar', upd_fail: 'Actualización fallida', upd_restart: 'Reiniciar app',
    chat_intro: "Soy <b>UnaBettingOS</b> — memoria e inteligencia agéntica de la app (qwen3.5:9b, local). Datos en vivo, vault Obsidian, grafo de conocimiento y memoria persistente: pregúntame por los partidos, el modelo o la historia del proyecto — o di \"recuerda que…\".",
    chat_ph: 'escribe… (Intro para enviar)', open_graph: 'abrir el grafo 3D', go: 'ir',
    filter: '⌕ filtrar…', register_bet: 'Registrar apuesta', save: 'Guardar',
  },
  fr: {
    act_cockpit: 'Cockpit de données', act_os: 'UnaBettingOS — mémoire agentique', act_graph: 'Graphe 3D',
    act_browser: 'Navigateur web agentique', act_explorer: 'Explorateur du projet', act_pipeline: 'Pipeline',
    act_loops: 'Boucles auto-évolutives', act_docs: 'Documentation', act_config: 'Config',
    t_cockpit: 'Cockpit', t_os: 'UnaBettingOS', t_graph: 'Graphe de connaissances', t_browser: 'Navigateur',
    t_explorer: 'Explorateur', t_pipeline: 'Pipeline', t_loops: 'Boucles', t_docs: 'Documentation', t_config: 'Config',
    s_data_actions: 'Données & actions', s_memory: 'Mémoire & connaissances', s_live: 'En direct',
    s_pipeline_dm: 'Pipeline données/modèle', s_shortcuts: 'Raccourcis', s_brain: 'Cerveau',
    s_runlogs: 'Logs (reports/loops)', s_root: 'Racine', s_obsidian: 'Obsidian',
    overview: 'Aperçu', signals: 'Signaux', bets: 'Paris', quotes: 'Cotes',
    bankroll: 'Bankroll', profit: 'Profit', winrate: 'Taux de gain', open_bets: 'Paris ouverts',
    decisions: 'Décisions', model: 'Modèle', accuracy: 'Précision', vs_market: 'vs Marché',
    last_train: 'Train', match: 'Match', when: 'Quand', edge: 'Edge', odds: 'Cote',
    stake: 'Mise €', status: 'Statut', record: 'Bilan', yield_: 'Yield',
    sec_bank: 'Banque', sec_model: 'Modèle', sub_honest: 'honnête, sans fuite', sub_market: 'favori B365 — à battre', sub_train: 'TennisLoopNightly 07:13',
    c_edgedist: 'Distribution de l\'edge — {n} dernières décisions', c_today: 'Matchs dans le feed (dernier snapshot)', c_traj: 'Trajectoire du modèle — accuracy & log loss', c_permodel: 'Accuracy par modèle (run actuel)',
    tournament: 'Tournoi', surface: 'Surf.', side: 'Côté', conf: 'Conf.', player: 'Parié sur', book: 'Book', takenodds: 'Cote prise', outcome: 'Résultat', modelprob: 'p modèle', bankroll_after: 'Bankroll €', profit_eur: 'Profit €',
    allstatus: 'tous les statuts', st_pending: 'en attente', st_won: 'gagné', st_lost: 'perdu',
    betmatch_ph: 'Match (ex. Sinner vs Alcaraz)', betplayer_ph: 'Parié sur (joueur)', betodds_ph: 'Cote', betstake_ph: 'Mise €', betnotes_ph: 'Notes / bookmaker (optionnel)', bet_add: '+ enregistrer', equity: 'Courbe d\'equity — bankroll après chaque pari réglé', bet_won: '✓ gagné', bet_lost: '✗ perdu', undo: '↩',
    f_edgepos: 'edge > 0 seulement', f_lowconf: 'exclure low-conf', f_clvpos: 'CLV positif seulement',
    ready: 'prêt', running: 'en cours :', finished: 'terminé (exit', errw: 'erreur', copyout: 'copier la sortie', copied: 'sortie copiée', copyfail: 'échec copie', file_open_failed: 'Impossible d’ouvrir', loading: 'chargement…', links_l: 'Liens :', nodata: 'aucune donnée', rows_l: 'lignes', choosematch: '— choisir un match —', snap_l: 'snapshot :', nosnap: 'aucun snapshot',
    q_today: 'quels sont les matchs du jour ?', q_sig: 'derniers signaux du modèle ?', q_model: 'comment va le modèle ?', q_bank: 'état du bankroll ?', q_vault: 'cherche dans le vault : pourquoi le backtest donnait 85% ?', q_graphelo: 'interroge le graphe : EloRating', q_remember: 'souviens-toi que : ', q_recall: 'que t\'ai-je demandé de retenir ?',
    note_os: '<b>UnaBettingOS</b> — centre de mémoire agentique. Modèle local <b>qwen3.5:9b</b> via Ollama. Connecté à : données en direct, vault Obsidian, graphe de connaissances, mémoire persistante.', note_memfile: 'La mémoire vit dans docs/obsidian/UnaBettingOS_Memoria.md — versionnée avec git.', note_cold: 'Note : la première réponse à froid charge le modèle en VRAM (~1-2 min) ; ensuite il reste chaud.',
    scanlive: '⚡ scanner les matchs en direct', note_scan: 'télécharge des cotes fraîches (the-odds-api, consomme des crédits) et lance modèle + news. Résultats dans l\'onglet Signaux.', stopb: '■ stop', note_ponly: 'Sortie dans l\'onglet "Pipeline". Commandes whitelistées seulement : le reste passe par les terminaux.',
    note_browser: 'Navigateur agentique : ouvre une URL, lis le contenu, suis les liens. UnaBettingOS peut aussi naviguer (outil browse_web).', brurl_ph: 'url ou domaine…', brback: 'retour', note_graph: 'Le graphe du projet (graphify) : nœuds-étoiles colorés par communauté, 3D. Glisser pour tourner, molette pour zoomer, clic sur un nœud pour focaliser.',
    l_exp: 'EXPERIMENTS.md', l_nightly: 'boucle nocturne', l_weekly: 'boucle hebdo', l_metrics: 'historique des métriques', loops_none: 'aucun run pour l\'instant',
    term_label: 'TERMINAL', vibe_hint: 'choisis un agent dans tmux (la session survit à la fermeture de l\'onglet)',
    upd_title: 'Mise à jour disponible', upd_btn: 'Mettre à jour', upd_later: 'Plus tard', upd_doing: 'mise à jour…', upd_done: 'Mis à jour ✓ — redémarre l\'app pour appliquer', upd_fail: 'Échec de la mise à jour', upd_restart: 'Redémarrer',
    chat_intro: "Je suis <b>UnaBettingOS</b> — la mémoire et l'intelligence agentique de l'app (qwen3.5:9b, local). Données en direct, vault Obsidian, graphe de connaissances et mémoire persistante : demande-moi les matchs, le modèle, l'historique du projet — ou dis \"souviens-toi que…\".",
    chat_ph: 'écris… (Entrée pour envoyer)', open_graph: 'ouvrir le graphe 3D', go: 'aller',
    filter: '⌕ filtrer…', register_bet: 'Enregistrer un pari', save: 'Enregistrer',
  },
  de: {
    act_cockpit: 'Daten-Cockpit', act_os: 'UnaBettingOS — agentisches Gedächtnis', act_graph: '3D-Wissensgraph',
    act_browser: 'Agentischer Webbrowser', act_explorer: 'Projekt-Explorer', act_pipeline: 'Pipeline',
    act_loops: 'Selbst-evolvierende Loops', act_docs: 'Dokumentation', act_config: 'Config',
    t_cockpit: 'Cockpit', t_os: 'UnaBettingOS', t_graph: 'Wissensgraph', t_browser: 'Browser',
    t_explorer: 'Explorer', t_pipeline: 'Pipeline', t_loops: 'Loops', t_docs: 'Dokumentation', t_config: 'Config',
    s_data_actions: 'Daten & Aktionen', s_memory: 'Gedächtnis & Wissen', s_live: 'Live',
    s_pipeline_dm: 'Daten/Modell-Pipeline', s_shortcuts: 'Verknüpfungen', s_brain: 'Gehirn',
    s_runlogs: 'Run-Logs (reports/loops)', s_root: 'Wurzel', s_obsidian: 'Obsidian',
    overview: 'Übersicht', signals: 'Signale', bets: 'Wetten', quotes: 'Quoten',
    bankroll: 'Bankroll', profit: 'Gewinn', winrate: 'Trefferquote', open_bets: 'Offene Wetten',
    decisions: 'Entscheidungen', model: 'Modell', accuracy: 'Genauigkeit', vs_market: 'vs Markt',
    last_train: 'Train', match: 'Match', when: 'Wann', edge: 'Edge', odds: 'Quote',
    stake: 'Einsatz €', status: 'Status', record: 'Bilanz', yield_: 'Yield',
    sec_bank: 'Bank', sec_model: 'Modell', sub_honest: 'ehrlich, leak-frei', sub_market: 'B365-Favorit — zu schlagen', sub_train: 'TennisLoopNightly 07:13',
    c_edgedist: 'Edge-Verteilung — letzte {n} Entscheidungen', c_today: 'Matches im Feed (letzter Snapshot)', c_traj: 'Modell-Verlauf — Accuracy & Log Loss', c_permodel: 'Accuracy je Modell (aktueller Run)',
    tournament: 'Turnier', surface: 'Belag', side: 'Seite', conf: 'Konf.', player: 'Wette auf', book: 'Buchm.', takenodds: 'Genommene Quote', outcome: 'Ergebnis', modelprob: 'Modell-p', bankroll_after: 'Bankroll €', profit_eur: 'Gewinn €',
    allstatus: 'alle Status', st_pending: 'offen', st_won: 'gewonnen', st_lost: 'verloren',
    betmatch_ph: 'Match (z.B. Sinner vs Alcaraz)', betplayer_ph: 'Wette auf (Spieler)', betodds_ph: 'Quote', betstake_ph: 'Einsatz €', betnotes_ph: 'Notizen / Buchmacher (optional)', bet_add: '+ eintragen', equity: 'Equity-Kurve — Bankroll nach jeder abgerechneten Wette', bet_won: '✓ gewonnen', bet_lost: '✗ verloren', undo: '↩',
    f_edgepos: 'nur Edge > 0', f_lowconf: 'low-conf ausschließen', f_clvpos: 'nur positives CLV',
    ready: 'bereit', running: 'läuft:', finished: 'beendet (exit', errw: 'Fehler', copyout: 'Ausgabe kopieren', copied: 'Ausgabe kopiert', copyfail: 'Kopie fehlgeschlagen', file_open_failed: 'Öffnen fehlgeschlagen', loading: 'lädt…', links_l: 'Links:', nodata: 'keine Daten', rows_l: 'Zeilen', choosematch: '— Match wählen —', snap_l: 'Snapshot:', nosnap: 'kein Snapshot',
    q_today: 'welche Matches sind heute?', q_sig: 'neueste Modell-Signale?', q_model: 'wie steht das Modell?', q_bank: 'Bankroll-Status?', q_vault: 'durchsuche das Vault: warum zeigte der Backtest 85%?', q_graphelo: 'frage den Graphen ab: EloRating', q_remember: 'merke dir, dass: ', q_recall: 'was solltest du dir merken?',
    note_os: '<b>UnaBettingOS</b> — agentische Gedächtniszentrale. Lokales Modell <b>qwen3.5:9b</b> via Ollama. Verbunden mit: Live-Daten, Obsidian-Vault, Wissensgraph, persistentem Gedächtnis.', note_memfile: 'Das Gedächtnis liegt in docs/obsidian/UnaBettingOS_Memoria.md — git-versioniert.', note_cold: 'Hinweis: die erste Kaltantwort lädt das Modell in den VRAM (~1-2 Min); danach bleibt es warm.',
    scanlive: '⚡ Live-Matches scannen', note_scan: 'holt frische Quoten (the-odds-api, verbraucht Credits) und führt Modell + News aus. Ergebnisse im Tab Signale.', stopb: '■ stopp', note_ponly: 'Ausgabe im Tab "Pipeline". Nur Whitelist-Befehle: alles andere über die Terminals.',
    note_browser: 'Agentischer Browser: URL öffnen, Inhalt lesen, Links folgen. UnaBettingOS kann auch browsen (browse_web-Tool).', brurl_ph: 'url oder Domain…', brback: 'zurück', note_graph: 'Der Projektgraph (graphify): Stern-Knoten nach Community gefärbt, 3D. Ziehen zum Drehen, Scrollen zum Zoomen, Klick auf einen Knoten zum Fokussieren.',
    l_exp: 'EXPERIMENTS.md', l_nightly: 'Nightly-Loop', l_weekly: 'Weekly-Loop', l_metrics: 'Metrik-Historie', loops_none: 'noch keine Runs',
    term_label: 'TERMINAL', vibe_hint: 'wähle einen Agenten in tmux (die Session überlebt das Schließen des Tabs)',
    upd_title: 'Update verfügbar', upd_btn: 'Jetzt aktualisieren', upd_later: 'Später', upd_doing: 'aktualisiere…', upd_done: 'Aktualisiert ✓ — App neu starten zum Anwenden', upd_fail: 'Update fehlgeschlagen', upd_restart: 'App neu starten',
    chat_intro: "Ich bin <b>UnaBettingOS</b> — das agentische Gedächtnis & die Intelligenz der App (qwen3.5:9b, lokal). Live-Daten, Obsidian-Vault, Wissensgraph und persistentes Gedächtnis: frag mich nach Matches, dem Modell, der Projektgeschichte — oder sag \"merke dir, dass…\".",
    chat_ph: 'schreiben… (Enter zum Senden)', open_graph: '3D-Graph öffnen', go: 'los',
    filter: '⌕ filtern…', register_bet: 'Wette eintragen', save: 'Speichern',
  },
};
let LANG = localStorage.getItem('mc-lang') || 'en';
const t = (k) => (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;

const $ = (s) => document.querySelector(s);
const escHtml = SafeHtml.escape;
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
const textEl = (tag, cls, text) => {
  const e = el(tag, cls);
  e.textContent = text;
  return e;
};
const fmt = (v, d = 2) => (v === null || v === undefined) ? '—' : Number(v).toFixed(d);

async function getJSON(url) {
  const r = await fetch(url);
  const data = await r.json().catch(() => ({}));
  if (!r.ok || (data && data.error)) throw new Error(data.detail || data.error || ('HTTP ' + r.status));
  return data;
}

let wsTokenPromise = null;

async function websocketUrl(path, params = {}) {
  if (!wsTokenPromise) {
    wsTokenPromise = getJSON('/api/session')
      .then(data => String(data.websocket_token || ''))
      .catch(err => {
        wsTokenPromise = null;
        throw err;
      });
  }
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = new URL(path, `${scheme}//${location.host}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });
  const token = await wsTokenPromise;
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

/* ================= TAB SYSTEM ================= */
const tabs = {};
let activeTab = null;

function openTab(id, title, build, opts = {}) {
  if (tabs[id]) { activateTab(id); return tabs[id]; }
  const pane = el('div', 'pane');
  $('#content').appendChild(pane);
  const tabEl = el('div', 'tab');
  const tabTitle = el('span', 'ttl');
  tabTitle.textContent = title;
  const tabClose = el('span', 'x');
  tabClose.textContent = '✕';
  tabEl.append(tabTitle, tabClose);
  $('#tabbar').appendChild(tabEl);
  const t = { id, title, paneEl: pane, tabEl, ...opts };
  tabs[id] = t;
  tabEl.addEventListener('click', (e) => {
    if (e.target.classList.contains('x')) closeTab(id); else activateTab(id);
  });
  build(pane, t);
  activateTab(id);
  return t;
}

function activateTab(id) {
  Object.values(tabs).forEach(t => { t.tabEl.classList.remove('active'); t.paneEl.classList.remove('active'); });
  const t = tabs[id];
  if (!t) return;
  activeTab = id;
  t.tabEl.classList.add('active'); t.paneEl.classList.add('active');
  if (t.onShow) t.onShow();
}

function closeTab(id) {
  const t = tabs[id];
  if (!t) return;
  if (t.dirty && !confirm(`"${t.title}" ha modifiche non salvate. Chiudere comunque?`)) return;
  if (t.onClose) t.onClose();
  t.paneEl.remove(); t.tabEl.remove();
  delete tabs[id];
  if (activeTab === id) {
    const left = Object.keys(tabs);
    if (left.length) activateTab(left[left.length - 1]);
    else activeTab = null;
  }
}

function setDirty(id, dirty) {
  const t = tabs[id];
  if (!t) return;
  t.dirty = dirty;
  const title = t.tabEl.querySelector('.ttl');
  title.textContent = t.title;
  if (dirty) {
    const marker = el('span', 'dirty');
    marker.textContent = '●';
    title.prepend(marker, ' ');
  }
}

/* ================= SORTABLE / FILTERABLE TABLE ================= */
/* makeTable(container, cols, rows, opts)
   - click intestazione: ordina (1° click discendente, 2° ascendente)
   - search box: filtra su tutte le colonne
   - opts.controls: [{el, test(row)}] filtri custom (select/checkbox)
   - opts.sortKey/sortDir: ordinamento iniziale                         */
function makeTable(container, cols, rows, opts = {}) {
  const state = { sortKey: opts.sortKey || null, sortDir: opts.sortDir || -1, query: '' };
  container.innerHTML = '';
  const bar = el('div', 'table-toolbar');
  const inp = el('input', 'tbl-search');
  inp.type = 'search'; inp.placeholder = t('filter');
  inp.oninput = () => { state.query = inp.value.toLowerCase(); draw(); };
  bar.appendChild(inp);
  (opts.controls || []).forEach(c => { bar.appendChild(c.el); c.onChange = draw; });
  const count = el('span', 'tbl-count');
  bar.appendChild(count);
  container.appendChild(bar);
  const wrap = el('div', 'table-wrap');
  const table = el('table');
  wrap.appendChild(table);
  container.appendChild(wrap);

  function visibleRows() {
    let out = rows;
    if (state.query) {
      out = out.filter(r => cols.some(c => String(r[c.key] ?? '').toLowerCase().includes(state.query)));
    }
    (opts.controls || []).forEach(c => { if (c.test) out = out.filter(c.test); });
    if (state.sortKey) {
      const k = state.sortKey, dir = state.sortDir;
      out = [...out].sort((a, b) => {
        const va = a[k], vb = b[k];
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        const na = Number(va), nb = Number(vb);
        if (Number.isFinite(na) && Number.isFinite(nb)) return (na - nb) * dir;
        return String(va).localeCompare(String(vb)) * dir;
      });
    }
    return out;
  }

  function draw() {
    const data = visibleRows();
    count.textContent = `${data.length}/${rows.length} ${t('rows_l')}`;
    if (!rows.length) { table.innerHTML = `<tr><td class="dim">${t('nodata')}</td></tr>`; return; }
    const head = '<tr>' + cols.map(c => {
      const sorted = state.sortKey === c.key;
      const arrow = sorted ? (state.sortDir === 1 ? ' ▲' : ' ▼') : '';
      return `<th data-key="${escHtml(c.key)}" class="${sorted ? 'sorted' : ''}">${escHtml(c.label)}${arrow}</th>`;
    }).join('') + '</tr>';
    const body = data.map(r => '<tr>' + cols.map(c => {
      let v = r[c.key];
      if (c.fmt) v = c.fmt(v, r);
      const cls = opts.cellClass ? (opts.cellClass(c.key, r) || '') : '';
      return `<td class="${escHtml(cls)}">${SafeHtml.tableCell(v, c.html === true)}</td>`;
    }).join('') + '</tr>').join('');
    table.innerHTML = head + body;
  }

  table.addEventListener('click', (e) => {
    const th = e.target.closest('th');
    if (!th || !th.dataset.key) return;
    if (state.sortKey === th.dataset.key) state.sortDir *= -1;
    else { state.sortKey = th.dataset.key; state.sortDir = -1; }  // primo click: decrescente
    draw();
  });

  draw();
  return { redraw: draw, state };
}

function makeCheck(label, test) {
  const lab = el('label', 'tbl-check', `<input type="checkbox"> ${escHtml(label)}`);
  const box = lab.querySelector('input');
  const ctl = { el: lab, test: null };
  box.onchange = () => { ctl.test = box.checked ? test : null; if (ctl.onChange) ctl.onChange(); };
  return ctl;
}

function makeSelect(options, testFactory) {
  const sel = el('select', 'tbl-select');
  options.forEach(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    sel.appendChild(option);
  });
  const ctl = { el: sel, test: null };
  sel.onchange = () => { ctl.test = sel.value ? testFactory(sel.value) : null; if (ctl.onChange) ctl.onChange(); };
  return ctl;
}

const dt = v => v ? String(v).slice(0, 16).replace('T', ' ') : '—';

/* ================= COCKPIT PANELS ================= */
const CHART_FONT = { family: 'IBM Plex Mono, monospace', size: 10 };

/* ---- temi: i colori dei grafici seguono le CSS var del tema attivo ---- */
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let INK, CLAY, GRASS, SUN, DIM;
function refreshThemeColors() {
  INK = cssVar('--ink'); CLAY = cssVar('--accent-2'); GRASS = cssVar('--accent');
  SUN = cssVar('--highlight'); DIM = cssVar('--ink-faint');
  if (window.Chart) { Chart.defaults.color = INK; Chart.defaults.borderColor = cssVar('--line'); }
}

const THEMES = [
  ['hermes', '🎾 Hermes'], ['onepiece', '⚓ One Piece'], ['matrix', '▮ Matrix'],
  ['batman', '🦇 Batman'], ['hitman', '♠ Hitman'], ['diablo', '🔥 Diablo IV'],
];

function applyTheme(th) {
  document.documentElement.dataset.theme = th;
  localStorage.setItem('mc-theme', th);
  refreshThemeColors();
  // terminali aperti: aggiorna i colori al volo
  Object.values(terms).forEach(x => {
    x.term.options.theme = { background: cssVar('--term-bg'), foreground: cssVar('--term-fg'), cursor: cssVar('--highlight') };
  });
  // pannello attivo: ri-renderizza coi colori nuovi
  if (activeTab && activeTab.startsWith('panel:')) {
    const name = activeTab.split(':')[1];
    if (PANELS[name]) { closeTab(activeTab); openPanel(name); }
  }
}

function blk(k, v, cls = '', sub = '') {
  return `<div class="blk ${cls}"><div class="k">${k}</div><div class="v">${v}</div>` +
         (sub ? `<div class="s">${sub}</div>` : '') + '</div>';
}

const PANELS = {
  overview: { title: 'Overview', render: async (pane) => {
    const [d, mo, dec, odds] = await Promise.all([
      getJSON('/api/overview'), getJSON('/api/model'),
      getJSON('/api/decisions?limit=500'), getJSON('/api/odds'),
    ]);
    const c = mo.current || {};
    pane.innerHTML = `<div class="pane-pad dash">
      <div class="section-bar">${t('sec_bank')} <small>betanalytix.db</small></div>
      <div class="blk-row">
        ${blk(t('bankroll'), d.bankroll !== null ? '€' + fmt(d.bankroll, 0) : '—', 'ink')}
        ${blk(t('profit'), '€' + fmt(d.total_profit, 0), d.total_profit < 0 ? 'alarm' : 'grass')}
        ${blk('ROI', d.roi_pct !== null ? fmt(d.roi_pct, 1) + '%' : '—', '')}
        ${blk(t('winrate'), d.win_rate !== null ? fmt(d.win_rate, 0) + '%' : '—', '')}
        ${blk(t('open_bets'), d.bets_open, 'sun')}
        ${blk(t('decisions'), d.decisions, '', t('snap_l') + ' ' + dt(d.last_scan))}
      </div>
      <div class="section-bar">${t('sec_model')} <small>${c.best_model || '—'} · test 2025+</small></div>
      <div class="blk-row">
        ${blk(t('accuracy'), c.accuracy ? (c.accuracy * 100).toFixed(1) + '%' : '—', 'grass', t('sub_honest'))}
        ${blk('Odds-ens', c.odds_ensemble_accuracy ? (c.odds_ensemble_accuracy * 100).toFixed(1) + '%' : '—', 'clay', 'real-odds rows')}
        ${blk('Log loss', c.log_loss ? c.log_loss.toFixed(3) : '—', 'ink')}
        ${blk('ROC AUC', c.roc_auc ? c.roc_auc.toFixed(3) : '—', '')}
        ${blk(t('last_train'), c.trained_at ? dt(c.trained_at) : '—', '', t('sub_train'))}
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>${t('c_edgedist').replace('{n}', dec.length)}</h4>
          <canvas id="ch-edge"></canvas></div>
        <div class="chart-box"><h4>${t('c_today')}</h4>
          <div class="today-list" id="today-list"></div></div>
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>${t('c_traj')}</h4>
          <canvas id="ch-hist"></canvas></div>
        <div class="chart-box"><h4>${t('c_permodel')}</h4>
          <canvas id="ch-models"></canvas></div>
      </div>
    </div>`;

    Chart.defaults.font = CHART_FONT;
    Chart.defaults.color = INK;

    // edge histogram
    const edges = dec.map(r => r.edge).filter(e => e !== null && isFinite(e));
    const bins = [-0.3, -0.2, -0.1, -0.05, 0, 0.05, 0.1, 0.2, 0.3, 0.5];
    const counts = new Array(bins.length - 1).fill(0);
    edges.forEach(e => { for (let i = 0; i < bins.length - 1; i++) if (e >= bins[i] && e < bins[i + 1]) { counts[i]++; break; } });
    new Chart($('#ch-edge'), {
      type: 'bar',
      data: { labels: bins.slice(0, -1).map((b, i) => `${b}–${bins[i + 1]}`),
              datasets: [{ data: counts, backgroundColor: bins.slice(0, -1).map(b => b >= 0 ? GRASS : CLAY), borderColor: INK, borderWidth: 1.5 }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: 'rgba(26,26,18,0.1)' } } } },
    });

    // today's matches with best legal price (top 8)
    const tl = $('#today-list');
    const matches = (odds.matches || []).slice(0, 8);
    if (!matches.length) tl.innerHTML = `<div class="sb-note">${t('nosnap')}</div>`;
    matches.forEach(async m => {
      const row = el('div', 'today-row');
      const matchName = el('span', 't-m');
      matchName.textContent = m;
      const prices = el('span', 't-o');
      prices.textContent = '…';
      row.append(matchName, prices);
      tl.appendChild(row);
      try {
        const dd = await getJSON('/api/odds?match=' + encodeURIComponent(m));
        const best1 = Math.max(...dd.rows.map(r => r.price_1 || 0));
        const best2 = Math.max(...dd.rows.map(r => r.price_2 || 0));
        row.querySelector('.t-o').textContent = `${best1.toFixed(2)} / ${best2.toFixed(2)}`;
      } catch (e) { row.querySelector('.t-o').textContent = '—'; }
    });

    // metrics history
    const hist = mo.history || [];
    new Chart($('#ch-hist'), {
      type: 'line',
      data: { labels: hist.map(h => String(h.trained_at).slice(5, 16).replace('T', ' ')),
        datasets: [
          { label: 'accuracy', data: hist.map(h => +h.accuracy * 100), borderColor: GRASS, backgroundColor: GRASS, yAxisID: 'y', tension: 0.25, pointRadius: 4 },
          { label: 'log loss', data: hist.map(h => +h.log_loss), borderColor: CLAY, backgroundColor: CLAY, yAxisID: 'y2', tension: 0.25, pointRadius: 4 },
        ] },
      options: { plugins: { legend: { labels: { boxWidth: 10 } } },
        scales: { y: { position: 'left', title: { display: true, text: 'acc %' }, grid: { color: 'rgba(26,26,18,0.1)' } },
                  y2: { position: 'right', title: { display: true, text: 'log loss' }, grid: { display: false } },
                  x: { grid: { display: false } } } },
    });

    // per-model accuracy
    const models = Object.entries(c.models || {}).filter(([k]) => k.startsWith('target_'));
    new Chart($('#ch-models'), {
      type: 'bar',
      data: { labels: models.map(([k]) => k.replace('target_', '')),
              datasets: [{ data: models.map(([, v]) => v.accuracy * 100), backgroundColor: models.map(([k]) => k === c.best_model ? SUN : INK), borderColor: INK, borderWidth: 1.5 }] },
      options: { indexAxis: 'y', plugins: { legend: { display: false } },
        scales: { x: { min: 60, max: 70, grid: { color: 'rgba(26,26,18,0.1)' }, title: { display: true, text: 'accuracy %' } }, y: { grid: { display: false } } } },
    });
  }},
  segnali: { title: 'Segnali', render: async (pane) => {
    const rows = await getJSON('/api/decisions?limit=500');
    pane.innerHTML = '<div class="pane-pad" style="height:100%"><div class="tbl-host" style="height:100%"></div></div>';
    makeTable(pane.querySelector('.tbl-host'), [
      { key: 'timestamp', label: t('when'), fmt: dt },
      { key: 'match_str', label: t('match') }, { key: 'tournament', label: t('tournament') },
      { key: 'surface', label: t('surface') },
      { key: 'odds_1', label: 'Q1', fmt: v => fmt(v) }, { key: 'odds_2', label: 'Q2', fmt: v => fmt(v) },
      { key: 'ml_prob_1', label: 'ML p1', fmt: v => fmt(v, 3) }, { key: 'ml_prob_2', label: 'ML p2', fmt: v => fmt(v, 3) },
      { key: 'edge', label: t('edge'), fmt: v => fmt(v, 3) }, { key: 'value_side', label: t('side') },
      { key: 'kelly_fraction', label: 'Kelly', fmt: v => fmt(v, 4) },
      { key: 'low_confidence', label: t('conf'), fmt: v => v ? 'LOW' : 'ok' },
    ], rows, {
      sortKey: 'timestamp', sortDir: -1,
      controls: [makeCheck(t('f_edgepos'), r => r.edge > 0),
                 makeCheck(t('f_lowconf'), r => !r.low_confidence)],
      cellClass: (k, r) => k === 'edge' ? (r.edge > 0 ? 'pos' : 'neg')
                         : k === 'low_confidence' ? (r.low_confidence ? 'neg' : 'dim') : '',
    });
  }},
  bet: { title: 'Bet', render: async (pane) => {
    const rows = await getJSON('/api/bets');
    const settled = rows.filter(r => r.status === 'won' || r.status === 'lost');
    const staked = settled.reduce((s, r) => s + (r.stake || 0), 0);
    const profit = settled.reduce((s, r) => s + (r.profit || 0), 0);
    const won = settled.filter(r => r.status === 'won').length;
    const bank = rows.filter(r => r.bankroll_after !== null)
                     .sort((a, b) => (a.resolved_at || '').localeCompare(b.resolved_at || ''));

    pane.innerHTML = `<div class="pane-pad dash" style="height:100%; overflow:auto">
      <div class="blk-row">
        ${blk(t('bankroll'), bank.length ? '€' + fmt(bank[bank.length - 1].bankroll_after, 0) : '—', 'ink')}
        ${blk(t('profit'), '€' + fmt(profit, 1), profit < 0 ? 'alarm' : 'grass')}
        ${blk('Yield', staked ? (profit / staked * 100).toFixed(1) + '%' : '—', '', 'profit / stake')}
        ${blk(t('record'), `${won}–${settled.length - won}`, 'sun', rows.filter(r => r.status === 'pending').length + ' ' + t('st_pending'))}
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>${t('equity')}</h4><canvas id="ch-bank"></canvas></div>
        <div class="chart-box"><h4>${t('register_bet')}</h4>
          <form id="bet-form" class="bet-form">
            <input name="match_str" placeholder="${t('betmatch_ph')}" required>
            <input name="side_name" placeholder="${t('betplayer_ph')}" required>
            <div class="bet-form-row">
              <input name="odds" type="number" step="0.01" min="1.01" placeholder="${t('betodds_ph')}" required>
              <input name="stake" type="number" step="0.5" min="0.5" placeholder="${t('betstake_ph')}" required>
            </div>
            <input name="notes" placeholder="${t('betnotes_ph')}">
            <button class="btn primary" type="submit">${t('bet_add')}</button>
            <span class="panel-note" id="bet-form-status"></span>
          </form></div>
      </div>
      <div class="tbl-host"></div></div>`;

    new Chart($('#ch-bank'), {
      type: 'line',
      data: { labels: bank.map(b => dt(b.resolved_at)),
        datasets: [{ label: 'bankroll €', data: bank.map(b => b.bankroll_after),
                     borderColor: INK, backgroundColor: SUN, pointRadius: 4, tension: 0.15, fill: false }] },
      options: { plugins: { legend: { display: false } },
        scales: { y: { grid: { color: 'rgba(26,26,18,0.1)' } }, x: { grid: { display: false } } } },
    });

    $('#bet-form').onsubmit = async (e) => {
      e.preventDefault();
      const f = new FormData(e.target), st = $('#bet-form-status');
      st.textContent = '…';
      try {
        const r = await fetch('/api/bet', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(Object.fromEntries(f.entries())) });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || d.error);
        toast('bet registrata');
        delete tabs['panel:bet']; closeTab('panel:bet'); openPanel('bet');
      } catch (err) { st.textContent = 'ERRORE: ' + err.message; }
    };

    const host = pane.querySelector('.tbl-host');
    makeTable(host, [
      { key: 'timestamp', label: t('when'), fmt: dt }, { key: 'match_str', label: t('match') },
      { key: 'side_name', label: t('player') }, { key: 'odds', label: t('odds'), fmt: v => fmt(v) },
      { key: 'stake', label: t('stake'), fmt: v => fmt(v) },
      { key: 'status', label: t('status') },
      { key: 'profit', label: t('profit_eur'), fmt: v => v === null ? '—' : fmt(v) },
      { key: 'bankroll_after', label: t('bankroll_after'), fmt: v => v === null ? '—' : fmt(v) },
      { key: 'id', label: t('outcome'), fmt: (v, r) => r.status === 'pending'
          ? `<button class="row-act win" data-id="${escHtml(v)}" data-do="won">${escHtml(t('bet_won'))}</button>
             <button class="row-act lose" data-id="${escHtml(v)}" data-do="lost">${escHtml(t('bet_lost'))}</button>`
          : `<button class="row-act" data-id="${escHtml(v)}" data-do="undo">${escHtml(t('undo'))}</button>`,
        html: true },
    ], rows, {
      sortKey: 'timestamp', sortDir: -1,
      controls: [makeSelect([['', t('allstatus')], ['pending', t('st_pending')], ['won', t('st_won')], ['lost', t('st_lost')]],
                            v => r => r.status === v)],
      cellClass: (k, r) => k === 'status' ? (r.status === 'won' ? 'pos' : (r.status === 'lost' ? 'neg' : 'dim'))
                         : (k === 'profit' && r.profit !== null) ? (r.profit > 0 ? 'pos' : 'neg') : '',
    });
    host.addEventListener('click', async (e) => {
      const b = e.target.closest('.row-act');
      if (!b) return;
      const url = b.dataset.do === 'undo' ? `/api/bet/${b.dataset.id}/undo` : `/api/bet/${b.dataset.id}/resolve`;
      try {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ won: b.dataset.do === 'won' }) });
        if (!r.ok) throw new Error((await r.json()).detail);
        toast(b.dataset.do === 'undo' ? 'esito annullato' : 'esito registrato: ' + b.dataset.do);
        closeTab('panel:bet'); openPanel('bet');
      } catch (err) { toast('errore: ' + err.message, true); }
    });
  }},
  clv: { title: 'CLV', render: async (pane) => {
    const d = await getJSON('/api/clv');
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="panel-note">${escHtml(d.note || '')}${d.mean_clv !== null ? ' · CLV medio: ' + (d.mean_clv * 100).toFixed(2) + '%' : ''}</div>
      <canvas id="clv-chart" width="960" height="240"></canvas>
      <div class="tbl-host"></div></div>`;
    const vals = (d.rows || []).filter(r => r.clv !== null && r.clv !== undefined).map(r => r.clv);
    drawClv(pane.querySelector('#clv-chart'), vals);
    makeTable(pane.querySelector('.tbl-host'), [
      { key: 'ts', label: t('when'), fmt: dt }, { key: 'match', label: t('match') },
      { key: 'side', label: t('side') }, { key: 'bookmaker', label: t('book') },
      { key: 'odds', label: t('takenodds'), fmt: v => fmt(v) },
      { key: 'clv', label: 'CLV', fmt: v => v === null ? '—' : (v * 100).toFixed(2) + '%' },
    ], d.rows || [], {
      sortKey: 'clv', sortDir: -1,
      controls: [makeCheck(t('f_clvpos'), r => r.clv !== null && r.clv > 0)],
      cellClass: (k, r) => k === 'clv' && r.clv !== null ? (r.clv > 0 ? 'pos' : 'neg') : '',
    });
  }},
  quote: { title: 'Quote', render: async (pane) => {
    const d = await getJSON('/api/odds');
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="toolbar"><select class="match-sel"></select>
        <span class="panel-note">${d.snapshot_ts ? escHtml(t('snap_l') + ' ' + d.snapshot_ts) : escHtml(t('nosnap'))}</span></div>
      <div class="tbl-host"></div></div>`;
    const sel = pane.querySelector('.match-sel');
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = t('choosematch');
    sel.appendChild(placeholder);
    (d.matches || []).forEach(match => {
      const option = document.createElement('option');
      option.textContent = match;
      sel.appendChild(option);
    });
    sel.onchange = async () => {
      if (!sel.value) return;
      const dd = await getJSON('/api/odds?match=' + encodeURIComponent(sel.value));
      makeTable(pane.querySelector('.tbl-host'), [
        { key: 'bookmaker', label: t('book') }, { key: 'p1', label: t('player') + ' 1' },
        { key: 'price_1', label: t('odds') + ' 1', fmt: v => fmt(v) },
        { key: 'p2', label: t('player') + ' 2' }, { key: 'price_2', label: t('odds') + ' 2', fmt: v => fmt(v) },
      ], dd.rows, { sortKey: 'price_1', sortDir: -1 });   // default: quota 1 decrescente
    };
  }},
};

function drawClv(cv, vals) {
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.font = '12px IBM Plex Mono, monospace';
  if (!vals.length) { ctx.fillStyle = '#8C8470'; ctx.fillText('Nessun dato CLV — accumula snapshot', 20, 40); return; }
  const pad = 30, W = cv.width - pad * 2, H = cv.height - pad * 2;
  const mx = Math.max(0.01, Math.max(...vals.map(Math.abs)));
  const y = v => pad + H / 2 - (v / mx) * (H / 2);
  const x = i => pad + (vals.length === 1 ? W / 2 : i * W / (vals.length - 1));
  ctx.strokeStyle = 'rgba(26,26,18,0.35)'; ctx.beginPath(); ctx.moveTo(pad, y(0)); ctx.lineTo(pad + W, y(0)); ctx.stroke();
  ctx.strokeStyle = '#C75A2A'; ctx.lineWidth = 2; ctx.beginPath();
  vals.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
  ctx.stroke();
  vals.forEach((v, i) => {
    ctx.fillStyle = v >= 0 ? '#2E6B3F' : '#C0392B';
    ctx.beginPath(); ctx.arc(x(i), y(v), 3, 0, Math.PI * 2); ctx.fill();
  });
}

const PANEL_TKEY = { overview: 'overview', segnali: 'signals', bet: 'bets', clv: 'CLV', quote: 'quotes' };
function openPanel(name) {
  const p = PANELS[name];
  const title = I18N[LANG][PANEL_TKEY[name]] || p.title;
  openTab('panel:' + name, title, async (pane) => {
    try { await p.render(pane); }
    catch (err) { pane.innerHTML = `<div class="pane-pad"><div class="banner">ERRORE: ${escHtml(err.message)}</div></div>`; }
  });
}

/* ================= EDITOR ================= */
const MODES = { py: 'python', yaml: 'yaml', yml: 'yaml', js: 'javascript', json: { name: 'javascript', json: true },
                md: 'markdown', markdown: 'markdown', sh: 'shell', ps1: 'shell', bat: 'shell',
                css: 'css', html: 'htmlmixed', txt: null, csv: null, log: null };

const IMG_EXT = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'];
const VID_EXT = ['mp4', 'webm', 'mov', 'mkv', 'm4v'];
const AUD_EXT = ['mp3', 'wav', 'ogg', 'm4a'];

function openMedia(path) {
  const id = 'media:' + path;
  if (tabs[id]) { activateTab(id); return; }
  const name = path.split('/').pop();
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
  const src = '/api/media?path=' + encodeURIComponent(path);
  let inner;
  if (IMG_EXT.includes(ext)) inner = `<img src="${src}" alt="${escHtml(name)}">`;
  else if (VID_EXT.includes(ext)) inner = `<video src="${src}" controls autoplay></video>`;
  else if (AUD_EXT.includes(ext)) inner = `<audio src="${src}" controls autoplay></audio>`;
  else if (ext === 'pdf') inner = `<iframe src="${src}" style="width:100%;height:100%;border:none"></iframe>`;
  else inner = `<div class="panel-note">anteprima non disponibile per .${escHtml(ext)}</div>`;
  openTab(id, name, (pane) => {
    pane.innerHTML = `<div class="media-host">${inner}</div>`;
  });
}

async function openFile(path, readonly = false) {
  const name0 = path.split('/').pop();
  const ext0 = name0.includes('.') ? name0.split('.').pop().toLowerCase() : '';
  if ([...IMG_EXT, ...VID_EXT, ...AUD_EXT, 'pdf'].includes(ext0)) { openMedia(path); return; }
  const id = 'file:' + path;
  if (tabs[id]) { activateTab(id); return; }
  let data;
  try { data = await getJSON('/api/file?path=' + encodeURIComponent(path)); }
  catch (err) { alert(t('file_open_failed') + ' ' + path + ': ' + err.message); return; }
  const name = path.split('/').pop();
  openTab(id, name, (pane, t) => {
    pane.innerHTML = `<div class="editor-host">
      <div class="editor-toolbar">
        <span>${escHtml(path)}${readonly ? ' · sola lettura' : ''}</span>
        ${readonly ? '' : '<button class="btn primary save">Salva (Ctrl+S)</button>'}
        <span class="status"></span>
      </div>
      <div class="editor-cm"></div></div>`;
    const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
    const cm = CodeMirror(pane.querySelector('.editor-cm'), {
      value: data.content, mode: MODES[ext] ?? null, lineNumbers: true,
      readOnly: readonly, lineWrapping: ['md', 'txt', 'log'].includes(ext), viewportMargin: 50,
    });
    t.cm = cm;
    t.onShow = () => setTimeout(() => cm.refresh(), 10);
    if (!readonly) {
      cm.on('change', () => setDirty(id, true));
      const save = async () => {
        const st = pane.querySelector('.status');
        st.textContent = 'salvataggio…';
        try {
          if (path === 'config/config.yaml') {
            const r = await fetch('/api/config', { method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ content: cm.getValue() }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || d.error);
            st.textContent = 'salvato ✓ (backup .bak)';
          } else {
            const r = await fetch('/api/file', { method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path, content: cm.getValue() }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || d.error);
            st.textContent = 'salvato ✓';
          }
          setDirty(id, false);
        } catch (err) { st.textContent = 'ERRORE: ' + err.message; }
      };
      pane.querySelector('.save').onclick = save;
      cm.setOption('extraKeys', { 'Ctrl-S': save });
    }
  });
}

/* ================= SIDEBAR / ACTIVITIES ================= */
const ACTS = {
  cockpit: { title: 'Cockpit', render: (body) => {
    ['overview', 'segnali', 'bet', 'clv', 'quote'].forEach(name => {
      const b = el('button', 'sb-item', '◧ ' + (I18N[LANG][PANEL_TKEY[name]] || PANELS[name].title));
      b.onclick = () => openPanel(name);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-note', 'betanalytix.db · odds_history.csv'));
  }},
  chat: { title: 'UnaBettingOS', render: (body) => {
    body.appendChild(el('div', 'sb-note', t('note_os')));
    body.appendChild(el('div', 'sb-section', t('s_data_actions')));
    [t('q_today'), t('q_sig'), t('q_model'), t('q_bank')].forEach(q => {
      const b = el('button', 'sb-item', '✦ ' + q);
      b.onclick = () => { openChat(); const inp = $('#chat-input'); if (inp) { inp.value = q; inp.focus(); } };
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', t('s_memory')));
    [t('q_vault'), t('q_graphelo'), t('q_remember'), t('q_recall')].forEach(q => {
      const b = el('button', 'sb-item', '🧠 ' + q);
      b.onclick = () => { openChat(); const inp = $('#chat-input'); if (inp) { inp.value = q; inp.focus(); } };
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-note', t('note_memfile')));
    openChat();
  }},
  browser: { title: 'Browser web', render: (body) => {
    body.appendChild(el('div', 'sb-note', t('note_browser')));
    body.appendChild(el('div', 'sb-section', t('s_shortcuts')));
    [['Sofascore tennis', 'https://www.sofascore.com/tennis'],
     ['ATP Tour', 'https://www.atptour.com'],
     ['Tennis Abstract', 'http://www.tennisabstract.com'],
     ['the-odds-api', 'https://the-odds-api.com']].forEach(([label, url]) => {
      const b = el('button', 'sb-item', '🌐 ' + label);
      b.onclick = () => openBrowser(url);
      body.appendChild(b);
    });
    openBrowser('https://www.sofascore.com/tennis');
  }},
  graph: { title: 'Knowledge graph', render: (body) => {
    body.appendChild(el('div', 'sb-note', t('note_graph')));
    const b = el('button', 'sb-item', '❂ ' + t('open_graph'));
    b.onclick = openGraph3D;
    body.appendChild(b);
    openGraph3D();
  }},
  explorer: { title: 'Esplora progetto', render: (body) => { body.appendChild(buildTree('')); } },
  pipeline: { title: 'Pipeline', render: (body) => {
    body.appendChild(el('div', 'sb-section', t('s_live')));
    const scan = el('button', 'sb-cmd', t('scanlive'));
    scan.dataset.cmd = 'scan';
    scan.onclick = () => runCommand('scan');
    body.appendChild(scan);
    body.appendChild(el('div', 'sb-note', t('note_scan')));
    body.appendChild(el('div', 'sb-section', t('s_pipeline_dm')));
    ['download', 'clean', 'features', 'train', 'backtest', 'inference', 'signals'].forEach(cmd => {
      const b = el('button', 'sb-cmd', '▶ ' + cmd);
      b.dataset.cmd = cmd;
      b.onclick = () => runCommand(cmd);
      body.appendChild(b);
    });
    const stop = el('button', 'sb-cmd stop', t('stopb'));
    stop.onclick = () => { if (runWs && runWs.readyState === 1) runWs.send(JSON.stringify({ type: 'stop' })); };
    body.appendChild(stop);
    body.appendChild(el('div', 'sb-note', t('note_ponly')));
  }},
  loops: { title: 'Loop autoevolutivi', render: async (body) => {
    body.appendChild(el('div', 'sb-section', t('s_brain')));
    [[t('l_exp'), 'EXPERIMENTS.md'],
     [t('l_nightly'), 'scripts/loops/nightly_maintenance.md'],
     [t('l_weekly'), 'scripts/loops/weekly_evolution.md'],
     [t('l_metrics'), 'reports/metrics_history.csv']].forEach(([label, p]) => {
      const b = el('button', 'sb-item', '¶ ' + label);
      b.onclick = () => openFile(p);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', t('s_runlogs')));
    try {
      const logs = await getJSON('/api/loops');
      if (!logs.length) body.appendChild(el('div', 'sb-note', t('loops_none')));
      logs.slice(0, 25).forEach(l => {
        const b = textEl('button', 'sb-item', '≡ ' + l.name);
        b.onclick = () => openFile(l.path, true);
        body.appendChild(b);
      });
    } catch (err) { body.appendChild(textEl('div', 'sb-note', 'errore: ' + err.message)); }
  }},
  docs: { title: 'Documentazione', render: async (body) => {
    body.appendChild(el('div', 'sb-section', t('s_root')));
    ['README.md', 'EXPERIMENTS.md', 'DATA_SOURCES.md', 'docs/ALPHA_FINDINGS.md', 'docs/PROJECT_EVALUATION.md'].forEach(p => {
      const b = el('button', 'sb-item', '¶ ' + p);
      b.onclick = () => openFile(p);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', 'Obsidian'));
    try {
      (await getJSON('/api/tree?path=docs/obsidian')).filter(i => !i.dir).forEach(i => {
        const b = textEl('button', 'sb-item', '¶ ' + i.name);
        b.onclick = () => openFile(i.path);
        body.appendChild(b);
      });
    } catch (err) { body.appendChild(textEl('div', 'sb-note', 'errore: ' + err.message)); }
  }},
  config: { title: 'Config', render: (body) => {
    const b = el('button', 'sb-item', '⚙ config/config.yaml');
    b.onclick = () => openFile('config/config.yaml');
    body.appendChild(b);
    const b2 = el('button', 'sb-item', '⚙ selected_features_atp.txt');
    b2.onclick = () => openFile('config/selected_features_atp.txt');
    body.appendChild(b2);
    body.appendChild(el('div', 'sb-note', 'config.yaml viene salvato con backup .bak automatico'));
    openFile('config/config.yaml');
  }},
};

function buildTree(path) {
  const wrap = el('div');
  getJSON('/api/tree?path=' + encodeURIComponent(path)).then(items => {
    items.forEach(item => {
      if (item.dir) {
        const dir = el('div', 'tree-dir');
        const btn = el('button', 'sb-item');
        const twist = el('span', 'tw');
        twist.textContent = '▸';
        btn.append(twist, `🗀 ${item.name}`);
        const children = el('div', 'tree-children');
        children.style.paddingLeft = '14px';
        let loaded = false;
        btn.onclick = () => {
          dir.classList.toggle('open');
          twist.textContent = dir.classList.contains('open') ? '▾' : '▸';
          if (!loaded) { children.appendChild(buildTree(item.path)); loaded = true; }
        };
        dir.appendChild(btn); dir.appendChild(children); wrap.appendChild(dir);
      } else {
        const btn = el('button', 'sb-item');
        btn.append(el('span', 'tw'), `· ${item.name}`);
        btn.onclick = () => openFile(item.path);
        wrap.appendChild(btn);
      }
    });
  }).catch(err => wrap.appendChild(textEl('div', 'sb-note', 'errore: ' + err.message)));
  return wrap;
}

const ACT_TKEY = { cockpit: 't_cockpit', chat: 't_os', graph: 't_graph', browser: 't_browser',
                   explorer: 't_explorer', pipeline: 't_pipeline', loops: 't_loops',
                   docs: 't_docs', config: 't_config' };
let currentAct = 'cockpit';
function renderSidebar(actId) {
  currentAct = actId;
  const act = ACTS[actId];
  $('#sb-title').textContent = (I18N[LANG][ACT_TKEY[actId]] || act.title).toUpperCase();
  const body = $('#sb-body');
  body.innerHTML = '';
  act.render(body);
}
$('#activitybar').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  document.querySelectorAll('#activitybar button').forEach(b => b.classList.toggle('active', b === btn));
  renderSidebar(btn.dataset.act);
});

/* ================= PIPELINE RUNNER ================= */
let runWs = null;

function pipelinePane() {
  return openTab('panel:pipeline', 'Pipeline', (pane) => {
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="toolbar">
        <span class="panel-note" id="pl-status" style="margin:0">${t('ready')}</span>
        <button class="btn" id="pl-copy">${t('copyout')}</button>
      </div>
      <pre class="cli-box" id="pl-out"></pre></div>`;
    pane.querySelector('#pl-copy').onclick = async () => {
      try {
        await navigator.clipboard.writeText($('#pl-out').textContent);
        toast(t('copied'));
      } catch (err) { toast(t('copyfail') + ': ' + err.message, true); }
    };
  });
}

async function runCommand(cmd) {
  pipelinePane();
  activateTab('panel:pipeline');
  const out = $('#pl-out'), status = $('#pl-status');
  const send = () => runWs.send(JSON.stringify({ cmd }));
  if (!runWs || runWs.readyState !== 1) {
    try {
      runWs = new WebSocket(await websocketUrl('/ws/run'));
    } catch (err) {
      status.textContent = t('errw');
      out.textContent += '[ERROR] ' + err.message + '\n';
      return;
    }
    runWs.onopen = send;
    runWs.onerror = () => { status.textContent = t('errw'); };
    runWs.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'start') {
        out.textContent = `$ ${m.cmd}\n`;
        status.textContent = t('running') + ' ' + m.cmd;
        document.querySelectorAll('.sb-cmd').forEach(b => b.classList.toggle('running', b.dataset.cmd === m.cmd));
      } else if (m.type === 'line') {
        out.textContent += m.text + '\n'; out.scrollTop = out.scrollHeight;
      } else if (m.type === 'exit') {
        out.textContent += `\n[exit ${m.code}]\n`;
        status.textContent = t('finished') + ' ' + m.code + ')';
        document.querySelectorAll('.sb-cmd').forEach(b => b.classList.remove('running'));
      } else if (m.type === 'error') {
        out.textContent += '[ERROR] ' + m.detail + '\n'; status.textContent = t('errw');
      }
    };
  } else send();
}

/* ================= TERMINALS ================= */
let termCount = 0;
const terms = {};

const WINDOWS_TERMINALS = navigator.userAgent.includes('Windows');
const primaryShell = WINDOWS_TERMINALS ? 'powershell' : 'shell';
const primaryShellButton = $('#term-new-ps');
const wslButton = $('#term-new-wsl');
primaryShellButton.textContent = WINDOWS_TERMINALS ? '+ PowerShell' : '+ Shell';
primaryShellButton.onclick = () => newTerminal(primaryShell);
wslButton.onclick = () => newTerminal('wsl');
if (!WINDOWS_TERMINALS) {
  wslButton.hidden = true;
}

/* --- vibe coding: menu di scelta agente (tmux) --- */
const VIBE_AGENTS = [
  { id: 'claude',   label: 'Claude Code', color: '#D97757', glyph: '✳' },
  { id: 'opencode', label: 'OpenCode',    color: '#1A1A12', glyph: '>_' },
  { id: 'codex',    label: 'Codex',       color: '#000000', glyph: '⬡' },
  { id: 'hermes',   label: 'Hermes',      color: '#8B6F47', glyph: '⚚' },
  { id: 'agy',      label: 'Antigravity', color: '#FF5A00', glyph: '⊼' },
];

$('#term-new-vibe').onclick = (e) => {
  e.stopPropagation();
  const old = $('.vibe-menu');
  if (old) { old.remove(); return; }
  const menu = el('div', 'vibe-menu');
  VIBE_AGENTS.forEach(a => {
    const item = el('button', 'vibe-item',
      `<span class="vibe-badge" style="background:${a.color}">${a.glyph}</span>
       <span>${a.label}</span><span class="vibe-tmux">tmux:vibe-${a.id}</span>`);
    item.onclick = () => {
      menu.remove();
      newTerminal(WINDOWS_TERMINALS ? 'wsl' : 'shell', { agent: a.id, label: a.label });
    };
    menu.appendChild(item);
  });
  const btn = $('#term-new-vibe').getBoundingClientRect();
  menu.style.left = btn.left + 'px';
  menu.style.bottom = (window.innerHeight - btn.top + 6) + 'px';
  document.body.appendChild(menu);
  const closeOnce = (ev) => {
    if (menu.contains(ev.target)) return;  // click su una voce: lascia arrivare il click
    menu.remove();
    window.removeEventListener('mousedown', closeOnce, true);
  };
  setTimeout(() => window.addEventListener('mousedown', closeOnce, true), 0);
};
$('#term-toggle').onclick = () => {
  $('#termpanel').classList.toggle('collapsed');
  $('#term-toggle').textContent = $('#termpanel').classList.contains('collapsed') ? '▴' : '▾';
  fitActiveTerm();
};

/* --- drag resize del pannello terminale --- */
(() => {
  const resizer = $('#term-resizer'), panel = $('#termpanel');
  let dragging = false;
  resizer.addEventListener('mousedown', (e) => {
    dragging = true;
    resizer.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ns-resize';
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const h = Math.min(Math.max(window.innerHeight - e.clientY, 110), window.innerHeight * 0.85);
    panel.style.flex = `0 0 ${h}px`;
    fitActiveTerm();
  });
  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove('dragging');
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    fitActiveTerm();
  });
})();

async function newTerminal(shell, opts = {}) {
  let endpoint;
  try {
    endpoint = await websocketUrl('/ws/term', {
      shell,
      agent: opts.agent,
    });
  } catch (err) {
    toast(err.message, true);
    return;
  }
  $('#termpanel').classList.remove('collapsed');
  const id = 't' + (++termCount);
  const label = opts.agent ? `⚡ ${opts.label || opts.agent}` : `${shell} #${termCount}`;
  const tab = el('div', 'ttab');
  tab.innerHTML = `<span>${label}</span><span class="x">✕</span>`;
  $('#term-tabs').appendChild(tab);
  const pane = el('div', 'tpane');
  pane.innerHTML = '<div style="height:100%"></div>';
  $('#term-panes').appendChild(pane);

  const term = new Terminal({
    fontFamily: '"IBM Plex Mono", "Cascadia Code", monospace', fontSize: 13, cursorBlink: true,
    theme: { background: cssVar('--term-bg'), foreground: cssVar('--term-fg'), cursor: cssVar('--highlight') },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(pane.firstChild);

  const ws = new WebSocket(endpoint);
  ws.onmessage = (ev) => term.write(ev.data);
  ws.onclose = () => term.write('\r\n[connessione chiusa' +
    (opts.agent ? ` — la sessione tmux vibe-${opts.agent} resta viva` : '') + ']\r\n');
  term.onData(d => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: d })); });
  term.onResize(({ cols, rows }) => {
    if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'resize', cols, rows }));
  });
  // copia/incolla: Ctrl+Shift+C copia la selezione, Ctrl+Shift+V incolla
  term.attachCustomKeyEventHandler((ev) => {
    if (ev.type !== 'keydown' || !ev.ctrlKey || !ev.shiftKey) return true;
    if (ev.code === 'KeyC' && term.hasSelection()) {
      navigator.clipboard.writeText(term.getSelection()).then(() => toast('selezione copiata'));
      return false;
    }
    if (ev.code === 'KeyV') {
      navigator.clipboard.readText().then(t => {
        if (t && ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: t }));
      });
      return false;
    }
    return true;
  });

  terms[id] = { term, fit, ws, tab, pane };
  tab.addEventListener('click', (e) => {
    if (e.target.classList.contains('x')) closeTerminal(id); else activateTerminal(id);
  });
  activateTerminal(id);
}

function activateTerminal(id) {
  Object.values(terms).forEach(t => { t.tab.classList.remove('active'); t.pane.classList.remove('active'); });
  const t = terms[id];
  if (!t) return;
  t.tab.classList.add('active'); t.pane.classList.add('active');
  requestAnimationFrame(() => { t.fit.fit(); t.term.focus(); });
}

function closeTerminal(id) {
  const t = terms[id];
  if (!t) return;
  try { t.ws.close(); } catch (e) { /* già chiusa */ }
  t.term.dispose(); t.tab.remove(); t.pane.remove();
  delete terms[id];
  const left = Object.keys(terms);
  if (left.length) activateTerminal(left[left.length - 1]);
}

function fitActiveTerm() {
  Object.values(terms).forEach(t => { if (t.pane.classList.contains('active')) t.fit.fit(); });
}
window.addEventListener('resize', fitActiveTerm);

/* ================= BROWSER AGENTICO ================= */
function openBrowser(url) {
  openTab('panel:browser', '🌐 Browser', (pane) => {
    pane.innerHTML = `<div class="browser-host">
      <form class="browser-bar" id="browser-bar">
        <button type="button" class="btn" id="br-back" title="${t('brback')}">←</button>
        <input id="br-url" placeholder="${t('brurl_ph')}" value="${url || ''}">
        <button class="btn primary" type="submit">${t('go')}</button>
      </form>
      <div class="browser-view" id="br-view"><div class="panel-note">${t('loading')}</div></div>
    </div>`;
    const hist = [];
    const go = async (u) => {
      const view = $('#br-view');
      view.innerHTML = `<div class="panel-note">${t('loading')} ${escHtml(u)}</div>`;
      try {
        const d = await getJSON('/api/browse?url=' + encodeURIComponent(u));
        $('#br-url').value = d.url;
        hist.push(d.url);
        const links = (d.links || []).map(l =>
          `<a href="#" data-href="${escHtml(l.href)}" class="br-link">${escHtml(l.text)}</a>`).join('');
        view.innerHTML = `<h2 class="br-title">${escHtml(d.title)}</h2>
          <div class="br-src">${escHtml(d.url)}</div>
          <pre class="br-text">${escHtml(d.text)}</pre>
          ${links ? '<div class="br-links"><b>' + t('links_l') + '</b>' + links + '</div>' : ''}`;
        view.querySelectorAll('.br-link').forEach(a =>
          a.onclick = (e) => { e.preventDefault(); go(a.dataset.href); });
        view.scrollTop = 0;
      } catch (err) {
        view.innerHTML = '<div class="banner">errore: ' + escHtml(err.message) + '</div>';
      }
    };
    $('#browser-bar').onsubmit = (e) => { e.preventDefault(); go($('#br-url').value.trim()); };
    $('#br-back').onclick = () => { hist.pop(); const p = hist.pop(); if (p) go(p); };
    if (url) go(url);
  });
  activateTab('panel:browser');
}

/* ================= GRAPH 3D ================= */
function openGraph3D() {
  openTab('panel:graph3d', '❂ Grafo 3D', (pane) => {
    pane.innerHTML = '<iframe src="/static/graph3d.html" style="width:100%;height:100%;border:none;display:block"></iframe>';
  });
  activateTab('panel:graph3d');
}

/* ================= CHAT AGENT ================= */
let chatWs = null;

function openChat() {
  openTab('panel:chat', '✦ Chat', (pane) => {
    pane.innerHTML = `<div class="chat-host">
      <div class="chat-msgs" id="chat-msgs">
        <div class="chat-msg bot">${t('chat_intro')}</div>
      </div>
      <form class="chat-form" id="chat-form">
        <input id="chat-input" autocomplete="off" placeholder="${t('chat_ph')}">
        <button class="btn primary" type="submit">▶</button>
      </form></div>`;
    $('#chat-form').onsubmit = (e) => { e.preventDefault(); sendChat(); };
  });
  activateTab('panel:chat');
}

/* template strutturati per i risultati dei tool (card animate) */
function chatTemplates(data) {
  let html = '';
  const tm = data.get_today_matches;
  if (tm && tm.matches && tm.matches.length) {
    html += '<div class="chat-cards">' + tm.matches.slice(0, 10).map(m =>
      `<div class="chat-card"><span class="cc-main">🎾 ${escHtml(m.match)}</span>
       <span class="cc-badge">${escHtml(m.best_quota_p1)} / ${escHtml(m.best_quota_p2)}</span></div>`).join('') + '</div>';
  }
  const sg = data.get_signals;
  if (Array.isArray(sg) && sg.length) {
    html += '<div class="chat-cards">' + sg.slice(0, 8).map(s =>
      `<div class="chat-card"><span class="cc-main">${escHtml(s.match)}</span>
       <span class="cc-badge ${s.edge > 0 ? 'pos' : 'neg'}">edge ${(s.edge * 100).toFixed(1)}%</span></div>`).join('') + '</div>';
  }
  const mm = data.get_model_metrics;
  if (mm && mm.current) {
    const c = mm.current;
    html += `<div class="chat-kpis">
      <div class="chat-kpi"><div class="k">Accuracy</div><div class="v">${(c.accuracy * 100).toFixed(1)}%</div></div>
      <div class="chat-kpi"><div class="k">Log loss</div><div class="v">${c.log_loss.toFixed(3)}</div></div>
      <div class="chat-kpi"><div class="k">ROC AUC</div><div class="v">${c.roc_auc.toFixed(3)}</div></div></div>`;
  }
  const bk = data.get_bankroll;
  if (bk && (bk.bankroll !== undefined)) {
    html += `<div class="chat-kpis">
      <div class="chat-kpi"><div class="k">Bankroll</div><div class="v">${bk.bankroll !== null ? '€' + Number(bk.bankroll).toFixed(0) : '—'}</div></div>
      <div class="chat-kpi"><div class="k">Profit</div><div class="v">€${Number(bk.total_profit || 0).toFixed(1)}</div></div>
      <div class="chat-kpi"><div class="k">Pending</div><div class="v">${escHtml(bk.bets_open)}</div></div>
      <div class="chat-kpi"><div class="k">Decisioni</div><div class="v">${escHtml(bk.decisions)}</div></div></div>`;
  }
  return html;
}

function chatMsg(cls, text, data) {
  const m = el('div', 'chat-msg ' + cls);
  if (cls === 'wait') {
    m.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  } else if (cls === 'bot') {
    // markdown leggero e sicuro + template card dai dati dei tool
    m.innerHTML = escHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      + (data ? chatTemplates(data) : '');
  } else {
    m.textContent = text;
  }
  $('#chat-msgs').appendChild(m);
  $('#chat-msgs').scrollTop = $('#chat-msgs').scrollHeight;
  return m;
}

async function ensureChatWs() {
  if (chatWs && chatWs.readyState === 1) return Promise.resolve();
  const endpoint = await websocketUrl('/ws/chat');
  return new Promise((resolve, reject) => {
    chatWs = new WebSocket(endpoint);
    chatWs.onopen = resolve;
    chatWs.onerror = () => reject(new Error('connessione chat fallita'));
    let pending = null;
    chatWs.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'tool') {
        if (m.status === 'start') pending = chatMsg('tool', `⚙ ${m.name} in esecuzione…`);
        else if (pending) { pending.textContent = `⚙ ${m.name} ✓`; pending = null; }
      } else if (m.type === 'reply') {
        document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
        chatMsg('bot', m.text, m.data);
      } else if (m.type === 'refresh') {
        toast('dati aggiornati dallo scan — riapri i pannelli per vederli');
        delete loadedPanels['panel:overview'];
      } else if (m.type === 'error') {
        document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
        chatMsg('err', 'Errore: ' + m.detail +
          (String(m.detail).includes('11434') ? ' — Ollama è acceso? (ollama serve)' : ''));
      }
    };
    chatWs.onclose = () => { chatWs = null; };
  });
}

async function sendChat() {
  const inp = $('#chat-input');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  chatMsg('me', text);
  chatMsg('wait', '…');
  try {
    await ensureChatWs();
    chatWs.send(JSON.stringify({ text }));
  } catch (err) {
    document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
    chatMsg('err', err.message);
  }
}
const loadedPanels = {};

/* ================= TOAST ================= */
function toast(msg, isErr = false) {
  const t = textEl('div', 'toast' + (isErr ? ' err' : ''), msg);
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3500);
}

/* ================= SCREENSHOT (click rotella + selezione) ================= */
let shotActive = false;

window.addEventListener('mousedown', (e) => {
  if (e.button !== 1 || shotActive) return;   // 1 = rotella
  e.preventDefault(); e.stopPropagation();
  startShot(e.clientX, e.clientY);
}, true);
window.addEventListener('auxclick', (e) => { if (e.button === 1) e.preventDefault(); }, true);

function startShot(sx, sy) {
  shotActive = true;
  const ov = el('div', 'shot-overlay');
  const rect = el('div', 'shot-rect');
  const hint = el('div', 'shot-hint', 'trascina per selezionare · Esc annulla');
  ov.appendChild(rect); ov.appendChild(hint);
  document.body.appendChild(ov);
  let cur = { x: sx, y: sy, w: 0, h: 0 };

  const update = (ex, ey) => {
    cur = { x: Math.min(sx, ex), y: Math.min(sy, ey), w: Math.abs(ex - sx), h: Math.abs(ey - sy) };
    rect.style.left = cur.x + 'px'; rect.style.top = cur.y + 'px';
    rect.style.width = cur.w + 'px'; rect.style.height = cur.h + 'px';
  };
  update(sx, sy);

  const onMove = (e) => update(e.clientX, e.clientY);
  const onUp = () => { cleanup(); captureShot(cur); };
  const onKey = (e) => { if (e.key === 'Escape') { cleanup(); shotActive = false; } };
  function cleanup() {
    window.removeEventListener('mousemove', onMove, true);
    window.removeEventListener('mouseup', onUp, true);
    window.removeEventListener('keydown', onKey, true);
    ov.remove();
  }
  window.addEventListener('mousemove', onMove, true);
  window.addEventListener('mouseup', onUp, true);
  window.addEventListener('keydown', onKey, true);
}

async function captureShot(r) {
  if (r.w < 3 || r.h < 3) { shotActive = false; return; }
  // wait two frames so the overlay is really gone before the screen grab
  await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));
  await new Promise(res => setTimeout(res, 80));
  try {
    const resp = await fetch('/api/screenshot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ x: r.x, y: r.y, w: r.w, h: r.h, dpr: window.devicePixelRatio }),
    });
    const d = await resp.json();
    if (!resp.ok) throw new Error(d.detail || d.error);
    toast(`screenshot ${d.clipboard ? 'copiato negli appunti' : 'salvato'} · ${d.path}`);
  } catch (err) {
    toast('screenshot fallito: ' + err.message, true);
  } finally {
    shotActive = false;
  }
}

/* ================= I18N APPLY ================= */
function applyLang(lang) {
  LANG = lang;
  localStorage.setItem('mc-lang', lang);
  document.documentElement.lang = lang;
  // tooltip activity bar
  document.querySelectorAll('#activitybar button[data-act]').forEach(b => {
    const k = 'act_' + (b.dataset.act === 'chat' ? 'os' : b.dataset.act);
    if (I18N[lang][k]) b.title = I18N[lang][k];
  });
  // etichette statiche del termbar
  const tl = $('#tp-label'); if (tl) tl.textContent = t('term_label');
  const th = $('#tp-hint'); if (th) th.textContent = t('vibe_hint');
  // ri-renderizza sidebar attiva
  renderSidebar(currentAct);
  // ri-renderizza i pannelli-cockpit aperti (titoli + contenuti localizzati)
  Object.keys(tabs).filter(id => id.startsWith('panel:')).forEach(id => {
    const name = id.split(':')[1];
    if (PANELS[name]) { const wasActive = activeTab === id; closeTab(id); openPanel(name); if (!wasActive) {} }
  });
}

/* ================= IN-APP UPDATER ================= */
async function checkUpdate(manual = false) {
  let d;
  try { d = await getJSON('/api/update/check'); }
  catch (e) { if (manual) toast('update check failed: ' + e.message, true); return; }
  if (!d.available) { if (manual) toast(t('upd_done').includes('✓') ? 'up to date ✓' : 'up to date'); return; }
  showUpdateModal(d);
}

function showUpdateModal(d) {
  if ($('.upd-overlay')) return;
  const ov = el('div', 'upd-overlay');
  const meta = d.mode === 'git'
    ? `${escHtml(d.current)} → <b>${escHtml(d.latest)}</b> · +${escHtml(d.behind)} commit${d.behind > 1 ? 's' : ''} · ${escHtml(dt(d.latest_date))}`
    : `v${escHtml(d.current)} → <b>${escHtml(d.latest)}</b> · ${escHtml(dt(d.latest_date))}`;
  ov.innerHTML = `<div class="upd-card">
    <h3>↻ ${t('upd_title')}</h3>
    <div class="upd-meta">${meta}</div>
    <div class="upd-notes">${escHtml(d.notes || '')}</div>
    <div class="upd-status" id="upd-status"></div>
    <div class="upd-actions">
      <button class="btn" id="upd-later">${t('upd_later')}</button>
      <button class="btn primary" id="upd-go">${t('upd_btn')}</button>
    </div></div>`;
  document.body.appendChild(ov);
  $('#upd-later').onclick = () => ov.remove();
  $('#upd-go').onclick = async () => {
    const st = $('#upd-status'); st.textContent = t('upd_doing');
    $('#upd-go').disabled = true;
    try {
      const r = await fetch('/api/update/apply', { method: 'POST' });
      const res = await r.json();
      if (!r.ok || !res.ok) throw new Error(res.detail || res.output || 'error');
      st.textContent = t('upd_done');
      $('#upd-go').textContent = t('upd_restart');
      $('#upd-go').disabled = false;
      $('#upd-go').onclick = () => location.reload();
    } catch (err) {
      st.textContent = t('upd_fail') + ': ' + err.message;
      $('#upd-go').disabled = false;
    }
  };
}

/* ================= BOOT ================= */
const themeSel = $('#theme-sel');
themeSel.innerHTML = THEMES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
themeSel.onchange = () => applyTheme(themeSel.value);
const savedTheme = localStorage.getItem('mc-theme') || 'hermes';
themeSel.value = savedTheme;
document.documentElement.dataset.theme = savedTheme;
refreshThemeColors();

const langSel = $('#lang-sel');
langSel.innerHTML = LANGS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
langSel.value = LANG;
langSel.onchange = () => applyLang(langSel.value);
document.documentElement.lang = LANG;

document.querySelectorAll('#activitybar button[data-act]').forEach(b => {
  const k = 'act_' + (b.dataset.act === 'chat' ? 'os' : b.dataset.act);
  if (I18N[LANG][k]) b.title = I18N[LANG][k];
});
{ const tl = $('#tp-label'); if (tl) tl.textContent = t('term_label');
  const th = $('#tp-hint'); if (th) th.textContent = t('vibe_hint'); }

renderSidebar('cockpit');
openPanel('overview');
setTimeout(() => checkUpdate(), 2500);   // check for a new release shortly after boot
