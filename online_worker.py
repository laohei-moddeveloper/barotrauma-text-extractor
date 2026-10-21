"""Bounded online work. A failed record must never discard other results."""
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_online(units, target, cache, cancelled, success, failure, warning=lambda message:None):
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='AbyssText-online') as pool:
        for start in range(0, len(units), 4):
            if cancelled(): break
            pending = {pool.submit(cache.translate, unit, target, cancelled=cancelled): unit
                       for unit in units[start:start+4]}
            for future in as_completed(pending):
                if cancelled():
                    for waiting in pending: waiting.cancel()
                    break
                unit = pending[future]
                try:
                    result = future.result()
                except Exception as error:
                    failure(unit, error)
                else:
                    if not cancelled(): success(result)
            try:
                cache.flush()
            except (OSError,ValueError):
                warning('本地缓存暂未保存；成功译文已保留，后续条目继续处理。')
