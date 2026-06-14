# Issue-driven dev loop — Gemini 3.1 Pro via the gemini CLI (maintainer's Google account).
# Runs headless in a CLEAN CLONE of the PUBLIC repo (with models+data so it can verify
# live/ML), turns one open issue into one PR per run. Opus reviews & merges.
#
# Register (every 6h, offset from the GPT-5.5 loop):
#   ... -File "G:\tennis betting\scripts\loops\run_dev_loop_gemini.ps1" -DevDir "C:\Users\Utente\unabetting-dev-gemini"
param(
    [string]$DevDir = 'C:\Users\Utente\unabetting-dev-gemini',
    [string]$Model  = 'gemini-3.1-pro'
)
$ErrorActionPreference = 'Continue'

$gemini = $env:GEMINI_BIN
if (-not $gemini) { $c = Get-Command gemini.ps1 -ErrorAction SilentlyContinue; if ($c) { $gemini = $c.Source } }
if (-not $gemini) { $gemini = 'C:\Users\Utente\AppData\Roaming\npm\gemini.ps1' }

if (-not (Test-Path $DevDir)) { git clone https://github.com/SandroHub013/UnaBetting.git $DevDir }
Set-Location $DevDir
git fetch origin --quiet
git switch --quiet main 2>$null
git reset --hard --quiet origin/main

$logDir = Join-Path $DevDir 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("dev_gemini_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

$prompt = 'Read and execute the instructions in scripts/loops/dev_issue.md. Work fully ' +
          'autonomously, ask no questions, turn ONE open unclaimed issue into exactly ONE ' +
          'pull request, and NEVER push to main or merge. Follow CONTRIBUTING.md literally.'

# -y = YOLO (auto-approve all tools) so it can run git/gh/pytest non-interactively.
& $gemini -m $Model -y -p $prompt 2>&1 | Tee-Object -FilePath $log

Get-ChildItem $logDir -Filter 'dev_gemini_*.log' -EA SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
