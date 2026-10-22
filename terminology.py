"""Conservative game terminology. User terms win; ambiguous short labels need context."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
DATA=json.loads((ROOT/'assets/barotrauma-terms.json').read_text(encoding='utf-8'))
REVISION=hashlib.sha256(json.dumps(DATA,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]+'-rules6'
ENTRIES=DATA['entries']
CREATURE_TERMS={entry['source'].casefold():entry['target'] for entry in ENTRIES
                if entry['key'].startswith('character.') and entry['source'].isascii() and entry['source'].isalpha()}
COMPOUND_WORD=re.compile(r'(?<!\w)[A-Za-z]{8,64}(?!\w)')
# These nouns also have common non-game meanings; never force them in dialogue.
AMBIGUOUS={'barotrauma','burn','stun','captain','engineer','mechanic','security officer','medical doctor','bleeding','psychosis','paralysis','lacerations','oxygen low'}


@lru_cache(maxsize=512)
def compound_parts(word,words=tuple(CREATURE_TERMS)):
    """One complete decomposition into 2–4 known creature names, or none.

    Dynamic programming caps path counts at two, so ambiguous input is rejected
    without enumerating exponentially many possible decompositions.
    """
    if not 8<=len(word)<=64 or not word.isascii() or not word.isalpha():return None
    word=word.casefold()
    if word in words:return None
    paths={(0,0):(1,())}
    for pos in range(len(word)):
        for count in range(4):
            previous=paths.get((pos,count))
            if previous is None:continue
            ways,parts=previous
            for name in words:
                if word.startswith(name,pos):
                    key=(pos+len(name),count+1);old=paths.get(key,(0,()))
                    paths[key]=(min(2,old[0]+ways),parts+(name,))
    complete=[paths[(len(word),n)] for n in range(2,5) if (len(word),n) in paths]
    return complete[0][1] if sum(ways for ways,_ in complete)==1 else None


def compound_terms(text,glossary=None):
    names=dict(CREATURE_TERMS)
    for source,target in (glossary or {}).items():
        if isinstance(source,str) and isinstance(target,str) and target.strip() and source.casefold() in names:
            names[source.casefold()]=target
    result={}
    for match in COMPOUND_WORD.finditer(text):
        parts=compound_parts(match[0].casefold())
        if parts:result[match[0]]=''.join(names[part] for part in parts)
    return result


@lru_cache(maxsize=512)
def partial_creature_parts(word):
    """Unique maximal known edges, leaving >=3 unknown letters in the middle."""
    if not word.isascii() or not word.isalpha() or not 7<=len(word)<=64:return None
    word=word.casefold()
    if word in CREATURE_TERMS or compound_parts(word):return None
    def edges(text,words):
        paths={(0,0):(1,())}
        for count in range(3):
            for (pos,n),(ways,parts) in list(paths.items()):
                if n!=count:continue
                for name in words:
                    end=pos+len(name)
                    if end<=len(text)-3 and text.startswith(name,pos):
                        key=(end,n+1);old=paths.get(key,(0,()))
                        paths[key]=(min(2,old[0]+ways),parts+(name,))
        positions={}
        for (pos,n),(ways,parts) in paths.items():
            old=positions.get(pos,(0,()))
            positions[pos]=(min(2,old[0]+ways),parts)
        return {pos:parts for pos,(ways,parts) in positions.items() if ways==1}
    left=edges(word,tuple(CREATURE_TERMS))
    right=edges(word[::-1],tuple(name[::-1] for name in CREATURE_TERMS))
    candidates=[]
    for start,head in left.items():
        for length,backward in right.items():
            end=len(word)-length
            if 3<=end-start<len(word):
                tail=tuple(name[::-1] for name in backward[::-1])
                candidates.append((start+length,head,tail,start,end))
    if not candidates:return None
    best=max(c[0] for c in candidates);winners=[c for c in candidates if c[0]==best]
    if len(winners)!=1:return None
    _,head,tail,start,end=winners[0]
    if word[start:end] in {'ing','iness','ish','ily','ers','ier','iest','less','like','ful','ness'}:return None
    return head,tail,start,end


def expand_creature_compounds(unit,text,target):
    """Add MT-only word boundaries; original game text is never modified.

    Lowercase names need explicit creature metadata. CamelCase boundaries can
    also establish the split. No internal matches in identifiers/ordinary words.
    Called only outside markup/placeholders and already matched whole terms.
    """
    if unit.source_language!='English' or target!='Simplified Chinese':return text
    keys,contexts=context_key(unit)
    creature=any(k.startswith('character.') for k in keys) or any(c.startswith('CharacterPrefab.') for c in contexts) or any(
        getattr(e,'category','').startswith('生物/角色') for e in getattr(unit,'occurrences',[]))
    def expand(match):
        word=match[0];partial=partial_creature_parts(word.casefold())
        if not partial:return word
        head,tail,start,end=partial
        boundaries=([start] if head else [])+([end] if tail else [])
        if not creature and not (not word.isupper() and all(word[i].isupper() and word[i-1].islower() for i in boundaries)):return word
        # Preserve the unknown name, only expose its CamelCase word boundaries.
        remainder=word[start:end]
        remainder=re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])',' ',remainder)
        offset=0;prefix=[]
        for part in head:prefix.append(word[offset:offset+len(part)]);offset+=len(part)
        offset=end;suffix=[]
        for part in tail:suffix.append(word[offset:offset+len(part)]);offset+=len(part)
        return ' '.join(prefix+[remainder]+suffix)
    return re.sub(r'(?<!\w)[A-Za-z]{7,64}(?!\w)',expand,text)


def context_key(unit):
    keys=tuple(sorted(getattr(unit,'keys',[]) or [])[:8])
    contexts=tuple(sorted({getattr(e,'context','')[:120] for e in getattr(unit,'occurrences',[])})[:4])
    return keys,contexts


def relevant_terms(unit,target,glossary=None):
    text=unit.source.casefold()
    keys,contexts=context_key(unit)
    health=any(k.startswith('affliction') for k in keys) or any('AfflictionPrefab.' in c for c in contexts)
    role=any(k.startswith('job') for k in keys) or any('JobPrefab.' in c for c in contexts)
    named=any(c in {'ItemPrefab.Name','CharacterPrefab.Name','AfflictionPrefab.Name','JobPrefab.Name'} for c in contexts)
    result={}
    if unit.source_language=='English' and target=='Simplified Chinese':
        result.update(compound_terms(unit.source,glossary))
        for entry in ENTRIES:
            if entry.get('scope')=='named' and entry['key'] not in keys and not (named and entry['source'].casefold()==text.strip()):continue
            variants=[entry['source']]
            if entry['key'].startswith('character.'):
                variants.extend({'Moloch':('Molochs',),'Thalamus':('Thalami','Thalamuses'),'Charybdis':('Charybdis',)}.get(entry['source'],(entry['source']+'s',)))
            for word in variants:
                if word.casefold() not in text:continue
                ambiguous=word.casefold() in AMBIGUOUS
                allowed=not ambiguous or entry['key'] in keys or (health and entry['key'].startswith('affliction')) or (role and entry['key'].startswith('job'))
                if allowed:result[word]=entry['target']
        # These are composition rules for submarine prose, not copied game keys.
        for phrase in ('crew member','crew members'):
            if phrase in text:result[phrase]='船员'
    if unit.source_language=='English' and target=='Simplified Chinese':
        # Verbs are constrained by their object, never a global word replacement.
        # "reload the webpage ... Coilgun guide" must retain software meaning.
        for match in re.finditer(r'\b(reload(?:ing|s)?)\s+(?:the\s+|an?\s+)?(?:coilgun|railgun|shotgun|revolver|chaingun|harpoon gun|smg)\b(?!\s+(?:mod|page|webpage|guide|script|resource|lua)\b)',unit.source,re.IGNORECASE):
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


def action_terms(unit,target):
    terms=relevant_terms(unit,target)
    return {word:value for word,value in terms.items() if value in {'装填','封堵'} and word.casefold().startswith(('reload','seal'))}


def repair_game_actions(unit,translated,target,glossary=None):
    """Keep verbs in the MT input for grammar; fix known object-scoped mistranslations.

    Called before protected noun/format values are restored, never inside them.
    """
    explicit={key.casefold() for key in (glossary or {})}
    for source,word in action_terms(unit,target).items():
        if source.casefold() in explicit:continue
        variants=('重新加载','重新载入','重载页面','重新装填','重载') if word=='装填' else ('封印','印章')
        for variant in variants:translated=translated.replace(variant,word)
    motion=re.search(r'\b(?:is|are|was|were)\s+moving\s+(?:towards?|to)\b',unit.source,re.IGNORECASE)
    creatures=[entry['source'] for entry in ENTRIES if entry['key'].startswith('character.')]
    if unit.source_language=='English' and target=='Simplified Chinese' and motion and not any(key.startswith('moving') for key in explicit):
        if compound_terms(unit.source) or any(re.search(r'(?<!\w)'+re.escape(name)+r'(?:s|es)?(?!\w)',unit.source,re.IGNORECASE) for name in creatures):
            # "moving" does not imply that a creature drives a vehicle.
            translated=translated.replace('驶向','移向').replace('驶往','移向').replace('开往','移向')
    return translated
