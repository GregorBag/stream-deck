$ErrorActionPreference = "Stop"

$project_root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$spec_path = Join-Path $project_root "packaging\dj_poltorashka.spec"
$build_path = Join-Path $project_root "build"
$dist_path = Join-Path $project_root "dist"

$venv_python = Join-Path $project_root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venv_python -PathType Leaf) {
    $python_path = $venv_python
}
else {
    $python_command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python_command) {
        Write-Error "Python не найден. Создайте окружение desktop_app\.venv."
        exit 1
    }
    $python_path = $python_command.Source
}

try {
    & $python_path -c "import PyInstaller"
}
catch {
    Write-Error "Не удалось запустить Python: $($_.Exception.Message)"
    exit 1
}
if ($LASTEXITCODE -ne 0) {
    Write-Error 'PyInstaller не установлен. Выполните: python -m pip install -e ".[dev,build]"'
    exit 1
}

Push-Location $project_root
try {
    & $python_path -m PyInstaller `
        --noconfirm `
        --clean `
        --workpath $build_path `
        --distpath $dist_path `
        $spec_path
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
