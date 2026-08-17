[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE '.agents\skills\metawingman'),
    [string]$SkillValidator = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundleBuilder = Join-Path $projectRoot 'scripts\build_skill_bundle.py'
$bundleVerifier = Join-Path $projectRoot 'scripts\verify_skill_bundle.py'
$bundleSource = Join-Path $projectRoot '.agents\skills\metawingman'
$skillsRoot = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.agents\skills'))
$target = [IO.Path]::GetFullPath($Destination)

if (-not $target.StartsWith($skillsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must be inside $skillsRoot"
}
if (-not (Test-Path -LiteralPath $bundleBuilder)) {
    throw "Bundle builder is missing: $bundleBuilder"
}
& python -c "import jsonschema; from jsonschema import Draft202012Validator"
if ($LASTEXITCODE -ne 0) {
    throw 'MetaWingman requires Python package jsonschema>=4 with Draft 2020-12 support. Install it explicitly, then rerun this installer.'
}
& python -X utf8 $bundleBuilder
if ($LASTEXITCODE -ne 0) { throw 'MetaWingman bundle build failed' }
& python -X utf8 $bundleVerifier $bundleSource
if ($LASTEXITCODE -ne 0) { throw 'MetaWingman bundle verification failed' }

$staging = Join-Path ([IO.Path]::GetTempPath()) ("metawingman-install-" + [Guid]::NewGuid().ToString('N'))
$backup = Join-Path ([IO.Path]::GetTempPath()) ("metawingman-backup-" + [Guid]::NewGuid().ToString('N'))
$installed = $false
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Copy-Item -LiteralPath $bundleSource -Destination $staging -Recurse
    $stagedSkill = Join-Path $staging 'metawingman'
    & python -X utf8 $bundleVerifier $stagedSkill
    if ($LASTEXITCODE -ne 0) { throw 'Staged MetaWingman bundle verification failed' }

    $validatorCandidates = @()
    if ($SkillValidator) {
        $validatorCandidates += $SkillValidator
    }
    if ($env:CODEX_HOME) {
        $validatorCandidates += (Join-Path $env:CODEX_HOME 'skills\.system\skill-creator\scripts\quick_validate.py')
    }
    $validatorCandidates += (Join-Path $env:USERPROFILE '.codex\skills\.system\skill-creator\scripts\quick_validate.py')
    $validator = $validatorCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($validator) {
        & python -X utf8 $validator $stagedSkill
        if ($LASTEXITCODE -ne 0) { throw 'Skill validation failed' }
    }
    else {
        Write-Warning 'Codex quick_validate.py was not found; cryptographic bundle validation passed, but skill metadata validation was skipped.'
    }

    if (Test-Path -LiteralPath $target) {
        Move-Item -LiteralPath $target -Destination $backup
    }
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Move-Item -LiteralPath $stagedSkill -Destination $target
        $installed = $true
    }
    catch {
        if (Test-Path -LiteralPath $backup) {
            if (Test-Path -LiteralPath $target) {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
            try {
                Move-Item -LiteralPath $backup -Destination $target
            }
            catch {
                Write-Warning "Automatic rollback failed. The previous installation is preserved at $backup"
            }
        }
        throw
    }
    if ($installed -and (Test-Path -LiteralPath $backup)) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
    Write-Host "MetaWingman installed to $target"
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ($installed -and (Test-Path -LiteralPath $backup)) {
        Write-Warning "Installation succeeded but the previous installation could not be removed: $backup"
    }
}
