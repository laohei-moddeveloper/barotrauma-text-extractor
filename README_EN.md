# AbyssText · Barotrauma localization workbench

[中文](README.md)

Version 0.2 development preview. A standalone desktop editor with an optional LuaCs client companion. This branch has not replaced the existing v0.1 Windows release or Workshop listing. Python 3.12+, Tkinter; standard-library runtime.

Run `python app.py`. Open a mod, select source/target languages, extract, filter/search, draft or edit, review, export. Switch the interface between Chinese and English without changing source or translation data.

Exact source duplicates share one row with all file/line/key contexts retained. Split meanings by context when necessary. Static XML/Lua/C# analysis distinguishes localization references and likely displayed text from low-confidence candidates. Filelist filtering applies to XML only; script execution and visibility are not proven.

Source detection prioritizes language-pack metadata, with conservative Japanese/Korean/CJK character hints. Untagged Latin languages need manual selection. Translation memory and drafts are isolated by project language pair. This is not a universal per-sentence language detector.

Edit targets, notes and glossary; inspect XML/layout previews; check placeholders, repeated markers, whitespace, line breaks and invalid XML characters before review. Export project JSON, reversible CSV, a native localization package, or a translated mod copy. Only reviewed, format-valid translations enter final exports. Source mods remain read-only; uncertain replacements are reported.

Offline translation-memory reuse is the default. An optional OpenAI-compatible provider can use an already running local Ollama model or your own remote service. No model downloads, bundled API credit, automatic paid retries or persisted API keys. Remote providers can charge you; none were called during cloud development.

## Optional in-game preview

Use **Connect game** to install the bundled AbyssTextLive into a new LocalMods folder or connect an existing installation. Install LuaCs client and enable the companion in game. Keep the desktop app running; choose a language pair and offline/local provider, then click **AbyssText · Translate** in game.

The client captures loaded language keys, native GUI text and selected plain-string font calls. Its own local JSON files carry requests/results. Translations update its native text pack, native controls and original font-call parameters, without a subtitle overlay or changes to other mods. Automatic game requests are limited to offline or loopback endpoints. Click again to restore, or use F3 commands `abyss_translate`, `abyss_stop`, `abyss_apply`.

Auto uses the game's default source language, usually English. Select other sources manually. The game should use your target language for native language-key overrides. Stop/restart preview after changing language pairs.

**Experimental: not validated in the real game.** Isolated LuaCs-fork tests pass, but actual API compatibility, font fallback, resizing and other hooks still require local verification. Images, unvisited screens, custom renderers and direct colored-font index calls are not covered; cached screens may need reopening. See [validation and limitations](docs/VALIDATION-v0.2.md).

## Checks and build

```console
python -m unittest discover -s tests -v
python tools/check_workbench_ui.py
python tools/benchmark.py
python app.py examples/workbench --source-language Auto --target-language French -o ../project.json
```

Run `build-windows.bat` on Windows to create `dist/BarotraumaTextExtractor.exe` with bundled companion resources. No game DLL, model or third-party mod content is bundled. CLI `--raw` exports ungrouped scanner evidence. Outputs must be outside the source mod. Exit codes: 0 clean, 1 failed, 2 exported with diagnostics/incomplete coverage.

Background work, cancellation, hash-based parse cache, debounced search and 150-row pagination keep the interface responsive. Synthetic results are recorded in the validation document, not claimed as real-world precision/recall.

The scanner never executes scripts. It does not implement full AST/type analysis or unpack DLLs, images or submarine files. It rejects symlinks, DTD/entities and oversized files; supports UTF-8 and BOM-marked UTF-16. Dynamic text can be missed. No guarantee of universal coverage or bug-free operation is claimed.
