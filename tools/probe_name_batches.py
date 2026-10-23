"""Opt-in paired real-network probe of eight owned fictional item names.

This tests cold throughput and preserves raw output for human review. It is not
an accuracy score. Both modes use the same names and at most two HTTP calls.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from free_online import TranslationCache

NAMES=['Ceramic Diving Helmet','Rescue Beacon','Abyssal Relay','Plasma Vent',
       'Emergency Repair Kit','Portable Signal Repeater','Hydrothermal Pump','Armored Storage Case']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();results=[]
    with tempfile.TemporaryDirectory() as temp:
        units=[SimpleNamespace(id=str(i),source=text,source_language='English',keys=['entityname.probe'+str(i)],occurrences=[]) for i,text in enumerate(NAMES)]
        for channel in ['mymemory','google']:
            for mode in ['single','batched']:
                cache=TranslationCache(Path(temp)/(channel+mode+'.json'))
                start=time.monotonic()
                if mode=='single':
                    def work(unit):
                        try:return [(unit,cache.translate(unit,'Simplified Chinese',channel=channel),None)]
                        except Exception as error:return [(unit,None,error)]
                    jobs=units
                else:
                    def work(group):return cache.translate_names([(u,None) for u in group],'Simplified Chinese',channel=channel)
                    jobs=[units[i:i+4] for i in range(0,len(units),4)]
                with ThreadPoolExecutor(max_workers=2) as pool:outcomes=[row for group in pool.map(work,jobs) for row in group]
                row={'channel':channel,'mode':mode,'seconds':round(time.monotonic()-start,3),'http_requests':cache.metrics['requests'],
                     'rows':[{'source':unit.source,'translation':out[unit.id]['translation'] if out else None,
                              'issues':out[unit.id]['issues'] if out else None,'error':str(error) if error else None} for unit,out,error in outcomes]}
                results.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    args.output.write_text(json.dumps({'real_network':True,'game_tested':False,'max_concurrency':2,
        'corpus':'eight owned fictional item names; raw translations, no semantic score; endpoint caching and run order can affect timings','results':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
