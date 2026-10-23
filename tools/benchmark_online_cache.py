"""Synthetic cache benchmark; makes zero network requests."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from free_online import TranslationCache

with tempfile.TemporaryDirectory() as directory:
    cache=TranslationCache(Path(directory)/'cache.json')
    units=[SimpleNamespace(id=str(i),source=f'Example text {i}',source_language='English') for i in range(200)]
    def fake(request,timeout):return io.BytesIO(b'{"responseStatus":200,"responseData":{"translatedText":"Cached translation"}}')
    for unit in units:cache.translate(unit,'French',fake)
    cache.flush()
    def forbid(*args,**kwargs):raise AssertionError('cache missed; no real network is allowed')
    tracemalloc.start();start=time.perf_counter()
    for i in range(10000):cache.translate(units[i%200],'French',forbid)
    seconds=time.perf_counter()-start
    _,peak=tracemalloc.get_traced_memory()
    print(json.dumps({'synthetic':True,'network_requests':0,'cached_lookups':10000,'seconds':round(seconds,4),'peak_python_allocation_mib':round(peak/1024/1024,3)},indent=2))
