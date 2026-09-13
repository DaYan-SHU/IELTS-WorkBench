"""雅思工作台后端。"""
import os
import time
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import scanner
import vocab
import db
import watcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def scan_and_store():
    t0 = time.time()
    if not os.path.isdir(scanner.ROOT):
        # 资料盘未挂载时扫描结果必为空，绝不能写库，否则会把整个索引清空
        print(f"[扫描] 资料目录不存在，跳过本次扫描：{scanner.ROOT}")
        return None
    items = scanner.scan()
    db.replace_items(items)
    words, failed = vocab.parse_all(scanner.ROOT)
    if failed:
        print("[词库] 有 CSV 读取失败，本次跳过词库同步以保留学习记录")
    else:
        db.sync_words(words)
    db.set_meta("scanned_root", scanner.ROOT)
    return len(items), len(words), time.time() - t0


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    need_scan = db.count_items() == 0 or db.get_meta("scanned_root") != scanner.ROOT
    if need_scan:
        scan_and_store()  # 根目录不存在时返回 None，保留库中现有数据
    elif db.count_words() == 0:
        words, failed = vocab.parse_all(scanner.ROOT)
        if not failed:
            db.sync_words(words)
    stop_watcher = watcher.start(scan_and_store)
    try:
        yield
    finally:
        stop_watcher()


app = FastAPI(title="雅思工作台", lifespan=lifespan)


def _ensure_inside_root(path: str) -> str:
    """校验路径位于资料根目录内且是存在的文件，返回规范化后的绝对路径。"""
    root = os.path.normcase(os.path.realpath(scanner.ROOT))
    p = os.path.normcase(os.path.realpath(path))
    try:
        common = os.path.normcase(os.path.commonpath([root, p]))
    except ValueError:
        raise HTTPException(status_code=403, detail="路径不在资料根目录内")
    if common != root:
        raise HTTPException(status_code=403, detail="路径不在资料根目录内")
    if not os.path.isfile(p):
        raise HTTPException(status_code=404, detail="文件不存在")
    return p


@app.get("/api/stats")
def stats():
    data = db.get_stats()
    data["root"] = scanner.ROOT
    data["root_exists"] = os.path.isdir(scanner.ROOT)
    return data


@app.get("/api/categories")
def categories():
    return db.get_categories()


@app.get("/api/folders")
def folders():
    return db.get_folders()


@app.get("/api/items")
def items(q: str = "", category: str = "", kind: str = "", folder: str = "", sort: str = "name"):
    return db.query_items(q=q, category=category, kind=kind, folder=folder, sort=sort)


@app.get("/api/facets")
def facets(q: str = "", category: str = "", kind: str = "", folder: str = ""):
    return db.get_facets(q=q, category=category, kind=kind, folder=folder)


class PlanIn(BaseModel):
    date: str = ""
    subject: str = ""
    title: str = ""


class PlanPatch(BaseModel):
    done: bool | None = None


@app.get("/api/plans")
def plans(date: str = ""):
    return db.list_plans(date or None)


@app.post("/api/plans")
def create_plan(payload: PlanIn):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="任务内容不能为空")
    d = payload.date or time.strftime("%Y-%m-%d")
    pid = db.add_plan(d, payload.subject or "", title)
    return {"id": pid}


@app.patch("/api/plans/{plan_id}")
def patch_plan(plan_id: int, payload: PlanPatch):
    if payload.done is not None:
        db.set_plan_done(plan_id, payload.done)
    return {"ok": True}


@app.delete("/api/plans/{plan_id}")
def delete_plan(plan_id: int):
    db.delete_plan(plan_id)
    return {"ok": True}


@app.get("/api/plan/stats")
def plan_stats():
    return db.plan_stats()


class MarkIn(BaseModel):
    known: int = 0


@app.get("/api/word/sources")
def word_sources():
    return db.word_sources()


@app.get("/api/words")
def words(source: str = "", mode: str = ""):
    # mode: '' 全部 / todo 未掌握 / fresh 未学 / unknown 不认识 / known 已认识
    return db.list_words(source or None, mode)


@app.get("/api/word/stats")
def word_stats(source: str = ""):
    return db.word_stats(source or None)


@app.post("/api/word/{word_id}/mark")
def mark_word(word_id: int, payload: MarkIn):
    if payload.known not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="known 只能是 0/1/2")
    db.mark_word(word_id, payload.known)
    return {"ok": True}


@app.post("/api/refresh")
def refresh():
    r = scan_and_store()
    if r is None:
        raise HTTPException(status_code=409, detail=f"资料目录不存在：{scanner.ROOT}")
    n, w, dt = r
    return {"total": n, "words": w, "seconds": round(dt, 2)}


@app.get("/api/open")
def open_file(path: str):
    p = _ensure_inside_root(path)
    try:
        os.startfile(p)  # Windows：用系统默认程序打开
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"打开失败：{e}")
    return {"ok": True}


@app.get("/api/raw")
def raw(path: str):
    p = _ensure_inside_root(path)
    media = mimetypes.guess_type(p)[0] or "application/octet-stream"
    return FileResponse(p, media_type=media)


# 静态文件挂在最后，避免抢占 /api 路由
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
