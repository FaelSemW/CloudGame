"""Upload an explicit, hashed asset manifest to a draft, then publish a preview."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
from github_ci import credential, request, REPO, ROOT


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def publish(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    tag = manifest['tag']
    if not re.fullmatch(r'v[0-9.]+-desktop-preview\.[0-9]+', tag):
        raise ValueError('Only an explicitly named desktop preview is supported')
    commit = manifest['commit']
    subprocess.run(['git', 'cat-file', '-e', commit + '^{commit}'], cwd=ROOT, check=True)
    assets = []
    names = set()
    for item in manifest['assets']:
        name = item['name']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in names:
            raise ValueError('Invalid or duplicate release filename')
        names.add(name)
        path = Path(item['path']).resolve(strict=True)
        if not path.is_relative_to(ROOT) or path.is_symlink() or not path.is_file():
            raise ValueError('Release asset must be an explicit regular workspace file')
        if digest(path) != item['sha256']:
            raise ValueError('Asset changed after preparation: ' + name)
        assets.append((name, path, item['sha256']))
    required = {'CloudGame-Setup.exe', 'cloud-game.pyz', 'SHA256SUMS',
                'qt-everywhere-src-6.12.0.tar.xz', 'CloudGame-Vulkan-SDK-sources.tar',
                'CloudGame-Desktop-sources.tar.gz'}
    if not required.issubset(names):
        raise ValueError('Missing binary or corresponding sources')
    if not any(re.fullmatch(r'CloudGame-Windows-sources-[a-f0-9]{7,40}\.tar\.gz', name) for name in names):
        raise ValueError('Missing versioned Windows corresponding sources')
    releases = json.loads(request('releases?per_page=100'))
    existing = next((release for release in releases if release['tag_name'] == tag), None)
    if existing and not existing['draft']:
        raise RuntimeError('Published release preserved; use a new version')
    release = existing or json.loads(request('releases', 'POST', {
        'tag_name': tag, 'target_commitish': commit, 'name': 'CloudGame desktop — preview integrado 0.1',
        'body': manifest['body'], 'draft': True, 'prerelease': True}))
    uploaded = {item['name']: item for item in release['assets']}
    for name, path, sha in assets:
        if name in uploaded:
            if uploaded[name].get('digest') != 'sha256:' + sha:
                raise RuntimeError('Existing draft asset differs; preserved: ' + name)
            continue
        connection = http.client.HTTPSConnection('uploads.github.com', timeout=90)
        try:
            connection.putrequest('POST', f'/repos/{REPO}/releases/{release["id"]}/assets?name={quote(name)}')
            connection.putheader('Authorization', 'Bearer ' + credential())
            connection.putheader('User-Agent', 'CloudGame-release')
            connection.putheader('Content-Type', 'application/octet-stream')
            connection.putheader('Content-Length', str(path.stat().st_size))
            connection.endheaders()
            with path.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    connection.send(chunk)
            response = connection.getresponse()
            result = json.loads(response.read())
            if response.status != 201 or result.get('digest') != 'sha256:' + sha:
                raise RuntimeError(f'Upload verification failed for {name}: HTTP {response.status}')
            print('Uploaded and verified: ' + name, flush=True)
        finally:
            connection.close()
    # No public binary is exposed until the entire source/binary set is present.
    result = json.loads(request(f'releases/{release["id"]}', 'PATCH',
                               {'draft': False, 'prerelease': True, 'body': manifest['body']}))
    print(result['html_url'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    publish(parser.parse_args().manifest)
