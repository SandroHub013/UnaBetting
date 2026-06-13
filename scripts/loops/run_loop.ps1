# UnaBetting loop runner — "My job is to write loops." (B. Cherny)
# Ogni loop è un prompt versionato in scripts/loops/<nome>.md eseguito da
# claude headless, col modello adeguato alla difficoltà del task.
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_loop.ps1 -Loop nightly_maintenance
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('nightly_maintenance', 'weekly_evolution', 'results_check',
                 'code_review', 'docs_repo_sync', 'pr_review', 'metrics_publish')]
    [string]$Loop,
    [string]$Model = ''   # override; senza, usa la mappa qui sotto
)

# modello per difficoltà: REVIEW+MERGE = capace (Opus 4.8); SVILUPPO = economico.
$modelMap = @{
    'pr_review'           = 'opus'     # review e merge PR pubbliche (era fable, dismesso), ogni 4h
    'code_review'         = 'opus'     # review profonda di modelli/sistema, ogni 3gg
    'weekly_evolution'    = 'sonnet'   # sviluppo/esperimenti: agente più economico
    'nightly_maintenance' = 'sonnet'   # routine operativa
    'docs_repo_sync'      = 'sonnet'   # docs, traduzioni, sync repo pubblica
    'results_check'       = 'haiku'    # esegui script + riassunto: semplice
    'metrics_publish'     = 'sonnet'   # pubblica metriche su app/sito/README + push pubblico
}
if (-not $Model) { $Model = $modelMap[$Loop] }

$repo = 'G:\tennis betting'
$claude = 'C:\Users\Utente\AppData\Roaming\npm\claude.cmd'
$logDir = Join-Path $repo 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "$($Loop)_$stamp.log"
$errLog = Join-Path $logDir "$($Loop)_$stamp.err.log"

$prompt = "Leggi ed esegui le istruzioni in scripts/loops/$Loop.md. Lavora in autonomia senza fare domande."

$proc = Start-Process -FilePath $claude `
    -ArgumentList @('-p', "`"$prompt`"", '--permission-mode', 'bypassPermissions', '--model', $Model) `
    -WorkingDirectory $repo `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog `
    -NoNewWindow -Wait -PassThru

# pulizia log più vecchi di 30 giorni
Get-ChildItem $logDir -Filter '*.log' |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

exit $proc.ExitCode
