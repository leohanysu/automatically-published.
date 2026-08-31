"""
TTS 配音 + Whisper 逐句对齐工具
用法: python tts_align.py <record_id> <text> <video_duration>
流程: edge-tts 生成配音 → faster-whisper 识别逐句时间戳 → 输出 alignment.json
输出: {mp3, rate, duration, segments: [{start, end, text, words: [{word, start, end}]}]}
"""

import subprocess, os, sys, json, time

TTS_VOICE = "en-US-AriaNeural"
WORK = os.path.expanduser("~/Downloads/feishu_videos/work")

# edge-tts 完整路径（sandbox PATH 解析不可靠，用绝对路径最稳）
EDGE_TTS = os.path.expanduser(r"~/AppData/Local/hermes/hermes-agent/venv/Scripts/edge-tts.exe")
if not os.path.exists(EDGE_TTS):
    EDGE_TTS = "edge-tts"  # 回退到 PATH 查找

def video_duration(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path.replace("\\", "/")],
                       capture_output=True, text=True, timeout=10)
    return float(r.stdout.strip())

def pick_rate(video_dur):
    if video_dur < 6: return "+70%"
    elif video_dur < 10: return "+55%"
    elif video_dur < 20: return "+50%"
    else: return "+40%"

def shorten(text, over_sec):
    words = text.split()
    n = min(len(words) - 8, int(over_sec * 3))
    return " ".join(words[:-n]) if n > 0 else text

def generate_voiceover(text, rate, mp3_path):
    """edge-tts 生成，带重试"""
    for attempt in range(3):
        r = subprocess.run([EDGE_TTS, "--voice", TTS_VOICE, "--rate", rate,
                            "--text", text, "--write-media", mp3_path.replace("\\", "/")],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 3000:
            return True
        print(f"  edge-tts 第{attempt+1}次失败，重试...")
        time.sleep(2)
    return False

def align_words(mp3_path):
    """faster-whisper 逐句+逐词时间戳"""
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(mp3_path.replace("\\", "/"), word_timestamps=True)
    result = {"duration": info.duration, "segments": []}
    for seg in segments:
        words = [{"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
                 for w in (seg.words or [])]
        result["segments"].append({
            "start": round(seg.start, 2), "end": round(seg.end, 2),
            "text": seg.text.strip(), "words": words
        })
    return result

def tts_and_align(rid, text, video_dur, out_dir=None):
    """完整流程：生成配音 + 对齐。返回 dict"""
    out_dir = out_dir or WORK
    os.makedirs(out_dir, exist_ok=True)
    rate = pick_rate(video_dur)
    mp3 = os.path.join(out_dir, f"{rid}_voice.mp3")
    
    # 生成 + 时长检查循环（超时自动精简）
    for _ in range(4):
        if not generate_voiceover(text, rate, mp3):
            raise RuntimeError("TTS 生成失败")
        dur = video_duration(mp3)
        if dur <= video_dur:
            break
        print(f"  配音{dur:.1f}s 超视频{video_dur:.1f}s，精简重试...")
        text = shorten(text, dur - video_dur)
    else:
        raise RuntimeError("TTS 时长无法适配")
    
    # Whisper 对齐
    print("  Whisper 对齐中...")
    alignment = align_words(mp3)
    
    result = {
        "rid": rid, "mp3": mp3, "rate": rate,
        "duration": dur, "video_duration": video_dur,
        "segments": alignment["segments"]
    }
    with open(os.path.join(out_dir, f"{rid}_alignment.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result

def build_scenes_from_alignment(alignment):
    """把逐句时间戳转成 HyperFrames 分镜（剪映式字幕）"""
    scenes = []
    for i, seg in enumerate(alignment["segments"]):
        text = seg["text"]
        # 按词数切成 1-2 行
        words = text.split()
        if len(words) <= 4:
            lines = [("big", text)]
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

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python tts_align.py <record_id> <text> <video_duration>")
        sys.exit(1)
    rid, text, vdur = sys.argv[1], sys.argv[2], float(sys.argv[3])
    result = tts_and_align(rid, text, vdur)
    print(f"\n✅ 对齐完成: {result['duration']:.1f}s, {len(result['segments'])}句")
    for s in result["segments"]:
        print(f"  [{s['start']:.1f}→{s['end']:.1f}] {s['text']}")
