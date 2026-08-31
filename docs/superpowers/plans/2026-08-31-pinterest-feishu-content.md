# Pinterest Feishu Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为当前飞书 Base 增加 Pinterest 专属标题、描述、标签字段，并为现有视频记录写入 Marshkiky 品牌化 Pinterest 文案，保持既有 Meta/TikTok 字段不变。

**Architecture:** 先读取字段和记录快照，创建三个独立文本字段，再按 record_id 批量写入固定模板文案；写入后重新读取字段、记录并做逐条校验。全过程不打开、不发布任何社媒视频。

**Tech Stack:** lark-cli Base API、PowerShell、Markdown 证据与 Obsidian 项目日志。

## Global Constraints

- Base token: `${FEISHU_BASE_TOKEN}`
- Table id: `tblJ1dgoGgNFoBIK`
- Preserve existing fields `视频标题`、`发布正文`、`IG/FB标签` unchanged.
- New fields: `Pinterest标题`、`Pinterest描述`、`Pinterest标签`，all plain text.
- Website CTA must point to `https://www.marshkiky.com/`.
- Do not run Meta, TikTok, X, YouTube, Reddit, or Pinterest publishing.
- Keep evidence artifacts and append an Obsidian log entry after verification.

### Task 1: Create Pinterest fields

**Files:**
- Create: `logs/pinterest-field-create-20260831.json`

- [x] **Step 1: Create three plain-text fields in one request**

Run:

```powershell
lark-cli base +field-create --base-token ${FEISHU_BASE_TOKEN} --table-id tblJ1dgoGgNFoBIK --json '[{"name":"Pinterest标题","type":"text"},{"name":"Pinterest描述","type":"text"},{"name":"Pinterest标签","type":"text"}]' --format json --as user
```

Expected: `ok: true` and three created field ids.

- [x] **Step 2: Read field schema and save evidence**

Run:

```powershell
lark-cli base +field-list --base-token ${FEISHU_BASE_TOKEN} --table-id tblJ1dgoGgNFoBIK --format ndjson --as user | Set-Content -Encoding utf8 logs/pinterest-field-create-20260831.json
```

Expected: fields named `Pinterest标题`、`Pinterest描述`、`Pinterest标签` exist and type is `text`.

### Task 2: Write Pinterest copy to all existing records

**Files:**
- Create: `logs/pinterest-write-20260831.json`

- [x] **Step 1: Export record ids and current fields**

Run:

```powershell
lark-cli base +record-list --base-token ${FEISHU_BASE_TOKEN} --table-id tblJ1dgoGgNFoBIK --field-id fldbknGQ6e --field-id fld8QH5cfN --field-id fldJ7j365Y --format ndjson --output ./logs/pinterest-write-source-20260831.ndjson --overwrite --as user
```

Expected: complete export with `has_more: false`; preserve source fields exactly.

- [x] **Step 2: Build per-record update JSON**

For every exported `record_id`, set a unique Pinterest title and description derived from that record's existing video hook; use the same brand tag set for all records. The final mapping is stored in `logs/pinterest-copy-refined-payload-20260831.json`. Example:

```json
{
  "Pinterest标题": "Zero-Calorie Cake Squishy for Stress Relief | Marshkiky",
  "Pinterest描述": "A sweet-looking squeeze with zero calories and 100% calming texture 🍰✨ Discover Marshkiky's handmade slow-rising squishy toys for cozy desk breaks, sensory play, collecting, and gifting. Shop this food-inspired design at https://www.marshkiky.com/ — made slowly, held softly.",
  "Pinterest标签": "#squishy #squishytoy #squishylover #stressrelieftoys #sensorytoys #fidgettoy #slowrisingsquishy #handmadesquishy #kawaiitoys #asmr #satisfying #deskaccessories #giftideas #marshkiky"
}
```

- [x] **Step 3: Batch update only the three new field ids**

Use `lark-cli base +record-batch-update` with the field ids returned by Task 1 and a JSON object keyed by the exported record ids. Do not include any existing field id in the update payload.

Expected: `ok: true` for all 14 records.

### Task 3: Verify and document

**Files:**
- Create: `logs/pinterest-write-verify-20260831.ndjson`
- Modify: `C:\Users\Administrator\.codex\Codex-Global-Vault\Codex-Projects\codex社媒自动化迁移包-2026-08-20\log.md`

- [x] **Step 1: Re-read new fields and preserved fields**

Run:

```powershell
lark-cli base +record-list --base-token ${FEISHU_BASE_TOKEN} --table-id tblJ1dgoGgNFoBIK --field-id fldbknGQ6e --field-id fld8QH5cfN --field-id fldJ7j365Y --field-id Pinterest标题 --field-id Pinterest描述 --field-id Pinterest标签 --format ndjson --output ./logs/pinterest-write-verify-20260831.ndjson --overwrite --as user
```

The field names resolve to the ids created in Task 1; the verification command intentionally includes both the three new fields and the three preserved fields.

Expected: 14 records, `has_more: false`, all three Pinterest fields populated, and existing fields match the source export byte-for-byte after JSON normalization.

- [x] **Step 2: Append an Obsidian milestone**

Record created field ids, number of updated records, verification result, and the fact that no publishing actions ran.

- [x] **Step 3: Report concise completion**

Provide field names, record count, verification status, and note that publishing was not run.
