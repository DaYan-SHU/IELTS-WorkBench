"""从词汇 CSV 解析单词（格式：序号,单词,释义）。跳过 macOS 的 ._ 垃圾文件。"""
import os
import csv
import io

# 常见的表头词，作为表头行跳过
HEADER_WORDS = {"word", "words", "单词", "词汇", "序号", "index", "number", "no", "no.", "id"}


def _read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def parse_file(path, source):
    # 读取失败向上抛出，由 parse_all 标记本次解析不完整，
    # 避免把"读不到"当成"空词库"而误清学习记录。
    text = _read_text(path)
    words = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row:
            continue
        # 去掉纯数字的首列序号
        if row[0].strip().isdigit():
            row = row[1:]
        if not row:
            continue
        word = row[0].strip()
        meaning = ",".join(x.strip() for x in row[1:]).strip() if len(row) > 1 else ""
        if not word or not meaning:
            continue
        if word.lower() in HEADER_WORDS:
            continue
        words.append({"word": word, "meaning": meaning, "source": source})
    return words


def parse_all(root):
    """扫描全部词库 CSV，返回 (words, failed)。

    - source 使用完整相对路径：不同分支的同名文件夹不再互相合并；
    - failed=True 表示有 CSV 读取失败，本次解析不完整，调用方应跳过同步。
    """
    words = []
    failed = False
    if not os.path.isdir(root):
        return words, failed
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith(".csv") or fn.startswith("._"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            source = os.path.splitext(rel)[0].replace("\\", "/")
            try:
                words.extend(parse_file(full, source))
            except (OSError, UnicodeDecodeError, csv.Error) as e:
                print(f"[词库] 读取失败：{full}（{e}）")
                failed = True
    return words, failed
