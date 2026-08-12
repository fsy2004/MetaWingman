[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE '.agents\skills\metawingman')
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillSource = Join-Path $projectRoot 'metawingman'
$toolkitSource = Join-Path $projectRoot 'toolkit'
$skillsRoot = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.agents\skills'))
$target = [IO.Path]::GetFullPath($Destination)

if (-not $target.StartsWith($skillsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must be inside $skillsRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $skillSource 'SKILL.md'))) {
    throw "Skill source is incomplete: $skillSource"
}
if (-not (Test-Path -LiteralPath (Join-Path $toolkitSource 'R'))) {
    throw "Toolkit source is incomplete: $toolkitSource"
}

$staging = Join-Path ([IO.Path]::GetTempPath()) ("metawingman-install-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Copy-Item -LiteralPath $skillSource -Destination $staging -Recurse
    $stagedSkill = Join-Path $staging 'metawingman'
    $stagedToolkit = Join-Path $stagedSkill 'scripts\r\toolkit'
    Copy-Item -LiteralPath $toolkitSource -Destination $stagedToolkit -Recurse

    $validator = Join-Path $env:USERPROFILE '.codex\skills\.system\skill-creator\scripts\quick_validate.py'
    if (Test-Path -LiteralPath $validator) {
        & python $validator $stagedSkill
        if ($LASTEXITCODE -ne 0) { throw 'Skill validation failed' }
    }

    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    Move-Item -LiteralPath $stagedSkill -Destination $target
    Write-Host "MetaWingman installed to $target"
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
