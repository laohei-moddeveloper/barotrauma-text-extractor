"""Package only tracked source, the built EXE, and our clean live companion."""
import hashlib
from pathlib import Path
import subprocess
import zipfile
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from extractor import VERSION


def main():
    output=ROOT/'artifacts'/VERSION
    output.mkdir(parents=True,exist_ok=True)
    exe=ROOT/'dist/BarotraumaTextExtractor.exe'
    if not exe.is_file():raise SystemExit('Build Windows EXE first')
    subprocess.run(['git','archive','--format=zip','--prefix=AbyssText-source/',
                    '-o',str(output/f'AbyssText-{VERSION}-source.zip'),'HEAD'],cwd=ROOT,check=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    with zipfile.ZipFile(output/f'AbyssText-{VERSION}-Windows-x64.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe,'AbyssText/BarotraumaTextExtractor.exe')
        for name in ['README.md','README_EN.md','docs/WINDOWS-v0.2.md','docs/VALIDATION-v0.2.md','docs/FIX-zero-translations-rc2.zh-CN.md','docs/INSTALL-rc4.zh-CN.md']:
            archive.write(ROOT/name,'AbyssText/'+name)
        archive.writestr('AbyssText/VERSION.txt',VERSION+'\nSource commit: '+commit+'\nExperimental live companion: awaiting user game acceptance.\n')
    with zipfile.ZipFile(output/f'AbyssTextLive-{VERSION}.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in ['filelist.xml','Live/Translations.xml','Lua/Autorun/abysstext.lua']:
            archive.write(ROOT/'live-mod/AbyssTextLive'/name,'AbyssTextLive/'+name)
        archive.write(ROOT/'docs/INSTALL-rc4.zh-CN.md','INSTALL-AND-LIMITS.zh-CN.md')
        archive.writestr('VERSION.txt',VERSION+'\nSource commit: '+commit+'\n')
    sums=[]
    for path in sorted(output.glob('*.zip')):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip():raise SystemExit('Corrupt archive: '+path.name)
            names=archive.namelist()
            if any(part in name.split('/') for name in names for part in ['.git','.venv','.local-release','__pycache__']):
                raise SystemExit('Unexpected private/generated path')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        sums.append(f'{digest}  {path.name}')
    sums.append(hashlib.sha256(exe.read_bytes()).hexdigest()+'  BarotraumaTextExtractor.exe (inside Windows ZIP)')
    (output/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')
    print('\n'.join(sums))


if __name__=='__main__':main()
