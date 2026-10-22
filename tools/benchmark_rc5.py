"""Compare our rc4 code with the current bridge/cache on identical owned fixtures.
No game, network, model or third-party scripts are executed.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from extractor import Entry,Report
from workbench import Project
from live_bridge import LiveBridge
from free_online import TranslationCache

BASELINE='f3163dbeb2818f4cd4ac9026b3211715cae661df'


def load_our_baseline(name,path,temp):
    content=subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
    file=Path(temp)/(name+'.py');file.write_bytes(content)
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result={'synthetic':True,'game_tested':False,'real_network_requests':0,'baseline_commit':BASELINE}
    with tempfile.TemporaryDirectory() as temp:
        oldbridge=load_our_baseline('baseline_bridge','live_bridge.py',temp)
        oldonline=load_our_baseline('baseline_online','free_online.py',temp)
        entries=[Entry(str(i),'<游戏内>',1,1,'游戏内显示','literal',f'Unseen item {i}',language='English',location={'live_priority':2}) for i in range(2000)]
        project=Project(Report('owned-fixture',entries))
        for unit in project.units:project.update(unit.id,'物品 '+unit.source.split()[-1])
        for name,cls in [('rc4',oldbridge.LiveBridge),('current',LiveBridge)]:
            directory=Path(temp)/name;directory.mkdir();(directory/'filelist.xml').write_text('<contentpackage name="AbyssTextLive"/>')
            bridge=cls(directory);bridge.publish(project,'one',True,False)
            before=(directory/'Live/response.json').stat().st_mtime_ns;start=time.perf_counter()
            for _ in range(50):bridge.publish(project,'one',True,False)
            result[name+'_idle_50_seconds']=round(time.perf_counter()-start,6)
            result[name+'_idle_response_rewritten']=(directory/'Live/response.json').stat().st_mtime_ns!=before
            result[name+'_full_response_bytes']=(directory/'Live/response.json').stat().st_size
            calls=[]
            def fake(request,timeout):
                text=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(text)
                return io.BytesIO(json.dumps({'responseStatus':200,'responseData':{'translatedText':text.replace('Alert','警告')}}).encode())
            cache=(oldonline.TranslationCache if name=='rc4' else TranslationCache)(Path(temp)/(name+'-cache.json'))
            for i in range(100):
                unit=SimpleNamespace(id=str(i),source=f'Alert [crew_{i}]',source_language='English')
                assert not cache.translate(unit,'Simplified Chinese',fake)[unit.id]['issues']
            result[name+'_repeated_template_http_calls']=len(calls)
        bridge=LiveBridge(Path(temp)/'current');bridge.delta_mode=True;bridge.session_id='test'
        bridge.publish(project,'one',True,False)
        packet=json.loads((bridge.data/'response.json').read_text(encoding='utf-8'))
        result['current_delta_records']=len(packet['translations']);result['current_delta_bytes']=(bridge.data/'response.json').stat().st_size
        result['current_delta_reduction_percent']=round((1-result['current_delta_bytes']/result['rc4_full_response_bytes'])*100,2)
        result['idle_cpu_reduction_percent']=round((1-result['current_idle_50_seconds']/result['rc4_idle_50_seconds'])*100,2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
