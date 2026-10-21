"""AbyssText desktop and command-line entry point."""
import argparse
from pathlib import Path
from extractor import export_report, scan


def gui():
    from desktop_ui import run
    run()


def main():
    parser = argparse.ArgumentParser(description="潜渊症模组汉化文字提取器：无参数启动窗口")
    parser.add_argument("folder", nargs="?", help="模组文件夹")
    parser.add_argument("-o", "--output", type=Path, help="导出 CSV / JSON（放在模组目录外）")
    parser.add_argument("--raw", action="store_true", help="导出未归并的扫描证据（兼容旧版）")
    parser.add_argument("--source-language", default="Auto", help="Auto / English / Japanese / …")
    parser.add_argument("--target-language", default="Simplified Chinese", help="目标游戏语言名")
    parser.add_argument("--install-live-mod",type=Path,help="安装内置插件到指定 LocalMods；拒绝覆盖已有目录")
    parser.add_argument("--check-online",type=Path,metavar='NEW_JSON',help="无窗口验证联网翻译，将结果写入新的 JSON 文件")
    args = parser.parse_args()
    if args.check_online:
        if args.check_online.exists() or args.check_online.is_symlink() or args.folder or args.output or args.install_live_mod or args.raw:
            parser.error('--check-online 需要新 JSON 路径，不能与扫描/安装参数组合')
        import json,time
        from types import SimpleNamespace
        from free_online import translate_unit
        start=time.monotonic()
        try:
            result=translate_unit(SimpleNamespace(id='network-check',source='Open hatch',source_language='English'),'Simplified Chinese')['network-check']
            report={'ok':not result['issues'],'translation':result['translation'],'issues':result['issues']}
        except Exception as error:
            report={'ok':False,'error':str(error)}
        report['elapsed_seconds']=round(time.monotonic()-start,3)
        # Exclusive creation honors the NEW_JSON contract even if another
        # process creates the path while the network request is in progress.
        try:
            args.check_online.parent.mkdir(parents=True,exist_ok=True)
            with args.check_online.open('x',encoding='utf-8') as output:
                json.dump(report,output,ensure_ascii=False)
        except OSError as error:
            parser.exit(1,'无法创建新的联网检查报告：'+str(error)+'\n')
        if not report['ok']:parser.exit(1)
        return
    if args.install_live_mod:
        if args.folder or args.output:
            parser.error("--install-live-mod 不能与扫描参数组合")
        from companion import install_companion
        try:
            print(install_companion(args.install_live_mod))
        except (OSError,ValueError) as error:
            parser.exit(1,str(error)+"\n")
        return
    if args.folder is None:
        if args.output:
            parser.error("--output 需要指定模组目录")
        gui()
        return
    if not args.output:
        parser.error("命令行扫描需要 -o 输出文件")
    try:
        source = Path(args.folder).resolve()
        if args.output.resolve().is_relative_to(source):
            raise ValueError("输出文件必须在模组目录以外")
        report = scan(source)
        if args.raw:
            export_report(report, args.output)
        else:
            from workbench import Project, export_csv
            project = Project(report,source_language=args.source_language,target_language=args.target_language)
            if args.output.suffix.lower() == ".csv":
                export_csv(project, args.output)
            elif args.output.suffix.lower() == ".json":
                project.save(args.output)
            else:
                raise ValueError("仅支持 .csv / .json")
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"扫描 {report.scanned} 文件，提取 {len(report.entries)} 条，诊断 {len(report.diagnostics)} 条。")
    for issue in report.diagnostics:
        print(f"  {issue['file']}: {issue['message']}")
    # Distinguish incomplete inventory in automation.
    if report.diagnostics:
        parser.exit(2)


if __name__ == "__main__":
    main()
