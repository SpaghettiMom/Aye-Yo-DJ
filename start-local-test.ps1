Param(
    [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Get-DockerCli {
    $dockerCommand = Get-Command "docker" -ErrorAction SilentlyContinue
    $candidates = @(
        $dockerCommand.Source,
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:LOCALAPPDATA\Docker\resources\bin\docker.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return $null
}

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example. Update DISCORD_TOKEN before running again." -ForegroundColor Yellow
    } else {
        Write-Host "Missing .env and .env.example. Create .env first." -ForegroundColor Red
    }
    exit 1
}

if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "Missing venv at venv\Scripts\Activate.ps1" -ForegroundColor Red
    Write-Host "Create it with: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

$dockerCli = Get-DockerCli
if (-not $dockerCli) {
    Write-Host "Docker CLI not found. Install Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Lavalink + yt-cipher..." -ForegroundColor Cyan
& $dockerCli compose up -d lavalink yt-cipher

if (-not $SkipPipInstall) {
    Write-Host "Installing/updating Python dependencies in venv..." -ForegroundColor Cyan
    & ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
}

$escapedRepo = $repoRoot.Replace("'", "''")
$escapedDockerCli = $dockerCli.Replace("'", "''")

$botCommand = @"
Set-Location '$escapedRepo'
& '.\venv\Scripts\Activate.ps1'
python bot.py
"@

$logsCommand = @"
Set-Location '$escapedRepo'
& '$escapedDockerCli' compose logs -f lavalink yt-cipher
"@

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $botCommand | Out-Null
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $logsCommand | Out-Null

Write-Host "Launched two terminals:" -ForegroundColor Green
Write-Host "  1) Bot terminal (venv + python bot.py)"
Write-Host "  2) Docker logs terminal (lavalink + yt-cipher)"
Write-Host ""
Write-Host "To stop later:" -ForegroundColor Yellow
Write-Host "  - Stop bot terminal with Ctrl+C"
Write-Host "  - Run: .\stop-local-test.ps1"
Write-Host "  - Or force-stop matching local bot process too: .\stop-local-test.ps1 -StopBotProcess"
