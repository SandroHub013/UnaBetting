# Scoped free-model dev loop. A weak/free OpenRouter model with ONE tight purpose
# (tests, docs, or i18n) — narrow scope keeps a weak model useful, not trivia.
# Runs opencode headless in a CLEAN CLONE of the PUBLIC repo, opens one PR per run.
# Low-risk scopes (docs/i18n/test only) are auto-merged by auto_merge_safe.ps1 (no Opus).
#
# Register example:
#   ... -File "G:\tennis betting\scripts\loops\run_dev_scoped.ps1"
#       -Model "openrouter/nex-agi/nex-n2-pro:free" -Scope "dev_scope_i18n.md"
#       -DevDir "C:\Users\Utente\unabetting-dev-i18n"
param(
    [Parameter(Mandatory)][string]$Model,
    [Parameter(Mandatory)][string]$Scope,   # prompt file in scripts/loops/
    [Parameter(Mandatory)][string]$DevDir
)
$ErrorActionPreference = 'Continue'

$opencode = $env:OPENCODE_BIN
if (-not $opencode) { $c = Get-Command opencode.cmd -ErrorAction SilentlyContinue; if ($c) { $opencode = $c.Source } }
if (-not $opencode) { $opencode = 'opencode' }

if (-not $env:OPENROUTER_API_KEY) { $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User') }
if (-not $env:OPENROUTER_API_KEY) { Write-Error 'OPENROUTER_API_KEY not set'; exit 1 }

if (-not (Test-Path $DevDir)) { git clone https://github.com/SandroHub013/UnaBetting.git $DevDir }
Set-Location $DevDir
git fetch origin --quiet
git switch --quiet main 2>$null
git reset --hard --quiet origin/main

$logDir = Join-Path $DevDir 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$tag = [IO.Path]::GetFileNameWithoutExtension($Scope)
$log = Join-Path $logDir ("$($tag)_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

$prompt = "Read and execute the instructions in scripts/loops/$Scope. Work fully " +
          "autonomously, ask no questions, stay STRICTLY inside your scope, open exactly " +
          "ONE pull request, and NEVER push to main or merge. Follow CONTRIBUTING.md."

& $opencode run --model $Model $prompt 2>&1 | Tee-Object -FilePath $log

Get-ChildItem $logDir -Filter "$($tag)_*.log" -EA SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
