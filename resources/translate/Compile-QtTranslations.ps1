param(
    [Parameter(Mandatory = $true)]
    [string]$TranslateDir,

    # Ruta al ejecutable lrelease. Si se deja vacio, se autodetecta
    # (pyside6-lrelease -> lrelease -> lrelease-qt6, en ese orden).
    [string]$LreleaseExe = "",

    # Patron de ficheros .ts a compilar dentro de TranslateDir.
    [string]$Pattern = "*.ts"
)

$ErrorActionPreference = "Stop"

function Resolve-LreleaseExe {
    param([string]$Explicit)

    if ($Explicit -ne "") {
        if (Get-Command $Explicit -ErrorAction SilentlyContinue) {
            return $Explicit
        }
        Write-Host "AVISO: no se encontro '$Explicit' en el PATH, se intentara autodetectar." -ForegroundColor Yellow
    }

    $candidates = @("pyside6-lrelease", "lrelease-qt6", "lrelease")
    foreach ($c in $candidates) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }

    return $null
}

# Normaliza la ruta de la carpeta de traducciones
if (-not (Test-Path -LiteralPath $TranslateDir)) {
    Write-Host "ERROR: la carpeta de traducciones no existe: $TranslateDir" -ForegroundColor Red
    exit 1
}
$TranslateDir = (Resolve-Path -LiteralPath $TranslateDir).Path

$lrelease = Resolve-LreleaseExe -Explicit $LreleaseExe
if (-not $lrelease) {
    Write-Host "ERROR: no se ha encontrado 'pyside6-lrelease' ni 'lrelease' en el PATH." -ForegroundColor Red
    Write-Host "Instala PySide6 (pip install pyside6) o anade lrelease de Qt al PATH, y vuelve a intentarlo." -ForegroundColor Red
    exit 1
}

Write-Host "Carpeta de traducciones: $TranslateDir"
Write-Host "Usando: $lrelease"
Write-Host ""

$tsFiles = Get-ChildItem -LiteralPath $TranslateDir -Filter $Pattern -File
if ($tsFiles.Count -eq 0) {
    Write-Host "No se han encontrado ficheros '$Pattern' en $TranslateDir" -ForegroundColor Yellow
    exit 0
}

$okCount = 0
$failCount = 0

foreach ($ts in $tsFiles) {
    $qmPath = [System.IO.Path]::ChangeExtension($ts.FullName, ".qm")
    Write-Host "Compilando: $($ts.Name) -> $([System.IO.Path]::GetFileName($qmPath))"

    & $lrelease $ts.FullName -qm $qmPath 2>&1 | ForEach-Object { Write-Host "    $_" }

    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $qmPath)) {
        $okCount++
    } else {
        Write-Host "    ERROR compilando $($ts.Name)" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host "Hecho. Compilados correctamente: $okCount   Fallidos: $failCount"

if ($failCount -gt 0) {
    exit 1
}
