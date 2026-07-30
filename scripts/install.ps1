param(
    [string]$Python,
    [string]$VaultPath,
    [string]$ManuscriptsRoot,
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
$pluginRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $pluginRoot ".venv"
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not $Python) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = (Get-Command python).Source
    } elseif (Test-Path -LiteralPath $bundledPython) {
        $Python = $bundledPython
    } else {
        throw "Python 3.11+ was not found. Pass -Python with an absolute executable path."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $venvRoot "Scripts\python.exe"))) {
    & $Python -m venv $venvRoot
}

$venvPython = Join-Path $venvRoot "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e (Join-Path $pluginRoot "mcp-server")

if (-not $ConfigPath) {
    $currentConfigPath = Join-Path $env:APPDATA "research-knowledge-workflow\config.toml"
    $legacyConfigPath = Join-Path $env:APPDATA "management-research-kb\config.toml"
    if (Test-Path -LiteralPath $currentConfigPath) {
        $ConfigPath = $currentConfigPath
    } elseif (Test-Path -LiteralPath $legacyConfigPath) {
        $ConfigPath = $legacyConfigPath
    } else {
        $ConfigPath = $currentConfigPath
    }
}

if ($VaultPath -and -not (Test-Path -LiteralPath $ConfigPath)) {
    $configDirectory = Split-Path -Parent $ConfigPath
    New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
    $cacheDirectory = Join-Path $env:LOCALAPPDATA "research-knowledge-workflow"
    $escapedVault = $VaultPath.Replace("\", "\\")
    $escapedCache = $cacheDirectory.Replace("\", "\\")
    $lines = @(
        "vault_path = `"$escapedVault`"",
        "notes_dir = `"知识笔记`"",
        "cache_dir = `"$escapedCache`"",
        "zotero_base_url = `"http://127.0.0.1:23119`"",
        "max_group_documents = 20",
        "max_chars = 120000"
    )
    if ($ManuscriptsRoot) {
        $escapedManuscripts = $ManuscriptsRoot.Replace("\", "\\")
        $lines += "manuscripts_root = `"$escapedManuscripts`""
    }
    Set-Content -LiteralPath $ConfigPath -Value $lines -Encoding UTF8
}

Write-Output "Python environment: $venvPython"
Write-Output "Config path: $ConfigPath"
Write-Output "Set RESEARCH_KNOWLEDGE_WORKFLOW_CONFIG to override the config path."
Write-Output "Legacy MANAGEMENT_RESEARCH_KB_CONFIG remains supported."
