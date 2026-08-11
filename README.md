# XHS Demand Radar

一个面向小红书需求挖掘的独立项目。采集、发布和评论能力全部通过可替换 Provider 接入，核心分析流程不依赖 MediaCrawler 或其他具体开源项目。

## 仓库边界

推荐把各个项目作为并列 Git 仓库：

```text
~/projects/social-platform-tools/xhs/
├── demand-radar/       # 本项目，独立 .git
├── MediaCrawler/       # 上游采集 Provider，独立 .git
├── Spider_XHS/         # 可选采集或发布 Provider
└── xiaohongshu-mcp/    # 可选发布、评论 Provider
```

本项目不修改、复制或提交任何上游仓库代码。适配器通过命令行或稳定协议调用外部项目，并把原始结果转换成统一数据格式。

### 外部 Provider

| 项目 | 上游仓库 | 计划用途 | 当前状态 |
| --- | --- | --- | --- |
| MediaCrawler | [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 小红书笔记、评论采集 | 已接入 |
| Spider_XHS | [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) | 备用采集或发布 Provider | 尚未接入 |
| xiaohongshu-mcp | [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) | 发布笔记、发评论、回复评论 | 尚未接入 |

以上项目均为独立的第三方仓库，其版权、许可证和使用要求以各自上游仓库为准；本项目的许可证不覆盖这些外部 Provider。

## 架构

```text
Collector Providers ──> 原始数据 ──> 统一数据格式 ──> 需求分析/聚类/评分/报告

Publisher Providers ──> 发布笔记 / 发布评论 / 回复评论
```

- `CollectorProvider`：采集笔记和评论，并负责解释自己的原始数据格式。
- `PublisherProvider`：按能力选择性实现发布笔记、发评论、回复评论。
- `ProviderRegistry`：按名称和能力选择 Provider，避免业务代码直接依赖具体项目。
- 每次运行记录 Provider 名称和上游 Git revision，便于规则变化后定位问题。
- 采集结果为 0 时运行失败，不会生成“今日没有需求”的错误结论。
- 发布写操作默认要求人工确认；当前版本尚未接入任何真实发布 Provider。

## 初始化

```bash
cd ~/projects/social-platform-tools/xhs/demand-radar
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/demand-radar providers
```

Provider 配置位于 `config/providers.yaml`。其中的相对路径统一相对于本项目根目录解析。

## MediaCrawler 采集

[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 需要先在它自己的仓库中安装依赖并完成小红书登录。健康检查通过后，可以运行：

```bash
.venv/bin/demand-radar collect \
  --provider mediacrawler \
  --keyword "有没有好用的工具" \
  --keyword "太麻烦了怎么办" \
  --max-notes 20 \
  --max-comments 10
```

适配器只调用 MediaCrawler CLI，并把输出写入本项目的 `data/raw/`；不会写入或修改 MediaCrawler 源码。首次登录需要人工完成二维码操作。

## 手工导入兜底

当自动采集规则失效时，可以导入符合统一格式的 JSONL：

```bash
.venv/bin/demand-radar collect \
  --provider manual_import \
  --input /absolute/path/to/canonical-records.jsonl
```

## 数据目录

- `data/raw/<provider>/<run_id>/`：各 Provider 的原始输出。
- `data/normalized/<provider>/<run_id>.jsonl`：统一格式的数据。
- `data/runs/<run_id>.json`：运行状态、数量、健康信息和上游 revision。
- `reports/`：后续需求分析报告。
- `logs/`、`runtime/`：运行日志与浏览器状态等本地文件。

这些运行产物默认不进入 Git。
