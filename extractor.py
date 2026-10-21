"""Read-only, evidence-based Barotrauma mod text inventory (stdlib only)."""
from __future__ import annotations

import bisect
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from xml.parsers import expat


VERSION = "0.2.0-rc2"
MAX_BYTES = 16 * 1024 * 1024


@dataclass
class Entry:
    id: str
    file: str
    line: int
    column: int
    category: str
    kind: str  # literal / reference / candidate
    text: str
    key: str = ""
    language: str = ""
    context: str = ""
    evidence: str = ""
    resolved: list[dict] = field(default_factory=list)
    translation: str = ""
    location: dict = field(default_factory=dict)


@dataclass
class Report:
    root: str
    entries: list[Entry] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    scanned: int = 0
    skipped: int = 0
    fingerprints: dict = field(default_factory=dict)

    def issue(self, file, message):
        self.diagnostics.append({"file": str(file), "message": message})

    def add(self, file, line, column, category, kind, text, **kwargs):
        if not text.strip():
            return
        identity = f"{file}\0{line}\0{column}\0{category}\0{text}"
        self.entries.append(Entry(hashlib.sha256(identity.encode()).hexdigest()[:20],
                                  file, line, column, category, kind, text, **kwargs))


# Context-specific fields: 'name' is deliberately NOT a global display field.
NAMES = {"item": "物品", "character": "生物/角色", "affliction": "症状",
         "job": "职业", "talent": "天赋", "talenttree": "天赋树",
         "mission": "任务", "locationtype": "地点", "order": "指令",
         "faction": "阵营", "ability": "能力", "recipe": "配方"}
DIALOGUE = {"conversationaction", "option", "forcesayaction", "messageboxaction",
            "tutorialsegment", "infotextaction", "showmessageaction"}
VISIBLE_FIELDS = {"description", "tooltip", "header", "buttontext", "displayname",
                  "name", "text", "message", "successtext", "failuretext"}
REFERENCE_FIELDS = {"nameidentifier", "descriptionidentifier", "textidentifier",
                    "texttag", "nametag", "descriptiontag", "messagetag"}
KEY_SHAPE = re.compile(r"^[A-Za-z_][\w.:-]*$")
PATH_SHAPE = re.compile(r"(?:[/\\]|\.(?:png|ogg|wav|xml|dll|lua|cs|jpg|sub)$)", re.I)


def decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def xml_entries(source: str, file: str, report: Report):
    """Expat supplies exact element positions and rejects malformed XML and DTDs."""
    parser = expat.ParserCreate()
    stack = []
    language = ""
    pack_depth = None
    raw = source.encode("utf-8")
    line_starts = [0] + [m.end() for m in re.finditer(r"\r\n|\r|\n", source)]

    def reject(*_):
        raise ValueError("禁止 DTD/实体声明；未读取外部实体")

    def start(tag, attrs):
        nonlocal language, pack_depth
        lower = tag.lower()
        attrs_lower = {k.lower(): v for k, v in attrs.items()}
        parent = stack[-1] if stack else None
        line, column = parser.CurrentLineNumber, parser.CurrentColumnNumber + 1
        context = "/".join(n["tag"] for n in stack) + "/" + tag
        node = {"tag": tag, "text": [], "line": line, "column": column,
                "attrs": attrs_lower, "context": context, "has_children": False}
        if parent:
            parent["has_children"] = True
        stack.append(node)
        if lower == "infotexts":
            language = attrs_lower.get("language", "unknown")
            pack_depth = len(stack)
            return
        owner = attrs_lower.get("identifier", "")
        # Attribute positions include multiline start tags; scan only this opening tag.
        attr_spans = {}
        attr_locations = {}
        opening = re.compile(rb"<[^\s/>]+(?:\s+[^\s=/>]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*\s*/?>").match(raw, parser.CurrentByteIndex)
        if opening:
            opening_text = opening[0].decode("utf-8")
            node["content_start"] = line_starts[line - 1] + column - 1 + len(opening_text)
            for match in re.finditer(r"([^\s=<>/]+)\s*=\s*([\"'])(.*?)\2", opening_text, re.S):
                prefix = opening_text[:match.start(3)]
                attr_spans[match[1].lower()] = (
                    line + prefix.count("\n"),
                    len(prefix.rsplit("\n", 1)[-1]) + (column if "\n" not in prefix else 1))
                offset = line_starts[line - 1] + column - 1 + match.start(3)
                attr_locations[match[1].lower()] = {"start": offset, "end": offset + len(match[3]),
                    "format": "xml-attribute", "quote": match[2]}
        if pack_depth is not None:
            return
        for attr, value in attrs_lower.items():
            category = ""
            kind = "literal"
            evidence = ""
            if attr in REFERENCE_FIELDS:
                category, kind = "本地化引用", "reference"
                evidence = f"XML 本地化引用字段 {tag}.{attr}"
            elif (lower in NAMES and attr in {"name", "description", "displayname"}):
                category = NAMES[lower] + ("介绍" if attr == "description" else "名称")
            elif lower in DIALOGUE and attr in VISIBLE_FIELDS:
                category = "对话/提示"
            elif lower in {"textdisplay", "terminal", "custominterface", "button", "textbox"} and attr in {"text", "buttontext", "tooltip", "header"}:
                category = "交互界面"
            elif attr in {"displayname", "tooltip"}:
                category, kind = "其他显示字段", "candidate"
            elif attr in VISIBLE_FIELDS and value.strip() and not PATH_SHAPE.search(value):
                # Unknown mod component fields remain visible for review, never asserted as UI.
                category, kind = "XML 待核查字段", "candidate"
            if category:
                location = dict(attr_locations.get(attr, {}))
                # Confirmed fallback keys from public ItemPrefab / AfflictionPrefab.
                if lower == "item" and attr == "name" and owner:
                    location["native_key"] = "entityname." + attrs_lower.get("nameidentifier", owner)
                if lower == "affliction" and attr in {"name", "description"} and owner:
                    location["native_key"] = ("afflictionname." if attr == "name" else "afflictiondescription.") + attrs_lower.get("translationoverride", owner)
                reference_key = value
                if lower == "item" and attr == "nameidentifier":
                    reference_key = "entityname." + value
                evidence = evidence or f"XML 字段规则 {tag}.{attr}；实际可见性取决于运行条件"
                row, col = attr_spans.get(attr, (line, column))
                report.add(file, row, col, category, kind, value,
                           key=reference_key if kind == "reference" else "", context=context + (f" [{owner}]" if owner else "") + "@" + attr,
                           evidence=evidence, location=location)
        # Implicit engine localization keys are references, not invented original text.
        prefixes = {"item": "entityname", "character": "entityname", "affliction": "afflictionname", "job": "jobname", "talent": "talentname"}
        if owner and lower in prefixes and not attrs_lower.get("name") and not attrs_lower.get("nameidentifier"):
            key = prefixes[lower] + "." + (attrs_lower.get("translationoverride", owner) if lower == "affliction" else owner)
            report.add(file, line, column, NAMES[lower] + "名称", "reference", key,
                       key=key, context=context, evidence="按常见游戏命名约定推导的查找键；需核对游戏版本、继承及覆盖")

    def end(tag):
        nonlocal pack_depth, language
        node = stack.pop()
        text = "".join(node["text"])
        if pack_depth is not None and len(stack) >= pack_depth and tag.lower() != "override" and not node["has_children"]:
            finish = line_starts[parser.CurrentLineNumber - 1] + parser.CurrentColumnNumber
            location = {"start": node.get("content_start", finish), "end": finish, "format": "xml-text"}
            report.add(file, node["line"], node["column"], "语言表", "literal", text,
                       key=tag, language=language, context=node["context"], evidence="原生 infotexts 语言表条目", location=location)
        elif pack_depth is None and text.strip():
            report.add(file, node["line"], node["column"], "XML 节点正文", "candidate", text,
                       context=node["context"], evidence="节点正文；需核查是否为玩家显示文本")
        if pack_depth is not None and len(stack) < pack_depth:
            pack_depth, language = None, ""

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = lambda text: stack[-1]["text"].append(text) if stack else None
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(source, True)


@dataclass
class Token:
    value: str
    offset: int
    string: bool = False
    dynamic: bool = False
    end: int = 0


def tokens(source: str, lua: bool):
    """Small lexer, not a Lua/C# compiler. Preserves strings; skips comments."""
    result = []
    i = 0
    while i < len(source):
        if source[i].isspace():
            i += 1
            continue
        if (lua and source.startswith("--", i)) or (not lua and source.startswith("//", i)):
            if lua and (long := re.compile(r"--\[(=*)\[").match(source, i)):
                finish = source.find("]" + long[1] + "]", i + len(long[0]))
                if finish < 0:
                    raise ValueError("未闭合 Lua 长注释")
                i = finish + len(long[1]) + 2
            else:
                finish = source.find("\n", i)
                i = len(source) if finish < 0 else finish
            continue
        if not lua and source.startswith("/*", i):
            finish = source.find("*/", i + 2)
            if finish < 0:
                raise ValueError("未闭合 C# 注释")
            i = finish + 2
            continue
        if lua and (long := re.compile(r"\[(=*)\[").match(source, i)):
            begin = i + len(long[0])
            finish = source.find("]" + long[1] + "]", begin)
            if finish < 0:
                raise ValueError("未闭合 Lua 长字符串")
            value = re.sub(r"\r\n|\n\r|\r", "\n", source[begin:finish])
            result.append(Token(value.removeprefix("\n"), i, True, end=finish + len(long[1]) + 2))
            i = finish + len(long[1]) + 2
            continue
        # Raw/interpolated C# strings are retained as review candidates.
        raw_match = re.compile(r'(\$*)("{3,})').match(source, i) if not lua else None
        if raw_match:
            begin = i + len(raw_match[0])
            finish = source.find(raw_match[2], begin)
            if finish < 0:
                raise ValueError("未闭合 C# 原始字符串")
            result.append(Token(source[begin:finish], i, True, True, finish + len(raw_match[2])))
            i = finish + len(raw_match[2])
            continue
        match = re.compile(r'(?:(?:\$@|@\$|@|\$)?")|\'').match(source, i)
        if match:
            prefix = match[0]
            quote = prefix[-1]
            verbatim = "@" in prefix and not lua
            begin = i
            i += len(prefix)
            chars = []
            while i < len(source):
                ch = source[i]
                if ch == quote:
                    if verbatim and source[i:i + 2] == '""':
                        chars.append('"'); i += 2; continue
                    i += 1
                    break
                if ch == "\\" and not verbatim:
                    escape = re.compile(r'\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2}|[0-9]{1,3}|.)', re.S).match(source, i)
                    if not escape:
                        raise ValueError("字符串末尾转义不完整")
                    value = escape[0][1:]
                    common = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0"}
                    if value in common:
                        chars.append(common[value])
                    elif value[0] in "uUx":
                        chars.append(chr(int(value[1:], 16)))
                    elif value.isdigit() and lua:
                        chars.append(chr(int(value)))
                    else:
                        chars.append("\\" + value)
                    i += len(escape[0]); continue
                chars.append(ch); i += 1
            else:
                raise ValueError("未闭合字符串")
            # Single quotes in C# are char literals, not localizable strings.
            if lua or quote == '"':
                result.append(Token("".join(chars), begin, True, "$" in prefix, i))
            continue
        identifier = re.compile(r"[A-Za-z_][\w]*").match(source, i)
        value = identifier[0] if identifier else source[i]
        result.append(Token(value, i))
        i += len(value)
    return result


# Zero-based argument indexes. All script hits remain candidates: execution and
# data flow cannot be established by this lexical pass.
SINKS = {"GUI.TextBlock": {1}, "GUI.Button": {1}, "GUITextBlock": {1},
         "GUIButton": {1}, "GUIMessageBox": {0, 1}, "GUI.MessageBox": {0, 1},
         "Character.Speak": {0}, "Speak": {0}, "ChatMessage.Create": {0, 1},
         "Game.SendDirectChatMessage": {0, 1}, "Game.SendMessage": {0},
         "Networking.SendChatMessage": {0}}


def script_entries(source, file, report):
    stream = tokens(source, file.lower().endswith(".lua"))
    # Fold only adjacent constant strings. Never evaluate code or expressions.
    folded = []
    cursor = 0
    lua = file.lower().endswith(".lua")
    while cursor < len(stream):
        token = stream[cursor]
        cursor += 1
        if token.string and not token.dynamic:
            combined = token.value
            finish = token.end
            while cursor < len(stream):
                width = 2 if lua else 1
                operator = [t.value for t in stream[cursor:cursor+width]]
                expected = [".","."] if lua else ["+"]
                next_index = cursor + width
                if operator != expected or next_index >= len(stream): break
                other = stream[next_index]
                if not other.string or other.dynamic: break
                combined += other.value
                finish = other.end
                cursor = next_index + 1
            token = Token(combined,token.offset,True,False,finish)
        folded.append(token)
    stream = folded
    lines = [i for i, ch in enumerate(source) if ch == "\n"]
    source_lines = source.splitlines()
    frames = []
    bindings = {}
    for i, token in enumerate(stream):
        if token.value == "(" and not token.string:
            parts = []
            j = i - 1
            if j >= 0 and re.fullmatch(r"[\w]+", stream[j].value) and not stream[j].string:
                parts.append(stream[j].value)
                j -= 1
                while j >= 1 and stream[j].value in {".", ":"} and re.fullmatch(r"[\w]+", stream[j - 1].value) and not stream[j - 1].string:
                    parts.extend([stream[j].value, stream[j - 1].value])
                    j -= 2
            name = "".join(reversed(parts)).replace(":", ".")
            frames.append([name, 0, "("])
        elif token.value in {"[", "{"} and not token.string:
            frames.append(["", 0, token.value])
        elif token.value in {")", "]", "}"} and not token.string:
            if frames:
                frames.pop()
        elif token.value == "," and not token.string and frames:
            frames[-1][1] += 1
        if not token.string:
            if token.value == "=" and i >= 1:
                bindings.pop(stream[i - 1].value,None)
            if frames and frames[-1][0] in SINKS and frames[-1][1] in SINKS[frames[-1][0]] and token.value in bindings:
                entry = bindings[token.value]
                entry.category = "脚本显示流向"
                entry.evidence += f"；同文件字面量变量传入 {frames[-1][0]}，仍需核查作用域与运行分支"
        if not token.string or not token.value.strip():
            continue
        name, arg, _ = frames[-1] if frames else ("", 0, "")
        row = bisect.bisect_left(lines, token.offset) + 1
        col = token.offset - (lines[row - 2] if row > 1 else -1)
        category, kind, key = "脚本待核查", "candidate", ""
        evidence = "字符串字面量；未追踪变量、函数封装及运行分支"
        if name in {"Text.Get", "Text.GetWithVariable", "Text.GetWithVariables"} and arg == 0 and not token.dynamic:
            previous = stream[i - 1].value if i else ""
            following = stream[i + 1].value if i + 1 < len(stream) else ""
            if previous == "(" and following in {",", ")"}:
                category, kind, key = "本地化引用", "reference", token.value
                evidence = f"{name} 的第 1 个字面量参数"
            else:
                category = "动态本地化键片段"
                evidence = f"{name} 首参数表达式中的字面量片段；未计算完整键"
        elif (name in SINKS and arg in SINKS[name]) or (name.endswith(".Speak") and arg == 0):
            category = "脚本显示调用"
            evidence = f"显示接口 {name} 第 {arg + 1} 个参数中的字符串；需核对签名与动态拼接"
        elif i >= 2 and stream[i - 1].value == "=" and stream[i - 2].value.lower() in {"text", "tooltip", "description", "displayname"}:
            category = "脚本显示赋值"
            evidence = "显示相关同名属性/变量赋值；对象类型与实际用途待核查"
        elif KEY_SHAPE.fullmatch(token.value) or PATH_SHAPE.search(token.value):
            # Keep these in the inventory for recall, but separate from useful prose.
            category = "脚本标识符/路径候选"
        if token.dynamic:
            kind, key = "candidate", ""
            evidence += "；插值/原始字符串未解析运行时表达式"
        report.add(file, row, col, category, kind, token.value, key=key,
                   context=source_lines[row - 1][:500], evidence=evidence,
                   location={"start": token.offset, "end": token.end,
                             "format": "dynamic" if token.dynamic else ("lua-string" if file.lower().endswith(".lua") else "cs-string")})
        if i >= 2 and stream[i-1].value == "=" and re.fullmatch(r"[A-Za-z_]\w*",stream[i-2].value) and (i<3 or stream[i-3].value not in {".",":"}):
            bindings[stream[i-2].value] = report.entries[-1]


def scan(root: Path, cancel=None, cache=None, progress=None, registered_only=False) -> Report:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("请选择存在的模组目录")
    report = Report(str(root))
    registered = None
    manifest = root/"filelist.xml"
    if registered_only and manifest.is_file() and not manifest.is_symlink():
        try:
            parser = expat.ParserCreate()
            registered = {"filelist.xml"}
            def resource(tag, attrs):
                value = next((v for k,v in attrs.items() if k.lower()=="file"),"")
                if not value or not value.lower().endswith(".xml"): return
                value=value.replace("\\","/").replace("%ModDir%/","")
                candidate=(root/value).resolve()
                if not candidate.is_relative_to(root) or "%" in value:
                    report.issue("filelist.xml","外部或无法解析的 XML 资源引用："+value)
                    return
                registered.add(candidate.relative_to(root).as_posix())
                if not candidate.is_file():report.issue(value,"清单引用的 XML 文件不存在")
            parser.StartElementHandler=resource
            def reject(*_):raise ValueError("清单不支持 DTD / 实体声明")
            parser.StartDoctypeDeclHandler=reject
            if manifest.stat().st_size>MAX_BYTES:raise ValueError("清单超过大小限制")
            parser.Parse(decode(manifest.read_bytes()),True)
        except (OSError,ValueError,expat.ExpatError) as error:
            registered=None
            report.issue("filelist.xml","无法确定资源范围，改为完整扫描："+str(error))
    # No symlink traversal, script execution, network access, or source modification.
    import os
    for base, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: report.issue(e.filename, str(e))):
        dirs[:] = sorted(d for d in dirs if d not in {".git", "__pycache__"} and not (Path(base) / d).is_symlink())
        for name in sorted(files):
            if cancel and cancel():
                report.issue("", "用户取消；报告不完整")
                return report
            path = Path(base) / name
            relative = path.relative_to(root).as_posix()
            if registered is not None and path.suffix.lower()==".xml" and relative not in registered:
                report.skipped+=1
                continue
            if path.suffix.lower() not in {".xml", ".lua", ".cs"}:
                report.skipped += 1
                if path.suffix.lower() in {".dll", ".sub"}:
                    report.issue(relative, "不支持编译程序集/潜艇压缩内容，可能含有未提取文字")
                continue
            start = len(report.entries)
            try:
                if path.is_symlink():
                    raise ValueError("跳过符号链接")
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError("文件超过 16 MiB 限制，未扫描")
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                report.fingerprints[relative] = digest
                source = decode(data)
                cache_key = (str(root), relative, digest)
                if cache is not None and cache_key in cache:
                    import copy
                    report.entries.extend(copy.deepcopy(cache[cache_key]))
                elif path.suffix.lower() == ".xml":
                    xml_entries(source, relative, report)
                else:
                    script_entries(source, relative, report)
                if cache is not None and cache_key not in cache:
                    import copy
                    cache[cache_key] = copy.deepcopy(report.entries[start:])
                report.scanned += 1
                if progress:
                    progress(relative, report.scanned)
            except (OSError, UnicodeError, ValueError, expat.ExpatError) as error:
                del report.entries[start:]  # Never present a broken file as completely parsed.
                report.issue(relative, str(error))
    tables = {}
    for entry in report.entries:
        if entry.category == "语言表":
            tables.setdefault(entry.key.lower(), []).append({"language": entry.language,
                "text": entry.text, "file": entry.file, "line": entry.line})
    for entry in report.entries:
        if entry.kind == "reference":
            entry.resolved = tables.get(entry.key.lower(), [])
        elif entry.category == "对话/提示" and KEY_SHAPE.fullmatch(entry.text) and entry.text.lower() in tables:
            entry.kind, entry.key = "reference", entry.text
            entry.resolved = tables[entry.text.lower()]
            entry.evidence += "；值与模组语言表键匹配，按引用展示（同名原文仍需核查）"
    return report


def export_report(report: Report, path: Path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps({"version": VERSION, **asdict(report)}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif path.suffix.lower() == ".csv":
        # UTF-8 BOM for Excel; neutralize spreadsheet formula execution.
        def safe(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(Entry.__dataclass_fields__))
            writer.writeheader()
            for entry in report.entries:
                values = asdict(entry)
                values["resolved"] = json.dumps(values["resolved"], ensure_ascii=False)
                values["location"] = json.dumps(values["location"], ensure_ascii=False)
                writer.writerow({key: safe(value) for key, value in values.items()})
        # Diagnostics must travel with the spreadsheet, rather than silently vanish.
        path.with_suffix(".diagnostics.json").write_text(json.dumps({"root": report.root,
            "scanned": report.scanned, "skipped": report.skipped,
            "diagnostics": report.diagnostics}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        raise ValueError("仅支持 .json / .csv")
