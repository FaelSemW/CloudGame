"""Start the real Qt client on a CI display and preserve startup diagnostics."""
import argparse
import os
from pathlib import Path
import subprocess
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary',type=Path)
args=parser.parse_args()
output=Path('build/desktop-smoke'); output.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,QT_QUICK_BACKEND='software',SDL_AUDIODRIVER='dummy')
with (output/'startup.log').open('w') as log:
    process=subprocess.Popen([str(args.binary.resolve())],stdout=log,stderr=subprocess.STDOUT,env=env)
    try:
        time.sleep(8)
        if process.poll() is not None: raise RuntimeError('Desktop process exited during startup')
        subprocess.run(['import','-window','root',str(output/'desktop.png')],check=True)
    finally:
        process.terminate()
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
diagnostics=(output/'startup.log').read_text(errors='replace')
for error in ['QQmlApplicationEngine failed','ReferenceError:','TypeError:','is not installed','Cannot assign','is not a type','Error loading QML']:
    if error in diagnostics: raise RuntimeError('QML startup failure: '+error)
print('Desktop startup passed. This does not validate real streaming.')
