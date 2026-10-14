$ErrorActionPreference = 'Stop'
# This test installs and starts the client only on an ephemeral GitHub runner.
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Execute este teste apenas no runner descartável do CI.' }
$testRoot = Join-Path $env:RUNNER_TEMP ('cloudgame-smoke-' + [guid]::NewGuid().ToString('N'))
$logRoot = Join-Path $PSScriptRoot '..\build\windows-smoke'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$setup = (Resolve-Path (Join-Path $PSScriptRoot '..\dist\CloudGame-Setup.exe')).Path
$installLog = Join-Path $logRoot 'install.log'
$install = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$testRoot`"", "/LOG=`"$installLog`"") -Wait -PassThru -WindowStyle Hidden
if ($install.ExitCode -ne 0) { throw "Instalação falhou: $($install.ExitCode)" }
$networkCli = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (-not (Test-Path -LiteralPath $networkCli -PathType Leaf)) { throw 'O instalador não preparou o Tailscale.' }
if (-not (Get-Service -Name Tailscale -ErrorAction SilentlyContinue)) { throw 'Serviço de rede não instalado.' }
$app = $null
try {
    $executable = Join-Path $testRoot 'Moonlight.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Executável não instalado.' }
    $app = Start-Process -FilePath $executable -WorkingDirectory $testRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot 'stdout.log') -RedirectStandardError (Join-Path $logRoot 'stderr.log')
    Start-Sleep -Seconds 10
    $app.Refresh()
    if ($app.HasExited) { throw "Cliente encerrou durante inicialização: $($app.ExitCode)" }
    Write-Output 'Instalação e inicialização Windows passaram. Streaming e GPU não foram validados.'
} finally {
    if ($app -and -not $app.HasExited) {
        $app.CloseMainWindow() | Out-Null
        if (-not $app.WaitForExit(5000)) { $app.Kill(); $app.WaitForExit() }
    }
    $uninstaller = Join-Path $testRoot 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Wait -PassThru -WindowStyle Hidden
        if ($uninstall.ExitCode -ne 0) { throw "Desinstalação falhou: $($uninstall.ExitCode)" }
    }
}
$diagnostics = (Get-Content -LiteralPath (Join-Path $logRoot 'stderr.log') -Raw) + (Get-Content -LiteralPath (Join-Path $logRoot 'stdout.log') -Raw)
if ($diagnostics -match 'QQmlApplicationEngine failed|ReferenceError:|TypeError:|Error loading QML') { throw 'Erro QML detectado; consulte os logs.' }
if (Test-Path -LiteralPath (Join-Path $testRoot 'Moonlight.exe')) { throw 'O desinstalador deixou o executável instalado.' }
