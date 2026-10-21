"""Audit delivered ZIPs against the commit, tested EXE and clean companion."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from extractor import VERSION


def audit():
    output=ROOT/'artifacts'/VERSION
    evidence=ROOT/'artifacts/evidence'
    receipt=json.loads((evidence/'frozen-checks.json').read_text(encoding='utf-8'))
    online=json.loads((evidence/'frozen-online.json').read_text(encoding='utf-8'))
    assert receipt['passed'] and len(receipt['checks'])==5 and all(c['passed'] for c in receipt['checks'])
    assert online['ok'] and not online['issues']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    hashes={}
    for line in (output/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest,name=line.split('  ',1)
        assert Path(name).name==name and name.endswith('.zip')
        assert hashlib.sha256((output/name).read_bytes()).hexdigest()==digest,name
        hashes[name]=digest
    assert len(hashes)==3
    for name in hashes:
        with zipfile.ZipFile(output/name) as archive:assert archive.testzip() is None,name
    with zipfile.ZipFile(output/f'AbyssText-{VERSION}-Windows-x64.zip') as archive:
        exe=archive.read('AbyssText/BarotraumaTextExtractor.exe')
        assert hashlib.sha256(exe).hexdigest()==receipt['exe_sha256']
        assert (output/'EXE-SHA256.txt').read_text(encoding='ascii').split()[0]==receipt['exe_sha256']
        assert commit in archive.read('AbyssText/VERSION.txt').decode()
    with zipfile.ZipFile(output/f'AbyssTextLive-{VERSION}.zip') as archive:
        clean=['filelist.xml','Live/Translations.xml','Lua/Autorun/abysstext.lua']
        assert set(archive.namelist())=={'AbyssTextLive/'+n for n in clean}|{'VERSION.txt','INSTALL-AND-LIMITS.zh-CN.md'}
        assert commit in archive.read('VERSION.txt').decode()
        for name in clean:
            assert archive.read('AbyssTextLive/'+name)==(ROOT/'live-mod/AbyssTextLive'/name).read_bytes()
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','-z','HEAD'],cwd=ROOT).decode().strip('\0').split('\0')
    with zipfile.ZipFile(output/f'AbyssText-{VERSION}-source.zip') as archive:
        files={n for n in archive.namelist() if not n.endswith('/')}
        assert files=={'AbyssText-source/'+n for n in tracked}
        for name in tracked:
            expected=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
            assert archive.read('AbyssText-source/'+name)==expected,name
    result={'version':VERSION,'source_commit':commit,'passed':True,'zip_sha256':hashes,
        'exe_sha256':receipt['exe_sha256'],'frozen_online':online,
        'source_all_tracked_files_match_commit':True,'plugin_clean_payload_matches_checkout':True,
        'windows_exe_matches_tested_exe':True,'game_tested':False}
    (evidence/'package-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # The fixed-sample receipt contains no user content or credentials. ASCII
    # keeps it readable in non-UTF-8 Windows log collectors too.
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':audit()
