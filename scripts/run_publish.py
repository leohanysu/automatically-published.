"""Runner for publish_ws.py - passes args via env to avoid shell quoting issues"""
import os, sys, asyncio, json
import websockets  # needed by publish_ws.main()

sys.path.insert(0, r"C:\Users\Administrator\AppData\Local\hermes\skills\media\squishy-factory-copy\scripts")

import importlib.util
spec = importlib.util.spec_from_file_location(
    "publish_ws",
    r"C:\Users\Administrator\AppData\Local\hermes\skills\media\squishy-factory-copy\scripts\publish_ws.py",
)
pw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pw)
pw.websockets = websockets  # publish_ws only imports websockets under __main__

video = os.environ["PW_VIDEO"]
title = os.environ["PW_TITLE"]
body = os.environ["PW_BODY"]
tags = os.environ["PW_TAGS"]

port, ws_path = pw.get_cdp_info()
print(f"CDP: ws://127.0.0.1:{port}{ws_path}")
ok = asyncio.run(pw.main(video, title, body, tags, f"ws://127.0.0.1:{port}{ws_path}"))
print(f"RESULT: {'SUCCESS' if ok else 'FAILED'}")
sys.exit(0 if ok else 1)
