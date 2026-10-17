import asyncio, sys, os
LISTEN, TARGET, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
c2s = s2c = 0
async def pipe(r, w, which):
    global c2s, s2c
    try:
        while data := await r.read(65536):
            if which == "c2s": c2s += len(data)
            else: s2c += len(data)
            w.write(data); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass
async def handle(cr, cw):
    sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    await asyncio.gather(pipe(cr, sw, "c2s"), pipe(sr, cw, "s2c"))
async def flush():
    while True:
        open(OUT, "w").write(f"{c2s} {s2c}\n"); await asyncio.sleep(0.2)
async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    await asyncio.gather(srv.serve_forever(), flush())
asyncio.run(main())
