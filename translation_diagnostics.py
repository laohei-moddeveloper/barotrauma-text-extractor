"""Small local diagnostic history. Never records source text or credentials."""
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone

from workbench import atomic_write


def safe_error(error):
    return re.sub(r'https?://\S+', '[endpoint]', str(error))[:400]


class TranslationDiagnostics:
    def __init__(self, path=None, enabled=True):
        self.enabled=enabled
        self.path=Path(path) if path else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'AbyssText'/'translation-status.json'
        self.events=[]
        self.dirty=False;self.last_flush=0

    def record(self, stage, uid, **details):
        if not self.enabled:return
        self.events.append({'time':datetime.now(timezone.utc).isoformat(), 'stage':stage,'id':uid,**details})
        self.events=self.events[-200:]
        self.dirty=True
        self.flush(force=stage in {'failed','rejected','task-error'})

    def flush(self,force=False):
        if not self.enabled or not self.dirty or (not force and time.monotonic()-self.last_flush<1):return
        try:
            if not self.path.is_symlink():
                atomic_write(self.path,json.dumps({'protocol':1,'events':self.events},ensure_ascii=False))
                self.dirty=False;self.last_flush=time.monotonic()
        except OSError:
            pass  # Diagnostic storage failure must not discard translations.
