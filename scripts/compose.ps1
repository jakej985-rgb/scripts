# M3TAL Unified Stack Operator (PowerShell)
# Enforces environment variable propagation across all compose projects.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Error "❌ Error: .env file not found at $EnvFile"
    exit 1
}

Write-Host "🚀 Launching M3TAL Stacks..." -ForegroundColor Cyan

# Define stacks in order of dependency
$Stacks = @(
    "docker/routing",
    "docker/media",
    "docker/maintenance"
)

foreach ($Stack in $Stacks) {
    $ComposeFile = Join-Path $Root "$Stack\docker-compose.yml"
    if (Test-Path $ComposeFile) {
        Write-Host "  📦 Starting $Stack..." -ForegroundColor Yellow
        docker compose --env-file "$EnvFile" -f "$ComposeFile" up -d
    } else {
        Write-Warning "  ⚠️ Warning: $ComposeFile not found, skipping..."
    }
}

Write-Host "✅ All stacks processed." -ForegroundColor Green
