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
import ssl
import time
from terminology import REVISION, context_key, policy_key, relevant_terms, term_pattern, exact_term, medical_template, action_terms, repair_game_actions, expand_creature_compounds
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from workbench import quality
from workbench import atomic_write
from languages import already_target_chinese

PROVIDER = "免配置联网翻译"
CHANNEL_LABELS={"mymemory":"MyMemory 免费接口","google":"Google 网页兼容（实验）"}
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


def canonicalize_shields(source,translated):
    # MyMemory inserts spaces into opaque markers. Accept only whitespace/case
    # variations of an exact known ID; never guess a missing or different token.
    for token in re.findall(r'_+ABYSSTEXT_\d+__',source):
        match=re.fullmatch(r'(_+)ABYSSTEXT_(\d+)__',token)
        pattern=re.escape(match[1])+r'[ \t]*ABYSSTEXT_[ \t]*'+match[2]+r'[ \t]*__'
        translated=re.sub(pattern,lambda _:token,translated,flags=re.IGNORECASE)
    return translated


def chinese_spacing(text,target):
    if target not in {'Simplified Chinese','Traditional Chinese'}:return text
    return ''.join(piece if TOKENS.fullmatch(piece) else re.sub(r'(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])','',piece)
        for piece in TOKENS.split(text))


def shields_intact(source,translated):
    tokens=re.findall(r'_+ABYSSTEXT_\d+__',source)
    return all(translated.count(token)==tokens.count(token) for token in tokens) and sorted(tokens)==sorted(re.findall(r'_+ABYSSTEXT_\d+__',translated))


class TranslationCache:
    """Bounded full-text + fragment cache with coalesced concurrent requests."""
    def __init__(self,path=None):
        self.path=Path(path) if path else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'AbyssText'/'online-cache.json'
        self.lock=threading.Lock();self.save_lock=threading.Lock()
        self.rows={};self.flights={};self.bytes=0;self.dirty=False;self.version=0;self.last_flush=0
        self.metrics={'requests':0,'fragment_hits':0,'unit_hits':0,'local_terms':0,'coalesced':0}
        try:
            if self.path.is_file() and not self.path.is_symlink() and self.path.stat().st_size<=8*1024*1024:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data,dict):self.rows={k:v for k,v in list(data.items())[-10000:] if isinstance(k,str) and len(k)==64 and isinstance(v,str) and len(v)<=20000}
        except (OSError,ValueError):pass
        self.bytes=sum(self.entry_bytes(k,v) for k,v in self.rows.items())

    @staticmethod
    def entry_bytes(key,value):return len(json.dumps({key:value},ensure_ascii=False).encode())

    @staticmethod
    def key(unit,target,glossary=None,channel="mymemory"):
        return hashlib.sha256(json.dumps(['unit-v5',channel,unit.source_language,target,unit.source,policy_key(unit,target,glossary)],ensure_ascii=False).encode()).hexdigest()

    def remember(self,key,value):
        with self.lock:
            previous=self.rows.get(key)
            if previous==value:return
            if previous is not None:self.bytes-=self.entry_bytes(key,previous)
            self.rows[key]=value;self.dirty=True;self.version+=1
            self.bytes+=self.entry_bytes(key,value)
            while len(self.rows)>10000 or self.bytes>8*1024*1024-2:
                oldest=next(iter(self.rows));self.bytes-=self.entry_bytes(oldest,self.rows.pop(oldest))

    def request_text(self,text,unit,target,opener,cancelled,glossary,channel):
        keys,contexts=context_key(unit)
        scope=(sorted({k.split('.')[0] for k in keys}),sorted({c.split('.')[0] for c in contexts}))
        key=hashlib.sha256(json.dumps(['fragment-v5',channel,unit.source_language,target,text,REVISION,scope,
            tuple(relevant_terms(unit,target,glossary).items())],ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            if key in self.rows:
                self.metrics['fragment_hits']+=1
                return self.rows[key]
            flight=self.flights.get(key)
            if flight is None:
                flight={'event':threading.Event(),'result':None,'error':None}
                self.flights[key]=flight;owner=True
            else:owner=False;self.metrics['coalesced']+=1
        if not owner:
            while not flight['event'].wait(.05):
                if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
            if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
            if flight['error'] is not None:raise flight['error']
            return flight['result']
        try:
            if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
            with self.lock:self.metrics['requests']+=1
            result=canonicalize_shields(text,fetch_text(text,CODES[unit.source_language],CODES[target],opener,channel))
            flight['result']=result
            if not cancelled() and not quality(text,result) and shields_intact(text,result):self.remember(key,result)
            return result
        except Exception as error:
            flight['error']=error;raise
        finally:
            with self.lock:
                self.flights.pop(key,None);flight['event'].set()

    def translate(self,unit,target,opener=urlopen,cancelled=lambda:False,glossary=None,channel="mymemory"):
        if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
        key=self.key(unit,target,glossary,channel)
        with self.lock:cached=self.rows.get(key)
        if cached is not None and not quality(unit.source,cached):
            with self.lock:self.metrics['unit_hits']+=1
            return {unit.id:{'translation':cached,'issues':[]}}
        if cached is not None:
            with self.lock:
                removed=self.rows.pop(key,None)
                if removed is not None:self.bytes-=self.entry_bytes(key,removed);self.dirty=True;self.version+=1
        local=exact_term(unit,target,glossary)
        if local is not None:
            with self.lock:self.metrics['local_terms']+=1
        result=translate_unit(unit,target,opener,cancelled,glossary,
            lambda text:self.request_text(text,unit,target,opener,cancelled,glossary,channel),channel=channel)
        if not cancelled() and not result[unit.id]['issues']:self.remember(key,result[unit.id]['translation'])
        return result

    @staticmethod
    def can_batch_name(unit,target,glossary=None):
        """Only short structured names without protected terms or prose."""
        if target!='Simplified Chinese' or getattr(unit,'source_language',None)!='English':return False
        text=getattr(unit,'source','')
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,\-'()/]{1,59}",text.strip()):return False
        keys,contexts=context_key(unit)
        named=any(k.startswith(('entityname.','character.','afflictionname.','jobname.')) for k in keys) or any(
            c in {'ItemPrefab.Name','CharacterPrefab.Name','AfflictionPrefab.Name','JobPrefab.Name'} for c in contexts)
        return named and not relevant_terms(unit,target,glossary)

    def translate_names(self,work,target,opener=urlopen,cancelled=lambda:False,channel='mymemory'):
        """At most four names per HTTP request; errors/results remain per unit.

        No waiting for a group to fill. Cached and local terms never enter the
        combined request. A malformed row falls back independently; a broken
        envelope falls back per unit. Transport/quota errors are not retried.
        """
        if not 1<=len(work)<=4:raise ValueError('名称合并批次必须为 1–4 条')
        output=[];cold=[]
        def single(unit,terms):
            try:output.append((unit,self.translate(unit,target,opener,cancelled,terms,channel),None))
            except Exception as error:output.append((unit,None,error))
        for unit,terms in work:
            if cancelled():return output
            key=self.key(unit,target,terms,channel)
            with self.lock:cached=self.rows.get(key)
            if (cached is not None and not quality(unit.source,cached)) or not self.can_batch_name(unit,target,terms):
                single(unit,terms)
            else:cold.append((unit,terms,key))
        if len(cold)<2:
            for unit,terms,_ in cold:single(unit,terms)
            return output
        query='\n'.join(f'__ABYSSROW_{i}__ {unit.source.strip()}' for i,(unit,_,_) in enumerate(cold))
        if len(query.encode())>480:
            for unit,terms,_ in cold:single(unit,terms)
            return output
        try:
            if cancelled():return output
            with self.lock:self.metrics['requests']+=1
            translated=fetch_text(query,'en',CODES[target],opener,channel)
        except Exception as error:
            return output+[(unit,None,error) for unit,_,_ in cold]
        # Accept whitespace/case changes in exact row IDs, never inferred IDs.
        translated=re.sub(r'__[ \t]*ABYSSROW_[ \t]*(\d+)[ \t]*__',lambda m:'__ABYSSROW_'+m[1]+'__',translated,flags=re.IGNORECASE)
        matches=list(re.finditer(r'__ABYSSROW_(\d+)__',translated))
        valid_ids=[m[1] for m in matches]
        # A missing boundary can silently merge two names. Require every row
        # exactly once, in order, before accepting any part of the envelope.
        envelope=valid_ids==list(map(str,range(len(cold)))) and not translated[:matches[0].start()].strip()
        rows={}
        if envelope:
            for n,match in enumerate(matches):
                value=translated[match.end():matches[n+1].start() if n+1<len(matches) else len(translated)].strip()
                if '\n' not in value and '\r' not in value and 'ABYSSROW' not in value.upper():rows[int(match[1])]=value
        for i,(unit,terms,key) in enumerate(cold):
            if cancelled():break
            value=rows.get(i,'')
            value=unit.source[:len(unit.source)-len(unit.source.lstrip())]+chinese_spacing(value,target)+unit.source[len(unit.source.rstrip()):]
            if i in rows and not quality(unit.source,value):
                self.remember(key,value)
                output.append((unit,{unit.id:{'translation':value,'issues':[],'origin':'联网短名称合并翻译（未校对）'}},None))
            else:single(unit,terms)
        return output

    def flush_due(self):
        if time.monotonic()-self.last_flush>=5:self.flush()

    def flush(self):
        # Disk I/O is outside the lookup lock. A concurrent update remains dirty.
        with self.save_lock:
            with self.lock:
                if not self.dirty:return
                snapshot=dict(self.rows);version=self.version
            if self.path.is_symlink():raise ValueError('Translation cache cannot be a symbolic link')
            content=json.dumps(snapshot,ensure_ascii=False)
            if len(content.encode())>8*1024*1024:raise ValueError('Translation cache exceeds size limit')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            atomic_write(self.path,content)
            with self.lock:
                self.dirty=self.version!=version;self.last_flush=time.monotonic()


def fetch_text(text,source,target,opener=urlopen,channel="mymemory"):
    if channel not in CHANNEL_LABELS:raise ValueError('不支持的免费翻译渠道')
    if channel=='google':
        query=urlencode({'client':'gtx','sl':source,'tl':target,'dt':'t','q':text})
        address='https://translate.googleapis.com/translate_a/single?'+query
    else:
        query=urlencode({'q':text,'langpair':source+'|'+target,'mt':'1'})
        address='https://api.mymemory.translated.net/get?'+query
    request=Request(address,headers={'User-Agent':'AbyssText/0.2 (desktop localization preview)'})
    try:
        with opener(request, timeout=30) as response:
            raw = response.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError("联网翻译响应过大。")
        data = json.loads(raw)
        if channel=='google':
            if not isinstance(data,list) or not data or not isinstance(data[0],list) or not data[0]:
                raise ValueError('Google 网页兼容渠道响应格式无效；未写入当前条目。')
            pieces=[]
            for item in data[0]:
                if not isinstance(item,list) or not item or not isinstance(item[0],str):
                    raise ValueError('Google 网页兼容渠道响应格式无效；未写入当前条目。')
                pieces.append(item[0])
            result=''.join(pieces)
            if not result.strip():raise ValueError('Google 网页兼容渠道返回空译文。')
            return html.unescape(result)
        if not isinstance(data,dict):raise ValueError('免费联网翻译响应格式无效；当前条目未写入。')
        if data.get("quotaFinished") is True or str(data.get("responseStatus")) in {"403","429"}:
            raise TranslationServiceError("免费联网翻译额度已用尽；已完成译文保留，请稍后继续。不会转用收费服务。",3600)
        body=data.get("responseData")
        if not isinstance(body,dict):raise ValueError('免费联网翻译响应格式无效；当前条目未写入。')
        result = body.get("translatedText")
        if str(data.get("responseStatus")) != "200" or not isinstance(result,str) or not result.strip():
            raise ValueError("免费联网翻译服务返回错误；已完成译文保留。")
        return html.unescape(result)
    except FileNotFoundError:
        raise TranslationServiceError("Windows 包缺少 HTTPS/TLS 运行资源；尚未发送翻译请求，请更新程序。") from None
    except ssl.SSLError:
        raise TranslationServiceError('HTTPS/TLS 证书或握手验证失败；保留证书验证，请检查系统时间和证书环境。') from None
    except HTTPError as error:
        if error.code in {403,429}:
            raise TranslationServiceError("免费联网翻译被限流或拒绝；已完成译文保留，一小时后有限重试。",3600) from None
        raise TranslationServiceError("免费联网翻译 HTTP 错误；已完成译文保留，稍后有限重试。",30) from None
    except URLError as error:
        if isinstance(error.reason,FileNotFoundError):
            raise TranslationServiceError('Windows 包缺少 HTTPS/TLS 运行资源；请更新程序。') from None
        if isinstance(error.reason,ssl.SSLError):
            raise TranslationServiceError('HTTPS/TLS 证书或握手验证失败；保留证书验证，请检查系统时间和证书环境。') from None
        raise TranslationServiceError("免费联网翻译暂不可用或超时；已完成译文保留，稍后有限重试。",30) from None
    except (TimeoutError,OSError):
        raise TranslationServiceError("免费联网翻译暂不可用或超时；已完成译文保留，稍后有限重试。",30) from None
    except (KeyError,TypeError,json.JSONDecodeError,UnicodeDecodeError):
        raise ValueError("免费联网翻译响应格式无效；当前条目未写入。") from None


def translate_unit(unit, target_language, opener=urlopen, cancelled=lambda: False, glossary=None, request_text=None, channel="mymemory"):
    if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
    if already_target_chinese(unit.source,unit.source_language,target_language):
        return {unit.id:{'translation':unit.source,'issues':[]}}
    source,target=CODES.get(unit.source_language),CODES.get(target_language)
    if not source or not target or source==target:
        raise ValueError('联网翻译暂不支持此语言对，请选择明确且不同的源/目标语言。')
    direct=exact_term(unit,target_language,glossary) or medical_template(unit,target_language,glossary)
    if direct is not None:return {unit.id:{'translation':direct,'issues':quality(unit.source,direct),'origin':'潜渊症术语 / 项目术语（未校对）'}}
    terms=relevant_terms(unit,target_language,glossary)
    # A masked verb looks like an unknown noun to MT and damages word order.
    # Leave known game verbs in the sentence, then repair only scoped bad senses.
    explicit={key.casefold() for key in (glossary or {})}
    for verb in action_terms(unit,target_language):
        if verb.casefold() not in explicit:terms.pop(verb,None)
    pattern=term_pattern(tuple(terms))
    lowered={k.casefold():v for k,v in terms.items()}
    def request(text):
        if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
        result=canonicalize_shields(text,request_text(text) if request_text else fetch_text(text,source,target,opener,channel))
        if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
        return result
    # Shield format and domain terms in one sentence so the free service sees
    # surrounding grammar. A damaged token triggers the conservative split path.
    prefix='__ABYSSTEXT_'
    while prefix in unit.source:prefix='_'+prefix
    substitutions={}
    def shield(value):
        token=prefix+str(len(substitutions))+'__';substitutions[token]=value;return token
    def prepare_piece(piece):
        # Preserve full names/phrases (especially explicit glossary overrides)
        # before exposing boundaries inside otherwise unknown creature names.
        spans=pattern.split(piece) if pattern else [piece]
        matches=list(pattern.finditer(piece)) if pattern else []
        return ''.join(expand_creature_compounds(unit,span,target_language,lowered)+(matches[i].group() if i<len(matches) else '')
                       for i,span in enumerate(spans))
    def shield_piece(piece):
        if not piece:return ''
        if TOKENS.fullmatch(piece):return shield(piece)
        piece=prepare_piece(piece)
        return pattern.sub(lambda m:shield(lowered[m.group().casefold()]),piece) if pattern else piece
    masked=''.join(shield_piece(piece) for piece in TOKENS.split(unit.source))
    if substitutions and len(masked.encode())<=480:
        unmasked_words=re.sub(re.escape(prefix)+r'\d+__','',masked)
        translated=request(masked) if any(c.isalpha() for c in unmasked_words) else masked
        format_tokens=[token for token,value in substitutions.items() if value.startswith(('‖','<'))]
        if shields_intact(masked,translated) and [translated.find(t) for t in format_tokens]==sorted(translated.find(t) for t in format_tokens):
            translated=repair_game_actions(unit,translated,target_language,glossary)
            for token,value in substitutions.items():translated=translated.replace(token,value)
            if not any(re.search(r'[\u3400-\u9fff] +[\u3400-\u9fff]',v) for v in terms.values()):translated=chinese_spacing(translated,target_language)
            if not quality(unit.source,translated):
                return {unit.id:{'translation':translated,'issues':[],'origin':'联网翻译 + 潜渊症术语（未校对）'}}
    output=[]
    for piece in TOKENS.split(unit.source):
        if cancelled():raise ValueError('翻译已取消；当前条目未写入。')
        if not piece or TOKENS.fullmatch(piece) or not any(c.isalpha() for c in piece):output.append(piece);continue
        piece=prepare_piece(piece)
        # Exact known spans stay local even if a provider damages shield tokens.
        spans=pattern.split(piece) if pattern else [piece]
        matches=list(pattern.finditer(piece)) if pattern else []
        for index,span in enumerate(spans):
            if span:
                leading=span[:len(span)-len(span.lstrip())];trailing=span[len(span.rstrip()):]
                text=span.strip();chunks=[];chunk='';size=0
                for char in text:
                    length=len(char.encode())
                    if size+length>480:chunks.append(chunk);chunk='';size=0
                    chunk+=char;size+=length
                if chunk:chunks.append(chunk)
                output.append(leading+''.join(repair_game_actions(unit,request(c),target_language,glossary) if any(x.isalpha() for x in c) else c for c in chunks)+trailing)
            if index<len(matches):output.append(lowered[matches[index].group().casefold()])
    translated=''.join(output)
    if not any(re.search(r'[\u3400-\u9fff] +[\u3400-\u9fff]',v) for v in terms.values()):translated=chinese_spacing(translated,target_language)
    return {unit.id:{'translation':translated,'issues':quality(unit.source,translated)}}
