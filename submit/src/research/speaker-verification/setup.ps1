param(
    [Parameter(Mandatory = $true)][string]$Python,
    [switch]$SmokeAssets
)
$ErrorActionPreference = 'Stop'
$researchRoot = $PSScriptRoot
$setupRun = Join-Path $researchRoot ('runs\setup-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $setupRun -Force | Out-Null
$version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3.12') { throw 'This tested environment requires Python 3.12; pass its executable with -Python.' }
$environmentPython = Join-Path $researchRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $environmentPython)) {
    & $Python -m venv (Join-Path $researchRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
# 依赖缓存和临时文件仅使用本研究目录，不改变全局设置。
$cacheRoot = Join-Path $researchRoot '.cache'
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
$savedEnvironment = @{}
foreach ($key in @('PIP_CACHE_DIR', 'PIP_CONFIG_FILE', 'TEMP', 'TMP')) {
    $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
try {
    $env:PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
    $env:PIP_CONFIG_FILE = 'NUL'
    $env:TEMP = $cacheRoot
    $env:TMP = $cacheRoot
    & $environmentPython -m pip install --disable-pip-version-check --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu -r (Join-Path $researchRoot 'requirements-lock.txt') *> (Join-Path $setupRun 'install.log')
    if ($LASTEXITCODE -ne 0) { throw "Dependency install failed; inspect $setupRun\install.log" }
    $modelArgs = @('-X', 'utf8', (Join-Path $researchRoot 'setup_models.py'))
    if ($SmokeAssets) { $modelArgs += '--smoke-assets' }
    & $environmentPython @modelArgs *> (Join-Path $setupRun 'model.log')
    if ($LASTEXITCODE -ne 0) { throw "Model setup failed; inspect $setupRun\model.log" }
    & $environmentPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
    Write-Output "Ready. Evidence: $setupRun"
} finally {
    foreach ($key in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process')
    }
}
