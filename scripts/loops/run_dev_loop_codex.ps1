# Senior dev-contributor loop — Codex on the maintainer's OpenAI subscription (GPT-5.5).
# Runs codex headless in a CLEAN CLONE of the PUBLIC repo (never the private tree),
# opening ONE substantive PR per run per scripts/loops/dev_contribute_pro.md.
# The Opus PR-review loop reviews & merges the good ones.
#
# Register (hourly):
#   $a=New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File "G:\tennis betting\scripts\loops\run_dev_loop_codex.ps1" -DevDir "C:\Users\Utente\unabetting-dev-codex"'
param(
    [string]$DevDir = 'C:\Users\Utente\unabetting-dev-codex',
    [string]$Model  = 'gpt-5.5'
)
$ErrorActionPreference = 'Continue'

$codex = $env:CODEX_BIN
if (-not $codex) { $c = Get-Command codex -ErrorAction SilentlyContinue; if ($c) { $codex = $c.Source } }
if (-not $codex) { $codex = 'C:\Users\Utente\AppData\Roaming\npm\codex.ps1' }

if (-not (Test-Path $DevDir)) {
    git clone https://github.com/SandroHub013/UnaBetting.git $DevDir
}
Set-Location $DevDir

# Each run starts from a clean, current public main.
git fetch origin --quiet
git switch --quiet main 2>$null
git reset --hard --quiet origin/main

$logDir = Join-Path $DevDir 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("dev_codex_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

$prompt = 'Read and execute the instructions in scripts/loops/dev_contribute_pro.md. ' +
          'Work fully autonomously, ask no questions, open exactly ONE substantive pull ' +
          'request, and NEVER push to main or merge. Follow CONTRIBUTING.md literally. ' +
          'Do NOT open a PR that only touches the loop runner scripts or their tests.'

# codex exec = non-interactive; bypass approvals/sandbox so it can run git/gh/pytest
# with network (it works in a disposable clone and its whole job is to open a PR).
& $codex exec --dangerously-bypass-approvals-and-sandbox -c model="$Model" $prompt 2>&1 |
    Tee-Object -FilePath $log

Get-ChildItem $logDir -Filter 'dev_codex_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
