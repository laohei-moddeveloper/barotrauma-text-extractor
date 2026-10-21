"""Synthetic repeatable performance probe. No game or translation API required."""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from extractor import scan
from workbench import Project


def timed(fn):
    start=time.perf_counter();value=fn();return value,round(time.perf_counter()-start,4)


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'fixture';root.mkdir()
        for i in range(100):
            tags=''.join(f'<entry{i}_{j}>Item {j%1000}</entry{i}_{j}>' for j in range(200))
            (root/f'{i}.xml').write_text('<infotexts language="English">'+tags+'</infotexts>',encoding='utf-8')
        cache={}
        report,cold=timed(lambda:scan(root,cache=cache))
        _,warm=timed(lambda:scan(root,cache=cache))
        project,group=timed(lambda:Project(report))
        start=time.perf_counter()
        for _ in range(100):project.filtered('Item 19')
        search=round((time.perf_counter()-start)*10,3)
        result={'files':report.scanned,'occurrences':len(report.entries),'unique':len(project.units),
            'cold_scan_seconds':cold,'cached_scan_seconds':warm,'group_seconds':group,'search_mean_ms':search}
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
