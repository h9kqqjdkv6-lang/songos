# PARSER_SPEC.md — SongOS Obsidian Markdown Parser Specification

> **读这个再写 `parser.py`。** 每种 Obsidian 特有语法必须有「输入 → 输出」的明确规则。开发靠直觉 = 边界语法必崩。

---

## 1. YAML Frontmatter

### 输入
```markdown
---
title: 2026-05-27 每日记录
type: daily-note
tags:
  - daily
  - 面试
  - 深圳
related:
  - "[[2026-05-26]]"
  - "[[面试复盘]]"
created: 2026-05-27
---
正文开始...
```

### 输出
```python
{
    "title": "2026-05-27 每日记录",
    "type": "daily-note",
    "tags": ["daily", "面试", "深圳"],
    "created": "2026-05-27",
    "related": ["2026-05-26", "面试复盘"]
}
```
- `type` 映射到 `note_type`（daily-note → DAILY, weekly-review → WEEKLY_REVIEW 等）
- `related` 中的 `[[]]` 剥离为纯文本
- 无 frontmatter → 返回 `{}`，不报错

---

## 2. `[[wikilinks]]`

### 输入
```markdown
参见 [[2026-05-26]] 和 [[面试复盘|上次面试的详细记录]]。
![[image.png]] 是嵌入图片，[[notexists]] 尚未创建。
```

### 输出
```python
[
    {"target": "2026-05-26",   "alias": None,        "context": "参见 和 …"},
    {"target": "面试复盘",      "alias": "上次面试的详细记录", "context": "…和 …"},
    # ![[image.png]] → 不生成 wikilink，归入 embeds
    {"target": "notexists",    "alias": None,         "context": " 尚未创建。"}
]
```
- `[[target|alias]]` → target 和 alias 分别提取
- `![[embeds]]` → 跳过，不存为 wikilink（存为 asset reference，此处不处理）
- `[[target]]` → alias=None

---

## 3. `![[embeds]]` (embedded files)

### 输入
```markdown
配置截图：![[screenshot.png]]
```

### 输出
从 wikilink 解析中排除。`links` 表不存嵌入资源。如需存，放入 `assets` 表（未定义，Phase 2）。

---

## 4. `#inline-tags`

### 输入
```markdown
今天面试了智远 #面试 #低空经济 收获很大
```

### 输出
```python
["面试", "低空经济"]
```
- 仅匹配 `#[^\s#]+`（不含空格的连续字符）
- 与 YAML frontmatter 的 `tags:` 字段分开存储（`tag_type = 'inline'`）
- frontmatter tags → `tag_type = 'frontmatter'`

---

## 5. `%%comments%%`

### 输入
```markdown
这段是正文。%%这是注释，不应该被索引。%% 继续正文。
```

### 输出
```python
# 正文内容（已剥离注释）
"这段是正文。 继续正文。"
```
- `%%...%%` 及其中间内容整体删除，不在任何步骤中保留

---

## 6. `- [ ]` / `- [x]` Tasks

### 输入
```markdown
- [ ] 等Offer + 确认出海安防形态
- [x] 完成面试复盘
```

### 输出
```python
[
    {"text": "等Offer + 确认出海安防形态", "completed": False},
    {"text": "完成面试复盘", "completed": True}
]
```
- 仅匹配行首 `- [ ]` 或 `- [x]`
- 不匹配有序列表 `1. [ ]`（Obsidian 任务语法仅支持无序列表）

---

## 7. `> callouts`

### 输入
```markdown
> [!note] 这是一条笔记
> [!warning] 注意这段逻辑
> 普通引用无 callout 类型
```

### 输出
```python
[
    {"type": "note",    "content": "这是一条笔记"},
    {"type": "warning", "content": "注意这段逻辑"},
    # 第三行无 ![...] → 不识别为 callout
]
```
- `> [!TYPE]` → 识别，type 小写存入
- 不含 `!` → 不识别

---

## 8. `dataview` Code Blocks

### 输入
````markdown
```dataview
TABLE file.ctime FROM "Daily_Notes" SORT file.ctime DESC
```
````

### 输出
跳过，不解析。存储为 `raw_code_block_type = 'dataview'`，内容不索引为正文。

---

## 9. Section Splitting（`## ` headings）

### 输入（来自真实 Daily Note）
```markdown
## 📋 今日行动

| 时间 | 事项 | 结果 |

## 💡 认知收获

- **这场面试和云世纪被拒之间隔了20天**

## 🧠 关键决策

- **接受"你太菜了"不防御**
```

### 输出
```python
[
    {"heading": "📋 今日行动", "heading_level": 2, "section_type": "ACTION", "content": "| 时间 | 事项 | 结果 |", "position": 1},
    {"heading": "💡 认知收获", "heading_level": 2, "section_type": "INSIGHT", "content": "- **这场面试和云世纪...**", "position": 2},
    {"heading": "🧠 关键决策", "heading_level": 2, "section_type": "DECISION", "content": "- **接受\"你太菜了\"不防御**", "position": 3},
]
```
### Section Type 映射规则

| Heading 匹配 | section_type |
|-------------|-------------|
| 含 `行动` | ACTION |
| 含 `认知` 或 `收获` | INSIGHT |
| 含 `决策` | DECISION |
| 含 `复盘` | REVIEW |
| 含 `待办` 或 `线索` | TODO |
| 含 `总结` | SUMMARY |
| 其他 | OTHER |

- `heading_level` > 2 不拆分（`###` 属于上层 `##` 的子内容）
- 连续 `## ` 之间为一段 content

---

## 10. Markdown Table Extraction（`📋 今日行动`）

### 输入
```markdown
| 时间 | 事项 | 结果 |
|------|------|------|
| 下午3:30 | 智远无人机面试 | 三面连过 |
| 面试后 | 全场复盘 | 完成复盘笔记 |
```

### 输出
```python
[
    {"时间": "下午3:30", "事项": "智远无人机面试", "结果": "三面连过"},
    {"时间": "面试后",   "事项": "全场复盘",       "结果": "完成复盘笔记"},
]
```
- 第一行为表头，后续行为数据
- 列数不固定，按实际表头动态解析
- 空行结束表格解析

---

## 11. Note Type Classification

| 路径匹配 | note_type |
|----------|-----------|
| `Daily_Notes/` | DAILY |
| `Weekly_Review` | WEEKLY_REVIEW |
| `Monthly_Review` | MONTHLY_REVIEW |
| `04 Project System/` | PROJECT |
| `05 Output System/` | OUTPUT |
| `03 Knowledge System/` | KNOWLEDGE |
| `99 Templates/` | TEMPLATE |
| 其他 | UNKNOWN |

---

## 12. Ignored Directories

遍历时跳过：`.obsidian`, `.git`, `.trash`, `.claude`, `.DS_Store`

---

## 13. Encoding

- 所有文件按 UTF-8 读取
- 非 UTF-8 → 跳过，log WARNING，不阻断

---

## 14. Parser Output Object

每个文件解析完毕后，产生一个 `ParsedNote` 对象：

```python
@dataclass
class ParsedNote:
    path: str
    file_hash: str           # SHA256 of raw bytes
    file_mtime: float
    note_type: str           # DAILY | KNOWLEDGE | PROJECT | OUTPUT | TEMPLATE | UNKNOWN
    title: str
    note_date: str | None
    word_count: int
    frontmatter: dict
    sections: list[dict]     # [{heading, heading_level, section_type, content, position}, ...]
    wikilinks: list[dict]    # [{target, alias, context}, ...]
    inline_tags: list[str]
    tasks: list[dict]        # [{text, completed}, ...]
```

### 测试基线

用 vault 前 50 篇 .md 跑解析器：
- 零异常退出
- `note_type ≠ UNKNOWN` 的笔记 ≥ 90%
- 每条 DAILY 至少识别到 3 个 sections
- wikilinks 数量 ≥ 50（真实 vault 的连接密度）

---

*写完 `parser.py` 后对照此文档逐条验证。任何一条不通过 = 解析器未完工。*
