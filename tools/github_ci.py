"""Read this project's CI using the normal Git credential helper, without logging credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
import zipfile
import io

REPO = 'FaelSemW/CloudGame'
ROOT = Path(__file__).resolve().parents[1]


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme != 'https':
            raise RuntimeError('Redirecionamento não HTTPS recusado.')
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(request.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def credential():
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    auth = subprocess.run(['git', 'credential', 'fill'], cwd=ROOT,
                          input='protocol=https\nhost=github.com\n\n', text=True,
                          capture_output=True, env=env, timeout=30)
    if auth.returncode:
        raise RuntimeError('Autenticação GitHub indisponível no Git Credential Manager.')
    fields = dict(line.split('=', 1) for line in auth.stdout.splitlines() if '=' in line)
    token = fields.get('password')
    if not token:
        raise RuntimeError('Git não retornou credencial utilizável.')
    return token


def request(path, method='GET', body=None):
    token = credential()
    url = 'https://api.github.com/repos/' + REPO + '/' + path
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'CloudGame-CI',
                 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'})
    with urllib.request.build_opener(SafeRedirect()).open(req, timeout=90) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['jobs', 'logs', 'artifacts', 'download'])
    parser.add_argument('id', type=int)
    args = parser.parse_args()
    if args.command in ('jobs', 'artifacts'):
        data = json.loads(request(f'actions/runs/{args.id}/{args.command}'))
        if args.command == 'jobs':
            print(json.dumps([{'id':j['id'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion'],
                'activeSteps':[s['name'] for s in j['steps'] if s['status']=='in_progress' or s['conclusion']=='failure']} for j in data['jobs']],indent=2))
        else:
            print(json.dumps([{'id':a['id'],'name':a['name'],'size':a['size_in_bytes']} for a in data['artifacts']],indent=2))
    elif args.command == 'logs':
        payload = request(f'actions/jobs/{args.id}/logs')
        output = ROOT / 'build' / f'job-{args.id}.log'
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(payload)
        print(output)
    else:
        payload = request(f'actions/artifacts/{args.id}/zip')
        output = ROOT / 'build' / f'artifact-{args.id}'
        output.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for member in archive.infolist():
                target = (output/member.filename).resolve()
                if not target.is_relative_to(output.resolve()):
                    raise RuntimeError('Caminho inválido no artefato.')
            archive.extractall(output)
        print(output)


if __name__ == '__main__':
    main()
