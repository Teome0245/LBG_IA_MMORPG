# Lance Claude Code vers Ollama local (sur le PC Windows).
# Usage (PowerShell) :
#   .\scripts\claude-ollama-local.ps1
#   $env:LBG_CLAUDE_OLLAMA_MODEL="gemma4:e2b"; .\scripts\claude-ollama-local.ps1
#
# Prérequis : Ollama tourne en local sur http://127.0.0.1:11434

$ErrorActionPreference = "Stop"

$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"

# Réutilise le script LAN (qui supporte désormais OLLAMA_BASE_URL + override modèle)
& "$PSScriptRoot\claude-ollama-lan.ps1" @args

