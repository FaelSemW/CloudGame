"""Generate the one-line-download installer for a concrete HTTPS release URL."""
import argparse
import hashlib
from pathlib import Path
import shlex
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def installer(base_url, digest):
    url = urlparse(base_url)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(c.isspace() for c in base_url)):
        raise ValueError('Informe a URL HTTPS real da pasta de downloads, sem credenciais ou parâmetros.')
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('SHA-256 inválido.')
    download = shlex.quote(base_url.rstrip('/') + '/cloud-game.pyz')
    return f'''#!/bin/sh
# Cloud Game — generated release installer. No remote commands from metadata.
set -eu
profile=''
case "${{1:-}}" in
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
    command -v "$tool" >/dev/null 2>&1 || {{ echo "Ferramenta ausente: $tool" >&2; exit 1; }}
done
stage=$(mktemp -d)
trap 'rm -f -- "$stage/cloud-game.pyz"; rmdir -- "$stage"' EXIT HUP INT TERM
echo 'Baixando Cloud Game e verificando a integridade…'
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 300 --output "$stage/cloud-game.pyz" {download}
printf '%s  %s\\n' '{digest}' "$stage/cloud-game.pyz" | sha256sum --check --status
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
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    artifact = ROOT / 'dist/cloud-game.pyz'
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    output = artifact.with_name('install.sh')
    output.write_text(installer(args.base_url, digest), encoding='utf-8', newline='\n')
    print(output)
    print('Publicação ainda necessária. Não compartilhe o comando antes de verificar os downloads publicados.')


if __name__ == '__main__':
    main()
