# SongOS 项目现状同步

> **给新加入上下文的 AI（CTO 角色）。读完此文档即拥有全部前置共识。请基于此文档推进，不要重新发散。**

---

## 项目定义

SongOS = **Personal Work Intelligence Engine（个人工作智能引擎）**

**不是**笔记软件、不是 Workflow SaaS、不是 Obsidian AI 插件。

**长期目标**：构建 Song 的 Digital Twin —— 让 AI 学会 Song 如何思考、如何决策、如何工作，最终自动化部分工作。

---

## 已否定的方向

| 方向 | 为什么放弃 |
|------|-----------|
| Workflow OS（记录→分析→自动化） | 过于宏大，倾向平台化，单人无法完成 |
| 单纯 Obsidian AI 插件（结构化数据库） | 与 Smart Connections/Dataview/Copilot 高度重叠 |

---

## 当前产品定位

**Smart Connections**：内容检索 — "找到和当前笔记相关的内容"  
**SongOS**：行为分析 — "发现你的行为模式、决策规律、自动化方向"

| 分析维度 | 具体问题 |
|----------|---------|
| 行为频率 | 哪些工作流重复最多？ |
| 决策密度 | 决策集中在哪些领域？ |
| 时间黑洞 | 时间主要花在哪里？ |
| 自动化优先级 | 哪些步骤值得先自动化？ |

---

## 核心数据假设

AI 学习的不是笔记内容，而是 **行为数据**：

```
Work  → 做了什么（写文章/开发功能/发抖音）
Why   → 为什么做（用户需求/市场机会/个人兴趣）
Signal → 结果如何（播放量/转化率/收入/反馈）
```

每日记录的 `📋行动` `🧠认知` `🧠决策` `🔄复盘` 即行为数据源。

---

## Obsidian Vault 现状

**主库**：`~/Desktop/obsidian知识库/我的数字花园/`

| 数据 | 状态 |
|------|------|
| Daily Notes | 18 天连续（5/13~5/28），结构化 YAML + 段落 |
| Weekly/Monthly Review | 模板已建，未填充 |
| Project System | 12 个活跃项目 |
| Knowledge System | 13 领域地图 |
| Output System | 随笔/框架/简报 等 |
| 摄影学院 | 16 模块课程 |

**关键结论**：不是"从零记录"，而是"激活存量"。应先开发 `ingest`，后开发 `log`。

---

## 开发顺序

```
✅ songos ingest（激活历史数据）      → 996 笔记入库
✅ songos analyze（发现模式）          → Song Behavioral Report v1  
⬜ songos log（增量追加记录）
⬜ songos agent（Digital Twin 行为模拟）
⬜ songos automate（Digital Twin 替代部分工作）
```

---

## 新增模块：analyzer.py

6 维度行为分析引擎，纯 SQLite 查询，无 AI 依赖：

| 维度 | 方法 | 回答的问题 |
|------|------|-----------|
| time_allocation | 行动内容关键词聚类 → 领域分布 + 周度趋势 | Song 时间花在哪？ |
| decision_patterns | 决策类型归类 + 决策节奏 + 决策高峰日 | Song 最常做哪些决策？ |
| project_duration | 项目活跃度评分（词数+链接数）+ 被引用排行 | 哪些项目持续时间最长？ |
| recurring_themes | 标签频率趋势 + 标签共现矩阵 | 哪些主题反复出现？ |
| template_candidates | 重复行动模式检测 + 表格结构识别 | 哪些工作可以模板化？ |
| automation_candidates | 频率 × 可重复性 评分 | 哪些工作适合优先自动化？ |

---

## 技术架构

- **语言**：Python 3.12
- **CLI**：typer
- **DB**：SQLite（6 表 + 9 索引 + ON DELETE CASCADE）
- **AI Provider**：Router 模式（DeepSeek → Gemini → Claude → GPT fallback），免费额度优先
- **环境**：macOS 本地，零云依赖
- **数据源**：Obsidian/Notion/飞书 等 ≠ 平台，只是数据源。SongOS 是中间层

---

## Schema（最终版）

```sql
-- 6 tables: notes, sections, links, entities, entity_mentions, tags, note_tags
-- 9 indexes + ON DELETE CASCADE on all FK relationships
-- Full DDL in README.md
```

**已通过 test_schema.py 验证**：建表、CASCADE 删除、索引全部通过。

---

## 当前工程状态

| 状态 | 产出 |
|------|------|
| ✅ Phase 0: `ingest` | config → db → md_parser → ingest → cli → reporter 全链路跑通 |
| ✅ Phase 1: `analyze` | analyzer.py 6 维度 + decision trajectory + 3 CLI 命令 |
| ✅ v0.1.1 | review 修复：user_name 配置、pyproject.toml、parser 改名、bug 修复 |
| ✅ v0.1.2 | files_unchanged 公式修复（排除已修改文件） |
| ✅ 开源 | GitHub 仓库就绪，README 面向公共 |

### 仓库结构

```
songos/
├── cli.py              ← 入口：songos（无参数=一句话洞察）
├── ingest.py           ← Obsidian → SQLite
├── md_parser.py        ← Markdown 解析器（避免遮蔽 builtin parser）
├── analyzer.py         ← 行为分析引擎
├── reporter.py         ← 报告生成器
├── db.py               ← SQLite 操作
├── config.py           ← 配置管理（user_name / output_language）
├── pyproject.toml      ← pip install -e . → songos 命令可用
├── test_schema.py      ← Schema 验证
├── examples/           ← demo_report.md
├── docs/               ← roadmap.md
├── README.md / LICENSE / .gitignore
```

---

## Phase 0 目标

**`songos ingest`** — 唯一功能。 ✅ 已完成

## Phase 1 目标（当前）

**`songos analyze`** — 行为分析引擎。 ✅ 已完成

命令：
```bash
songos analyze                          # 完整行为报告 → stdout
songos analyze --mode actions           # 只看行动分析
songos analyze --mode decisions         # 只看决策分析
songos analyze --mode projects          # 只看项目周期
songos analyze --mode themes            # 只看主题趋势
songos analyze --mode templates         # 只看模板化候选
songos analyze --mode automation        # 只看自动化优先级
songos analyze --write-vault            # 写入 Obsidian Dashboard
```

---

## CTO 要求

1. 基于上述共识推进，不要重新发散讨论
2. 如发现逻辑漏洞、Schema 问题、Parser 问题，直接指出
3. 不要默认上述方案一定正确
4. 下一步：按 plan 顺序开始编码（config → db → parser → ingest → cli → reporter → 端到端测试）
