"""Game language names, aliases and conservative metadata-based detection."""
from collections import Counter
import re

ALIASES = {
    "English": ("en", "en-us", "en-gb"),
    "Simplified Chinese": ("简体中文", "中文(简体)", "zh", "zh-cn", "schinese"),
    "Traditional Chinese": ("繁體中文", "繁体中文", "zh-tw", "tchinese"),
    "Japanese": ("ja", "japanese", "日本語"), "Korean": ("ko", "한국어"),
    "Russian": ("ru", "русский"), "German": ("de", "deutsch"),
    "French": ("fr", "français"), "Spanish": ("es", "español"),
    "Brazilian Portuguese": ("pt-br", "Portuguese"), "Polish": ("pl",),
    "Ukrainian": ("uk",), "Turkish": ("tr",), "Italian": ("it",),
    "Czech": ("cs",), "Hungarian": ("hu",), "Romanian": ("ro",),
}
NAMES = tuple(ALIASES)


def canonical_language(name):
    if name in {"Auto", "自动识别", "Auto-detect"}: return "Auto"
    folded=name.strip().casefold()
    for language,aliases in ALIASES.items():
        if folded==language.casefold() or folded in {a.casefold() for a in aliases}:return language
    return name.strip()


def detect_language(entries,target):
    counts=Counter(canonical_language(e.language) for e in entries if e.language)
    other={key:value for key,value in counts.items() if key!=target}
    if "English" in other:return "English", "语言表 language 属性"
    if other:return max(other,key=other.get), "语言表 language 属性"
    raw=" ".join(e.text for e in entries if not e.language)[:50000]
    if re.search(r"[ぁ-ゟァ-ヿ]",raw):return "Japanese", "脚本文字字符特征（候选）"
    if re.search(r"[가-힣]",raw):return "Korean", "脚本文字字符特征（候选）"
    if re.search(r"[\u4e00-\u9fff]",raw):return "Simplified Chinese", "脚本文字字符特征（候选，未区分简繁）"
    if counts:return max(counts,key=counts.get), "语言表 language 属性"
    return "English", "未标注语言的文字按 English 处理；其他拉丁文字请手动选择"
