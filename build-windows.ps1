param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
& $Python -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer required'"
if ($LASTEXITCODE) { throw "Python 3.12 or newer required" }
if (!(Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE) { throw "venv failed" }
}
& .\.venv\Scripts\python.exe -c "import sys; assert sys.version_info >= (3,12), 'Existing build environment needs Python 3.12+'"
if ($LASTEXITCODE) { throw "Existing build environment needs Python 3.12+" }
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw "Build dependencies failed" }
$tlsPolicyPath = & .\.venv\Scripts\python.exe -c "import pathlib,ssl; p=pathlib.Path(ssl.__file__).with_name('codex-rejected-cas.pem'); print(str(p) if p.is_file() else '')"
if ($LASTEXITCODE) { throw "TLS runtime resource detection failed" }
$tlsDataArgs = @()
if ($tlsPolicyPath) { $tlsDataArgs = @('--add-data', "$tlsPolicyPath;.") }
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --onefile --windowed --name BarotraumaTextExtractor --icon "assets/abysstext.ico" --version-file "assets/windows-version.txt" --add-data "assets;assets" --add-data "live-mod;live-mod" @tlsDataArgs app.py
if ($LASTEXITCODE) { throw "EXE build failed" }
Write-Output "dist/BarotraumaTextExtractor.exe"
