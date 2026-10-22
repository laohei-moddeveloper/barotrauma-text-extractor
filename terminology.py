"""Conservative game terminology. User terms win; ambiguous short labels need context."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
DATA=json.loads((ROOT/'assets/barotrauma-terms.json').read_text(encoding='utf-8'))
REVISION=hashlib.sha256(json.dumps(DATA,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]+'-rules2'
ENTRIES=DATA['entries']
# These nouns also have common non-game meanings; never force them in dialogue.
AMBIGUOUS={'barotrauma','burn','stun','captain','engineer','mechanic','security officer','medical doctor','bleeding','psychosis','paralysis','lacerations','oxygen low'}


def context_key(unit):
    keys=tuple(sorted(getattr(unit,'keys',[]) or [])[:8])
    contexts=tuple(sorted({getattr(e,'context','')[:120] for e in getattr(unit,'occurrences',[])})[:4])
    return keys,contexts


def relevant_terms(unit,target,glossary=None):
    text=unit.source.casefold()
    keys,contexts=context_key(unit)
    health=any(k.startswith('affliction') for k in keys) or any('AfflictionPrefab.' in c for c in contexts)
    role=any(k.startswith('job') for k in keys) or any('JobPrefab.' in c for c in contexts)
    result={}
    if unit.source_language=='English' and target=='Simplified Chinese':
        for entry in ENTRIES:
            word=entry['source']
            if word.casefold() not in text:continue
            ambiguous=word.casefold() in AMBIGUOUS
            allowed=not ambiguous or entry['key'] in keys or (health and entry['key'].startswith('affliction')) or (role and entry['key'].startswith('job'))
            if allowed:result[word]=entry['target']
    if unit.source_language=='English' and target=='Simplified Chinese':
        # Verbs are constrained by their object, never a global word replacement.
        # "reload the webpage ... Coilgun guide" must retain software meaning.
        for match in re.finditer(r'\b(reload(?:ing|s)?)\s+(?:the\s+|an?\s+)?(?:coilgun|railgun|shotgun|revolver|chaingun|harpoon gun|smg)\b',unit.source,re.IGNORECASE):
            result[match[1]]='装填'
        for match in re.finditer(r'\b(seal(?:ing|s)?)\s+(?:the\s+)?(?:hull\s+)?breach(?:es)?\b',unit.source,re.IGNORECASE):
            result[match[1]]='封堵'
    # User-provided glossary belongs to the current project language pair.
    for key,value in (glossary or {}).items():
        if isinstance(key,str) and isinstance(value,str) and key.strip() and key.casefold() in text and value.strip():
            for previous in list(result):
                if previous.casefold()==key.casefold():del result[previous]
            result[key]=value
    return dict(sorted(result.items(),key=lambda pair:(-len(pair[0]),pair[0]))[:128])


def policy_key(unit,target,glossary=None):
    return REVISION,context_key(unit),tuple(relevant_terms(unit,target,glossary).items())


@lru_cache(maxsize=32)
def term_pattern(words):
    if not words:return None
    # Unicode word boundaries avoid coilgun inside mycoilgunidentifier.
    return re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(w) for w in words)+r')(?!\w)',re.IGNORECASE)


def exact_term(unit,target,glossary=None):
    text=unit.source.strip()
    for source,translated in relevant_terms(unit,target,glossary).items():
        if source.casefold()==text.casefold():
            return unit.source[:len(unit.source)-len(unit.source.lstrip())]+translated+unit.source[len(unit.source.rstrip()):]
    return None


def medical_template(unit,target,glossary=None):
    """Only a narrow, complete medical instruction with two known medical terms."""
    if unit.source_language!='English' or target!='Simplified Chinese':return None
    match=re.fullmatch(r'(\s*)(?:Treat|Cure) (.+?) with (.+?)([.!]?)(\s*)',unit.source,re.IGNORECASE)
    if not match:return None
    condition,medicine=match[2],match[3]
    # No generic "treat someone with respect" or unknown mod substance guessing.
    conditions={e['source'].casefold() for e in ENTRIES if e['key'].startswith('afflictionname.')}
    medical_keys={'entityname.antidama1','entityname.antidama2','entityname.antinarc','entityname.antiparalysis','entityname.calyxanide','entityname.antibleeding1','entityname.antibleeding2','entityname.antibleeding3'}
    medicines={e['source'].casefold() for e in ENTRIES if e['key'] in medical_keys}
    if condition.casefold() not in conditions or medicine.casefold() not in medicines:return None
    terms=relevant_terms(unit,target,glossary)
    mapping={e['source'].casefold():e['target'] for e in ENTRIES if e['key'].startswith('afflictionname.') or e['key'] in medical_keys}
    mapping.update({k.casefold():v for k,v in terms.items()})
    if condition.casefold() not in mapping or medicine.casefold() not in mapping:return None
    return match[1]+'使用'+mapping[medicine.casefold()]+'治疗'+mapping[condition.casefold()]+('。' if match[4] else '')+match[5]
