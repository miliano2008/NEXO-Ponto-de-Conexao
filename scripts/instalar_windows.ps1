# NEXO - instalador para Windows (chamado por INSTALAR_WINDOWS.bat)
# 1) instala o Python 3.12 se nao houver Python 3.10+  2) chama iniciar.bat
# Texto sem acentos de proposito: o PowerShell 5.1 do Windows le scripts como ANSI.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)   # raiz do projeto
$VersaoPython = "3.12.7"

function Encontrar-Python {
    # Retorna o comando de um Python 3.10+ ou $null.
    # O "python.exe" falso da Microsoft Store nao imprime versao e e ignorado.
    $candidatos = @(
        @("py", "-3"), @("python"), @("python3"),
        @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"),
        @("$env:ProgramFiles\Python312\python.exe")
    )
    foreach ($c in $candidatos) {
        try {
            $args2 = @()
            if ($c.Count -gt 1) { $args2 = $c[1..($c.Count - 1)] }
            $saida = & $c[0] @args2 --version 2>&1 | Out-String
            if ($saida -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) { return ,$c }
        } catch { }
    }
    return $null
}

function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host ""
Write-Host "=== NEXO - instalacao no Windows ===" -ForegroundColor Cyan

if (-not (Test-Path "app\servidor.py")) {
    Write-Host "[ERRO] Extraia o .zip inteiro antes de executar o instalador." -ForegroundColor Red
    exit 1
}

$py = Encontrar-Python
if ($py) {
    Write-Host "Python ja instalado: $(& $py[0] @($py | Select-Object -Skip 1) --version 2>&1)" -ForegroundColor Green
} else {
    Write-Host "Python 3.10+ nao encontrado. Instalando o Python $VersaoPython (somente para este usuario, sem precisar de administrador)..."
    $instalado = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Usando o winget..."
        try {
            winget install -e --id Python.Python.3.12 --scope user --silent `
                --accept-package-agreements --accept-source-agreements
            $instalado = $true
        } catch { Write-Host "winget falhou, tentando download direto..." -ForegroundColor Yellow }
    }

    if (-not $instalado -or -not (Encontrar-Python)) {
        $arq = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "" }
        $nome = if ($arq) { "python-$VersaoPython-$arq.exe" } else { "python-$VersaoPython.exe" }
        $url = "https://www.python.org/ftp/python/$VersaoPython/$nome"
        $destino = Join-Path $env:TEMP $nome
        Write-Host "Baixando $url ..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $destino -UseBasicParsing
        Write-Host "Instalando (pode levar 1-2 minutos)..."
        $p = Start-Process -FilePath $destino -Wait -PassThru -ArgumentList `
            "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0"
        if ($p.ExitCode -ne 0) {
            Write-Host "[ERRO] O instalador do Python retornou o codigo $($p.ExitCode)." -ForegroundColor Red
            Write-Host "Instale manualmente: https://www.python.org/downloads/ (marque 'Add python.exe to PATH')."
            exit 1
        }
    }

    Atualizar-Path
    $py = Encontrar-Python
    if (-not $py) {
        Write-Host "[ERRO] Python instalado, mas nao encontrado. Feche esta janela e rode INSTALAR_WINDOWS.bat de novo." -ForegroundColor Red
        exit 1
    }
    Write-Host "Python instalado com sucesso." -ForegroundColor Green
}

# Garante que o iniciar.bat encontre este Python mesmo antes de reabrir o terminal
$pastaPy = Split-Path (& $py[0] @($py | Select-Object -Skip 1) -c "import sys; print(sys.executable)")
$env:Path = "$pastaPy;$pastaPy\Scripts;$env:Path"

Write-Host ""
Write-Host "Preparando e iniciando o NEXO..." -ForegroundColor Cyan
& cmd /c "iniciar.bat"
