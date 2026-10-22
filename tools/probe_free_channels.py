"""Small opt-in real network regression sample. Only built-in fictional public game sentences.
Term checks measure specified names, never whole-sentence semantic correctness.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from free_online import translate_unit

SAMPLES=[
 ('A Husk infection prevents the crew member from speaking.',['画皮寄生虫感染']),
 ('Reload the Coilgun before the Mudraptor reaches the airlock.',['电磁枪','泥偶迅猛龙']),
 ('Keep a spare Welding Fuel Tank near the junction box.',['焊接油箱']),
 ('The Railgun Loader needs power from a supercapacitor.',['轨道炮装弹器']),
 ('The Crawler is moving toward the Ballast Flora.',['藻鬃爬行者','压载植物群']),
 ('Treat opiate overdose with Naloxone.',['阿片类药物中毒','纳洛酮'])]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'our_rc4.py';path.write_bytes(subprocess.check_output(['git','show','f3163db:free_online.py'],cwd=ROOT))
        spec=importlib.util.spec_from_file_location('our_rc4',path);baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
        jobs=[(mode,index,source,expected) for mode in ('rc4-mymemory','rc5-mymemory','rc5-google') for index,(source,expected) in enumerate(SAMPLES)]
        def work(job):
            mode,index,source,expected=job;requests=0;start=time.monotonic()
            def network(request,timeout):
                nonlocal requests
                requests+=1;return urlopen(request,timeout=timeout)
            result={'mode':mode,'sample':index,'source':source,'expected_terms':expected}
            try:
                unit=SimpleNamespace(id='sample',source=source,source_language='English',keys=(),occurrences=[])
                out=baseline.translate_unit(unit,'Simplified Chinese',network) if mode=='rc4-mymemory' else translate_unit(unit,'Simplified Chinese',network,channel=mode.split('-')[1])
                data=out['sample'];result.update(translation=data['translation'],issues=data['issues'],ok=not data['issues'],
                    expected_terms_present=all(term in data['translation'] for term in expected))
            except Exception as error:result.update(ok=False,error=str(error),expected_terms_present=False)
            result.update(seconds=round(time.monotonic()-start,3),requests=requests)
            print(json.dumps(result,ensure_ascii=True),flush=True);return result
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,jobs))
    output={'real_network':True,'game_tested':False,'corpus':'six owned development regression sentences; lexical term check, not blind or full human quality scoring','results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
