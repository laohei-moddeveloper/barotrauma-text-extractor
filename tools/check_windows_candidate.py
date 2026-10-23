"""Exercise the frozen executable outside the checkout without opening a GUI."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def verify(exe, output):
    output.mkdir(parents=True, exist_ok=True)
    receipt={'protocol':1,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
             'game_tested':False,'checks':[],'optional_checks':[]}
    failed=False
    with tempfile.TemporaryDirectory(prefix='AbyssText-frozen-') as temp:
        root=Path(temp)
        candidate=root/'BarotraumaTextExtractor.exe'
        shutil.copy2(exe,candidate)
        env=os.environ.copy()
        env['PATH']=str(Path(env['SYSTEMROOT'])/'System32')
        env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
        env['LOCALAPPDATA']=str(root/'AppData')
        def run(name,args,check,expected=0,required=True):
            nonlocal failed
            item={'name':name}
            try:
                result=subprocess.run([str(candidate),*map(str,args)],cwd=root,env=env,
                    capture_output=True,timeout=100)
                item['exit_code']=result.returncode
                item['passed']=result.returncode==expected and bool(check())
            except Exception as error:
                item.update(passed=False,error=type(error).__name__+': '+str(error))
            receipt['checks' if required else 'optional_checks'].append(item)
            failed=failed or (required and not item['passed'])
        sample=root/'FixtureMod';sample.mkdir()
        (sample/'filelist.xml').write_text('<contentpackage name="Isolated fixture"><Item file="%ModDir%/items.xml"/></contentpackage>',encoding='utf-8')
        (sample/'items.xml').write_text('<Items><Item identifier="fixture" name="Open hatch" description="A test hatch."/></Items>',encoding='utf-8')
        before={p.name:p.read_bytes() for p in sample.iterdir()}
        scan=root/'scan.json'
        run('read-only fixture scan',['--raw',sample,'-o',scan],lambda:scan.is_file() and
            any(e['text']=='Open hatch' for e in json.loads(scan.read_text(encoding='utf-8'))['entries']) and
            before=={p.name:p.read_bytes() for p in sample.iterdir()})
        mods=root/'LocalMods';mods.mkdir()
        installed=mods/'AbyssTextLive'
        required=['filelist.xml','Live/Translations.xml','Lua/Autorun/abysstext.lua']
        source=Path(__file__).resolve().parents[1]/'live-mod/AbyssTextLive'
        run('bundled companion integrity',['--install-live-mod',mods],lambda:all(
            (installed/name).read_bytes()==(source/name).read_bytes() for name in required) and
            sorted(str(p.relative_to(installed)).replace('\\','/') for p in installed.rglob('*') if p.is_file())==sorted(required))
        snapshot={n:(installed/n).read_bytes() for n in required} if installed.is_dir() else {}
        run('existing companion refuses overwrite',['--install-live-mod',mods],lambda:
            snapshot and all((installed/n).read_bytes()==data for n,data in snapshot.items()),expected=1)
        # A real frozen import verifies the bundled registry and SQLite module.
        human_root=root/'HumanFixtures';human_root.mkdir()
        for mod_id,language,text in [('1234567890','English','Phantom Wrench'),('2861028841','Simplified Chinese','幻影扳手')]:
            package=human_root/mod_id;package.mkdir()
            filename='Inactive/AmmoModSC.xml' if mod_id=='2861028841' else 'text.xml'
            target=package/filename;target.parent.mkdir(parents=True,exist_ok=True)
            (package/'filelist.xml').write_text(f'<contentpackage steamworkshopid="{mod_id}"><Text file="%ModDir%/{filename}"/></contentpackage>',encoding='utf-8')
            target.write_text(f'<infotexts language="{language}"><entityname.phantom>Phantom Wrench</entityname.phantom></infotexts>'.replace('Phantom Wrench',text),encoding='utf-8')
        # Registry routes Ammo Mod to its real owner ID, not this fixture ID.
        (human_root/'1234567890'/'filelist.xml').write_text('<contentpackage steamworkshopid="2742414355"><Text file="%ModDir%/text.xml"/></contentpackage>',encoding='utf-8')
        human_bank=root/'human.sqlite3';human_report=root/'human.json'
        def check_human_import():
            if not human_report.is_file():return False
            import sqlite3
            with closing(sqlite3.connect(human_bank)) as bank:
                rows=bank.execute('SELECT scope,source,translation FROM pairs').fetchall()
            return json.loads(human_report.read_text(encoding='utf-8'))['records']==1 and rows==[('2742414355','Phantom Wrench','幻影扳手')]
        run('actual frozen human-memory import',['--import-human-memory',human_root,'--cache-path',human_bank,'-o',human_report],check_human_import)
        online=root/'online.json'
        def check_online():
            if not online.is_file():return False
            data=json.loads(online.read_text(encoding='utf-8'))
            return data.get('ok') is True and not data.get('issues') and bool(data.get('translation')) and data.get('compound_check')=={'translation':'画皮泥偶迅猛龙','ok':True}
        run('actual frozen HTTPS translation',['--check-online',online],check_online)
        if online.is_file():
            shutil.copy2(online,output/'frozen-online.json')
            saved=online.read_bytes()
            run('online output refuses overwrite',['--check-online',online],lambda:online.read_bytes()==saved,expected=2)
        google=root/'google-online.json'
        def check_google():
            if not google.is_file():return False
            data=json.loads(google.read_text(encoding='utf-8'))
            return data.get('ok') is True and not data.get('issues') and data.get('channel')=='google'
        run('Google experimental frozen HTTPS',['--check-online',google,'--online-channel','google'],check_google,required=False)
        if google.is_file():shutil.copy2(google,output/'frozen-google-online.json')
    receipt['passed']=not failed
    (output/'frozen-checks.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return 1 if failed else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,default=Path('dist/BarotraumaTextExtractor.exe'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/evidence'))
    args=parser.parse_args()
    if os.name!='nt':parser.error('Requires actual Windows; do not substitute Linux source execution')
    raise SystemExit(verify(args.exe.resolve(),args.output.resolve()))
