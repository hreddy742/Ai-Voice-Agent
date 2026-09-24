[CmdletBinding()]
param(
    [switch]$Restart,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Directory]::GetParent($PSScriptRoot).FullName
$logsDirectory = [System.IO.Path]::Combine($projectRoot, "logs")
$postgresContainer = "dograh-test-postgres"

function Write-Status([string]$Message) {
    [Console]::WriteLine($Message)
}

function Get-ListeningProcessIds([int]$Port) {
    $processIds = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($line in (& netstat.exe -ano -p tcp)) {
        if ($line -notmatch "LISTENING") { continue }
        $parts = $line.Trim() -split "\s+"
        if ($parts.Length -lt 5) { continue }
        if ($parts[1] -notmatch ":$Port$") { continue }
        [void]$processIds.Add([int]$parts[-1])
    }
    return $processIds
}

function Test-ListeningPort([int]$Port) {
    return (Get-ListeningProcessIds $Port).Count -gt 0
}

function Stop-PortProcess([int]$Port) {
    foreach ($processId in Get-ListeningProcessIds $Port) {
        $process = [System.Diagnostics.Process]::GetProcessById($processId)
        $process.Kill()
        $process.WaitForExit(10000)
    }
}

function Wait-ForPostgres {
    for ($attempt = 1; $attempt -le 30; $attempt += 1) {
        $null = & docker exec $postgresContainer pg_isready -U postgres
        if ($LASTEXITCODE -eq 0) { return }
        [System.Threading.Thread]::Sleep(1000)
    }
    throw "Postgres container '$postgresContainer' did not become ready."
}

function Ensure-TestDatabase {
    $exists = & docker exec $postgresContainer psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'test_db'"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the local Postgres databases." }
    if ($exists.Trim() -ne "1") {
        $null = & docker exec $postgresContainer createdb -U postgres test_db
        if ($LASTEXITCODE -ne 0) { throw "Could not create the test_db database." }
    }
}

function Start-BackgroundCommand([string]$Name, [string]$ScriptName, [string]$LogName) {
    $scriptPath = [System.IO.Path]::Combine($PSScriptRoot, $ScriptName)
    $logPath = [System.IO.Path]::Combine($logsDirectory, $LogName)
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "cmd.exe"
    $startInfo.Arguments = "/d /c `"`"$scriptPath`" > `"$logPath`" 2>&1`""
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) { throw "Could not start $Name." }
    Write-Status "Started $Name. Log: $logPath"
}

if ($WhatIf) {
    Write-Status "Would ensure Docker services, then start backend on 8001 and frontend on 3022."
    exit 0
}

$null = [System.IO.Directory]::CreateDirectory($logsDirectory)
$null = & docker info
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not running." }

$containerLines = @(& docker ps -a --filter "name=^/$postgresContainer$" --format "{{.Names}}")
$containerExists = [string]::Join("", $containerLines).Trim()
if ($containerExists -ne $postgresContainer) {
    $null = & docker run -d --name $postgresContainer `
        -e POSTGRES_USER=postgres `
        -e POSTGRES_PASSWORD=postgres `
        -e POSTGRES_DB=postgres `
        -p 15432:5432 `
        pgvector/pgvector:pg17
    if ($LASTEXITCODE -ne 0) { throw "Could not create the local Postgres container." }
} else {
    $null = & docker start $postgresContainer
    if ($LASTEXITCODE -ne 0) { throw "Could not start the local Postgres container." }
}
Wait-ForPostgres
Ensure-TestDatabase

$previousDirectory = [Environment]::CurrentDirectory
try {
    [Environment]::CurrentDirectory = $projectRoot
    $null = & docker compose -f docker-compose-local.yaml up -d redis minio
    if ($LASTEXITCODE -ne 0) { throw "Could not start Redis and MinIO." }
} finally {
    [Environment]::CurrentDirectory = $previousDirectory
}

if ($Restart) {
    if (Test-ListeningPort 8001) { Stop-PortProcess 8001 }
    if (Test-ListeningPort 3022) { Stop-PortProcess 3022 }
}

if (-not (Test-ListeningPort 8001)) {
    Start-BackgroundCommand "Porter backend" "start_porter_local.cmd" "porter-backend.log"
} else {
    Write-Status "Porter backend is already listening on port 8001."
}

if (-not (Test-ListeningPort 3022)) {
    Start-BackgroundCommand "Porter frontend" "start_porter_ui.cmd" "porter-frontend.log"
} else {
    Write-Status "Porter frontend is already listening on port 3022."
}

Write-Status "Porter console: http://localhost:3022/porter"
