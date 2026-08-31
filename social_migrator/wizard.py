from .config import Config


def run_wizard(input_fn=input, output_fn=print) -> Config:
    output_fn("你好，我是奶团。我会一步一步帮你把自动发布准备好。")
    output_fn("先说明白：飞书多维表格就是你的视频仓库和发布数据库，视频放进去后，我会补齐发布信息。")
    agent = input_fn("你现在使用哪个 Agent（Codex、Claude Code、Cursor 或其他）？ ").strip()
    model = input_fn("这个 Agent 使用的模型叫什么、什么版本？ ").strip()
    vision = input_fn("这个模型能看懂图片吗？能/不能/不确定： ").strip().lower()
    native_vision = True if vision in {"能", "可以", "yes", "y"} else False if vision in {"不能", "no", "n"} else None
    base = input_fn("请提供飞书多维表格链接或 Base token；如果还没有，我可以带你创建： ").strip()
    platforms = input_fn("要启用哪些平台（meta,tiktok,x,youtube,pinterest），直接回车默认 meta,tiktok： ").strip()
    selected = [p.strip() for p in platforms.split(",") if p.strip()] or ["meta", "tiktok"]
    cfg = Config(agent=agent, model=model, native_vision=native_vision, feishu_base_token=base, platforms=selected)
    output_fn("向导完成：下一步先运行 preflight，不会自动发布；通过后我会再向你确认是否发布 1 条视频。")
    return cfg
