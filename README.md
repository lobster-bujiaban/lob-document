# LOB Document

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)

LOB Document 当前目标是一个**可演示的文档解析 MVP**：通过本地 Web 工作台或统一 CLI 读取 PDF、Word、Markdown 和图片，输出结构化 JSON、可阅读的 Markdown 和图片资产。

本期聚焦文件输入、文本提取、OCR、基础结构恢复与结果展示。RAG 集成、完整质量评测、生产化和源码对照研究不作为本期交付前置条件。

## 核心链路

```text
File
  → Detect / Load
  → Page Decode
  → Layout / OCR
  → Block Normalize
  → Reading Order
  → Document Tree
  → Markdown / JSON / Image Assets
  → Source References / Diagnostics
```

## 演示目标

使用选定的原生 PDF、扫描 PDF、Word、Markdown 和图片样例，通过同一 CLI 展示：

- 结构化文档树；
- 基础阅读顺序清晰的 Markdown；
- 基础表格、图片资产和已有的图注关联结果；
- PDF/图片的页码、坐标，以及 Word/Markdown 的顺序或行号来源信息；
- 已有的 OCR 与低置信内容等结构化诊断（不等同于完整质量报告）。

## 当前范围与状态

- [x] 统一领域模型、稳定身份与 CLI
- [x] 原生 PDF 文本、坐标和基础版面提取
- [x] 基础文档树与 Markdown/JSON 导出
- [x] 本地与云端 OCR 适配、原生文本融合
- [x] 基础表格恢复、图片提取与图注关联
- [x] PDF、Word、Markdown 和图片 Loader
- [x] 本地 Web 工作台：上传、OCR 设置、任务状态、原文对照、结果预览和下载
- [ ] 固定演示样例、确认运行环境并逐项核对输出

勾选表示已有实现，不表示对任意文档均能准确解析，也不代表演示验收已经通过。演示收尾与验收标准见 [实施计划](./docs/IMPLEMENTATION_PLAN.md)。

公式识别、复杂跨页表格、RAG Chunk、`lob-vector` 集成、评测平台、生产化 API 和完整源码映射均为后续可选扩展，不阻塞本期交付。

## 技术基线

- Python 3.12+，使用 `uv` 管理依赖。
- Pydantic 定义文档、页面、块、来源和诊断协议。
- 核心领域模型不依赖具体 PDF、OCR 或模型 SDK。
- 固定本地样例作为回归基线，不依赖在线文档。
- 原始文件只读，所有派生产物写入独立 artifacts 目录。

## 快速开始

使用根目录启动脚本启动网页：

```bash
./start.sh
./start.sh --port 8095
./start.sh --help
./start.sh parse <文件路径> --output artifacts/result.json --markdown artifacts/result.md
```

默认访问 [本地工作台](http://127.0.0.1:8093)。脚本需要 `uv`、Node.js 20.19+ 和 npm，会按锁文件准备依赖并构建前端；首次运行可能需要联网。相对输入和输出路径以项目根目录为准。

### Web 工作台

- 参考同级 `lob-flow` 的米白、橙色与深蓝视觉风格，采用 React + TypeScript + Vite；FastAPI 同源托管页面与接口。
- 上传最大 20 MB 的文档，选择自动 OCR、强制 OCR 或仅原生文本；云端 OCR 必须单独勾选上传授权，密钥不传给前端。
- 左侧保留解析记录；原文件与结果并排显示，可切换阅读预览、Markdown 源文、JSON 和诊断。
- PDF、图片可以原文预览，Markdown 展示原文，Word 提供原文件下载与解析结果展示。
- 支持下载 Markdown、JSON 和包含图片资产的 ZIP 结果包。页面不自动加载文档中的外部图片；HTML 表格经过安全过滤后展示。
- 任务和文件保存在 `artifacts/web/`，服务重启后仍可查看已完成记录；中断的任务标记失败，可重新上传。没有自动清理，需要手动管理本地产物。
- 演示版最多同时解析 2 个任务、最多接受 4 个未完成任务，单任务超时 10 分钟；不展示虚假的百分比进度。
- 仅绑定本机，不提供登录或生产级隔离，不应暴露到公网。OCR 依赖与模型识别质量仍需在演示环境确认。

前端开发可在后端运行时执行 `npm --prefix web run dev`，默认代理至 `127.0.0.1:8093`。日常演示使用 `./start.sh` 即可。

也可以直接运行 CLI：

```bash
uv run lob-document --help
uv run lob-document parse samples/baseline.pdf --output artifacts/baseline.json --markdown artifacts/baseline.md
uv run lob-document schema --output artifacts/source-document.schema.json
```

`parse` 命令读取 PDF 文件身份、页面结构和原生文本层，输出文本块、坐标、字体、字号与阅读顺序；
文件和节点 ID 基于内容生成，同一输入可重复得到稳定结构。没有原生文本层的页面会输出
`no_native_text` 诊断，供后续 OCR 阶段处理。

页面坐标使用 PDF point（1/72 英寸），原点位于页面左上角，`x` 向右、`y` 向下。解析器会拆分
同一底层文本块中横向分离的内容，按视觉行从上到下、同行从左到右排列，并初步标记标题、页眉和页脚。
文档树会排除页眉页脚、归一化段内换行并组织标题和正文；Markdown 中的 `source` 注释保留页码、
坐标和来源块 ID，可用于回跳原文。

OCR 默认使用 `auto` 模式：有效原生文本不足时才调用本地 Tesseract。可通过 `--ocr never` 禁用，
或用 `--ocr always` 强制执行并与原生文本去重；`--ocr-language` 用于指定语言。OCR 引擎通过
统一接口注入，云端适配器必须显式标记为云服务，并且只有策略明确允许时才能接收页面数据。

SiliconFlow 云端 OCR 使用视觉模型和 `/chat/completions` 接口。复制 `.env.example` 为 `.env` 并填写
`SILICONFLOW_API_KEY`，然后显式选择并允许云端处理：

```bash
uv run lob-document parse samples/scanned.pdf \
  --ocr auto --ocr-engine siliconflow --allow-cloud-ocr \
  --output artifacts/scanned.json --markdown artifacts/scanned.md
```

只有触发 OCR 的页面会以 JPEG 图片上传；原始 PDF 不会整体上传。模型可通过
`SILICONFLOW_OCR_MODEL` 调整，默认使用实测可稳定返回坐标 JSON 的 `Qwen/Qwen3-VL-8B-Instruct`。
云端推理默认等待 300 秒，可通过 `SILICONFLOW_TIMEOUT_SECONDS` 调整；超时或服务错误会记录为
`cloud_ocr_failed`，不会与本地 OCR 运行时缺失混淆。

嵌入图片会写入输出目录的 `assets/`，按内容哈希命名并在 `figure` 节点中记录；覆盖页面大部分
区域的扫描背景图会过滤，避免与 OCR 结果重复。

Markdown Loader 的标题、列表和段落会进入同一文档树，来源引用保留
原文件行号；CLI 会根据 `.pdf`、`.md` 或 `.markdown` 后缀自动选择 Loader。

图片 Loader 支持 PNG、JPG、JPEG 和 WEBP。图片作为单页 `figure` 保存，默认对整图执行 OCR；
输出目录会保存按哈希命名的图片副本，并将识别文本绑定到图片页面坐标。

Word Loader 支持 `.docx`，解析标题、段落、列表、表格和内嵌图片，统一输出为同一套文档树、
来源引用和 Markdown。Word 文档的来源引用使用文档顺序索引和行号语义。

解析器会将原生 PDF 表格线和云端视觉模型识别出的表格归一为 `TableData` / `TableCell`，保存
行列索引、合并跨度、文本、坐标和置信度。表内散落文本会去重；普通表格输出 Markdown，包含
合并单元格时输出 HTML 表格以保留结构。

## 项目边界

- 文档解析和结构恢复属于本项目；向量索引与检索属于 `lob-vector`。
- 不绕过加密、访问控制或文档权限。
- 首期不训练 OCR、布局或视觉语言模型，重点研究推理链路和工程组合。
- 本期以固定演示样例可重复运行、输出可查看且边界说明清楚为完成标准，不承诺任意文档的解析准确率或生产服务能力。

## License

Apache License 2.0。
