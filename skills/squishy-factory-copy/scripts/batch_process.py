"""
捏捏乐社媒视频批量处理脚本 v1.0
用法: python batch_process.py <record_id1> <record_id2> ...
流程: 读取记录 → 下载视频 → 上传comfly → Gemini生成文案 → 解析 → 回写飞书
      → TTS配音 → HyperFrames渲染 → 上传成品视频
"""

import subprocess, os, json, sys, re, time, shutil

# ============ 配置 ============
BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
TABLE_ID = "tblDI9jnIMqCP59S"
COMFLY_KEY = os.environ.get("COMFLY_API_KEY", "")
COMFLY_URL = "https://ai.comfly.org/v1"
FIELD_VIDEO = "fldaZm0opu"        # 视频字段
FIELD_TITLE = "fldbknGQ6e"        # 视频标题
FIELD_BODY = "fld8QH5cfN"         # 发布正文
FIELD_FULL = "fldr5zdALy"         # 发布标题参考
FIELD_DUB = "fldOPdvuT4"          # 配音剪辑视频
TTS_VOICE = "en-US-AriaNeural"

WORK = os.path.expanduser("~/Downloads/feishu_videos/work")
HF_BASE = os.path.expanduser("~/Downloads/feishu_videos/squishy-overlay")

# 关键: sandbox/execute_code 中 PATH 不含 npm 全局目录，必须显式加入
NPM_BIN = os.path.expanduser(r"~/AppData/Roaming/npm")
os.environ["PATH"] = NPM_BIN + os.pathsep + os.environ.get("PATH", "")

# ============ 通用 ============
def run(cmd, timeout=60, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return r

def run_json(cmd, timeout=60, cwd=None):
    r = run(cmd, timeout, cwd)
    if not r.stdout.strip():
        raise RuntimeError(f"空输出: {cmd[0]} rc={r.returncode} stderr={r.stderr[:200]}")
    # lark-cli 输出可能带 "Uploading..." 前缀，找到第一个 {
    idx = r.stdout.find("{")
    if idx < 0:
        raise RuntimeError(f"无JSON: {r.stdout[:200]}")
    return json.loads(r.stdout[idx:])

def lark(*args, timeout=60):
    return run_json(["lark-cli", *args], timeout=timeout)

def video_duration(path):
    r = run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path.replace("\\", "/")])
    return float(r.stdout.strip())

def video_size_mb(path):
    return os.path.getsize(path) / 1048576

# ============ Step 1: 读取记录 ============
def get_record(rid):
    d = lark("base", "+record-get", "--base-token", BASE_TOKEN,
             "--table-id", TABLE_ID, "--record-id", rid, "--format", "json")
    data = d["data"]["data"][0]
    fields = d["data"]["fields"]
    rec = {}
    for i, fname in enumerate(fields):
        if i < len(data):
            rec[fname] = data[i]
    return rec

# ============ Step 2: 下载视频 ============
def download_video(rid, rec):
    os.makedirs(WORK, exist_ok=True)
    vids = rec.get("视频") or []
    if not vids:
        raise RuntimeError(f"{rid}: 无视频字段")
    token = vids[0]["file_token"]
    path = os.path.join(WORK, f"{rid}_src.mp4")
    lark("base", "+record-download-attachment", "--base-token", BASE_TOKEN,
         "--table-id", TABLE_ID, "--record-id", rid, "--file-token", token,
         "--output", os.path.basename(path), "--overwrite", timeout=120)
    if not os.path.exists(path):
        raise RuntimeError(f"{rid}: 下载失败")
    return path, token

# ============ Step 3: 准备 Gemini 用视频 ============
def prep_for_gemini(src, rid):
    """≤19MB直接用，>19MB压缩（comfly限制~20MB）"""
    gemini_path = os.path.join(WORK, f"{rid}_gemini.mp4")
    if video_size_mb(src) <= 19:
        shutil.copy(src, gemini_path)
    else:
        run(["ffmpeg", "-y", "-i", src.replace("\\", "/"),
             "-c:v", "libx264", "-crf", "22", "-preset", "fast", "-an",
             gemini_path.replace("\\", "/")], timeout=120)
    return gemini_path

# ============ Step 4: 上传 comfly ============
def upload_comfly(path):
    r = run(["curl", "-s", "--max-time", "90", "--noproxy", "*",
             f"{COMFLY_URL}/files",
             "-H", f"Authorization: Bearer {COMFLY_KEY}",
             "-F", "purpose=vision",
             "-F", f"file=@{path.replace(os.sep, '/')}"], timeout=100)
    return json.loads(r.stdout)["url"]

# ============ Step 5: Gemini 生成 ============
PROMPT = """你是中国硅胶捏捏乐源头工厂（China Silicone Squishy Factory — Direct Source）的海外社媒文案专家。根据视频素材生成面向美国批发商（B2B）的高转化英文帖文。

工厂优势：
- 食品级硅胶 + 无毒检测认证（Food-grade silicone, lab-tested non-toxic）
- 每月 10+ 新款（10+ new styles every month）
- 源头工厂价格，无中间商（Factory-direct pricing, no middleman markup）

标题：从以下7种风格随机选1种，纯英文，30-80字符，1-2个emoji：1.身份直给 2.痛点共鸣 3.新品展示 4.质量打底 5.B端术语 6.社交证明 7.反转

正文骨架（150-250词，纯英文，5层结构）：
1.我是谁（1-2句亮明源头工厂）
2.我能解决什么（针对批发商痛点）
3.为什么选我（食品级硅胶+无毒检测 / 每月10+新款 / 源头价格）
4.结合素材（提及视频中的产品款式）
5.行动号召（DM us for wholesale catalog and factory pricing）

输出格式：【标题】（纯英文）+【正文】（150-250词）+【标签】（5-10个#标签）"""

def gemini_generate(video_url):
    """3级降级: pro → flash → 报错"""
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
            content = data["choices"][0]["message"]["content"]
            return content, model
        except Exception:
            print(f"  {model} 失败({r.stdout[:60]}), 降级...")
            time.sleep(2)
    raise RuntimeError("Gemini 全部模型失败")

# ============ Step 6: 解析 + 回写 ============
def parse_result(content):
    title_m = re.search(r'【标题】\s*\n?\s*(.+?)\n', content) or \
              re.search(r'【Title】\s*\n?\s*(.+?)\n', content)
    title = title_m.group(1).strip() if title_m else ""
    body_m = re.search(r'【正文】\s*\n?\s*(.+?)(?=\n\s*【标签】|\n\s*【Hashtags】|\Z)', content, re.DOTALL)
    if not body_m:
        body_m = re.search(r'【Body】\s*\n?\s*(.+?)(?=\n\s*【标签】|\n\s*【Hashtags】|\Z)', content, re.DOTALL)
    body = body_m.group(1).strip() if body_m else ""
    return title, body

def writeback(rid, full, title, body):
    field_map = {FIELD_FULL: full, FIELD_TITLE: title, FIELD_BODY: body}
    path = os.path.join(WORK, f"{rid}_upsert.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(field_map, f, ensure_ascii=False)
    lark("base", "+record-upsert", "--base-token", BASE_TOKEN,
         "--table-id", TABLE_ID, "--record-id", rid,
         "--json", open(path, encoding="utf-8").read())

# ============ Step 7: TTS 配音 + Whisper 对齐（剪映式） ============
def tts_voiceover(rid, text, video_dur):
    """Edge TTS 生成 + faster-whisper 逐句对齐
    返回 {mp3, rate, duration, segments:[{start,end,text,words}]}
    """
    from tts_align import tts_and_align
    result = tts_and_align(rid, text, video_dur)
    return result

def build_scenes_from_alignment(alignment):
    """把 whisper 逐句时间戳转成 HyperFrames 分镜（字幕与配音精确对齐）"""
    scenes = []
    for seg in alignment["segments"]:
        words = seg["text"].split()
        if len(words) <= 4:
            lines = [("big", seg["text"])]
        elif len(words) <= 8:
            mid = len(words) // 2
            lines = [("big", " ".join(words[:mid])), ("big", " ".join(words[mid:]))]
        else:
            third = len(words) // 3
            lines = [("big", " ".join(words[:third])),
                     ("big", " ".join(words[third:2*third])),
                     ("mid", " ".join(words[2*third:]))]
        scenes.append((seg["start"], seg["end"], lines))
    return scenes

# ============ Step 8: HyperFrames 渲染 ============
def render_video(rid, src_path, mp3_path, adur, vdur, w, h, scenes):
    proj = os.path.join(HF_BASE, f"batch_{rid}")
    assets = os.path.join(proj, "assets")
    os.makedirs(assets, exist_ok=True)
    # 配置复制
    for f in ["hyperframes.json", "meta.json", "package.json"]:
        src_cfg = os.path.join(HF_BASE, f)
        if os.path.exists(src_cfg) and not os.path.exists(os.path.join(proj, f)):
            shutil.copy(src_cfg, proj)
    # 预处理源视频 (crf1 无损去原声)
    prepped = os.path.join(WORK, f"{rid}_prepped.mp4")
    run(["ffmpeg", "-y", "-i", src_path.replace("\\", "/"),
         "-c:v", "libx264", "-crf", "1", "-preset", "fast", "-an",
         "-r", "30", "-g", "30", "-keyint_min", "30", "-movflags", "+faststart",
         prepped.replace("\\", "/")], timeout=180)
    shutil.copy(prepped, os.path.join(assets, "source.mp4"))
    shutil.copy(mp3_path, os.path.join(assets, "voiceover.mp3"))
    # 生成 index.html
    html = build_html(w, h, adur + 0.3, scenes)
    with open(os.path.join(proj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    # check + render
    r = run(["npx", "hyperframes", "check"], timeout=60, cwd=proj)
    if r.returncode != 0:
        print(f"  ⚠ check 警告，继续渲染")
    r = run(["npx", "hyperframes", "render", "--quality", "high", "--crf", "16"],
            timeout=300, cwd=proj)
    # 找最新渲染
    renders_dir = os.path.join(proj, "renders")
    files = sorted(os.listdir(renders_dir)) if os.path.exists(renders_dir) else []
    if not files:
        raise RuntimeError(f"{rid}: 渲染失败")
    return os.path.join(renders_dir, files[-1])

def build_html(w, h, total, scenes):
    scenes_html, animations = "", []
    for i, (start, end, lines) in enumerate(scenes):
        dur = end - start
        lh = "".join(f'          <div class="{c}-text">{t}</div>\n' for c, t in lines)
        scenes_html += f'''      <div id="scene{i}" class="clip" data-start="{start}" data-duration="{dur:.2f}" data-track-index="3">
        <div class="caption-box" style="bottom:{170 - i*10}px">
{lh}        </div>
      </div>

'''
        anim = f'tl.from("#scene{i} .big-text", {{ opacity: 0, y: 15, duration: 0.3, stagger: 0.06 }}, {start + 0.2})'
        if any(c == "mid" for c, _ in lines):
            anim += f'\n        .from("#scene{i} .mid-text", {{ opacity: 0, y: 12, duration: 0.25 }}, {start + 0.5})'
        if any(c == "small" for c, _ in lines):
            anim += f'\n        .from("#scene{i} .small-text", {{ opacity: 0, duration: 0.25 }}, {start + 0.8})'
        animations.append(anim)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width={w}, height={h}" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; width: {w}px; height: {h}px; overflow: hidden; background: #000; font-family: "Inter", sans-serif; }}
#bg-video {{ position: absolute; top: 0; left: 0; width: {w}px; height: {h}px; object-fit: cover; }}
.caption-box {{ position: absolute; left: 24px; right: 24px; text-align: center; z-index: 10; background: rgba(0,0,0,0.65); border-radius: 12px; padding: 14px 12px; }}
.big-text {{ font-weight: 800; font-size: {int(w*0.048)}px; color: #FFFFFF; line-height: 1.15; }}
.mid-text {{ font-weight: 700; font-size: {int(w*0.037)}px; color: #FFFFFF; line-height: 1.15; margin-top: 3px; }}
.small-text {{ font-weight: 600; font-size: {int(w*0.031)}px; color: #EEEEEE; margin-top: 4px; }}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.1f}" data-width="{w}" data-height="{h}">
<video id="bg-video" class="clip" data-start="0" data-duration="{total:.1f}" data-track-index="1" src="assets/source.mp4" muted autoplay playsinline></video>
<audio id="voiceover" class="clip" data-start="0" data-duration="{total:.1f}" data-track-index="2" src="assets/voiceover.mp3"></audio>
{scenes_html}</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(animations)};
window.__timelines["main"] = tl;
</script></body></html>'''

# ============ Step 9: 上传成品（覆盖旧视频） ============
def upload_dub(rid, mp4_path):
    """覆盖式上传：先移除旧附件，再上传新视频"""
    # 1. 读取当前记录的配音剪辑视频字段，拿到旧 file_token
    rec = get_record(rid)
    old_attachments = rec.get("配音剪辑视频") or []
    if old_attachments:
        tokens = [a["file_token"] for a in old_attachments]
        print(f"  移除旧视频 {len(tokens)} 个: {[t[:12]+'...' for t in tokens]}")
        lark("base", "+record-remove-attachment", "--base-token", BASE_TOKEN,
             "--table-id", TABLE_ID, "--record-id", rid,
             "--field-id", FIELD_DUB,
             *[t for pair in [("--file-token", t) for t in tokens] for t in pair],
             "--yes", timeout=60)
        print(f"  旧视频已移除")
    # 2. 上传新视频
    lark("base", "+record-upload-attachment", "--base-token", BASE_TOKEN,
         "--table-id", TABLE_ID, "--record-id", rid,
         "--field-id", FIELD_DUB, "--file", mp4_path.replace("\\", "/"), timeout=120)
    print(f"  新视频已上传（覆盖）")

# ============ 主流程 ============
def process(rid):
    print(f"\n===== {rid} =====")
    rec = get_record(rid)
    if rec.get("视频标题"):
        print(f"  已有标题，跳过文案生成")
    src, token = download_video(rid, rec)
    print(f"  视频 {video_size_mb(src):.1f}MB {video_duration(src):.1f}s")
    gemini_v = prep_for_gemini(src, rid)
    url = upload_comfly(gemini_v)
    print(f"  comfly 上传 ✅")
    content, model = gemini_generate(url)
    print(f"  Gemini {model} ✅ ({len(content)}字符)")
    title, body = parse_result(content)
    print(f"  标题: {title[:60]}")
    writeback(rid, content, title, body)
    print(f"  飞书文案回写 ✅")
    vdur = video_duration(src)
    # 用标题作为配音文本（简短有力）+ whisper 对齐
    align = tts_voiceover(rid, title, vdur)
    adur = align["duration"]
    print(f"  TTS {align['rate']} → {adur:.1f}s ✅ ({len(align['segments'])}句对齐)")
    # 分辨率
    r = run(["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             src.replace("\\", "/")])
    w, h = [int(x) for x in r.stdout.strip().split(",")]
    # 分镜: 用 whisper 对齐时间轴（字幕与配音逐句同步）
    scenes = build_scenes_from_alignment(align)
    out = render_video(rid, src, align["mp3"], adur, vdur, w, h, scenes)
    print(f"  渲染 ✅ {out}")
    upload_dub(rid, out)
    print(f"  成品上传飞书 ✅")
    return {"rid": rid, "title": title, "video": out}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python batch_process.py <record_id> [record_id...]")
        sys.exit(1)
    for rid in sys.argv[1:]:
        try:
            result = process(rid)
            print(f"✅ {rid} 完成")
        except Exception as e:
            print(f"❌ {rid} 失败: {e}")
