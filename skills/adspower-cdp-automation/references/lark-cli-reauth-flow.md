# lark-cli 授权过期 → 二维码重授权流程（实测 2026-08-19）

## 触发信号

`lark-cli base +url-resolve --url <wiki链接>` 或任何 base 读操作返回：

```json
{"ok": false, "error": {"type": "authentication", "subtype": "token_missing",
  "hint": "run: lark-cli auth login to re-authorize"}}
```

## 完整流程（一步都不能省）

### 1. 后台启动授权（会阻塞等扫码，必须 background）

```bash
lark-cli auth login --recommend   # 后台跑：terminal(background=true)
```

输出里会给出 `verification_url`（形如
`https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=...&user_code=XXXX-XXXX`）
和 `user_code`。注意：**不要在同一轮展示 URL 后立刻阻塞执行 --device-code**，也不要短 timeout 反复重试——每次重启会作废上一轮的 device code。

### 2. 生成 PNG 二维码（必须步骤）

```bash
cd "C:/Users/Administrator"   # --output 只接受相对路径！
lark-cli auth qrcode "<verification_url>" --output feishu_auth_qr.png
```

返回 `{"ok": true, "file_path": "C:\\Users\\Administrator\\feishu_auth_qr.png"}`。
⚠️ `--output` 必须是当前目录相对路径，绝对路径会报 invalid_argument。

### 3. 回复用户：先 URL 再二维码图片

回复中**先输出 URL（原样、不可修改的 opaque string），再把二维码 PNG 用 MEDIA: 标签贴在其下方**。仅生成文件不算完成，必须展示图片。

### 4. 等用户回复"好了"后，poll 后台进程确认

```python
# process(action='poll', session_id=...) → status=exited 即授权完成
# 可再跑 lark-cli auth status 确认 scopes
```

## 陷阱

- 授权进程最长阻塞约 10 分钟；terminal 前台跑会 timeout，必须 background=true
- 二维码 PNG 只有 ~876 字节，正常（纯二维码图像）
- 授权后 scopes 包含 base:field:read / base:record:read / wiki:node:retrieve 等，url-resolve 即可用
- 同一 flow 只对同一 user_code 有效，作废后重新 `auth login` 拿新码
