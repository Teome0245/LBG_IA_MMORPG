# Lance Claude Code vers Ollama LAN (VM 110) ou Ollama local (PC).
# Usage (PowerShell) :
#   .\scripts\claude-ollama-lan.ps1              # défaut : LAN 192.168.0.110
#   $env:OLLAMA_BASE_URL="http://127.0.0.1:11434"; .\scripts\claude-ollama-lan.ps1   # local PC
#   $env:LBG_CLAUDE_OLLAMA_MODEL="gemma4:e2b"; .\scripts\claude-ollama-lan.ps1       # override modèle

$ErrorActionPreference = "Stop"

$base = $env:OLLAMA_BASE_URL
if ([string]::IsNullOrWhiteSpace($base)) { $base = "http://192.168.0.110:11434" }
$model = $env:LBG_CLAUDE_OLLAMA_MODEL
if ([string]::IsNullOrWhiteSpace($model)) { $model = "gemma4:e2b" }

$env:ANTHROPIC_BASE_URL = $base
$env:ANTHROPIC_AUTH_TOKEN = "ollama"
$env:ANTHROPIC_API_KEY = ""
$env:ANTHROPIC_MODEL = $model
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $model
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $model
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $model
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

& $claude --model $model @args
