#!/usr/bin/env bash
set -euo pipefail

# 从任意工作目录启动；相对样例和输出路径均以项目根目录为准。
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf '%s\n' \
    'LOB Document 本地文档解析工作台' \
    '' \
    '用法：' \
    '  ./start.sh                 启动网页，默认 http://127.0.0.1:8093' \
    '  ./start.sh --port 8095     指定网页端口' \
    '  ./start.sh parse <文件路径> --output artifacts/result.json --markdown artifacts/result.md' \
    '  ./start.sh parse <文件路径> --ocr never --output artifacts/result.json' \
    '  ./start.sh schema --output artifacts/source-document.schema.json' \
    '  ./start.sh parse --help' \
    '' \
    '相对路径以项目根目录为准。uv 会按锁文件准备依赖；首次运行可能需要联网。' \
    '本地 OCR 需要 Tesseract 和语言包；云端 OCR 需配置 .env 并显式允许上传。'
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' '错误：未找到 uv，请先安装 uv，并确保它位于 PATH 中。' >&2
  exit 127
fi

if [[ "${1:-}" == "parse" || "${1:-}" == "schema" ]]; then
  exec uv run --locked lob-document "$@"
fi

PORT=8093
if [[ $# -gt 0 ]]; then
  if [[ $# -ne 2 || "$1" != "--port" || ! "$2" =~ ^[0-9]{1,5}$ ]]; then
    printf '%s\n' '错误：请使用 ./start.sh [--port 端口]，或 --help 查看用法。' >&2
    exit 2
  fi
  PORT=$((10#$2))
  if (( PORT < 1 || PORT > 65535 )); then
    printf '%s\n' '错误：端口必须在 1～65535 之间。' >&2
    exit 2
  fi
fi

if ! command -v npm >/dev/null 2>&1; then
  printf '%s\n' '错误：请先安装 Node.js 20.19+（含 npm）。' >&2
  exit 127
fi

uv sync --locked
if [[ ! -d web/node_modules || ! -f web/node_modules/.package-lock.json ]] || \
   [[ web/package-lock.json -nt web/node_modules/.package-lock.json ]]; then
  npm --prefix web ci --no-fund --no-audit
fi
npm --prefix web run build
printf '\n%s\n' "工作台地址：http://127.0.0.1:$PORT" '按 Ctrl+C 停止服务。请勿将演示服务暴露到公网。'
exec uv run --locked uvicorn lob_document.web:app --host 127.0.0.1 --port "$PORT"
