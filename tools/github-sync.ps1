<#
.SYNOPSIS
    MetaWingman: push local -> Gitee -> GitHub, then verify that the
    published branch SHAs match local.

.DESCRIPTION
    Primary route: direct `git push origin` through the local proxy
    (git config http.https://github.com/.proxy http://127.0.0.1:7892).
    Fallback route: when github.com is unreachable even via proxy, push to
    the public Gitee mirror and trigger .github/workflows/sync-gitee.yml
    (GitHub-side pull from Gitee, auth via the GH_SYNC_TOKEN repo secret).
    A 30-minute cron also runs that workflow automatically, so GitHub
    converges even if this script is not used.

.EXAMPLE
    pwsh tools/github-sync.ps1
#>
param(
    [string[]]$Branches = @('main', 'codex/github-beta'),
    [int]$PollTimeoutSeconds = 600
)
$ErrorActionPreference = 'Stop'
# Native stderr (e.g. Gitee's banner, git progress) must not abort the script.
$PSNativeCommandUseErrorActionPreference = $false
$Repo = 'fsy2004/MetaWingman'

function Invoke-Step([string]$Name, [scriptblock]$Body) {
    Write-Host "== $Name" -ForegroundColor Cyan
    # Native stderr (Gitee banner, git progress) must not terminate the step,
    # regardless of PowerShell version semantics.
    $PSNativeCommandUseErrorActionPreference = $false
    $ErrorActionPreference = 'Continue'
    & $Body
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { throw "step failed: $Name (exit $LASTEXITCODE)" }
}

function Verify-Shas([string[]]$Names) {
    $fail = $false
    foreach ($b in $Names) {
        $ghSha = (git rev-parse "origin/$b" 2>$null).Trim()
        $localSha = (git rev-parse $b).Trim()
        $ok = ($ghSha -eq $localSha)
        if (-not $ok) { $fail = $true }
        $color = if ($ok) { 'Green' } else { 'Red' }
        Write-Host ("{0}: github={1} local={2} {3}" -f $b, $ghSha, $localSha, $(if ($ok) { 'OK' } else { 'MISMATCH' })) -ForegroundColor $color
    }
    return -not $fail
}

Invoke-Step 'push to gitee' {
    git push gitee @Branches
}

Write-Host '== push to github (direct via local proxy)' -ForegroundColor Cyan
$ErrorActionPreference = 'Continue'
git push origin @Branches
$directOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if ($directOk) {
    Write-Host '== verify (origin remote-tracking refs)' -ForegroundColor Cyan
    if (Verify-Shas $Branches) {
        Write-Host "synced (direct): $Repo" -ForegroundColor Green
        exit 0
    }
    Write-Warning 'direct push succeeded but SHA mismatch; falling back to bridge'
}

Write-Host 'falling back to Actions sync bridge...' -ForegroundColor Yellow

$before = (gh run list --repo $Repo --workflow sync-gitee.yml --limit 1 --json databaseId 2>$null | ConvertFrom-Json)[0].databaseId

Invoke-Step 'trigger GitHub sync workflow' {
    gh workflow run sync-gitee.yml --repo $Repo
}

Write-Host 'waiting for sync run to complete...'
$deadline = (Get-Date).AddSeconds($PollTimeoutSeconds)
$completed = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    $runs = gh run list --repo $Repo --workflow sync-gitee.yml --limit 1 --json databaseId,status,conclusion 2>$null | ConvertFrom-Json
    $run = $runs[0]
    if (-not $run -or $run.databaseId -le $before) { continue }
    Write-Host ("run={0} status={1} conclusion={2}" -f $run.databaseId, $run.status, $run.conclusion)
    if ($run.status -eq 'completed') { $completed = $true; break }
}
if (-not $completed) { throw 'sync run did not complete within the timeout' }

$ErrorActionPreference = 'Continue'
git fetch origin --quiet
$ErrorActionPreference = 'Stop'
Write-Host '== verify (fetched origin refs)' -ForegroundColor Cyan
if (Verify-Shas $Branches) {
    Write-Host "synced (bridge): $Repo" -ForegroundColor Green
    exit 0
}
Write-Error 'verification failed: GitHub is out of sync with local'
exit 1
