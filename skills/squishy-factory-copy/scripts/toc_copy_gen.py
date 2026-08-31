"""批量生成社媒 ToC 文案（心理学驱动版提示词）: 下载→压缩→comfly上传→Gemini→回写"""
import subprocess, os, json, sys, re, time, shutil

# ============ 配置 ============
BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
TABLE_ID = "tblJ1dgoGgNFoBIK"
COMFLY_KEY = os.environ.get("COMFLY_API_KEY", "")
COMFLY_URL = "https://ai.comfly.org/v1"
FIELD_TITLE = "fldbknGQ6e"   # 视频标题
FIELD_BODY = "fld8QH5cfN"    # 发布正文
FIELD_IG_TAGS = "fldJ7j365Y" # IG/FB标签 (text)
FIELD_FULL = "fldr5zdALy"    # 发布标题参考(完整回复)
# 注: tiktok标签(fld0Qx2af5) 用户有默认值，不生成不覆盖

WORK = os.path.expanduser("~/Downloads/feishu_videos/toc_generate")
NPM_BIN = os.path.expanduser(r"~/AppData/Roaming/npm").replace("/", os.sep)
os.environ["PATH"] = NPM_BIN + os.pathsep + os.environ.get("PATH", "")
# Windows 下 .cmd 需要完整路径 + shell=True 兼容
LARK = os.path.join(NPM_BIN, "lark-cli.cmd")
os.makedirs(WORK, exist_ok=True)

# ============ 心理学驱动版提示词（社媒 ToC） ============
PROMPT = """你是中国硅胶捏捏乐源头工厂（China Silicone Squishy Factory — Direct Source）的海外社媒种草专家（TikTok / IG Reels）。你不写"产品介绍"，你制造"情绪体验"——用户买的不是硅胶玩具，是3秒钟的平静。

核心认知：决策靠感性，文案点燃情绪；卖点=情绪解决方案（焦虑→平静、无聊→愉悦、孤独→陪伴）；每条必须制造至少一个情绪峰值（峰终定律）。

定位句（选1个）：1."The last stress ball you'll ever need." 2."We turn pressure into something cute." 3."3 seconds of calm, in your pocket." 4."Your desk deserves a soft moment." 5."Anxiety hates this one simple toy."

钩子池（每次随机选1种，禁止连续重复）：
1.【损失厌恶】"Every stressful day without one is a wasted day." 强调失去
2.【蔡格尼克】"Wait for the last squeeze... you won't believe it." 悬念未解
3.【感官先行】"Hear that? That's stress leaving." 第一句调起听觉
4.【反差认知】"It looks like dessert. It's NOT dessert." 认知冲突
5.【社交认同】"The squishy taking over US shelves right now." 别人都在用
6.【自我一致性】"You deserve a minute of calm." 给身份贴标签
7.【稀缺性】"This month's styles are limited. When they're gone, gone."

情绪弧线（150-220词，纯英文）：
1.触发：前3秒钩子
2.情绪放大：把压力具象化（长会议、赶deadline、地铁拥挤），先让用户"痛"再给解药
3.感官细节：至少2种感官（触觉：捏下去慢慢回弹像在呼吸；听觉：薄膜脆响+绵软回弹；视觉：多巴胺配色），禁止抽象词
4.身份认同：给用户贴标签（if you're a soft-life person / desk aesthetic lover...）
5.峰值收尾：结尾必须舒服（"好了。压力没了。"）峰终定律
6.CTA：互动引导（Comment your fav / Which one would you squeeze?）

可变奖励暗示："Every style feels different. Try your luck." / "Next drop is even softer."

标签（两套输出，只回写IG/FB；TikTok标签用户有默认值不写入）：
【IG/FB标签】5-10个，三层组合：垂直#squishy #fidgettoys #asmr #stressrelief；泛流量#satisfying #aesthetic #desksetup；场景#softlife #cozyvibes
【TikTok标签】可给可不给，仅供参考不落库

禁止：B2B口吻（wholesale/MOQ/factory pricing）；功能参数堆砌（食品级/检测）；空洞形容词（amazing/great/soft没画面感）；结尾突兀；平铺直叙。

输出格式（严格按此格式）：
【定位句】(1个)
【标题】(≤60字符, 1-2 emoji)
【正文】(150-220词, 纯英文, 情绪弧线6段)
【IG/FB标签】(5-10个, 每个带#)
【TikTok标签】(3-5个, 每个带#)
【钩子原理】(标注本次钩子+原理)"""

# ============ 工具函数 ============
def run(cmd, timeout=60, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)

def run_json(cmd, timeout=60, cwd=None):
    r = run(cmd, timeout, cwd)
    if not r.stdout.strip():
        raise RuntimeError(f"空输出: {cmd[0]} rc={r.returncode} stderr={r.stderr[:200]}")
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

def download_video(rid, rec):
    vids = rec.get("视频") or []
    if not vids:
        raise RuntimeError(f"{rid}: 无视频字段")
    token = vids[0]["file_token"]
    path = os.path.join(WORK, f"{rid}_src.mp4")
    # --output 必须是相对路径，先 cd 到 WORK
    r = run([LARK, "base", "+record-download-attachment", "--base-token", BASE_TOKEN,
             "--table-id", TABLE_ID, "--record-id", rid, "--file-token", token,
             "--output", os.path.basename(path), "--overwrite"], timeout=300, cwd=WORK)
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError(f"{rid}: 下载失败 rc={r.returncode} {r.stdout[-200:]}")
    return path

def prep_for_gemini(src, rid):
    """>19MB 限码率压缩（保留音频！ASMR 声音是内容灵魂），否则直接用"""
    size_mb = os.path.getsize(src) / 1048576
    out = os.path.join(WORK, f"{rid}_gemini.mp4")
    if size_mb <= 19:
        shutil.copy(src, out)
    else:
        print(f"  压缩 {size_mb:.0f}MB -> <19MB (限码率,保留音频)...")
        run(["ffmpeg", "-y", "-i", src.replace("\\", "/"),
             "-preset", "veryfast", "-b:v", "1000k", "-maxrate", "1000k",
             "-bufsize", "2000k", "-c:a", "aac", "-b:a", "96k",
             "-vf", "scale=540:960",
             out.replace("\\", "/")], timeout=300)
        final_mb = os.path.getsize(out) / 1048576
        print(f"  压缩后 {final_mb:.0f}MB")
    return out

def upload_comfly(path):
    r = run(["curl", "-s", "--max-time", "120", "--noproxy", "*",
             f"{COMFLY_URL}/files",
             "-H", f"Authorization: Bearer {COMFLY_KEY}",
             "-F", "purpose=vision",
             "-F", f"file=@{path.replace(os.sep, '/')}"], timeout=140)
    return json.loads(r.stdout)["url"]

def gemini_generate(video_url):
    for model in ["gemini-3.1-pro-preview", "gemini-3-flash-preview"]:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": video_url}}
            ]}],
            "max_tokens": 4096
        })
        r = run(["curl", "-s", "--max-time", "300", "--noproxy", "*",
                 f"{COMFLY_URL}/chat/completions",
                 "-H", "Content-Type: application/json",
                 "-H", f"Authorization: Bearer {COMFLY_KEY}",
                 "-d", body], timeout=320)
        try:
            data = json.loads(r.stdout)
            return data["choices"][0]["message"]["content"], model
        except Exception:
            print(f"  {model} 失败({r.stdout[:60]}), 降级...")
            time.sleep(2)
    raise RuntimeError("Gemini 全部失败")

def parse_result(content):
    """解析【定位句】【标题】【正文】【IG/FB标签】【TikTok标签】"""
    def grab(section):
        m = re.search(rf"【{section}】\s*\n?\s*(.+?)(?=\n\s*【|\Z)", content, re.DOTALL)
        return m.group(1).strip() if m else ""
    position = grab("定位句") or grab("Position")
    title = grab("标题") or grab("Title")
    body = grab("正文") or grab("Body")
    ig_tags = grab("IG/FB标签") or grab("IG/FB tags") or grab("IGTags")
    tk_tags = grab("TikTok标签") or grab("TikTok tags") or grab("TkTags")
    if not ig_tags:
        # 兼容旧版单标签
        ig_tags = grab("标签") or grab("Hashtags") or grab("Tags")
    return position, title, body, ig_tags, tk_tags

def writeback(rid, full, position, title, body, ig_tags):
    """只回写 IG/FB标签；tiktok标签用户有默认值不覆盖"""
    field_map = {
        FIELD_FULL: full,
        FIELD_TITLE: title,
        FIELD_BODY: body,
        FIELD_IG_TAGS: ig_tags,
    }
    path = os.path.join(WORK, f"{rid}_upsert.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(field_map, f, ensure_ascii=False)
    lark("base", "+record-upsert", "--base-token", BASE_TOKEN,
         "--table-id", TABLE_ID, "--record-id", rid,
         "--json", open(path, encoding="utf-8").read(), timeout=60)
    return position

# ============ 主流程 ============
def process(rid):
    print(f"\n===== {rid} =====")
    rec = get_record(rid)
    if rec.get("视频标题"):
        print(f"  已有标题，跳过")
        return None
    src = download_video(rid, rec)
    print(f"  视频 {os.path.getsize(src)/1048576:.0f}MB")
    gemini_v = prep_for_gemini(src, rid)
    print(f"  Gemini用 {os.path.getsize(gemini_v)/1048576:.0f}MB")
    url = upload_comfly(gemini_v)
    print(f"  comfly上传 ✅")
    content, model = gemini_generate(url)
    print(f"  Gemini {model} ✅ ({len(content)}字符)")
    position, title, body, ig_tags, tk_tags = parse_result(content)
    print(f"  定位: {position[:50]}")
    print(f"  标题: {title[:60]}")
    print(f"  IG/FB标签: {ig_tags[:60]}")
    writeback(rid, content, position, title, body, ig_tags)
    print(f"  飞书回写 ✅")
    return {"rid": rid, "title": title}

if __name__ == "__main__":
    rids = sys.argv[1:]
    for rid in rids:
        try:
            r = process(rid)
            print(f"✅ {rid} 完成" + (f": {r['title'][:50]}" if r else "（跳过）"))
        except Exception as e:
            print(f"❌ {rid} 失败: {e}")
