# Verify destination selection, database initialization, shortcut defaults and data preservation.
# This opt-in test briefly registers an installation and removes it afterward.
# It refuses to run if Training Planner is already installed or its shortcuts exist.
param([string]$Installer = 'dist\TrainingPlanner-Setup-0.1.0.exe')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-Setup {
    param([string]$Executable, [string[]]$Arguments)
    $setupProcess = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait
    if ($setupProcess.ExitCode -ne 0) {
        throw "Setup failed with exit code $($setupProcess.ExitCode)."
    }
}

$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$appId = '{873B0856-64BD-4907-B42F-E0BC84D1F250}_is1'
foreach ($key in @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$appId",
    "HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\$appId"
)) {
    if (Test-Path -LiteralPath $key) {
        throw 'An existing Training Planner installation must not be affected by this test.'
    }
}
$shortcuts = @(
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'Training Planner.lnk'),
    (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Training Planner.lnk')
)
foreach ($shortcut in $shortcuts) {
    if (Test-Path -LiteralPath $shortcut) {
        throw "An existing shortcut must not be affected by this test: $shortcut"
    }
}

$testRoot = Join-Path (Split-Path -Parent $PSScriptRoot) ('build\installer smoke ' + [guid]::NewGuid())
$destination = Join-Path $testRoot 'selected destination'
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$setupArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $destination + '"'))
$uninstaller = Join-Path $destination 'unins000.exe'
$database = Join-Path $destination 'data\training.db'
try {
    Invoke-Setup $installerPath $setupArguments
    if (-not (Test-Path -LiteralPath $database)) { throw 'Setup did not initialize the database.' }
    foreach ($shortcut in $shortcuts) {
        if (Test-Path -LiteralPath $shortcut) { throw 'Setup created an unsolicited shortcut.' }
    }

    $log = Join-Path $testRoot 'server.log'
    $server = Start-Process -FilePath (Join-Path $destination 'TrainingPlanner.exe') -ArgumentList @('--no-browser', '--port', '0') -WorkingDirectory $testRoot -RedirectStandardOutput $log -RedirectStandardError (Join-Path $testRoot 'server-error.log') -WindowStyle Hidden -PassThru
    try {
        $deadline = (Get-Date).AddSeconds(30)
        $url = $null
        do {
            if ((Get-Content -LiteralPath $log -Raw) -match 'Training Planner: (http://127\.0\.0\.1:\d+)') {
                $url = $Matches[1]
                break
            }
            if ($server.HasExited) { throw 'Installed server failed to start.' }
            Start-Sleep -Milliseconds 100
        } while ((Get-Date) -lt $deadline)
        if (-not $url) { throw 'Timed out waiting for the installed server.' }
        Invoke-RestMethod -Uri "$url/api/sessions" -Method Post -ContentType 'application/json' -Body (@{ day = (Get-Date -Format 'yyyy-MM-dd'); activity = 'gym' } | ConvertTo-Json) -TimeoutSec 5 | Out-Null
    } finally {
        if (-not $server.HasExited) { Stop-Process -Id $server.Id }
        $server.WaitForExit()
    }
    $originalHash = (Get-FileHash -LiteralPath $database).Hash
    Invoke-Setup $installerPath $setupArguments
    if ((Get-FileHash -LiteralPath $database).Hash -ne $originalHash) {
        throw 'Reinstallation changed the existing database.'
    }
} finally {
    if (Test-Path -LiteralPath $uninstaller) {
        Invoke-Setup $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    }
}
if (-not (Test-Path -LiteralPath $database)) { throw 'Uninstall removed user data.' }
if ((Get-FileHash -LiteralPath $database).Hash -ne $originalHash) { throw 'Uninstall changed user data.' }
if (Test-Path -LiteralPath (Join-Path $destination 'TrainingPlanner.exe')) { throw 'Uninstall left the executable behind.' }
Write-Host "Installer smoke test passed. Logs and preserved test data: $testRoot"
