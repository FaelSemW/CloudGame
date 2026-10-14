#!/bin/sh
# Cloud Game — generated release installer. No remote commands from metadata.
set -eu
profile=''
case "${1:-}" in
    '') ;;
    --software) profile='--software' ;;
    *) echo 'Opção inválida. Use --software para testar a sessão nativa por CPU, sem VM.' >&2; exit 1 ;;
esac
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
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https'     --connect-timeout 20 --max-time 300 --output "$stage/cloud-game.pyz" https://raw.githubusercontent.com/FaelSemW/CloudGame/main/downloads/host-native-preview-3/cloud-game.pyz
printf '%s  %s\n' 'e2e582d245f3d946c4439ea04e8e798fecb199375a47c618d80cfeac483ccc30' "$stage/cloud-game.pyz" | sha256sum --check --status
python3 "$stage/cloud-game.pyz" verify
# The resumable wizard prepares missing native prerequisites after elevation.
if [ "$(id -u)" = 0 ]; then
    python3 "$stage/cloud-game.pyz" install $profile
elif command -v pkexec >/dev/null 2>&1; then
    pkexec /usr/bin/python3 "$stage/cloud-game.pyz" install $profile
else
    echo 'Autorização administrativa necessária para instalar o HOST.'
    sudo /usr/bin/python3 "$stage/cloud-game.pyz" install $profile
fi
