# LOB Document

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)

LOB Document 从 MinerU、Docling 和 MarkItDown 的源码调用链出发，研究企业文档进入 RAG 前的解析过程，并实现一条可解释、可评测、可追溯的文档结构化链路。

项目重点不是封装已有解析工具，而是掌握文件载入、页面布局、阅读顺序、OCR、表格、公式、图片、结构化输出和 RAG Chunk 之间的状态转换与质量边界。

## 核心链路

```text
File
  → Detect / Load
  → Page Decode
  → Layout / OCR
  → Block Normalize
  → Reading Order
  → Document Tree
  → Markdown / JSON / RAG Chunks
  → Quality Report
```

## 首个里程碑

输入一份包含标题、正文、表格、图片和页眉页脚的固定 PDF，输出：

- 结构化文档树；
- 保持正确阅读顺序的 Markdown；
- 携带页码、坐标和层级路径的 RAG Chunk；
- 可定位丢失、乱序和低置信内容的质量报告。

## 阶段路线

- [ ] 阶段 0：研究基线、样例集与统一领域模型
- [ ] 阶段 1：原生 PDF 文本、坐标与页面结构
- [ ] 阶段 2：版面分析、阅读顺序与文档树
- [ ] 阶段 3：扫描件 OCR 与原生文本融合
- [ ] 阶段 4：表格、图片和数学公式
- [ ] 阶段 5：多格式 Loader 与统一输出
- [ ] 阶段 6：RAG Chunk、引用溯源与 `lob-vector` 集成
- [ ] 阶段 7：质量评测、批处理与生产化
- [ ] 阶段 8：MinerU、Docling、MarkItDown 源码映射与差异清单

完整任务、步骤和验收标准见 [实施计划](./docs/IMPLEMENTATION_PLAN.md)。

## 技术基线

- Python 3.12+，使用 `uv` 管理依赖。
- Pydantic 定义文档、页面、块、来源和诊断协议。
- 核心领域模型不依赖具体 PDF、OCR 或模型 SDK。
- 固定本地样例作为回归基线，不依赖在线文档。
- 原始文件只读，所有派生产物写入独立 artifacts 目录。

## 快速开始

```bash
uv run lob-document --help
uv run lob-document parse samples/baseline.pdf --output artifacts/baseline.json
uv run lob-document schema --output artifacts/source-document.schema.json
```

阶段 0 的 `parse` 命令读取 PDF 文件身份、页数、页面尺寸和旋转信息，暂不提取正文；
文件 ID 基于内容哈希生成，同一输入可重复得到稳定结构。

## 项目边界

- 文档解析和结构恢复属于本项目；向量索引与检索属于 `lob-vector`。
- 不绕过加密、访问控制或文档权限。
- 首期不训练 OCR、布局或视觉语言模型，重点研究推理链路和工程组合。
- 不以单份演示效果作为完成标准，必须保留固定样例和可重复指标。

## License

Apache License 2.0。
