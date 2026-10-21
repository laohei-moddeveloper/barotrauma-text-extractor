param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
& $Python -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer required'"
if ($LASTEXITCODE) { throw "Python 3.12 or newer required" }
& $Python -m venv .venv
if ($LASTEXITCODE) { throw "venv failed" }
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw "Build dependencies failed" }
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --onefile --windowed --name BarotraumaTextExtractor --add-data "live-mod;live-mod" app.py
if ($LASTEXITCODE) { throw "EXE build failed" }
Write-Output "dist/BarotraumaTextExtractor.exe"
