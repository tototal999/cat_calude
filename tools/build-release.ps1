param(
    [ValidatePattern('^\d+\.\d+\.\d+(?:\.\d+)?$')]
    [string]$Version = '7.0.0'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python311 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
$python = if (Test-Path -LiteralPath $python311 -PathType Leaf) { $python311 } else { 'python' }
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDirectory = Join-Path $projectRoot 'build\release-logs'
$logFile = Join-Path $logDirectory "ClaudeCat-$timestamp.log"
$manifestFile = Join-Path $projectRoot 'dist\ClaudeCat_release-manifest.json'
$payloadDirectory = Join-Path $projectRoot 'dist\ClaudeCat'
$executable = Join-Path $payloadDirectory 'ClaudeCat.exe'
$checkDirectory = Join-Path $projectRoot "build\release-check-$timestamp"
$generatedSources = @(
    (Join-Path $projectRoot 'config\_baked_policy.py'),
    (Join-Path $projectRoot 'config\_baked_deployment.py')
)

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$transcriptStarted = $false
$failure = $null
$verification = @()

try {
    Start-Transcript -LiteralPath $logFile -Force | Out-Null
    $transcriptStarted = $true
    Write-Host "Release build started: $timestamp"
    Write-Host "Version: $Version"
    Write-Host "Python: $python"

    if (Test-Path -LiteralPath $manifestFile) {
        Remove-Item -LiteralPath $manifestFile -Force
        Write-Host 'Removed stale release manifest.'
    }

    $runningClaudeCat = @(Get-Process ClaudeCat -ErrorAction SilentlyContinue)
    if ($runningClaudeCat) {
        $runningIds = ($runningClaudeCat.Id -join ', ')
        throw "ClaudeCat is already running (PID: $runningIds). Close it before a release build."
    }

    Write-Host 'Step 1/8: Python business-logic tests'
    & $python -m unittest test_logic.py
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE." }
    $verification += 'python-tests'

    Write-Host 'Step 2/8: Frontend JavaScript syntax'
    & node --check frontend\chat.js
    if ($LASTEXITCODE -ne 0) { throw "JavaScript check failed with exit code $LASTEXITCODE." }
    $verification += 'frontend-js'

    Write-Host 'Step 3/8: PyInstaller onedir build'
    & $python -m PyInstaller ClaudeCat.spec --clean -y
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Packaged executable was not created: $executable"
    }
    $verification += 'pyinstaller-onedir'

    Write-Host 'Step 4/8: Packaged company deployment check'
    New-Item -ItemType Directory -Path $checkDirectory -Force | Out-Null
    $originalLocalAppData = $env:LOCALAPPDATA
    try {
        $env:LOCALAPPDATA = $checkDirectory
        & $executable --deployment-check
        if ($LASTEXITCODE -ne 0) { throw "Deployment check failed with exit code $LASTEXITCODE." }
    } finally {
        $env:LOCALAPPDATA = $originalLocalAppData
    }
    $verification += 'company-deployment'

    Write-Host 'Step 5/8: Packaged document formats'
    & $python verify_packaged_documents.py $executable
    if ($LASTEXITCODE -ne 0) { throw "Document verification failed with exit code $LASTEXITCODE." }
    $verification += 'pdf-docx-pptx-xlsx'

    Write-Host 'Step 6/8: Packaged document workflow'
    & $python verify_packaged_workflow.py $executable
    if ($LASTEXITCODE -ne 0) { throw "Workflow verification failed with exit code $LASTEXITCODE." }
    $verification += 'document-workflow'

    Write-Host 'Step 7/8: Release-content policy'
    $forbidden = @(Get-ChildItem -LiteralPath $payloadDirectory -File -Recurse | Where-Object {
        $_.Name -match '^(feature-policy|company-defaults)\.json$' -or
        $_.Name -match 'feature[_-]policy[_-]editor|open-feature-policy-editor'
    })
    if ($forbidden) {
        throw "Management or source-policy files leaked into dist: $($forbidden.FullName -join ', ')"
    }
    $verification += 'release-content'

    Write-Host 'Step 8/8: Packaged GUI startup smoke'
    $guiProcess = $null
    $originalLocalAppData = $env:LOCALAPPDATA
    try {
        $env:LOCALAPPDATA = $checkDirectory
        $guiProcess = Start-Process -FilePath $executable -WorkingDirectory $payloadDirectory -PassThru
        Start-Sleep -Seconds 8
        $guiProcess.Refresh()
        if ($guiProcess.HasExited) {
            throw "Packaged GUI exited early with code $($guiProcess.ExitCode)."
        }
        $verification += 'gui-smoke'
    } finally {
        $env:LOCALAPPDATA = $originalLocalAppData
        if ($null -ne $guiProcess -and -not $guiProcess.HasExited) {
            Stop-Process -Id $guiProcess.Id -Force
            Wait-Process -Id $guiProcess.Id -ErrorAction SilentlyContinue
        }
        foreach ($spawnedProcess in @(Get-Process ClaudeCat -ErrorAction SilentlyContinue)) {
            Stop-Process -Id $spawnedProcess.Id -Force
            Wait-Process -Id $spawnedProcess.Id -ErrorAction SilentlyContinue
        }
    }
    Write-Host 'Release verification passed.'
} catch {
    $failure = $_
    Write-Host "Release build failed: $($_.Exception.Message)"
} finally {
    foreach ($generatedSource in $generatedSources) {
        if (Test-Path -LiteralPath $generatedSource -PathType Leaf) {
            try {
                Remove-Item -LiteralPath $generatedSource -Force
                Write-Host "Removed generated source: $generatedSource"
            } catch {
                if ($null -eq $failure) { $failure = $_ }
                Write-Host "Failed to remove generated source: $generatedSource"
            }
        }
    }
    if (Test-Path -LiteralPath $checkDirectory) {
        try {
            Remove-Item -LiteralPath $checkDirectory -Recurse -Force
        } catch {
            if ($null -eq $failure) { $failure = $_ }
            Write-Host "Failed to remove release-check directory: $checkDirectory"
        }
    }
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
}

if ($null -ne $failure) { throw $failure }

$policyPath = Join-Path $projectRoot 'feature-policy.json'
$deploymentPath = Join-Path $projectRoot 'company-defaults.json'
$policyDocument = Get-Content -LiteralPath $policyPath -Raw -Encoding utf8 | ConvertFrom-Json
$deploymentDocument = Get-Content -LiteralPath $deploymentPath -Raw -Encoding utf8 | ConvertFrom-Json
$disabledFeatures = @($policyDocument.features.PSObject.Properties |
    Where-Object { $_.Value -eq $false } | ForEach-Object { $_.Name })
$models = @([string]$deploymentDocument.llm.model) +
    @($deploymentDocument.llm.fallback_models | ForEach-Object { [string]$_ })
$models = @($models | Where-Object { $_ } | Select-Object -Unique)
$payloadFiles = @(Get-ChildItem -LiteralPath $payloadDirectory -File -Recurse)
$gitCommit = (& git rev-parse HEAD).Trim()
$gitDirty = [bool]@(& git status --porcelain)

$manifest = [ordered]@{
    product = 'ClaudeCat'
    version = $Version
    built_at = (Get-Date).ToUniversalTime().ToString('o')
    git_commit = $gitCommit
    git_dirty = $gitDirty
    feature_policy_sha256 = (Get-FileHash -LiteralPath $policyPath -Algorithm SHA256).Hash.ToLowerInvariant()
    disabled_features = $disabledFeatures
    company_deployment_sha256 = (Get-FileHash -LiteralPath $deploymentPath -Algorithm SHA256).Hash.ToLowerInvariant()
    allowed_model_count = $models.Count
    executable_sha256 = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
    payload_file_count = $payloadFiles.Count
    payload_size_bytes = [long](($payloadFiles | Measure-Object -Property Length -Sum).Sum)
    verification = $verification
    build_log = "build/release-logs/$([IO.Path]::GetFileName($logFile))"
    build_log_sha256 = (Get-FileHash -LiteralPath $logFile -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestFile -Encoding utf8

Write-Host "Release completed: $executable"
Write-Host "Manifest: $manifestFile"
Write-Host "Build log: $logFile"
