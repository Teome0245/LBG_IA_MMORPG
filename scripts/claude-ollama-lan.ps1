# Lance Claude Code vers Ollama LAN (VM 110, modèle gemma4-claude).
# Usage (PowerShell) : .\scripts\claude-ollama-lan.ps1
# Ou depuis la racine du dépôt : claude

$ErrorActionPreference = "Stop"

$env:ANTHROPIC_BASE_URL = "http://192.168.0.110:11434"
$env:ANTHROPIC_AUTH_TOKEN = "ollama"
$env:ANTHROPIC_API_KEY = ""
$env:ANTHROPIC_MODEL = "gemma4-claude"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "gemma4-claude"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "gemma4-claude"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "gemma4-claude"
$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"

try {
    $ver = Invoke-RestMethod -Uri "$($env:ANTHROPIC_BASE_URL)/api/version" -TimeoutSec 5
    Write-Host "Ollama $($ver.version) sur $($env:ANTHROPIC_BASE_URL)"
} catch {
    Write-Error "Ollama injoignable sur $($env:ANTHROPIC_BASE_URL) : $_"
}

$claude = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
if (-not (Test-Path $claude)) {
    Write-Error "Claude Code introuvable : $claude"
}

& $claude --model gemma4-claude @args
