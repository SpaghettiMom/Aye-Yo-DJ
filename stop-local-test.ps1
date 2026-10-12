Param(
    [switch]$StopBotProcess
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

$dockerCli = Get-DockerCli
if (-not $dockerCli) {
    Write-Host "Docker CLI not found. Install Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

Write-Host "Stopping Lavalink + yt-cipher..." -ForegroundColor Cyan
& $dockerCli compose stop lavalink yt-cipher

if ($StopBotProcess) {
    $escapedRepo = [Regex]::Escape($repoRoot)
    $botProcs = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match '^python(\.exe)?$' -and
            $_.CommandLine -match 'bot\.py' -and
            $_.CommandLine -match $escapedRepo
        }

    if ($botProcs) {
        foreach ($proc in $botProcs) {
            try {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
                Write-Host "Stopped bot process PID $($proc.ProcessId)" -ForegroundColor Yellow
            } catch {
                Write-Host "Failed to stop PID $($proc.ProcessId): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "No matching bot.py process found for this repo." -ForegroundColor DarkYellow
    }
}

Write-Host "Local test services are stopped." -ForegroundColor Green
Write-Host "If the bot terminal is still open, close it or press Ctrl+C there." -ForegroundColor Yellow
