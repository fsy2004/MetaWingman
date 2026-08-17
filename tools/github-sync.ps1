<#
.SYNOPSIS
    MetaWingman: push local -> Gitee -> GitHub via the Actions sync bridge,
    then verify that GitHub branch SHAs match local.

.DESCRIPTION
    Direct pushes to github.com are reset/blocked from this network, while
    gitee.com (SSH) and api.github.com are reachable. The canonical flow:
      1. git push gitee main codex/github-beta
      2. trigger .github/workflows/sync-gitee.yml (GitHub-side pull from the
         public Gitee mirror, auth via the GH_SYNC_TOKEN repo secret)
      3. poll the run until completion
      4. compare GitHub branch SHAs with local
    A 30-minute cron also runs the same workflow automatically, so GitHub
    converges even if this script is not used.

.EXAMPLE
    pwsh tools/github-sync.ps1
#>
param(
    [string[]]$Branches = @('main', 'codex/github-beta'),
    [int]$PollTimeoutSeconds = 600
)
$ErrorActionPreference = 'Stop'
$Repo = 'fsy2004/MetaWingman'

function Invoke-Step([string]$Name, [scriptblock]$Body) {
    Write-Host "== $Name" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0) { throw "step failed: $Name (exit $LASTEXITCODE)" }
}

Invoke-Step 'push to gitee' {
    git push gitee @Branches
}

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

$fail = $false
foreach ($b in $Branches) {
    $ghSha = (gh api "repos/$Repo/branches/$b" --jq '.commit.sha' 2>$null).Trim()
    $localSha = (git rev-parse $b).Trim()
    $ok = ($ghSha -eq $localSha)
    if (-not $ok) { $fail = $true }
    $color = if ($ok) { 'Green' } else { 'Red' }
    Write-Host ("{0}: github={1} local={2} {3}" -f $b, $ghSha, $localSha, $(if ($ok) { 'OK' } else { 'MISMATCH' })) -ForegroundColor $color
}
if ($fail) { Write-Error 'verification failed: GitHub is out of sync with local'; exit 1 }
Write-Host "synced: $Repo" -ForegroundColor Green
