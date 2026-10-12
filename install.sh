#!/bin/sh
# Cloud Game — generated release installer. No remote commands from metadata.
set -eu
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo 'Cloud Game HOST requer Bazzite Linux x86_64.' >&2
    exit 1
fi
if ! grep -qi bazzite /etc/os-release; then
    echo 'Este instalador de HOST suporta somente Bazzite.' >&2
    exit 1
fi
for tool in curl python3 sha256sum mktemp; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Ferramenta ausente: $tool" >&2; exit 1; }
done
stage=$(mktemp -d)
trap 'rm -f -- "$stage/cloud-game.pyz"; rmdir -- "$stage"' EXIT HUP INT TERM
echo 'Baixando Cloud Game e verificando a integridade…'
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https'     --connect-timeout 20 --max-time 300 --output "$stage/cloud-game.pyz" https://raw.githubusercontent.com/FaelSemW/CloudGame/main/downloads/cloud-game.pyz
printf '%s  %s\n' '1ceac4ec914136bfdf084dd408c988735a5d00f4bea45000d526e3d16fe04832' "$stage/cloud-game.pyz" | sha256sum --check --status
python3 "$stage/cloud-game.pyz" verify
# Preflight must finish before elevation or filesystem installation.
python3 "$stage/cloud-game.pyz" doctor
if [ "$(id -u)" = 0 ]; then
    python3 "$stage/cloud-game.pyz" install
elif command -v pkexec >/dev/null 2>&1; then
    pkexec /usr/bin/python3 "$stage/cloud-game.pyz" install
else
    echo 'Autorização administrativa necessária para instalar o HOST.'
    sudo /usr/bin/python3 "$stage/cloud-game.pyz" install
fi
