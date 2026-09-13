"""SQLite 存取层：文件索引的读写与查询。"""
import os
import shutil
import sqlite3
import time
from datetime import date, timedelta

from scanner import CATEGORY_META

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ielts.db")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")  # 后台监听扫描与接口请求并发时等待解锁
    return conn


def _exec(sql, params=(), many=None):
    conn = _connect()
    try:
        if many is not None:
            conn.executemany(sql, many)
        else:
            conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _query(sql, params=()):
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def backup_db():
    """启动时做一次文件级备份，防止 U 盘热插拔等意外损坏数据库。"""
    if not os.path.exists(DB_PATH):
        return
    try:
        shutil.copy2(DB_PATH, DB_PATH + ".bak")
    except OSError as e:
        print(f"[备份] 数据库备份失败：{e}")


def init_db():
    backup_db()
    _exec("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            rel TEXT,
            folder TEXT,
            ext TEXT,
            kind TEXT,
            size INTEGER,
            mtime REAL,
            category TEXT
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_category ON items(category)")
    _exec("CREATE INDEX IF NOT EXISTS idx_folder ON items(folder)")
    _exec("CREATE INDEX IF NOT EXISTS idx_kind ON items(kind)")
    _exec("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            subject TEXT DEFAULT '',
            title TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at REAL
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_plans_date ON plans(date)")
    _exec("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            source TEXT NOT NULL,
            known INTEGER DEFAULT 0
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS idx_words_source ON words(source)")
    # (word, source) 唯一：增量同步时靠它 upsert，从而保留 known 学习状态。
    # 旧库可能存在重复行：先把每组最大的 known（2 不认识 > 1 认识 > 0）合并到保留行，再去重。
    _exec(
        "UPDATE words SET known = ("
        "SELECT MAX(w2.known) FROM words w2 "
        "WHERE w2.word = words.word AND w2.source = words.source)"
    )
    _exec(
        "DELETE FROM words WHERE id NOT IN "
        "(SELECT MIN(id) FROM words GROUP BY word, source)"
    )
    _exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_words_word_source ON words(word, source)")
    _exec("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")


def replace_items(items):
    """整体替换文件索引。单事务写入，避免中途失败留下半截数据。"""
    conn = _connect()
    try:
        conn.execute("DELETE FROM items")
        conn.executemany(
            "INSERT INTO items (path, name, rel, folder, ext, kind, size, mtime, category) "
            "VALUES (:path, :name, :rel, :folder, :ext, :kind, :size, :mtime, :category)",
            items,
        )
        conn.commit()
    finally:
        conn.close()


def count_items():
    return _query("SELECT COUNT(*) AS n FROM items")[0]["n"]


def count_words():
    return _query("SELECT COUNT(*) AS n FROM words")[0]["n"]


def get_meta(key):
    rows = _query("SELECT value FROM meta WHERE key = ?", (key,))
    return rows[0]["value"] if rows else None


def set_meta(key, value):
    _exec("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def get_stats():
    row = _query("SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS s FROM items")[0]
    total, total_size = row["n"], row["s"]
    by_category = {r["category"]: r["n"] for r in _query(
        "SELECT category, COUNT(*) AS n FROM items GROUP BY category")}
    by_kind = {r["kind"]: r["n"] for r in _query(
        "SELECT kind, COUNT(*) AS n FROM items GROUP BY kind")}
    by_ext = {r["ext"]: r["n"] for r in _query(
        "SELECT ext, COUNT(*) AS n FROM items GROUP BY ext ORDER BY n DESC LIMIT 20")}
    return {
        "total": total,
        "total_size": total_size,
        "by_category": by_category,
        "by_kind": by_kind,
        "by_ext": by_ext,
    }


def get_categories():
    counts = {r["category"]: r["n"] for r in _query(
        "SELECT category, COUNT(*) AS n FROM items GROUP BY category")}
    return [
        {"name": name, "count": counts.get(name, 0), "icon": icon, "color": color}
        for name, icon, color in CATEGORY_META
    ]


def get_folders():
    return _query("SELECT folder AS name, COUNT(*) AS count FROM items GROUP BY folder ORDER BY folder")


def query_items(q="", category="", kind="", folder="", sort="name"):
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR folder LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if folder:
        sql += " AND folder = ?"
        params.append(folder)
    order = {
        "name": "name COLLATE NOCASE ASC",
        "size": "size DESC",
        "mtime": "mtime DESC",
        "kind": "kind ASC, name COLLATE NOCASE ASC",
    }
    sql += " ORDER BY " + order.get(sort, "name COLLATE NOCASE ASC")
    return _query(sql, params)


def _where(q="", folder="", category="", kind=""):
    sql = "WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR folder LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if folder:
        sql += " AND folder = ?"
        params.append(folder)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    return sql, params


def get_facets(q="", folder="", category="", kind=""):
    """联动计数：科目维度忽略 category 过滤，类型维度忽略 kind 过滤。"""
    cat_sql, cat_params = _where(q=q, folder=folder, kind=kind)
    cats = _query(
        f"SELECT category AS name, COUNT(*) AS count FROM items {cat_sql} GROUP BY category",
        cat_params,
    )
    kind_sql, kind_params = _where(q=q, folder=folder, category=category)
    kinds = _query(
        f"SELECT kind AS name, COUNT(*) AS count FROM items {kind_sql} GROUP BY kind",
        kind_params,
    )
    return {"categories": cats, "kinds": kinds}


# ---------- 学习计划 ----------
def list_plans(day=None):
    if day:
        return _query("SELECT * FROM plans WHERE date = ? ORDER BY done ASC, id ASC", (day,))
    return _query("SELECT * FROM plans ORDER BY date DESC, done ASC, id ASC")


def add_plan(day, subject, title):
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO plans (date, subject, title, done, created_at) VALUES (?, ?, ?, 0, ?)",
            (day, subject, title, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def set_plan_done(plan_id, done):
    _exec("UPDATE plans SET done = ? WHERE id = ?", (1 if done else 0, plan_id))


def delete_plan(plan_id):
    _exec("DELETE FROM plans WHERE id = ?", (plan_id,))


def plan_stats():
    today = date.today()
    today_str = today.isoformat()

    def _count(sql, params=()):
        return _query(sql, params)[0]["n"]

    total_done = _count("SELECT COUNT(*) AS n FROM plans WHERE done = 1")
    total_all = _count("SELECT COUNT(*) AS n FROM plans")
    today_done = _count("SELECT COUNT(*) AS n FROM plans WHERE date = ? AND done = 1", (today_str,))
    today_total = _count("SELECT COUNT(*) AS n FROM plans WHERE date = ?", (today_str,))

    done_dates = set(r["date"] for r in _query("SELECT DISTINCT date FROM plans WHERE done = 1"))
    streak = 0
    d = today if today_done > 0 else today - timedelta(days=1)
    while d.isoformat() in done_dates:
        streak += 1
        d -= timedelta(days=1)

    days = []
    for i in range(6, -1, -1):
        ds = (today - timedelta(days=i)).isoformat()
        days.append({
            "date": ds,
            "done": _count("SELECT COUNT(*) AS n FROM plans WHERE date = ? AND done = 1", (ds,)),
            "total": _count("SELECT COUNT(*) AS n FROM plans WHERE date = ?", (ds,)),
        })

    by_subject = _query(
        "SELECT subject, COUNT(*) AS n FROM plans WHERE done = 1 AND subject != '' "
        "GROUP BY subject ORDER BY n DESC"
    )
    return {
        "streak": streak,
        "today_done": today_done,
        "today_total": today_total,
        "total_done": total_done,
        "total_all": total_all,
        "days": days,
        "by_subject": by_subject,
    }


# ---------- 词汇 ----------
def sync_words(words):
    """增量同步单词索引，保留已有的 known 学习状态（刷新索引不再清空学习记录）。

    - 已存在的 (word, source)：更新释义，known 保持不变；
    - 新出现的 (word, source)：插入，known=0；
    - 词库(source)被移动/重命名/标识规则变更后：按 (word, meaning) 把旧 known 迁移到新词库；
    - 旧行匹配不到新解析结果的（内容已不存在）直接清除，不再残留幽灵词库；
    - 解析结果为空（如资料盘未挂载）时保留旧数据，避免误删。
    """
    if not words:
        return
    conn = _connect()
    try:
        conn.executemany(
            "INSERT INTO words (word, meaning, source, known) VALUES (?, ?, ?, 0) "
            "ON CONFLICT(word, source) DO UPDATE SET meaning = excluded.meaning",
            [(w["word"], w["meaning"], w["source"]) for w in words],
        )
        alive_sources = {w["source"] for w in words}
        pair_source = {}
        for w in words:
            pair_source.setdefault((w["word"], w["meaning"]), w["source"])
        rows = conn.execute("SELECT id, word, meaning, source, known FROM words").fetchall()
        for r in rows:
            if r["source"] in alive_sources:
                continue
            target = pair_source.get((r["word"], r["meaning"]))
            if target and r["known"]:
                conn.execute(
                    "UPDATE words SET known = ? WHERE word = ? AND source = ? AND known < ?",
                    (r["known"], r["word"], target, r["known"]),
                )
            conn.execute("DELETE FROM words WHERE id = ?", (r["id"],))
        conn.commit()
    finally:
        conn.close()


def word_sources():
    return _query("SELECT source, COUNT(*) AS count FROM words GROUP BY source ORDER BY source")


KNOWN_MODES = {
    "todo": "known != 1",    # 未掌握：未学 + 不认识
    "fresh": "known = 0",    # 未学
    "unknown": "known = 2",  # 不认识
    "known": "known = 1",    # 已认识
}


def list_words(source=None, mode=""):
    sql = "SELECT * FROM words WHERE 1=1"
    params = []
    if source:
        sql += " AND source = ?"
        params.append(source)
    cond = KNOWN_MODES.get(mode)
    if cond:
        sql += " AND " + cond
    sql += " ORDER BY id"
    return _query(sql, params)


def word_stats(source=None):
    """词库掌握情况统计（不受练习筛选影响）。"""
    sql = ("SELECT COUNT(*) AS total, "
           "COALESCE(SUM(known = 1), 0) AS known, "
           "COALESCE(SUM(known = 2), 0) AS unknown FROM words")
    params = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    row = _query(sql, params)[0]
    row["fresh"] = row["total"] - row["known"] - row["unknown"]
    return row


def mark_word(word_id, known):
    _exec("UPDATE words SET known = ? WHERE id = ?", (known, word_id))
