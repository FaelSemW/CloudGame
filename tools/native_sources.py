"""Fetch pinned upstream code and assemble native clients without discarding edits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'moonlight-qt': ('moonlight-stream/moonlight-qt', 'a57e947d7185fd01384f6973df4df59ae2968d01'),
    'moonlight-android': ('moonlight-stream/moonlight-android', 'b48494cb96bff23d8886c4775cc4f39a1075495d'),
}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Âncora upstream ausente ou ambígua: ' + old[:80])
    return source.replace(old, new)


def assemble(name, sync=False):
    remote, commit = PINS[name]
    repo = ROOT / 'third_party' / name
    if not repo.exists():
        if not sync:
            raise RuntimeError('Fontes ausentes; execute com --sync.')
        subprocess.run(['git', 'clone', '--no-checkout', 'https://github.com/' + remote + '.git', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'checkout', '--detach', commit], check=True)
    if git(repo, 'rev-parse', 'HEAD') != commit:
        raise RuntimeError('Checkout diferente do lock; preservado: ' + str(repo))
    if sync:
        subprocess.run(['git', '-C', str(repo), 'submodule', 'update', '--init', '--recursive'], check=True)
    def original(path):
        return subprocess.check_output(['git', '-C', str(repo), 'show', 'HEAD:' + path]).decode('utf-8').replace('\r\n', '\n')
    outputs = {}
    if name == 'moonlight-qt':
        main = original('app/main.cpp')
        main = '#include "cloudgame/platformclient.h"\n' + main
        # The context object must outlive the engine and its QML bindings.
        main = replace(main, '    QQmlApplicationEngine engine;', '    PlatformClient cloudGame;\n    QQmlApplicationEngine engine;\n    engine.rootContext()->setContextProperty("CloudGame", &cloudGame);')
        main = replace(main, 'initialView = "qrc:/gui/PcView.qml";', 'initialView = "qrc:/gui/CloudGameView.qml";')
        main = replace(main, 'setOrganizationName("Moonlight Game Streaming Project")', 'setOrganizationName("CloudGame")')
        main = replace(main, 'setApplicationName("Moonlight")', 'setApplicationName("Cloud Game")')
        outputs['app/main.cpp'] = main
        outputs['app/app.pro'] = original('app/app.pro') + '\n# Cloud Game native control integration\nSOURCES += cloudgame/platformclient.cpp\nHEADERS += cloudgame/platformclient.h\n'
        outputs['app/qml.qrc'] = replace(original('app/qml.qrc'), '<file>gui/PcView.qml</file>', '<file>gui/PcView.qml</file>\n        <file>gui/CloudGameView.qml</file>')
        outputs['app/gui/main.qml'] = replace(original('app/gui/main.qml'), 'AutoUpdateChecker.start()', '// Updates are distributed through CloudGame releases.')
        overlay = ROOT / 'integrations/qt'
    else:
        ET.register_namespace('android','http://schemas.android.com/apk/res/android')
        android = '{http://schemas.android.com/apk/res/android}'
        tree = ET.fromstring(original('app/src/main/AndroidManifest.xml'))
        application = tree.find('application')
        application.set(android+'allowBackup','false')
        application.set(android+'label','Cloud Game')
        # Explicit rules must also exclude device-to-device transfer on Android 12+.
        application.attrib.pop(android+'fullBackupContent', None)
        application.set(android+'dataExtractionRules','@xml/cloudgame_backup_rules')
        for activity in application.findall('activity'):
            if activity.get(android+'name') == '.PcView':
                activity.set(android+'exported','false')
                for intent in list(activity.findall('intent-filter')):
                    activity.remove(intent)
        activity = ET.SubElement(application,'activity',{android+'name':'.cloudgame.CloudGameActivity',android+'exported':'true',android+'configChanges':'keyboardHidden|orientation|screenSize',android+'label':'Cloud Game'})
        intent = ET.SubElement(activity,'intent-filter')
        ET.SubElement(intent,'action',{android+'name':'android.intent.action.MAIN'})
        ET.SubElement(intent,'category',{android+'name':'android.intent.category.LAUNCHER'})
        outputs['app/src/main/AndroidManifest.xml'] = ET.tostring(tree,encoding='unicode')
        outputs['app/src/nonRoot/AndroidManifest.xml'] = replace(original('app/src/nonRoot/AndroidManifest.xml'), 'android:label="@string/app_label"', 'android:label="Cloud Game"')
        outputs['app/src/main/assets/cloudgame-license.txt'] = ('Cloud Game: https://github.com/FaelSemW/CloudGame\nMoonlight Android: https://github.com/moonlight-stream/moonlight-android\nBase: ' + commit + '\nEste programa incorpora Moonlight Android e moonlight-common-c sob GPLv3. As alterações e scripts de compilação ficam no repositório CloudGame.\n\n' + (ROOT / 'licenses/moonlight-android-LICENSE.txt').read_text(encoding='utf-8'))
        gradle = replace(original('app/build.gradle'), 'applicationId "com.limelight"', 'applicationId "io.github.faelsemw.cloudgame"')
        gradle = replace(gradle, 'applicationId "com.limelight.root"', 'applicationId "io.github.faelsemw.cloudgame.root"')
        gradle = replace(gradle, 'versionName "12.2"', 'versionName "0.1.0-dev"')
        outputs['app/build.gradle'] = gradle
        outputs['app/src/main/res/xml/cloudgame_backup_rules.xml'] = '<data-extraction-rules><cloud-backup><exclude domain="root" path="."/><exclude domain="sharedpref" path="."/><exclude domain="file" path="."/><exclude domain="database" path="."/><exclude domain="external" path="."/></cloud-backup><device-transfer><exclude domain="root" path="."/><exclude domain="sharedpref" path="."/><exclude domain="file" path="."/><exclude domain="database" path="."/><exclude domain="external" path="."/></device-transfer></data-extraction-rules>'
        overlay = ROOT / 'integrations/android'
    for file in overlay.rglob('*'):
        if file.is_file(): outputs[file.relative_to(overlay).as_posix()] = file.read_text(encoding='utf-8')
    stamp = repo / '.git/cloudgame-overlay.json'
    previous = json.loads(stamp.read_text()) if stamp.exists() else {}
    hashes = {}
    # Validate every destination before mutating any of them.
    for path, content in outputs.items():
        target = repo / path
        if target.exists():
            current = target.read_text(encoding='utf-8').replace('\r\n','\n')
            current_hash = hashlib.sha256(current.encode()).hexdigest()
            if current != content and current_hash != previous.get(path):
                try: clean = original(path)
                except subprocess.CalledProcessError: clean = None
                if current != clean: raise RuntimeError('Edição local preservada: ' + str(target))
        hashes[path] = hashlib.sha256(content.encode()).hexdigest()
    for path, content in outputs.items():
        target = repo / path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content,encoding='utf-8',newline='\n')
    stamp.write_text(json.dumps(hashes,indent=2))
    print(f'{name}: integração aplicada em {commit}; ainda requer compilação.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=list(PINS)+['all'])
    parser.add_argument('--sync',action='store_true')
    args=parser.parse_args()
    for target in PINS if args.target == 'all' else [args.target]: assemble(target,args.sync)
