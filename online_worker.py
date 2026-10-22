"""Two requests at most, with a bounded live priority queue and no batch barrier."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import heapq
import threading
import time


def live_priority(unit):
    return min((e.location.get('live_priority',2) for e in getattr(unit,'occurrences',[]) if e.file=='<游戏内>'),default=2)


class LiveFeed:
    def __init__(self,limit=16):
        self.limit=limit;self.condition=threading.Condition();self.rows={};self.heap=[];self.serial=0;self.closed=False

    def submit(self,unit,glossary=None):
        """Return accepted and an optional deferred background id. Never drop it."""
        with self.condition:
            if self.closed:return False,None
            priority=live_priority(unit);previous=self.rows.get(unit.id);deferred=None
            if previous and previous[0]<=priority:return True,None
            if previous is None and len(self.rows)>=self.limit:
                worst=max(self.rows,key=lambda uid:(self.rows[uid][0],self.rows[uid][1]))
                if self.rows[worst][0]<=priority:return False,None
                deferred=worst;del self.rows[worst]
            self.serial+=1;row=(priority,self.serial,unit,glossary)
            self.rows[unit.id]=row;heapq.heappush(self.heap,(priority,self.serial,unit.id))
            if len(self.heap)>self.limit*4:
                self.heap=[(r[0],r[1],uid) for uid,r in self.rows.items()];heapq.heapify(self.heap)
            self.condition.notify_all();return True,deferred

    def queued_ids(self):
        with self.condition:return tuple(self.rows)

    def promote(self,unit,glossary=None):
        with self.condition:
            if unit.id not in self.rows:return False,None
            return self.submit(unit,glossary)

    def pop(self):
        with self.condition:
            while self.heap:
                priority,serial,uid=heapq.heappop(self.heap);row=self.rows.get(uid)
                if row is not None and row[:2]==(priority,serial):
                    del self.rows[uid];return row[2],row[3]
            return None

    def pending(self):
        with self.condition:return len(self.rows)

    def wait_or_close(self):
        with self.condition:
            if self.rows:return True
            self.condition.wait(.3)
            if self.rows:return True
            self.closed=True;return False

    def close(self):
        with self.condition:
            deferred=tuple(self.rows);self.closed=True;self.rows.clear();self.heap.clear();self.condition.notify_all()
            return deferred


def run_online(units,target,cache,cancelled,success,failure,warning=lambda message:None,glossary=None,channel='mymemory',feed=None,deferred=lambda ids:None):
    iterator=iter(units);finished=0;limited=False
    def flush():
        try:getattr(cache,'flush_due',cache.flush)()
        except (OSError,ValueError):warning('本地缓存暂未保存；成功译文已保留，后续条目继续处理。')
    try:
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='AbyssText-online') as pool:
            pending={}
            while not cancelled():
                while len(pending)<2 and not cancelled() and not limited:
                    if feed is not None:work=feed.pop()
                    else:
                        unit=next(iterator,None);work=(unit,glossary) if unit is not None else None
                    if work is None:break
                    unit,terms=work
                    future=pool.submit(cache.translate,unit,target,cancelled=cancelled,glossary=terms,channel=channel)
                    pending[future]=unit
                if not pending:
                    if not limited and feed is not None and feed.wait_or_close():continue
                    break
                done,_=wait(pending,timeout=.05,return_when=FIRST_COMPLETED)
                for future in done:
                    unit=pending.pop(future)
                    if cancelled():continue
                    try:result=future.result()
                    except Exception as error:
                        failure(unit,error)
                        if getattr(error,'retry_after',0)>=3600:limited=True
                    else:
                        if not cancelled():success(result)
                    finished+=1
                    if finished%4==0:flush()
            for future in pending:future.cancel()
        if finished%4:flush()
    finally:
        if feed is not None:
            waiting=feed.close()
            if waiting:deferred(waiting)
