"""补齐 IG/FB标签：对已有标题、但 IG/FB标签 为空的记录，用原视频再生成一次（只写 IG/FB标签 字段）"""
import subprocess, os, json, sys, re, time, shutil

BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
TABLE_ID = "tblJ1dgoGgNFoBIK"
COMFLY_KEY = os.environ.get("COMFLY_API_KEY", "")
COMFLY_URL = "https://ai.comfly.org/v1"
FIELD_IG_TAGS = "fldJ7j365Y"

WORK = os.path.expanduser("~/Downloads/feishu_videos/toc_generate")
NPM_BIN = os.path.expanduser(r"~/AppData/Roaming/npm").replace("/", os.sep)
os.environ["PATH"] = NPM_BIN + os.pathsep + os.environ.get("PATH", "")
LARK = os.path.join(NPM_BIN, "lark-cli.cmd")
os.makedirs(WORK, exist_ok=True)

# 精简提示词：只生成 IG/FB 标签（复用心理学框架）
PROMPT = """你是中国硅胶捏捏乐源头工厂的海外社媒种草专家（Instagram / Facebook Reels）。
根据视频生成 IG/FB 发布用的标签组。

规则：
- 5-10个标签，纯英文，每个带#
- 三层组合：垂直类(#squishy #fidgettoys #asmr #stressrelief) + 泛流量(#satisfying #aesthetic #desksetup) + 场景类(#softlife #cozyvibes)
- 结合视频内容选最贴切的，不要硬凑
- 输出格式：【IG/FB标签】
标签直接跟在【IG/FB标签】后面，一行内用空格分隔"""

def run(cmd, timeout=60, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)

def run_json(cmd, timeout=60, cwd=None):
    r = run(cmd, timeout, cwd)
    idx = r.stdout.find("{")
    if idx < 0:
        raise RuntimeError(f"无JSON: {r.stdout[:200]}")
    return json.loads(r.stdout[idx:])

def lark(*args, timeout=60):
    return run_json([LARK, *args], timeout=timeout)

def get_record(rid):
    d = lark("base", "+record-get", "--base-token", BASE_TOKEN,
             "--table-id", TABLE_ID, "--record-id", rid, "--format", "json")
    data = d["data"]["data"][0]
    fields = d["data"]["fields"]
    return {f: data[i] for i, f in enumerate(fields) if i < len(data)}

def process(rid):
    print(f"\n===== {rid} =====")
    rec = get_record(rid)
    if rec.get("IG/FB标签"):
        print(f"  已有 IG/FB标签，跳过")
        return None
    vids = rec.get("视频") or []
    if not vids:
        print(f"  无视频，跳过"); return None
    token = vids[0]["file_token"]
    src = os.path.join(WORK, f"{rid}_src.mp4")
    if not os.path.exists(src):
        r = run([LARK, "base", "+record-download-attachment", "--base-token", BASE_TOKEN,
                 "--table-id", TABLE_ID, "--record-id", rid, "--file-token", token,
                 "--output", os.path.basename(src), "--overwrite"], timeout=300, cwd=WORK)
        if not os.path.exists(src):
            raise RuntimeError(f"下载失败 {r.stdout[-150:]}")
    print(f"  视频 {os.path.getsize(src)/1048576:.0f}MB")
    # 压缩（限码率）
    gemini_v = os.path.join(WORK, f"{rid}_gemini.mp4")
    if os.path.getsize(src)/1048576 > 19:
        run(["ffmpeg", "-y", "-i", src.replace("\\", "/"),
             "-preset", "veryfast", "-b:v", "1000k", "-maxrate", "1000k",
             "-bufsize", "2000k", "-c:a", "aac", "-b:a", "96k",
             "-vf", "scale=540:960",
             gemini_v.replace("\\", "/")], timeout=300)
    else:
        shutil.copy(src, gemini_v)
    # 上传
    r = run(["curl", "-s", "--max-time", "120", "--noproxy", "*",
             f"{COMFLY_URL}/files",
             "-H", f"Authorization: Bearer {COMFLY_KEY}",
             "-F", "purpose=vision",
             "-F", f"file=@{gemini_v.replace(os.sep, '/')}"], timeout=140)
    url = json.loads(r.stdout)["url"]
    print(f"  comfly上传 ✅")
    # Gemini
    body = json.dumps({
        "model": "gemini-3.1-pro-preview",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": url}}
        ]}],
        "max_tokens": 2048
    })
    r = run(["curl", "-s", "--max-time", "300", "--noproxy", "*",
             f"{COMFLY_URL}/chat/completions",
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {COMFLY_KEY}",
             "-d", body], timeout=320)
    content = json.loads(r.stdout)["choices"][0]["message"]["content"]
    m = re.search(r"【IG/FB标签】\s*\n?\s*(.+)", content)
    ig_tags = m.group(1).strip() if m else ""
    if not ig_tags:
        raise RuntimeError(f"解析失败: {content[:200]}")
    print(f"  IG/FB标签: {ig_tags[:80]}")
    # 回写（只写 IG/FB标签）
    path = os.path.join(WORK, f"{rid}_igtags.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({FIELD_IG_TAGS: ig_tags}, f, ensure_ascii=False)
    lark("base", "+record-upsert", "--base-token", BASE_TOKEN,
         "--table-id", TABLE_ID, "--record-id", rid,
         "--json", open(path, encoding="utf-8").read(), timeout=60)
    print(f"  飞书回写 ✅")
    return {"rid": rid, "tags": ig_tags[:50]}

if __name__ == "__main__":
    for rid in sys.argv[1:]:
        try:
            r = process(rid)
            print(f"✅ {rid} 完成" + (f": {r['tags']}" if r else "（跳过）"))
        except Exception as e:
            print(f"❌ {rid} 失败: {e}")
