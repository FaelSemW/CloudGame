# Installs the official network service. No shared enrollment credentials.
$ErrorActionPreference = 'Stop'
$cli = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (Test-Path -LiteralPath $cli -PathType Leaf) { exit 0 }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('CloudGame-Network-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$msi = Join-Path $stage 'tailscale.msi'
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://pkgs.tailscale.com/stable/tailscale-setup-1.104.1-amd64.msi' -OutFile $msi
    if ((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ne '6da8bcdb0d45a214cae0e8a88c2987ad48dec134bf04dffb9c05f1354c02b0b4') { throw 'Integridade do Tailscale inválida.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $msi
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Tailscale Inc\.') { throw 'Assinatura do Tailscale não confirmada.' }
    # The OS prompts for administrator authorization; credentials never enter CloudGame.
    $installer = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -Verb RunAs -ArgumentList @('/i', "`"$msi`"", '/passive', '/norestart') -Wait -PassThru -WindowStyle Hidden
    if ($installer.ExitCode -notin @(0, 3010)) { throw "Tailscale não instalado (código $($installer.ExitCode))." }
    if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) { throw 'Executável Tailscale ausente após instalação.' }
} finally {
    if (Test-Path -LiteralPath $msi) { Remove-Item -LiteralPath $msi -Force }
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage }
}
