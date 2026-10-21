"""Translation units, review, persistence and safe exports. No UI/network side effects."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass, field
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET

from extractor import Entry, Report, VERSION, decode
from languages import canonical_language, detect_language

SOURCE_LANGUAGES = {"english", "en", "en-us", "en-gb", ""}
TARGET_LANGUAGES = {"simplified chinese", "简体中文", "中文(简体)", "zh", "zh-cn", "schinese"}
STATES = ("未翻译", "草稿", "已校对", "忽略")
PLACEHOLDER = re.compile(r"\[[^\]\n]+\]|\{(?:\{[^{}]*\}|[^{}]+)\}|%(?:\d+\$)?[-+#0 \d.]*(?:[sdifouxXeEgGc]|%)|‖[^‖]+‖|</?[A-Za-z][^>]*>")
XML_KEY = re.compile(r"^[A-Za-z_][\w.\-]*$")


def source_id(text,language="English"):
    # No whitespace/case normalization: punctuation and significant spaces matter.
    prefix="" if canonical_language(language)=="English" else canonical_language(language)+"\0"
    return hashlib.sha256((prefix+text).encode("utf-8")).hexdigest()[:24]


def category(entry):
    if entry.category == "语言表":
        key = entry.key.lower()
        for prefix, label in [("entityname.", "物品 / 生物"), ("entitydescription.", "描述 / 提示"),
                              ("affliction", "症状 / 效果"), ("talent", "职业 / 天赋"),
                              ("job", "职业 / 天赋"), ("mission", "任务 / 对话"), ("event", "任务 / 对话")]:
            if key.startswith(prefix): return label
        return "界面 / 语言表"
    text = entry.category
    for word, label in [("物品", "物品 / 生物"), ("生物", "物品 / 生物"), ("症状", "症状 / 效果"),
                         ("天赋", "职业 / 天赋"), ("职业", "职业 / 天赋"), ("对话", "任务 / 对话")]:
        if word in text: return label
    if entry.kind == "candidate": return "脚本 / 待核查"
    return "描述 / 提示"


def quality(source, translation):
    issues = []
    if not translation.strip(): return ["译文为空"]
    if Counter(PLACEHOLDER.findall(source)) != Counter(PLACEHOLDER.findall(translation)):
        issues.append("占位符或格式标记不一致")
    if re.match(r"^\s*",source)[0] != re.match(r"^\s*",translation)[0] or re.search(r"\s*$",source)[0] != re.search(r"\s*$",translation)[0]:
        issues.append("首尾空白发生变化")
    if source.count("\n") != translation.count("\n"):
        issues.append("换行数量不同")
    if source == translation and re.search(r"[a-z]{3}", source): issues.append("译文与英文原文相同")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]",translation): issues.append("包含无效 XML / 控制字符")
    return issues


@dataclass
class Unit:
    id: str
    source: str
    translation: str = ""
    state: str = "未翻译"
    notes: str = ""
    occurrences: list[Entry] = field(default_factory=list)
    origin: str = ""
    source_language: str = "English"

    @property
    def categories(self): return sorted({category(e) for e in self.occurrences})

    @property
    def keys(self):
        return sorted({e.key for e in self.occurrences if e.key and (e.category == "语言表" or e.kind == "reference")} |
                      {e.location["native_key"] for e in self.occurrences if e.location.get("native_key")})

    @property
    def candidate(self):
        return all(e.kind == "candidate" and e.category not in {"脚本显示调用", "脚本显示流向"} for e in self.occurrences)

    @property
    def issues(self): return quality(self.source, self.translation) if self.translation else []


class Project:
    def __init__(self, report: Report, previous=None, source_language=None, target_language=None):
        self.report = report
        self.source_choice=canonical_language(source_language or (previous.source_choice if previous else "English"))
        self.target_language=canonical_language(target_language or (previous.target_language if previous else "Simplified Chinese"))
        self.source_language,self.detection=(detect_language(report.entries,self.target_language) if self.source_choice=="Auto" else (self.source_choice,"用户指定"))
        keep_previous=bool(previous and previous.target_language==self.target_language and previous.source_language==self.source_language)
        self.units: list[Unit] = []
        self.unresolved = []
        self.memory = {}
        self.glossary = {}
        self.path = None
        self.dirty = False
        groups = {}
        chinese = defaultdict(set)
        for e in report.entries:
            if e.category == "语言表" and canonical_language(e.language)==self.target_language:
                chinese[e.key.casefold()].add(e.text)
        for e in report.entries:
            if e.kind == "reference":
                texts = {r["text"] for r in e.resolved if canonical_language(r["language"])==self.source_language}
                if not texts:
                    self.unresolved.append(e)
                    continue
            else:
                if e.language and canonical_language(e.language)!=self.source_language: continue
                texts = {e.text}
            for text in texts:
                # Keep exact source duplicates only once, with every location attached.
                if text not in groups:
                    groups[text] = Unit(source_id(text,self.source_language), text,source_language=self.source_language)
                groups[text].occurrences.append(e)
        self.units = list(groups.values())
        old = {u.id: u for u in previous.units} if keep_previous else {}
        if keep_previous:
            self.memory = dict(previous.memory)
            self.glossary = dict(previous.glossary)
        for unit in self.units:
            if unit.id in old:
                prior = old[unit.id]
                unit.translation, unit.state, unit.notes, unit.origin = prior.translation, prior.state, prior.notes, prior.origin
            else:
                choices = set().union(*(chinese.get(k.casefold(), set()) for k in unit.keys)) if unit.keys else set()
                if len(choices) == 1:
                    unit.translation, unit.state, unit.origin = choices.pop(), "草稿", "模组已有目标译文"
                elif len(choices) > 1:
                    unit.notes = "同一原文对应多个已有目标译文，请按上下文校对或拆分语境。"
        # Keep explicitly split homonyms split across a rescan / moved project.
        if keep_previous:
            splits = defaultdict(list)
            for prior in previous.units:
                if "." in prior.id:splits[prior.source].append(prior)
            rebuilt = []
            for unit in self.units:
                priors=splits.get(unit.source)
                if not priors:
                    rebuilt.append(unit);continue
                remaining=list(unit.occurrences)
                for prior in priors:
                    signatures={(e.file,e.key or e.context) for e in prior.occurrences}
                    matching=[e for e in remaining if (e.file,e.key or e.context) in signatures]
                    if not matching:continue
                    rebuilt.append(Unit(prior.id,unit.source,prior.translation,prior.state,prior.notes,matching,prior.origin,self.source_language))
                    remaining=[e for e in remaining if e not in matching]
                if remaining:rebuilt.append(Unit(unit.id,unit.source,occurrences=remaining,source_language=self.source_language))
            self.units=rebuilt
        self._index()

    def _index(self):
        self.by_id = {u.id: u for u in self.units}
        self.search_index = {u.id: (u.source + " " + u.translation + " " + " ".join(u.keys) + " " +
                            " ".join(e.file + " " + e.context for e in u.occurrences) + " " + u.notes).casefold() for u in self.units}

    def update(self, unit_id, translation, state=None, notes=None):
        unit = self.by_id[unit_id]
        if state is not None and state not in STATES: raise ValueError("未知校对状态")
        if state == "已校对" and quality(unit.source, translation):
            raise ValueError("请先处理质量检查：" + "；".join(quality(unit.source, translation)))
        unit.translation = translation
        unit.state = state or ("草稿" if translation else "未翻译")
        if notes is not None: unit.notes = notes
        if unit.state == "已校对": self.memory[unit.source] = translation
        self.search_index[unit.id] = (unit.source + " " + translation + " " + " ".join(unit.keys) + " " +
            " ".join(e.file + " " + e.context for e in unit.occurrences) + " " + unit.notes).casefold()
        self.dirty = True

    def filtered(self, query="", category_name="全部文本", state="全部状态", candidates=False):
        words = query.casefold().split()
        return [u for u in self.units if (candidates or not u.candidate)
                and (category_name == "全部文本" or category_name in u.categories)
                and (state == "全部状态" or (state == "有质量问题" and u.issues) or state == u.state)
                and all(word in self.search_index[u.id] for word in words)]

    def draft_local(self, units):
        found = []
        for unit in units:
            text = self.memory.get(unit.source) or self.glossary.get(unit.source)
            if not unit.translation and text:
                self.update(unit.id, text)
                unit.origin = "译文记忆 / 术语表"
                found.append(unit.id)
        return found

    def split_context(self, unit_id):
        """Homonyms: user can explicitly split grouped source by file/key."""
        unit = self.by_id[unit_id]
        buckets = defaultdict(list)
        for entry in unit.occurrences:
            buckets[(entry.file, entry.key or entry.context)].append(entry)
        if len(buckets) < 2: return False
        self.units.remove(unit)
        for index, entries in enumerate(buckets.values()):
            clone = Unit(unit.id + "." + str(index), unit.source, unit.translation, "草稿" if unit.translation else "未翻译", unit.notes, entries, unit.origin,unit.source_language)
            self.units.append(clone)
        self._index()
        self.dirty = True
        return True

    def save(self, path):
        path = outside_source(self.report, Path(path))
        payload = {"format": "abysstext-project-2", "version": VERSION, "report": asdict(self.report),
                   "units": [asdict(u) for u in self.units], "memory": self.memory, "glossary": self.glossary,
                   "source_language":self.source_choice,"target_language":self.target_language}
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        self.path, self.dirty = path, False

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 128 * 1024 * 1024: raise ValueError("工程文件过大")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data,dict) or data.get("format") != "abysstext-project-2": raise ValueError("不支持的工程文件")
        raw = data["report"]
        report = Report(**{**raw, "entries": [Entry(**e) for e in raw["entries"]]})
        project = cls(report,source_language=data.get("source_language","English"),target_language=data.get("target_language","Simplified Chinese"))
        project.units = [Unit(**{**u, "occurrences": [Entry(**e) for e in u["occurrences"]]}) for u in data["units"]]
        if any(u.state not in STATES for u in project.units): raise ValueError("工程包含无效校对状态")
        project.memory, project.glossary = data.get("memory", {}), data.get("glossary", {})
        project.path = path
        project._index()
        return project

    def import_table(self, path):
        path = Path(path)
        if path.stat().st_size > 32 * 1024 * 1024: raise ValueError("导入文件过大")
        if path.suffix.casefold() == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k,v in data.items()):
                raise ValueError("术语表应为 原文:译文 的 JSON 对象")
            self.glossary.update(data)
            self.dirty = True
            return len(data)
        count = 0
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows=list(csv.DictReader(handle))
            for row in rows:
                if row.get("target_language") and canonical_language(row["target_language"])!=self.target_language:
                    raise ValueError("导入译文的目标语言与当前项目不一致")
                if row.get("source_language") and canonical_language(row["source_language"])!=self.source_language:
                    raise ValueError("导入译文的源语言与当前项目不一致")
            for row in rows:
                if row.get("abysstext_csv")=="1":
                    row={k:(v[1:] if isinstance(v,str) and v.startswith("'") else v) for k,v in row.items()}
                if row.get("target_language") and canonical_language(row["target_language"])!=self.target_language:
                    raise ValueError("导入译文的目标语言与当前项目不一致")
                source, target = row.get("source", row.get("text", "")), row.get("translation", "")
                if source and target:
                    self.memory[source] = target
                    # Import by stable ID first, preserving explicitly split homonyms.
                    matches = [self.by_id[row["id"]]] if row.get("id") in self.by_id else [u for u in self.units if u.source == source]
                    for unit in matches:
                        if not unit.translation: self.update(unit.id, target)
                    count += 1
        self.dirty = True
        return count


def outside_source(report, path):
    path = Path(path).resolve()
    if path.is_relative_to(Path(report.root).resolve()): raise ValueError("请保存到源模组目录之外")
    return path


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        name = Path(f.name)
        f.write(content)
    try: name.replace(path)
    finally: name.unlink(missing_ok=True)


def export_csv(project, path):
    path = outside_source(project.report, path)
    def safe(value):
        text = str(value)
        return "'" + text if text.startswith("'") or text.lstrip().startswith(("=", "+", "-", "@")) else text
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "source", "translation", "state", "categories", "keys", "occurrences", "notes", "abysstext_csv","source_language","target_language"])
        for u in project.units:
            writer.writerow([safe(x) for x in [u.id,u.source,u.translation,u.state," / ".join(u.categories),";".join(u.keys),
                json.dumps([{"file":e.file,"line":e.line,"context":e.context} for e in u.occurrences],ensure_ascii=False),u.notes,"1",u.source_language,project.target_language]])


def native_xml(project, include_drafts=False):
    texts, reasons = {}, []
    for unit in project.units:
        if not unit.translation or unit.state == "忽略": continue
        if unit.state != "已校对" and not include_drafts: continue
        if unit.issues:
            reasons.append({"source": unit.source, "reason": "；".join(unit.issues)})
            continue
        if not unit.keys:
            reasons.append({"source": unit.source, "reason": "硬编码文字没有已知本地化键，请导出翻译副本或人工适配"})
        for key in unit.keys:
            if not XML_KEY.fullmatch(key):
                reasons.append({"source":unit.source,"reason":"无效 XML 本地化键: "+key})
                continue
            folded = key.casefold()
            if folded in texts and texts[folded] != unit.translation:
                raise ValueError("本地化键译文冲突：" + key)
            texts[folded] = unit.translation
    target_language=getattr(project,"target_language","Simplified Chinese")
    root = ET.Element("infotexts", language=target_language, translatedname={"Simplified Chinese":"中文(简体)","Traditional Chinese":"中文(繁體)"}.get(target_language,target_language))
    if target_language in {"Simplified Chinese","Traditional Chinese","Japanese"}:root.set("nowhitespace","true")
    override = ET.SubElement(root, "Override")
    for key, text in sorted(texts.items()): ET.SubElement(override, key).text = text
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True), reasons, len(texts)


def export_native(project, target):
    target = outside_source(project.report, target)
    if target.exists(): raise ValueError("请选择尚不存在的新目录，避免覆盖已有文件")
    content, reasons, count = native_xml(project)
    if not count: raise ValueError("没有已校对且可导出的本地化键；请先校对，硬编码文字使用翻译副本")
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".abysstext-native-",dir=target.parent))
    try:
        atomic_write(stage/"Translations.xml", content)
        root = ET.Element("contentpackage", name="AbyssText 汉化", corepackage="False", modversion=VERSION)
        ET.SubElement(root,"Text",file="%ModDir%/Translations.xml")
        atomic_write(stage/"filelist.xml", ET.tostring(root, encoding="unicode", xml_declaration=True))
        atomic_write(stage/"export-report.json", json.dumps({"keys":count,"requires_manual_work":reasons},ensure_ascii=False,indent=2))
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return count, reasons


def replacement(entry, text, source):
    fmt = entry.location.get("format")
    if fmt in {"xml-text", "xml-attribute"}:
        escaped = html.escape(text, quote=fmt=="xml-attribute")
        if fmt=="xml-attribute": escaped = escaped.replace("\n", "&#10;").replace("\r", "&#13;").replace("\t", "&#9;")
        return escaped
    if fmt == "cs-string" and source[entry.location["start"]:entry.location["end"]].startswith('@"'):
        return '@"' + text.replace('"','""') + '"'
    if fmt in {"cs-string", "lua-string"}:
        return '"' + text.replace("\\","\\\\").replace('"','\\"').replace("\r","\\r").replace("\n","\\n").replace("\t","\\t") + '"'
    raise ValueError("动态字符串或缺少定位，无法安全替换")


def export_copy(project, target):
    """Translate a NEW full mod copy, checking source fingerprints before any write."""
    target = outside_source(project.report, target)
    source_root = Path(project.report.root).resolve()
    if target.exists(): raise ValueError("请选择尚不存在的新目录")
    edits, skipped = defaultdict(dict), []
    def checked_path(root,relative):
        normalized=relative.replace("\\","/")
        if Path(normalized).is_absolute() or ".." in Path(normalized).parts or ":" in normalized:
            raise ValueError("非法源文件路径")
        path=(root/normalized).resolve()
        if not path.is_relative_to(root):raise ValueError("非法源文件路径")
        return path
    for relative,digest in project.report.fingerprints.items():
        if hashlib.sha256(checked_path(source_root,relative).read_bytes()).hexdigest()!=digest:
            raise ValueError("源文件已变化，请重新扫描再导出："+relative)
    for unit in project.units:
        if unit.state != "已校对" or not unit.translation: continue
        if unit.issues: raise ValueError("仍有质量问题：" + unit.source[:50])
        for entry in unit.occurrences:
            if entry.kind == "reference" or entry.file == "<游戏内>": continue
            if entry.kind=="candidate" and entry.category not in {"脚本显示调用","脚本显示流向"} and not unit.candidate:
                skipped.append({"file":entry.file,"line":entry.line,"reason":"同文但用途未确认的内部候选，不随显示文字批量替换"})
                continue
            loc = entry.location
            if not loc or loc.get("format") == "dynamic":
                skipped.append({"file":entry.file,"line":entry.line,"reason":"缺少安全定位或动态表达式"})
                continue
            key = (loc["start"],loc["end"])
            previous = edits[entry.file].get(key)
            if previous and previous[1] != unit.translation: raise ValueError("同一源位置译文冲突")
            edits[entry.file][key] = (entry,unit.translation)
    prepared = {}
    for relative, changes in edits.items():
        path = checked_path(source_root,relative)
        if not path.is_relative_to(source_root) or path.is_symlink(): raise ValueError("非法源文件路径")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != project.report.fingerprints.get(relative):
            raise ValueError("源文件已变化，请重新扫描再导出："+relative)
        source = decode(data)
        previous_start = len(source)+1
        for (start,end),(entry,text) in sorted(changes.items(), reverse=True):
            if not 0 <= start < end <= len(source) or end > previous_start: raise ValueError("替换位置重叠或无效")
            source = source[:start] + replacement(entry,text,source) + source[end:]
            previous_start = start
        if data.startswith(b"\xff\xfe"): output = b"\xff\xfe"+source.encode("utf-16-le")
        elif data.startswith(b"\xfe\xff"): output=b"\xfe\xff"+source.encode("utf-16-be")
        else: output=(b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b"")+source.encode("utf-8")
        prepared[relative] = output
    # Reject links anywhere instead of following assets outside the chosen mod.
    if any(p.is_symlink() for p in source_root.rglob("*")): raise ValueError("源模组包含符号链接，未复制")
    if not prepared: raise ValueError("没有可安全替换的已校对条目")
    target.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".abysstext-export-",dir=target.parent))
    try:
        shutil.copytree(source_root,stage,dirs_exist_ok=True,ignore=shutil.ignore_patterns(".git","__pycache__"))
        for relative,digest in project.report.fingerprints.items():
            if hashlib.sha256(checked_path(stage,relative).read_bytes()).hexdigest()!=digest:
                raise ValueError("复制期间源文件发生变化，未导出："+relative)
        for relative,data in prepared.items(): (stage/relative).write_bytes(data)
        filelist = stage/"filelist.xml"
        if filelist.exists():
            # Minimal metadata edit: copied mod is a local fork, never reuse Workshop ID/hash.
            text = decode(filelist.read_bytes())
            text = re.sub(r'\s+(?:expectedhash|steamworkshopid)\s*=\s*([\"\']).*?\1',"",text,flags=re.I)
            filelist.write_text(text,encoding="utf-8")
        atomic_write(stage/"abysstext-export.json",json.dumps({"changed":sorted(prepared),"skipped":skipped,"version":VERSION},ensure_ascii=False,indent=2))
        stage.rename(target)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return len(prepared), skipped
