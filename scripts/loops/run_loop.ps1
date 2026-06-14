# UnaBetting loop runner — "My job is to write loops." (B. Cherny)
# Each loop is a versioned prompt in scripts/loops/<name>.md, executed by
# claude headless with the model that matches the task difficulty.
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_loop.ps1 -Loop nightly_maintenance
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('nightly_maintenance', 'weekly_evolution', 'results_check',
                 'code_review', 'docs_repo_sync', 'pr_review', 'metrics_publish')]
    [string]$Loop,
    [string]$Model = ''   # override; otherwise use the map below
)

# Difficulty map: REVIEW+MERGE = capable (Opus 4.8); DEV = cheaper.
$modelMap = @{
    'pr_review'           = 'opus'     # review and merge public PRs, every 4h
    'code_review'         = 'opus'     # deep model/system review, every 3d
    'weekly_evolution'    = 'sonnet'   # development/experiments: cheaper agent
    'nightly_maintenance' = 'sonnet'   # operational routine
    'docs_repo_sync'      = 'sonnet'   # docs, translations, public repo sync
    'results_check'       = 'haiku'    # run script + summary: simple
    'metrics_publish'     = 'sonnet'   # publish metrics to app/site/README + public push
}
if (-not $Model) { $Model = $modelMap[$Loop] }

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $scriptRoot '..\..')).Path
$claude = $env:CLAUDE_BIN
if (-not $claude) {
    $cmd = Get-Command claude.cmd -ErrorAction SilentlyContinue
    if ($cmd) { $claude = $cmd.Source }
}
if (-not $claude) { $claude = 'claude' }
$logDir = Join-Path $repo 'reports\loops'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $logDir "$($Loop)_$stamp.log"
$errLog = Join-Path $logDir "$($Loop)_$stamp.err.log"

$prompt = "Read and execute the instructions in scripts/loops/$Loop.md. Work fully autonomously without asking questions."

$proc = Start-Process -FilePath $claude `
    -ArgumentList @('-p', "`"$prompt`"", '--permission-mode', 'bypassPermissions', '--model', $Model) `
    -WorkingDirectory $repo `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog `
    -NoNewWindow -Wait -PassThru

# Prune logs older than 30 days
Get-ChildItem $logDir -Filter '*.log' |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

exit $proc.ExitCode
