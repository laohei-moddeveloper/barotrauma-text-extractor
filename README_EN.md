# AbyssText · Barotrauma Text Extractor

[Steam Workshop / 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)
Extract first. Translate with context.

A standalone, read-only text inventory tool for Barotrauma mod translators. Scan XML, Lua and C#; inspect source locations and extraction evidence; export CSV or JSON with an empty translation column.

Download the Windows x64 ZIP from [v0.1.0 prerelease](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/releases/tag/v0.1.0), extract it and run `BarotraumaTextExtractor.exe`. Python is not required for the packaged app. Do not enable the Workshop package as an in-game mod: this is an external utility.

The 0.1.0 prototype uses static rules. It does not execute mod code, modify source files, translate automatically, write translations back, extract compiled DLL strings, or guarantee full coverage. Reference keys and review candidates are distinguished from literal text. Check diagnostics and confirm results against the actual mod/game version. GUI filters affect the view; exports include the entire inventory.

Source: Python 3.12+ standard library. Run `python app.py` for the desktop UI, or `python app.py examples -o inventory.json`. Export outside the input directory. Exit codes: 0 complete, 1 invalid arguments/export error, 2 exported with diagnostics. CSV is UTF-8 BOM and guards spreadsheet-formula prefixes; use JSON for exact text.

Test: `python -m unittest discover -s tests -v`. Build: `powershell -File build-windows.ps1 -Python python`. See [Chinese documentation](README.md) for extraction rules and limitations.
