# Weekly loop — docs & public-repo sync

You are UnaBetting's documentation/repo sync run (G:\tennis betting). The public repo is
github.com/SandroHub013/UnaBetting. **English is the project's canonical language.**

## Rules
- Push ONLY via the additive flow: `git fetch unabetting main` → work on top → normal
  commit → `git push unabetting public-main:main` (NO `--force`). NEVER push the private
  history, NEVER the `origin` remote. If a push would require force, STOP and report
  divergence instead of forcing.
- Before EVERY push: `git ls-files` must not contain `betanalytix.db`, `debug_bet365*`,
  `Cattura.PNG`, `.antigravitycli`, `*.mp4`, personal screenshots; and
  `git grep -iE "api[_-]?key.{0,6}[A-Za-z0-9]{16}|github_pat_|sk-or-"` must be empty.
  If you find anything: STOP, do not push, write an alert.
- Budget ~60 minutes.

## Steps
1. **English everywhere**: keep all docs in English (README, CONTRIBUTING, DATA_SOURCES,
   docs/obsidian/*, scripts/loops/*, code comments, commit messages). Translate any
   remaining Italian content incrementally; the Obsidian vault and script comments are
   the main backlog.
2. **Repo graphics**: ensure README has badges, mermaid diagrams (architecture + data
   flow + loops) and current screenshots from `docs/assets/`.
3. **Obsidian/site**: align `docs/obsidian/Index.md` and `docs/web/` with the current
   project state (new features, metrics, loops). Run `python scripts/build_web_graph.py`
   to refresh `docs/web/graph-data.js` from the latest graphify export, so the website's
   live 3D knowledge graph stays in sync with the codebase.
4. **Tests**: `python -m pytest tests/ -q` must be green before the push (excluding known
   failures tracked in EXPERIMENTS.md).
5. **Additive push**: `git fetch unabetting main`; fast-forward `public-main` onto it;
   bring the updated public files from the working branch; commit; push to `unabetting
   main` without force. Return to the working branch.
6. Local commits per block + `chore(loop): docs/repo sync YYYY-MM-DD`.
