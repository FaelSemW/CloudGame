# Cloud Game desktop installer. Requires a published, complete Windows release.
$ErrorActionPreference = 'Stop'
$repository = 'FaelSemW/CloudGame'
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases/latest" -Headers @{'User-Agent'='CloudGame-Installer'}
$setup = @($release.assets | Where-Object name -EQ 'CloudGame-Setup.exe')
$checksums = @($release.assets | Where-Object name -EQ 'SHA256SUMS')
if ($setup.Count -ne 1 -or $checksums.Count -ne 1) {
    throw 'Nenhuma versão desktop completa foi publicada. O instalador não usará um pacote de painel como substituto.'
}
foreach ($asset in @($setup[0], $checksums[0])) {
    $url = [uri]$asset.browser_download_url
    if ($url.Scheme -ne 'https' -or $url.Host -ne 'github.com' -or -not $url.AbsolutePath.StartsWith("/$repository/releases/download/")) {
        throw 'URL de distribuição inválida.'
    }
}
$stage = Join-Path ([IO.Path]::GetTempPath()) ('CloudGame-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $setupFile = Join-Path $stage 'CloudGame-Setup.exe'
    $hashFile = Join-Path $stage 'SHA256SUMS'
    Invoke-WebRequest -Uri $setup[0].browser_download_url -OutFile $setupFile -UseBasicParsing
    Invoke-WebRequest -Uri $checksums[0].browser_download_url -OutFile $hashFile -UseBasicParsing
    $match = [regex]::Match((Get-Content -LiteralPath $hashFile -Raw), '(?m)^([a-fA-F0-9]{64})  CloudGame-Setup\.exe\r?$')
    if (-not $match.Success -or (Get-FileHash -LiteralPath $setupFile -Algorithm SHA256).Hash -ne $match.Groups[1].Value) {
        throw 'A integridade do instalador não foi confirmada.'
    }
    $process = Start-Process -FilePath $setupFile -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Instalação falhou, código $($process.ExitCode)." }
    Write-Host 'Cloud Game instalado. Abra pelo menu Iniciar e informe o endereço privado do seu HOST.'
} finally {
    # Only the two fixed files created by this invocation; no recursive deletion.
    foreach ($name in @('CloudGame-Setup.exe','SHA256SUMS')) {
        $path = Join-Path $stage $name
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage }
}
