"""扫描雅思资料，建立文件索引（仅元数据），并按文件夹名自动分类到雅思科目。"""
import os
import string


def _find_root():
    """自动定位「雅思」资料文件夹（U盘便携场景下盘符会变）。"""
    # 显式覆盖（排障/测试用）：设置环境变量 IELTS_ROOT 指向资料目录
    env_root = os.environ.get("IELTS_ROOT")
    if env_root:
        env_root = os.path.abspath(env_root)
        if os.path.isdir(env_root):
            return env_root
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    candidates = [
        r"E:\雅思",                          # 原电脑固定盘
        os.path.join(here, "雅思"),           # 工作台内部
        os.path.join(parent, "雅思"),         # 工作台同级（U盘：U:\雅思 与 U:\雅思工作台）
    ]
    for letter in string.ascii_uppercase:
        candidates.append(f"{letter}:\\雅思")  # 所有盘符
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            if os.path.isdir(c):
                return c
        except OSError:
            continue
    return r"E:\雅思"  # 兜底（找不到时）


# 资料根目录
ROOT = _find_root()

# 科目显示顺序 + 图标 + 颜色（用于前端）
CATEGORY_META = [
    ("真题", "", "#e74c3c"),
    ("听力", "", "#3498db"),
    ("阅读", "", "#2ecc71"),
    ("口语", "", "#9b59b6"),
    ("写作", "", "#e67e22"),
    ("词汇", "", "#f39c12"),
    ("语法", "", "#16a085"),
    ("其他", "", "#95a5a6"),
]
CATEGORY_ORDER = [c for c, _, _ in CATEGORY_META]

# 分类规则：按顺序匹配，文件夹名里第一个命中的关键词决定科目。
# 注意顺序敏感：越具体、越独特的词越靠前（例如「大作文」在「真题」之前）。
CLASSIFY_RULES = [
    # 写作（先放作者/书名/特征词）
    ("顾家北", "写作"),
    ("慎小嶷", "写作"),
    ("杜仕明", "写作"),
    ("Simon", "写作"),
    ("套句式", "写作"),
    ("六字真言", "写作"),
    ("大作文", "写作"),
    ("小作文", "写作"),
    ("翻译", "写作"),
    ("写作", "写作"),
    # 真题（剑桥/九分达人等成套题）
    ("剑桥", "真题"),
    ("九分达人", "真题"),
    ("官方指南", "真题"),
    ("真题", "真题"),
    # 口语
    ("张天真", "口语"),
    ("杨帅", "口语"),
    ("发音", "口语"),
    ("口语", "口语"),
    # 听力
    ("何琼", "听力"),
    ("王陆", "听力"),
    ("黑眼睛", "听力"),
    ("807", "听力"),
    ("听力", "听力"),
    # 阅读
    ("刘洪波", "阅读"),
    ("场景词", "阅读"),
    ("阅读", "阅读"),
    ("Taking sides", "阅读"),
    # 词汇
    ("词汇", "词汇"),
    ("单词", "词汇"),
    ("短语", "词汇"),
    ("同义词", "词汇"),
    # 语法
    ("语法", "语法"),
    ("Grammar", "语法"),
]

# 扩展名 -> 文件大类（用于筛选和图标）
KIND_MAP = {
    "pdf": "document",
    "doc": "document", "docx": "document",
    "ppt": "document", "pptx": "document",
    "xls": "spreadsheet", "xlsx": "spreadsheet",
    "csv": "spreadsheet",
    "txt": "text", "md": "text",
    "mp3": "audio", "m4a": "audio", "wma": "audio", "wav": "audio",
    "mp4": "video", "mov": "video", "mkv": "video", "avi": "video",
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image",
    "zip": "archive", "rar": "archive", "7z": "archive",
}

# 跳过这些无用的文件
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SKIP_EXTS = {"lnk", "dmg"}


def classify(folder_name: str) -> str:
    """根据文件夹名返回科目（识别不到归「其他」）。"""
    for keyword, category in CLASSIFY_RULES:
        if keyword in folder_name:
            return category
    return "其他"


def kind_of(ext: str) -> str:
    return KIND_MAP.get(ext, "other")


def scan(root: str = ROOT):
    """遍历 root，返回文件元数据列表（不读取文件内容，速度很快）。"""
    items = []
    if not os.path.isdir(root):
        return items
    root_abs = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过隐藏目录
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn in SKIP_NAMES or fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower().lstrip(".")
            if ext in SKIP_EXTS:
                continue

            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_abs)
            parts = rel.split(os.sep)
            folder = parts[0] if len(parts) > 1 else "(根目录)"

            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
            except OSError:
                size, mtime = 0, 0

            # 先按文件夹名分类，识别不到（其他）时再按文件名兜底
            category = classify(folder)
            if category == "其他":
                category = classify(fn)

            items.append({
                "path": full,
                "name": fn,
                "rel": rel,
                "folder": folder,
                "ext": ext,
                "kind": kind_of(ext),
                "size": size,
                "mtime": mtime,
                "category": category,
            })
    return items
