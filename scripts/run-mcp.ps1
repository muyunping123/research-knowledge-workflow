$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $pluginRoot ".venv\Scripts\python.exe"
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if ($env:MANAGEMENT_RESEARCH_KB_PYTHON) {
    $python = $env:MANAGEMENT_RESEARCH_KB_PYTHON
} elseif (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = (Get-Command python).Source
} elseif (Test-Path -LiteralPath $bundledPython) {
    $python = $bundledPython
} else {
    [Console]::Error.WriteLine("Python was not found. Run scripts/install.ps1 first.")
    exit 1
}

$sourceRoot = Join-Path $pluginRoot "mcp-server\src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$sourceRoot$([IO.Path]::PathSeparator)$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $sourceRoot
}

& $python -m management_research_kb.server
exit $LASTEXITCODE
