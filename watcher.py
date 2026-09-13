"""资料目录实时监听：文件增/删/改后自动去抖重扫，兼容 U 盘热插拔。

- watchdog 递归监听资料根目录，事件合并去抖后触发一次完整扫描；
- 扫描进行中又来新事件会自动补扫一轮，保证大批量复制后最终一致；
- 守护线程定期检查目录：U 盘拔出时停止监听，重新插入后重建监听并补扫；
- 另有定时兜底全扫，防止个别移动盘丢失文件事件。
"""
import os
import threading
import time

import scanner

DEBOUNCE_SECONDS = 1.5        # 事件静默这么久后才扫描（合并连续写入）
SUPERVISE_INTERVAL = 3.0      # 检查目录是否存在（U 盘插拔）的间隔
SAFETY_RESCAN_SECONDS = 600   # 兜底全扫间隔，防止移动盘事件丢失


class _ChangeHandler:
    """watchdog 事件回调：过滤隐藏文件/系统垃圾后标记「有变更」。

    用动态导入 watchdog 的方式构造，避免模块导入时强依赖。
    """

    def __new__(cls, root, dirty):
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                src = event.src_path or ""
                try:
                    rel = os.path.relpath(src, root)
                except ValueError:
                    return
                parts = rel.split(os.sep)
                if not parts or rel == ".":
                    return
                if any(p.startswith(".") for p in parts):  # 隐藏目录/文件、macOS ._ 文件
                    return
                name = parts[-1]
                if name in scanner.SKIP_NAMES:
                    return
                ext = os.path.splitext(name)[1].lower().lstrip(".")
                if ext in scanner.SKIP_EXTS:
                    return
                dirty.set()

        return Handler()


def start(rescan, root=None):
    """启动监听，返回 stop()。rescan 是无参回调（如 app.scan_and_store）。"""
    root = root or scanner.ROOT
    stop_event = threading.Event()
    dirty = threading.Event()

    def worker():
        while not stop_event.is_set():
            if not dirty.wait(2.0):
                continue
            # 静默期：只要还有新事件就重新计时，等写入稳定后再扫
            while dirty.wait(DEBOUNCE_SECONDS):
                dirty.clear()
            dirty.clear()
            try:
                rescan()
            except Exception as e:  # 单次扫描失败不能让监听线程死掉
                print(f"[监听] 自动扫描失败：{e}")

    def supervise():
        observer = None
        started_once = False
        last_safety = time.time()
        while not stop_event.is_set():
            try:
                exists = os.path.isdir(root)
            except OSError:
                exists = False
            if observer is None and exists:
                try:
                    from watchdog.observers import Observer
                    observer = Observer()
                    observer.schedule(_ChangeHandler(root, dirty), root, recursive=True)
                    observer.start()
                    if started_once:
                        dirty.set()  # 资料盘重新挂载，索引可能已过期，补扫一次
                    started_once = True
                except OSError:
                    observer = None
            elif observer is not None and not exists:
                try:
                    observer.stop()
                    observer.join(timeout=3)
                except Exception:
                    pass
                observer = None
            if observer is not None and time.time() - last_safety > SAFETY_RESCAN_SECONDS:
                dirty.set()
                last_safety = time.time()
            stop_event.wait(SUPERVISE_INTERVAL)
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=3)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="rescan-worker").start()
    threading.Thread(target=supervise, daemon=True, name="root-supervisor").start()

    def stop():
        stop_event.set()

    return stop
