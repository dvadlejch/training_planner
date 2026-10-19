param(
    [ValidateSet('package', 'installer', 'release')]
    [string]$Target = 'installer',
    [string]$Uv = 'uv'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'Windows packages must be built on Windows.'
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
Push-Location $projectRoot
try {
    # Match the optional local Node installation supported by the Makefile.
    $env:PATH = "$projectRoot\.tools\node;$projectRoot\.tools\node\bin;$env:PATH"
    foreach ($tool in @($Uv, 'node', 'npm.cmd')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "Missing prerequisite: $tool. See README Windows release instructions."
        }
    }

    $compiler = $null
    if ($Target -ne 'package') {
        if ($env:ISCC) {
            $compiler = $env:ISCC
        } elseif (Test-Path -LiteralPath '.tools\inno\ISCC.exe') {
            $compiler = Join-Path $projectRoot '.tools\inno\ISCC.exe'
        } elseif (Get-Command ISCC.exe -ErrorAction SilentlyContinue) {
            $compiler = (Get-Command ISCC.exe).Source
        } else {
            foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA)) {
                $candidate = Join-Path $base 'Inno Setup 6\ISCC.exe'
                if (Test-Path -LiteralPath $candidate) {
                    $compiler = $candidate
                    break
                }
                $candidate = Join-Path $base 'Programs\Inno Setup 6\ISCC.exe'
                if (Test-Path -LiteralPath $candidate) {
                    $compiler = $candidate
                    break
                }
            }
        }
        if (-not $compiler -or -not (Test-Path -LiteralPath $compiler)) {
            throw 'Inno Setup 6 compiler missing. Install it or set ISCC to its ISCC.exe path.'
        }
    }

    # Never let PyInstaller's replacement of an old build erase runtime data.
    if (Test-Path -LiteralPath 'dist\TrainingPlanner\data') {
        throw 'dist\TrainingPlanner contains runtime data. Move that folder before rebuilding.'
    }

    if ($Target -eq 'release') {
        Invoke-Checked $Uv @('sync', '--locked', '--extra', 'dev')
        Invoke-Checked $Uv @('run', '--no-sync', 'ruff', 'check', 'src', 'tests')
        Invoke-Checked $Uv @('run', '--no-sync', 'ruff', 'format', '--check', 'src', 'tests')
        Invoke-Checked $Uv @('run', '--no-sync', 'mypy', 'src', 'tests')
        Invoke-Checked $Uv @('run', '--no-sync', 'pytest', '-q')
    }
    # Use the same runtime/build-only environment for every target. Optional
    # imports must not pull installed development tools into release bundles.
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $projectRoot '.venv-build'
    Invoke-Checked $Uv @('sync', '--locked', '--extra', 'build', '--no-dev')
    Invoke-Checked 'npm.cmd' @('--prefix', 'frontend', 'ci')
    if ($Target -eq 'release') {
        Invoke-Checked 'npm.cmd' @('--prefix', 'frontend', 'test')
        Invoke-Checked 'npm.cmd' @('--prefix', 'frontend', 'run', 'typecheck')
    }
    Invoke-Checked 'npm.cmd' @('--prefix', 'frontend', 'run', 'build')

    New-Item -ItemType Directory -Force -Path 'build', 'dist' | Out-Null
    Invoke-Checked $Uv @(
        'run', '--no-sync', 'pyinstaller', '--noconfirm', '--clean', '--onedir',
        '--name', 'TrainingPlanner', '--distpath', 'dist', '--workpath', 'build\pyinstaller',
        '--specpath', 'build', '--paths', "$projectRoot\src",
        '--icon', "$projectRoot\assets\icons\summit-calendar.ico",
        '--add-data', "$projectRoot\frontend\dist;training_planner/web",
        'src\training_planner\__main__.py'
    )
    Invoke-Checked $Uv @(
        'run', '--no-sync', 'python', 'tests\windows_smoke.py', 'dist\TrainingPlanner'
    )

    if ($Target -ne 'package') {
        $projectMetadata = Get-Content -LiteralPath 'pyproject.toml' -Raw
        if ($projectMetadata -notmatch '(?m)^version\s*=\s*"([^"]+)"\s*$') {
            throw 'Could not read the application version from pyproject.toml.'
        }
        $version = $Matches[1]
        Invoke-Checked $compiler @("/DAppVersion=$version", 'installer\windows.iss')
        Write-Host "Installer: $projectRoot\dist\TrainingPlanner-Setup-$version.exe"
    } else {
        Write-Host "Application: $projectRoot\dist\TrainingPlanner\TrainingPlanner.exe"
    }
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment
    Pop-Location
}
