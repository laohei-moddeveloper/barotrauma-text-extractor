"""Install only our bundled client module into a new, user-selected directory."""
from pathlib import Path
import shutil
import sys


def install_companion(parent, resource_root=None):
    resources=Path(resource_root) if resource_root else Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    source=resources/'live-mod'/'AbyssTextLive'
    if not (source/'filelist.xml').is_file():raise ValueError('找不到随程序提供的游戏插件资源')
    parent=Path(parent).resolve()
    if not parent.is_dir():raise ValueError('请选择游戏 LocalMods 目录')
    target=parent/'AbyssTextLive'
    if target.exists() or target.is_symlink():raise ValueError('插件目录已存在；请连接已有插件，或先手动备份旧版本')
    # Explicit allowlist excludes runtime requests, drafts and local settings.
    files=['filelist.xml','Live/Translations.xml','Lua/Autorun/abysstext.lua']
    try:
        target.mkdir()
        for name in files:
            original=source/name
            if original.is_symlink() or not original.is_file():raise ValueError('游戏插件资源不完整')
            destination=target/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,destination)
    except Exception:
        shutil.rmtree(target,ignore_errors=True)
        raise
    return target
