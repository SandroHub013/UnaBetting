# Runner headless per i loop autoevolutivi del progetto tennis-betting.
# Invocato da Windows Task Scheduler:
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_loop.ps1 -Loop nightly_maintenance
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_loop.ps1 -Loop weekly_evolution
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('nightly_maintenance', 'weekly_evolution')]
    [string]$Loop
)

$repo = 'G:\tennis betting'
$claude = 'C:\Users\Utente\AppData\Roaming\npm\claude.cmd'
$logDir = Join-Path $repo 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "$($Loop)_$stamp.log"
$errLog = Join-Path $logDir "$($Loop)_$stamp.err.log"

$prompt = "Leggi ed esegui le istruzioni in scripts/loops/$Loop.md. Lavora in autonomia senza fare domande."

$proc = Start-Process -FilePath $claude `
    -ArgumentList @('-p', "`"$prompt`"", '--permission-mode', 'bypassPermissions') `
    -WorkingDirectory $repo `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog `
    -NoNewWindow -Wait -PassThru

# pulizia log più vecchi di 30 giorni
Get-ChildItem $logDir -Filter '*.log' |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

exit $proc.ExitCode
