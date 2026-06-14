# Windows hourly dev-contributor loop.
# Runs opencode on the FREE OpenRouter model in a CLEAN CLONE of the PUBLIC repo
# (never the private working tree), opening ONE PR per run per CONTRIBUTING.md.
# The Opus PR-review loop reviews & merges the good ones.
#
# Register (hourly):
#   $a=New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File "<path-to-this-script>\run_dev_loop_win.ps1"'
#   $t=New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 9999)
#   Register-ScheduledTask -TaskName TennisLoopDevContribute -Action $a -Trigger $t -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew)
param(
    [string]$DevDir = '',
    [string]$Model  = 'openrouter/nex-agi/nex-n2-pro:free'
)
$ErrorActionPreference = 'Continue'

if (-not $DevDir) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    $DevDir = (Resolve-Path (Join-Path $scriptRoot '..\..')).Path
}

$opencode = $env:OPENCODE_BIN
if (-not $opencode) {
    $cmd = Get-Command opencode.cmd -ErrorAction SilentlyContinue
    if ($cmd) { $opencode = $cmd.Source }
}
if (-not $opencode) { $opencode = 'opencode' }

if (-not $env:OPENROUTER_API_KEY) {
    $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User')
}
if (-not $env:OPENROUTER_API_KEY) { Write-Error 'OPENROUTER_API_KEY not set'; exit 1 }

if (-not (Test-Path $DevDir)) {
    git clone https://github.com/SandroHub013/UnaBetting.git $DevDir
}
Set-Location $DevDir

# Always start each run from a clean, current public main.
git fetch origin --quiet
git switch --quiet main 2>$null
if ($LASTEXITCODE -ne 0) {
    git switch --quiet --create main origin/main 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Unable to reset to origin/main'; exit 1 }
}
git reset --hard --quiet origin/main
if ($LASTEXITCODE -ne 0) { Write-Error 'Unable to reset to origin/main'; exit 1 }

$logDir = Join-Path $DevDir 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("dev_contribute_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

$prompt = 'Read and execute the instructions in scripts/loops/dev_contribute.md. ' +
          'Work fully autonomously, ask no questions, open exactly ONE pull request, ' +
          'and NEVER push to main or merge. Follow CONTRIBUTING.md literally.'

& $opencode run --model $Model $prompt 2>&1 | Tee-Object -FilePath $log
$opencodeExit = $LASTEXITCODE

Get-ChildItem $logDir -Filter 'dev_contribute_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force

exit $opencodeExit
