# db-output

一个本地优先、规则驱动的数据采集项目，用于投资和求职场景下的数据收集、清洗与结果落库。

## 当前范围

当前仓库包含：

- 需求文档
- 实现方案文档
- 可运行的 Python 项目骨架
- 本地 CLI，用于任务校验与执行
- 来源目录检查 CLI，用于查看已配置的数据源网站
- 任务运行检查 CLI，用于查看本地产物与运行状态
- `raw`、`normalized`、`artifacts` 三层存储
- 便于校验的 SQLite 输出
- 位于 `configs/sources/` 下的配置化来源定义
- 通用 `HTML`、`RSS`、`JSON API` 连接器，而不是在核心代码里硬编码站点
- 所有现有连接器共享的 target/topic 相关性匹配逻辑

## 架构说明

当前核心代码不再硬编码具体公司或网站。

- 任务 JSON 描述领域、目标、时间范围和来源策略
- `src/app/sources/registry.py` 从 `configs/sources/<domain>/*.json` 载入来源定义
- `src/app/services/task_service.py` 根据任务选择匹配的来源配置
- `src/app/connectors/` 里的通用连接器执行对应来源
- topic 限制由 `task.topic_scope` 和来源配置里的 `topic_terms` 共同驱动
- 如果后续切换到同结构的新站点，原则上只需要新增来源配置，而不是重写核心连接器

这意味着当前 `v0.1` 采用“手工维护来源目录 + 通用连接器执行”的方式。业务层决定选哪些源，连接器只负责执行。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

校验任务：

```powershell
db-output validate tasks/examples/company_qianxin_recent_half_year.json
```

查看已配置来源：

```powershell
db-output sources --domain jobs
```

预览某个任务会选中哪些来源：

```powershell
db-output sources --task-file tasks/examples/jobs_python_org_rss_recent.json
```

运行 company_intel 任务：

```powershell
db-output run tasks/examples/company_qianxin_recent_half_year.json
```

运行 jobs HTML 任务：

```powershell
db-output run tasks/examples/jobs_python_org_recent.json
```

运行 jobs RSS 任务：

```powershell
db-output run tasks/examples/jobs_python_org_rss_recent.json
```

运行 public_sentiment API 任务：

```powershell
db-output run tasks/examples/public_sentiment_openai_tech_recent.json
```

运行 finance 财报任务：

```powershell
db-output run tasks/examples/finance_ibm_earnings_recent.json
```

运行 finance 日线行情任务：

```powershell
db-output run tasks/examples/finance_ibm_daily_quotes_recent.json
```

运行 finance 监管公告 RSS 任务：

```powershell
db-output run tasks/examples/finance_sec_press_recent.json
```

查看本地已完成任务：

```powershell
db-output tasks --domain jobs
```

查看某个任务的状态、计数和产物路径：

```powershell
db-output status job-python-org-rss-001
```

查看某个任务保存下来的运行报告和质量报告：

```powershell
db-output report job-python-org-rss-001 --kind all
```

`db-output logs <task_id>` 是 `report` 的别名。

测试链路产生的临时结果说明文件只保留在本地，不纳入版本控制。

默认输出目录是 `data/`。
## Quality Behavior

- quality_policy.dedupe_mode=strict will deduplicate normalized records by dedupe_key before writing output.
- quality_policy.required_fields and quality_policy.max_missing_ratio will drop records that exceed the allowed missing-field ratio.
- normalized.jsonl.gz keeps normalized candidates for inspection, while SQLite only stores the post-quality output rows.