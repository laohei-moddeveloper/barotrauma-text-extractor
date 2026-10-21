"""Bounded online work. A failed record must never discard other results."""
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_online(units, target, cache, cancelled, success, failure):
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
            cache.flush()
