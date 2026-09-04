"""Local demonstration API. Jobs and outputs stay under artifacts/web/."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lob_document.domain import SourceDocument
from lob_document.exporters import export_markdown

ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / "artifacts" / "web"
DIST = ROOT / "web" / "dist"
MAX_BYTES = 20 * 1024 * 1024
FORMATS = {".pdf", ".docx", ".md", ".markdown", ".png", ".jpg", ".jpeg", ".webp"}
lock = threading.RLock()
jobs: dict[str, dict] = {}
pool = ThreadPoolExecutor(max_workers=2)
slots = threading.BoundedSemaphore(4)


def save(job: dict) -> None:
    with lock:
        jobs[job["id"]] = job
        path = JOBS / job["id"] / "status.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    JOBS.mkdir(parents=True, exist_ok=True)
    for path in JOBS.glob("*/status.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] in {"queued", "running"}:
                job.update(status="failed", error="服务已重启，请重新上传解析。")
            save(job)
        except (ValueError, KeyError, OSError):
            continue
    yield


app = FastAPI(title="LOB Document", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    # Block cross-site form submissions and DNS-rebinding against this local tool.
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        if urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "不允许跨站提交。"}, status_code=403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse({"detail": "仅允许本地同源访问。"}, status_code=403)
    if request.method == "POST":
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "无效请求长度。"}, status_code=400)
        if length <= 0 or length > MAX_BYTES + 65536:
            return JSONResponse({"detail": "请选择不超过 20 MB 的文件。"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def get_job(job_id: str) -> dict:
    with lock:
        if not re.fullmatch(r"[a-f0-9]{32}", job_id) or job_id not in jobs:
            raise HTTPException(404, "任务不存在。")
        return dict(jobs[job_id])


def parse_job(job: dict, source: Path, mode: str, engine: str, language: str, cloud: bool):
    folder = source.parent
    started = time.monotonic()
    try:
        job.update(status="running")
        save(job)
        command = [sys.executable, "-m", "lob_document", "parse", str(source),
                   "--output", str(folder / "result.json"), "--ocr", mode,
                   "--ocr-engine", engine, "--ocr-language", language]
        if cloud:
            command.append("--allow-cloud-ocr")
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
        if process.returncode:
            # Keep provider messages / configuration details out of browser responses.
            raise RuntimeError("解析失败，请检查文件是否损坏、加密，以及 OCR 环境配置。")
        document = SourceDocument.model_validate_json((folder / "result.json").read_text(encoding="utf-8"))
        document.source.filename = job["filename"]
        if document.document_tree is not None and not document.metadata.get("Title"):
            document.document_tree.title = Path(job["filename"]).stem
        payload = document.model_dump(mode="json")

        def normalize(value):
            if isinstance(value, dict):
                if "asset" in value and isinstance(value["asset"], dict):
                    value["asset"]["path"] = "assets/" + Path(value["asset"]["path"]).name
                for child in value.values():
                    normalize(child)
            elif isinstance(value, list):
                for child in value:
                    normalize(child)

        normalize(payload)
        document = SourceDocument.model_validate(payload)
        (folder / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "result.md").write_text(export_markdown(document), encoding="utf-8")
        with ZipFile(folder / "results.zip", "w", ZIP_DEFLATED) as archive:
            for name in ("result.json", "result.md"):
                archive.write(folder / name, name)
            for path in (folder / "assets").glob("*"):
                if path.is_file():
                    archive.write(path, "assets/" + path.name)
        job.update(status="succeeded", pages=document.page_count,
                   blocks=sum(len(p.blocks) for p in document.pages))
    except subprocess.TimeoutExpired:
        job.update(status="failed", error="解析超过 10 分钟，已停止。请缩小文件或调整 OCR 设置后重试。")
    except Exception as exc:
        job.update(status="failed", error=str(exc) if isinstance(exc, RuntimeError) else "无法处理此文件，请检查文件格式与解析环境。")
    finally:
        job["duration"] = round(time.monotonic() - started, 1)
        save(job)
        slots.release()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/jobs")
def list_jobs():
    with lock:
        return sorted((dict(job) for job in jobs.values()), key=lambda job: job["created"], reverse=True)


@app.post("/api/jobs", status_code=202)
async def create_job(file: UploadFile = File(...), mode: str = Form("auto"),
                     engine: str = Form("local"), language: str = Form("chi_sim+eng"),
                     allow_cloud: bool = Form(False)):
    filename = (file.filename or "document").replace("\\", "/").split("/")[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in FORMATS:
        raise HTTPException(400, "支持 PDF、DOCX、Markdown、PNG、JPG 和 WEBP。")
    if mode not in {"auto", "always", "never"} or engine not in {"local", "siliconflow"}:
        raise HTTPException(400, "无效 OCR 设置。")
    if not re.fullmatch(r"[A-Za-z0-9_+\-]{1,80}", language):
        raise HTTPException(400, "无效 OCR 语言。")
    if engine == "siliconflow" and not allow_cloud:
        raise HTTPException(400, "使用云端 OCR 前必须明确允许上传页面图片。")
    if not slots.acquire(blocking=False):
        raise HTTPException(429, "任务队列已满，请稍后重试。")
    job_id = uuid.uuid4().hex
    folder = JOBS / job_id
    try:
        folder.mkdir(parents=True)
        source = folder / ("source" + suffix)
        size = 0
        with source.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "文件不能超过 20 MB。")
                output.write(chunk)
        if not size:
            raise HTTPException(400, "文件为空。")
        # Bound common document expansion before launching a parser subprocess.
        if suffix == ".docx":
            try:
                with ZipFile(source) as archive:
                    if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                        raise HTTPException(400, "Word 解压后超过演示版限制。")
            except BadZipFile:
                raise HTTPException(400, "文件不是有效的 DOCX 文档。") from None
        job = {"id": job_id, "filename": filename[:200], "suffix": suffix,
               "size": size, "created": time.time(), "status": "queued",
               "mode": mode, "engine": engine, "error": None}
        save(job)
        pool.submit(parse_job, dict(job), source, mode, engine, language, allow_cloud)
        return job
    except Exception:
        slots.release()
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()
        folder.rmdir()
        raise
    finally:
        await file.close()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    return get_job(job_id)


@app.get("/api/jobs/{job_id}/result")
def result(job_id: str):
    job = get_job(job_id)
    if job["status"] != "succeeded":
        raise HTTPException(409, "解析结果尚未就绪。")
    folder = JOBS / job_id
    return {"document": json.loads((folder / "result.json").read_text(encoding="utf-8")),
            "markdown": (folder / "result.md").read_text(encoding="utf-8")}


@app.get("/api/jobs/{job_id}/source")
def source_file(job_id: str):
    job = get_job(job_id)
    suffix = job["suffix"]
    types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg", ".webp": "image/webp", ".md": "text/plain", ".markdown": "text/plain"}
    return FileResponse(JOBS / job_id / ("source" + suffix), media_type=types.get(suffix, "application/octet-stream"),
                        filename=job["filename"], content_disposition_type="attachment" if suffix == ".docx" else "inline")


@app.get("/api/jobs/{job_id}/assets/{name}")
def asset(job_id: str, name: str):
    get_job(job_id)
    if Path(name).name != name or name in {".", ".."}:
        raise HTTPException(404)
    path = JOBS / job_id / "assets" / name
    if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/download/{kind}")
def download(job_id: str, kind: str):
    job = get_job(job_id)
    if job["status"] != "succeeded" or kind not in {"json", "md", "zip"}:
        raise HTTPException(404)
    name = "results.zip" if kind == "zip" else "result." + kind
    return FileResponse(JOBS / job_id / name, filename=name)


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
