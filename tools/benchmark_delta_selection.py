"""Isolated top-eight selection benchmark; never represents real-game FPS."""
import argparse
import heapq
import json
from pathlib import Path
import time
import tracemalloc


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    priorities={f'Unseen item {i}':i%4 for i in range(20000)}
    key=lambda source:(priorities[source],source)
    results={}
    for name,select in [('full_sort',lambda:sorted(priorities,key=key)[:8]),
                        ('bounded_top8',lambda:heapq.nsmallest(8,iter(priorities),key=key))]:
        start=time.perf_counter()
        for _ in range(40):selected=select()
        elapsed=(time.perf_counter()-start)*1000/40
        tracemalloc.start();select();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        results[name]={'mean_ms':elapsed,'peak_temporary_bytes':peak,'selected':selected}
    assert results['full_sort']['selected']==results['bounded_top8']['selected']
    report={'synthetic':True,'game_tested':False,'candidate_count':len(priorities),'iterations':40,
            'notes':'Only candidate selection is timed; excludes XML, IPC, rendering and network.',**results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
