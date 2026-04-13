# M3TAL Unified Stack Operator (v2.0 Hardened)
# Enforces Centralized Authority and Shared Network Integrity

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $Root ".env"

# 1. Fail early if .env is missing
if (-not (Test-Path $EnvFile)) {
    Write-Error "❌ ERROR: .env file not found at $EnvFile"
    Write-Host "   M3TAL requires a valid .env at the repository root to load configuration." -ForegroundColor Yellow
    exit 1
}

# 2. Guarantee shared network exists
Write-Host "🌐 Checking shared 'proxy' network..." -ForegroundColor Cyan
$NetworkCheck = docker network ls --filter name=^proxy$ --format "{{.Name}}"
if (-not $NetworkCheck) {
    Write-Host "  📦 Creating 'proxy' network..." -ForegroundColor Yellow
    docker network create proxy
}

# Selective Stack Control
$Stack = $args[0]

if ($null -ne $Stack) {
    Write-Host "🚀 Launching M3TAL Selective Stack: $Stack..." -ForegroundColor Green
    $ComposeFile = Join-Path $Root "docker\$Stack\docker-compose.yml"
    
    if (Test-Path $ComposeFile) {
        docker compose --env-file "$EnvFile" -f "$ComposeFile" up -d
    } else {
        Write-Error "❌ Error: Stack '$Stack' not found at $ComposeFile"
        exit 1
    }
} else {
    Write-Host "🚀 Launching ALL M3TAL Stacks (Production Authority)..." -ForegroundColor Green
    
    # We use multiple -f flags to ensure a single compose context (Audit Rec)
    docker compose --env-file "$EnvFile" `
        -f "$Root\docker\routing\docker-compose.yml" `
        -f "$Root\docker\media\docker-compose.yml" `
        -f "$Root\docker\maintenance\docker-compose.yml" `
        up -d
}

Write-Host "✅ Deployment processed." -ForegroundColor Green
