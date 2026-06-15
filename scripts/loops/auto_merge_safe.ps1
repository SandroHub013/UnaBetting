# Light auto-merge gate — NO LLM (zero model quota). Merges only the truly low-risk
# free-loop PRs (docs / tests / i18n strings) so they don't burn the Opus review loop.
# Everything else is left untouched for the Opus PRReview loop.
#
# A PR is auto-merged ONLY if ALL hold:
#   - every changed file is "safe": tests/**, docs/**, *.md, *.txt, or a UI JS file
#     under src/dashboard/static/ (i18n) that passes `node --check`
#   - the diff contains no secret/personal-data patterns
#   - `pytest tests/ -q` is green on the PR checkout
# Otherwise: skip (leave for Opus).
param([string]$DevDir = 'C:\Users\Utente\unabetting-dev-i18n')
$ErrorActionPreference = 'Continue'
$repo = 'SandroHub013/UnaBetting'
$SAFE = '^(tests/|docs/)|\.md$|\.txt$'
$JS   = '^src/dashboard/static/.*\.js$'
$SECRET = 'github_pat_|sk-or-|sk-ant-|-----BEGIN|ODDS_API_KEY=|OPENROUTER_API_KEY='

if (-not (Test-Path $DevDir)) { git clone "https://github.com/$repo.git" $DevDir }
Set-Location $DevDir; git fetch origin --quiet

$open = gh pr list --repo $repo --state open --json number,headRefName | ConvertFrom-Json
foreach ($pr in $open) {
    $n = $pr.number
    $files = gh pr view $n --repo $repo --json files | ConvertFrom-Json | ForEach-Object { $_.files.path }
    $jsFiles = @()
    $allSafe = $true
    foreach ($f in $files) {
        if ($f -match $SAFE) { continue }
        elseif ($f -match $JS) { $jsFiles += $f }
        else { $allSafe = $false; break }
    }
    if (-not $allSafe) { "skip #$n (touches non-safe paths) -> Opus"; continue }

    $diff = gh pr diff $n --repo $repo 2>$null
    if ($diff -match $SECRET) { "skip #$n (secret-shaped content)"; continue }

    git fetch origin "$($pr.headRefName)" --quiet 2>$null
    git switch --quiet --detach FETCH_HEAD 2>$null
    $jsOk = $true
    foreach ($j in $jsFiles) { node --check $j 2>$null; if ($LASTEXITCODE -ne 0) { $jsOk = $false } }
    if (-not $jsOk) { "skip #$n (JS syntax error)"; git switch --quiet main 2>$null; continue }

    $env:PYTHONUTF8 = '1'
    python -X utf8 -m pytest tests/ -q 2>&1 | Out-Null
    $green = ($LASTEXITCODE -eq 0)
    git switch --quiet main 2>$null
    if (-not $green) { "skip #$n (pytest red)"; continue }

    gh pr edit $n --repo $repo --add-label 'loop-automerged' 2>$null
    gh pr comment $n --repo $repo --body '✅ auto-merged by the light gate (scope confined to docs/tests/i18n, pytest green, no secrets — no Opus review needed).' 2>$null
    gh pr merge $n --repo $repo --squash --delete-branch 2>$null
    "MERGED #$n (safe scope)"
}
