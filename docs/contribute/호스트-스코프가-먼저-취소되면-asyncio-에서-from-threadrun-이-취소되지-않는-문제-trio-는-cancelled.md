---
id: 호스트-스코프가-먼저-취소되면-asyncio-에서-from-threadrun-이-취소되지-않는-문제-trio-는-cancelled
title: "호스트 스코프가 먼저 취소되면 asyncio 에서 from_thread.run() 이 취소되지 않는 문제 (Trio 는 Cancelled)"
sidebar_position: 61
slug: "61"
tags: [Discussion]
keywords: [Discussion]
last_update:
  date: 2026-10-19
---

## anyio Discussion (Q&A): asyncio 에서 호스트 스코프가 먼저 취소되면 from_thread.run() 이 취소되지 않음

### 한 줄 요약

`to_thread.run_sync()` 로 돌던 워커 스레드가 블로킹 작업을 하는 사이 호스트 쪽 cancel scope 가 취소되면, 그 뒤에 부르는 `anyio.from_thread.run()` 이 asyncio 백엔드에서는 취소되지 않고 끝까지 돈다. 같은 스레드에서 `from_thread.check_cancelled()` 는 취소를 알리고, Trio 백엔드에서는 같은 `from_thread.run()` 이 바로 `Cancelled` 를 낸다. 의도된 동작인지 묻는다.

### 배경 (SceneMaker 에서 쓰는 곳)

- `api/api-external/lib/client/proxy.py` 의 `forward()` 가 동기(def) FastAPI 핸들러 안에서 `anyio.from_thread.run(request.body)` 로 요청 본문을 읽는다. 핸들러는 Starlette 가 `anyio.to_thread.run_sync()` 로 워커 스레드에서 돌린다.
- `lib/http/compose.py` 의 compose 핸들러는 본문을 읽기 전에 DB 조회(`t_compose.select_composes` )를 블로킹으로 먼저 한다. 그 사이 요청 스코프가 취소되면 이번에 찾은 경우와 같은 순서가 된다.
- `@app.middleware("http")` (BaseHTTPMiddleware) 를 쓰므로 엔드포인트는 Starlette 의 anyio task group 안에서 돈다. 즉 anyio cancel scope 로 취소될 수 있는 구조다.
- 운영 버전: anyio 4.15.1 / starlette 1.6.0 / fastapi 0.141.1 / uvicorn 0.52.4 (GPU 서버 venv 확인). 장애를 겪은 것은 아니고, 이 경로의 취소 동작을 시험하다 찾았다. 본문에도 "checking what happens" 로 적었다.

### 재현

```python
import sys, time
import anyio
from anyio import from_thread, to_thread

def worker():
    time.sleep(0.3)  # 이 사이에 move_on_after(0.1) 만료
    try:
        from_thread.check_cancelled()
    except BaseException as exc:
        print("check_cancelled():", type(exc).__name__)
    start = time.monotonic()
    try:
        from_thread.run(anyio.sleep, 2)
        print(f"from_thread.run(): returned after {time.monotonic() - start:.1f}s")
    except BaseException as exc:
        print(f"from_thread.run(): {type(exc).__name__} after {time.monotonic() - start:.1f}s")

async def main():
    with anyio.move_on_after(0.1):
        await to_thread.run_sync(worker)

anyio.run(main, backend=sys.argv[1])
```

결과 (anyio 4.15.1 과 master 6219807, Python 3.12.12 / 3.13.12, trio 0.34.0 모두 동일):

```text
asyncio: check_cancelled(): CancelledError / from_thread.run(): returned after 2.0s
trio:    check_cancelled(): Cancelled      / from_thread.run(): Cancelled after 0.0s
```

- `anyio.sleep_forever` 로 바꾸면 asyncio 쪽은 끝나지 않는다 (timeout 10초로 확인, trio 는 바로 종료).
- 스레드가 이미 `from_thread.run()` 안에서 기다리는 중에 취소되면 asyncio 도 정상적으로 취소된다. "취소된 뒤에 호출" 한 경우만 문제다.
- 원인 추정 (코드 확인): asyncio `CancelScope._deliver_cancellation` 은 취소할 태스크가 없으면(호스트 태스크는 to_thread 의 shield 안에 있음) 재시도를 멈추고 `_cancel_handle = None` 이 된다. `from_thread.run()` 이 만든 태스크는 그 뒤에 `scope._tasks` 에 추가되는데 전달을 다시 시작하지 않는다. 같은 원리로 shield 안에서 이미 취소된 task group 에 `start_soon()` 한 자식도 asyncio 에서만 취소되지 않는다.

### 묻는 것

`from_thread.run()` 이 Trio 처럼 이 경우에도 취소되어야 하는지, 아니면 호스트가 취소됐을 수 있는 상황에서는 `check_cancelled()` 만 믿어야 하는지.

### 중복 확인

issues/PRs/discussions 를 키워드 20여 개로 검색 (`repro.txt` 에 전체 기록). 가장 가까운 것은 `#1113` (check_cancelled 의 CancelledError 가 스코프 밖으로 새던 문제, 4.14.0 에서 수정)과 `#629` (check_cancelled 도입). 이번 건은 from_thread.run 이 아예 취소되지 않는 문제라 다르다. 열린 PR `#1093` , `#1260` 도 다른 경로(_spawn 의 task_done, native cancel 재시도)를 다룬다.

링크: https://github.com/agronholm/anyio/discussions/1427

