"""Keyless MyMemory GET translation. No purchases, accounts or paid fallback.

Public API: https://mymemory.translated.net/doc/spec.php
Usage limits: https://mymemory.translated.net/doc/usagelimits.php
Only captured source text and the language pair are transmitted. No TM writes.
"""
import html
import json
import re
import hashlib
import os
from pathlib import Path
import threading
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from workbench import quality
from workbench import atomic_write
from languages import already_target_chinese

PROVIDER = "免配置联网翻译"
CODES = dict(zip(
    ["English", "Simplified Chinese", "Traditional Chinese", "Japanese", "Korean", "Russian", "German", "French", "Spanish", "Brazilian Portuguese", "Polish", "Ukrainian", "Turkish", "Italian", "Czech", "Hungarian", "Romanian"],
    ["en", "zh-CN", "zh-TW", "ja", "ko", "ru", "de", "fr", "es", "pt-BR", "pl", "uk", "tr", "it", "cs", "hu", "ro"]))
# Preserve rich tags, placeholders and line boundaries locally; never ask the
# service to rewrite markup. This trades some sentence context for safe output.
TOKENS = re.compile(r"(‖[^‖]*‖|<[^>]*>|\[[^\]\n]+\]|\{[^}\n]+\}|%(?:\d+\$)?[-+#0 .\d]*[a-zA-Z]|\r\n|\n|\r)")


class TranslationServiceError(ValueError):
    def __init__(self,message,retry_after=0):
        super().__init__(message)
        self.retry_after=retry_after


class TranslationCache:
    """Bounded language-pair cache; local only, no API keys or project paths."""
    def __init__(self,path=None):
        self.path=Path(path) if path else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'AbyssText'/'online-cache.json'
        self.lock=threading.Lock()
        self.rows={}
        self.bytes=0
        self.dirty=False
        if self.path.is_file() and not self.path.is_symlink() and self.path.stat().st_size<=8*1024*1024:
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data,dict):self.rows={k:v for k,v in list(data.items())[-10000:] if isinstance(k,str) and len(k)==64 and isinstance(v,str) and len(v)<=20000}
            except (OSError,ValueError):pass
        self.bytes=sum(self.entry_bytes(k,v) for k,v in self.rows.items())

    @staticmethod
    def entry_bytes(key,value):
        return len(json.dumps({key:value},ensure_ascii=False).encode())

    @staticmethod
    def key(unit,target):
        return hashlib.sha256(json.dumps([unit.source_language,target,unit.source],ensure_ascii=False).encode()).hexdigest()

    def translate(self,unit,target,opener=urlopen,cancelled=lambda:False):
        key=self.key(unit,target)
        with self.lock:cached=self.rows.get(key)
        if cached is not None:
            return {unit.id:{'translation':cached,'issues':quality(unit.source,cached)}}
        result=translate_unit(unit,target,opener,cancelled)
        if not result[unit.id]['issues']:
            with self.lock:
                previous=self.rows.get(key)
                if previous is not None:self.bytes-=self.entry_bytes(key,previous)
                self.rows[key]=result[unit.id]['translation'];self.dirty=True
                self.bytes+=self.entry_bytes(key,self.rows[key])
                while len(self.rows)>10000 or self.bytes>8*1024*1024-2:
                    oldest=next(iter(self.rows));self.bytes-=self.entry_bytes(oldest,self.rows.pop(oldest))
        return result

    def flush(self):
        with self.lock:
            if not self.dirty:return
            if self.path.is_symlink():raise ValueError('Translation cache cannot be a symbolic link')
            content=json.dumps(self.rows,ensure_ascii=False)
            # Enforce a byte bound too; extremely long translations must not grow
            # the cache beyond the documented startup-read limit.
            if len(content.encode())>8*1024*1024:raise ValueError('Translation cache exceeds size limit')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            atomic_write(self.path,content);self.dirty=False


def translate_unit(unit, target_language, opener=urlopen, cancelled=lambda: False):
    if already_target_chinese(unit.source,unit.source_language,target_language):
        return {unit.id:{"translation":unit.source,"issues":[]}}
    source = CODES.get(unit.source_language)
    target = CODES.get(target_language)
    if not source or not target or source == target:
        raise ValueError("联网翻译暂不支持此语言对，请选择明确且不同的源/目标语言。")
    output = []
    for piece in TOKENS.split(unit.source):
        if cancelled():
            raise ValueError("翻译已取消；当前条目未写入。")
        if not piece or TOKENS.fullmatch(piece) or not any(c.isalpha() for c in piece):
            output.append(piece)
            continue
        leading = piece[:len(piece)-len(piece.lstrip())]
        trailing = piece[len(piece.rstrip()):]
        text = piece.strip()
        # Unicode-safe chunks under the documented 500-byte request limit.
        chunks, chunk = [], ""
        for char in text:
            if len((chunk+char).encode("utf-8")) > 480:
                chunks.append(chunk); chunk = ""
            chunk += char
        if chunk: chunks.append(chunk)
        translated = []
        for chunk in chunks:
            if cancelled(): raise ValueError("翻译已取消；当前条目未写入。")
            query = urlencode({"q":chunk,"langpair":source+"|"+target,"mt":"1"})
            request = Request("https://api.mymemory.translated.net/get?"+query,
                              headers={"User-Agent":"AbyssText/0.2 (desktop localization preview)"})
            try:
                with opener(request, timeout=30) as response:
                    raw = response.read(1024*1024+1)
                if len(raw)>1024*1024: raise ValueError("联网翻译响应过大。")
                data = json.loads(raw)
                if data.get("quotaFinished") or str(data.get("responseStatus")) in {"403","429"}:
                    raise TranslationServiceError("免费联网翻译额度已用尽；已完成译文保留，请稍后继续。不会转用收费服务。",3600)
                result = data.get("responseData",{}).get("translatedText")
                if str(data.get("responseStatus")) != "200" or not isinstance(result,str) or not result:
                    raise ValueError("免费联网翻译服务返回错误；已完成译文保留。")
                translated.append(html.unescape(result))
            except FileNotFoundError:
                raise TranslationServiceError("Windows 包缺少 HTTPS/TLS 运行资源；尚未发送翻译请求，请更新程序。") from None
            except HTTPError as error:
                if error.code in {403,429}:
                    raise TranslationServiceError("免费联网翻译被限流或拒绝；已完成译文保留，一小时后有限重试。",3600) from None
                raise TranslationServiceError("免费联网翻译 HTTP 错误；已完成译文保留，稍后有限重试。",30) from None
            except (URLError,TimeoutError,OSError):
                raise TranslationServiceError("免费联网翻译暂不可用或超时；已完成译文保留，稍后有限重试。",30) from None
            except (KeyError,TypeError,json.JSONDecodeError):
                raise ValueError("免费联网翻译响应格式无效；当前条目未写入。") from None
        output.append(leading+"".join(translated)+trailing)
    result = "".join(output)
    return {unit.id:{"translation":result,"issues":quality(unit.source,result)}}
