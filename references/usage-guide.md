# Amazon Review Insight Usage Guide

## 中文说明

这份文档面向没有编程基础的使用者，说明如何在 Claude 中使用 `amazon-review-insight` 这个 skill。

正常使用时，用户只需要做 5 件事：

1. 准备一个 Amazon 评论文件
2. 在 Claude 中附上这个评论文件
3. 告诉 Claude 使用 `amazon-review-insight`
4. 等待 Claude 检查环境和默认配置
5. 等待 Claude 返回分析结果文件

正常情况下，用户不需要手动运行任何内部 Python 脚本。

### 这个 Skill 是做什么的

这个 skill 会分析 Amazon 评论数据，并产出以下结果：

- 一份带品牌样式的 HTML 报告
- 一份结构化的 JSON 分析结果
- 一份清洗后的 XLSX 评论表
- 一份简短的 Markdown 摘要

报告是英文商业汇报风格，通常会包含这些内容：

- Executive Summary
- 评分与趋势分析
- 消费者人群画像
- 词云与语义洞察
- Top Advantages
- Top Pain Points
- 建议动作

### 使用前需要准备什么

标准使用时，你只需要准备一个文件：

1. 一个 Amazon 评论文件

默认情况下：

- skill 本体会使用项目里自带的默认 runtime config
- skill 本体会使用项目里自带的 provider registry
- 真正的 API key 从环境变量里读取

只有高级用户需要额外提供自定义 runtime config。

### 评论文件要求

评论文件应当是 Amazon 评论导出的 Excel 或 CSV。

文件中必须包含以下列：

- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Name` 或 `Author`
- `Verified Purchase`

如果缺少这些字段，skill 会停止并提示具体问题。

### 默认配置是什么

这个 skill 现在内置两份默认配置：

- `runtime_config.default.json`
- `provider_registry.json`

它们负责：

- 默认 provider 策略
- fallback 顺序
- provider 定义
- 默认 model/base_url
- 要从哪个环境变量读取真实 key

所以对普通使用者来说，不需要每次再准备一个 runtime config 文件。

### runtime config 文件是什么

runtime config 文件现在是“高级覆盖配置”。

它只在下面这些场景需要：

- 你想临时切换默认 provider
- 你想调整 fallback 顺序
- 你想临时改 `max_reviews`
- 你想临时改 timeout / retries
- 你想对某个 provider 做临时 override

普通使用者可以完全不提供它。

你可以从这个示例文件开始：

- [config/runtime_config.example.json](../config/runtime_config.example.json)

配置格式说明在这里：

- [config/runtime_config.schema.json](../config/runtime_config.schema.json)

通常不需要从零手写，直接从 example 文件改就可以。

### provider registry 文件是什么

provider registry 文件用来告诉 skill：

- 平台有哪些 provider 可以用
- 每个 provider 默认的 `base_url`
- 每个 provider 默认的 `model`
- 每个 provider 对应的 API key 环境变量名

你可以从这个示例文件开始：

- [config/provider_registry.example.json](../config/provider_registry.example.json)

项目内置默认文件：

- [config/provider_registry.json](../config/provider_registry.json)

### runtime config 文件里一般会写什么

一个典型的 runtime config 文件通常会包含：

- 默认 provider
- fallback provider 顺序
- 最大分析评论数
- 超时和最大重试次数
- 可选的 provider override

例如：

```json
{
  "analysis": {
    "max_reviews": 75000,
    "chunk_size": 150,
    "max_chunks": 500,
    "default_provider": "deepseek",
    "fallback_order": ["deepseek", "minimax"]
  },
  "provider_registry_path": "./config/provider_registry.json",
  "provider_overrides": {
    "deepseek": {
      "model": "deepseek-v4-flash"
    }
  }
}
```

这里不会直接放真实 API key，也不应该把真实 key 放在 runtime config 里。

### provider registry 文件里一般会写什么

```json
{
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-v4-flash",
      "api_key_env": "DEEPSEEK_API_KEY"
    },
    "minimax": {
      "base_url": "https://api.minimaxi.com/v1",
      "model": "MiniMax-M2.7",
      "api_key_env": "MINIMAX_API_KEY"
    }
  }
}
```

### API 规则

这个 skill 本身不包含任何可用的 API key。

真正使用它的人，需要自己提供 API 访问权限。

推荐方式是：

- 把 API key 放在自己的环境变量里
- 在 provider registry 文件里维护 `api_key_env`

例如：

```json
{
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-v4-flash",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  }
}
```

这表示：环境里需要先有 `DEEPSEEK_API_KEY`，skill 会从环境里读取真正的 key。

### 在 Claude 里应该怎么说

在 Claude 中使用这个 skill 时，用户应该附上：

- 评论文件

然后可以直接对 Claude 说：

```text
请使用 amazon-review-insight 分析这份 Amazon 评论文件。请使用系统默认配置运行完整流程，并返回 report、analysis JSON、cleaned XLSX 和简短摘要。
```

也可以用更短一点的话术：

```text
请使用 amazon-review-insight 处理这份评论文件，并返回最终报告。
```

### 推荐使用流程

对非技术用户来说，推荐把整个过程理解成下面 6 步：

1. 附上 Amazon 评论文件
2. 告诉 Claude 使用 `amazon-review-insight`
3. 等待 Claude 检查环境和默认配置
4. 等待 Claude 完成分析
5. 打开最终返回的 `report.html`

用户不需要知道内部具体跑了哪些脚本。

### Claude 内部会做什么

当用户提供完文件后，Claude 应该自动完成这些动作：

1. 识别评论文件
2. 加载默认 runtime config 和 provider registry
3. 检查环境和 provider 配置
4. 运行完整分析流程
5. 返回结果文件和简短总结

内部执行通常会通过这些脚本完成：

- [scripts/check_env.py](../scripts/check_env.py)
- [scripts/run_pipeline.py](../scripts/run_pipeline.py)

这些是 Claude 的内部执行工具，不是普通用户的直接操作入口。

### 最终返回的文件分别是什么意思

这个 skill 通常会返回 4 个主要文件。

#### 1. `report.html`

这是主要的阅读型报告。

它适合直接打开阅读、分享给同事、用于业务讨论。

一般来说，这是用户最先应该看的文件。

#### 2. `analysis.json`

这是结构化的机器可读结果。

适合后续程序处理，或者给更懂数据的同事继续使用。

#### 3. `cleaned_reviews.xlsx`

这是审计和追溯文件。

它可以帮助用户查看：

- 清洗后的评论内容
- review ID
- 哪些样本被选入分析
- 分析过程中使用到的关键字段

如果要复核结论来源，这个文件最重要。

#### 4. `summary.md`

这是简短摘要。

适合快速查看，不想先打开完整 HTML 报告时使用。

### 常见报错与问题

#### 1. 缺少字段

如果评论文件没有包含要求的列，skill 会停止。

请检查文件里是否真的有这些列：

- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Name` 或 `Author`
- `Verified Purchase`

#### 2. provider 没配置好

如果没有可用的 provider，skill 会提示没有可用配置。

这时请检查：

- runtime config 文件里写的 provider 是否正确
- 对应的 API key 环境变量是否真的存在

这是最常见的配置问题。

#### 3. 缺少依赖

如果机器没有完成一次性安装，Claude 可能会报缺少依赖，例如：

- `pandas`
- `openpyxl`
- `openai`

这属于安装问题，不是评论文件本身的问题。

#### 4. 分析比较慢

评论很多时，分析可能需要更久，因为模型要分批处理评论 chunk。默认每个 chunk 150 条，最多 500 个 chunk。

如果只是做测试，可以在 runtime config 里降低：

- `analysis.max_reviews`
- `analysis.chunk_size`
- `analysis.max_chunks`

### 怎么阅读最终报告

最终的 HTML 报告是商业汇报风格。

通常你会看到这些模块：

- executive summary
- rating distribution
- trend signals
- persona clusters
- word cloud and semantic insights
- top advantages
- top pain points
- recommendations

实际阅读时，建议按这个顺序看：

1. executive summary
2. top advantages
3. top pain points
4. recommendations
5. 需要时再回看图表

### 正常使用时，用户不需要做什么

在正常使用中，用户不应该需要：

- 手动运行 `preprocess.py`
- 手动运行 `llm_analysis.py`
- 手动运行 `generate_report.py`
- 修改 skill 安装目录里的文件
- 把 API key 直接写进 skill 文件

这些都属于安装或维护工作，不属于普通使用流程。

### 给同事的一句话版本

在 Claude 里同时附上 Amazon 评论文件和 runtime config JSON 文件，然后让 Claude 使用 `amazon-review-insight` 并返回最终报告即可。

---

## English Guide

This guide is for non-technical users who want to use the `amazon-review-insight` skill inside Claude.

The normal user experience is simple:

1. prepare one Amazon review file
2. prepare one runtime config file
3. attach both files in Claude
4. ask Claude to use the skill
5. wait for Claude to return the output files

The user should not need to manually run internal Python scripts during normal use.

### What This Skill Does

This skill analyzes Amazon review data and produces:

- a branded HTML report
- a structured JSON analysis result
- a cleaned XLSX review table
- a short markdown summary

The report is designed for business-style review analysis and includes:

- executive summary
- rating and trend analysis
- customer personas
- word cloud and semantic insights
- top advantages
- top pain points
- strategic recommendations

### What You Need Before Using It

You need two files:

1. an Amazon review file
2. a runtime config JSON file

These two files are task inputs.

They are not part of the skill package itself.

That means:

- the installed skill stays fixed
- each analysis task can use its own review file
- each analysis task can use its own runtime config file

### Review File

The review file should be an Excel or CSV export from Amazon review data.

It must contain these columns:

- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Name` or `Author`
- `Verified Purchase`

If any of these fields are missing, the skill will stop and report the issue.

### Runtime Config File

The runtime config file tells the skill:

- which model provider to use
- which model name to use
- where to find the API key
- how many reviews to analyze
- which fallback order to try if one provider fails

Start from:

- [config/runtime_config.example.json](../config/runtime_config.example.json)

The config format is described by:

- [config/runtime_config.schema.json](../config/runtime_config.schema.json)

In most cases, the user does not need to write this file from scratch.

They should start from the example file and only change the provider settings they actually need.

### What The Runtime Config File Usually Contains

A runtime config file normally includes:

- which provider to try first
- which fallback providers to try next
- which model name to use for each provider
- which API key variable name Claude should look for
- how many reviews to analyze

A typical pattern looks like this:

```json
{
  "analysis": {
    "max_reviews": 75000,
    "chunk_size": 150,
    "max_chunks": 500,
    "fallback_order": ["deepseek", "gemini", "qwen", "minimax"]
  },
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-v4-flash",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  }
}
```

This does not place the real API key inside the file.

It only tells the skill which environment variable should hold the real key.

### Important API Rule

This skill does not contain any active API key.

The person using the skill must provide their own API access.

The recommended pattern is:

- keep the API key in the user's environment
- let the runtime config file point to the environment variable name

Example:

```json
{
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-v4-flash",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  }
}
```

That means the user must already have `DEEPSEEK_API_KEY` available in their environment.

### What To Say In Claude

When using the skill inside Claude, the user should attach:

- the review file
- the runtime config file

Then they can say something like:

```text
Use amazon-review-insight to analyze this Amazon review file with the attached runtime config file. Run the full workflow and return the report, analysis JSON, cleaned XLSX, and a short summary.
```

Another valid version:

```text
Please use the amazon-review-insight skill on this review file and this runtime config JSON. Return the generated report files and summarize the main findings.
```

If the user wants a shorter message, this is also enough:

```text
Use amazon-review-insight with these two files and return the final report.
```

### Recommended Claude Workflow For Users

For non-technical usage, the user should think about the process like this:

1. attach the Amazon review file
2. attach the runtime config JSON file
3. tell Claude to use `amazon-review-insight`
4. wait for Claude to validate the setup
5. wait for Claude to finish the analysis
6. open the returned `report.html`

The user does not need to know which internal script handles each stage.

### What Claude Should Do

After the user provides the files, Claude should:

1. identify the review file
2. identify the runtime config file
3. validate the environment
4. run the internal pipeline
5. return the output files and summary

The internal pipeline is implemented through:

- [scripts/check_env.py](../scripts/check_env.py)
- [scripts/run_pipeline.py](../scripts/run_pipeline.py)

These are internal execution tools for Claude. They are not the normal user interface.

### What The Output Files Mean

The skill usually returns four main files.

#### 1. `report.html`

This is the main presentation report.

It is meant for reading, sharing, and business discussion.

This is usually the first file the user should open.

#### 2. `analysis.json`

This is the structured machine-readable result.

It is useful if another tool, analyst, or workflow needs to reuse the findings.

#### 3. `cleaned_reviews.xlsx`

This is the audit and traceability file.

It helps the user review:

- cleaned comments
- review IDs
- sampled rows
- fields used by the analysis workflow

This is the best file for checking where conclusions came from.

#### 4. `summary.md`

This is the short written summary.

It is useful when the user wants a quick recap without opening the full HTML report.

### Common Failure Cases

#### 1. Missing Columns

If the review file does not include the required columns, the skill will stop.

The user should check whether the file really contains:

- `Content`
- `Rating`
- `Date`
- `Helpful`
- `Name` or `Author`
- `Verified Purchase`

#### 2. Provider Not Configured

If no provider is usable, the skill will report that no configured provider was found.

The user should check:

- whether the runtime config file points to the correct provider
- whether the needed API key environment variable exists

This is the most common setup issue.

#### 3. Missing Dependencies

If the machine was never set up, Claude may report missing dependencies such as:

- `pandas`
- `openpyxl`
- `openai`

This is an installation issue, not a review-data issue.

#### 4. Slow Analysis

Large review sets may take time because the model must process many review chunks. The default is 150 reviews per chunk and up to 500 chunks.

If the user only wants a quick test, reduce:

- `analysis.max_reviews`
- `analysis.chunk_size`
- `analysis.max_chunks`

inside the runtime config file.

### How To Read The Final Report

The final HTML report is designed as a business-style summary.

Typical sections include:

- executive summary
- rating distribution
- review trend signals
- persona clusters
- word cloud and semantic insights
- top advantages
- top pain points
- recommendations

A practical reading order is:

1. executive summary
2. top advantages
3. top pain points
4. recommendations
5. supporting charts if needed

### What The User Should Not Need To Do

During normal use, the user should not need to:

- manually run `preprocess.py`
- manually run `llm_analysis.py`
- manually run `generate_report.py`
- edit the skill package itself
- paste API keys into the skill files

Those are setup or maintenance tasks, not the normal user workflow.

### One-Sentence Version For Teammates

Attach an Amazon review file and a runtime config JSON file in Claude, then ask Claude to use `amazon-review-insight` and return the final report.
