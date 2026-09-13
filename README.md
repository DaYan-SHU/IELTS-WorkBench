# 雅思工作台 (IELTS Workbench)

一个**免安装、U 盘便携**的本地雅思学习工具：把散落在硬盘各处的雅思资料变成一个可搜索的资料库，同时提供单词学习和学习计划功能。纯本地运行，数据不出电脑。

![Tech](https://img.shields.io/badge/Python-FastAPI-blue) ![DB](https://img.shields.io/badge/DB-SQLite-green) ![License](https://img.shields.io/badge/use-free-lightgrey)

## 功能

### 资料库
- 自动扫描「雅思」资料目录（支持 U 盘盘符变化后自动重新定位）
- 按分类 / 文件类型 / 文件夹多维浏览与筛选，全文搜索
- 单击直接用系统默认程序打开文件，音频 / 视频 / PDF 可在线预览
- 文件增删改后自动重新索引（watchdog 监控，1.5 秒防抖合并）

### 单词学习
- 自动识别资料目录中的 CSV 词表并导入
- 三态标记：未学 / 已认识 / 未掌握，按来源、状态筛选背诵
- 学习记录持久保存，重建索引不会丢失

### 学习计划
- 按日期添加每日任务，勾选完成，自动统计完成率

## 快速开始

### 方式一：U 盘便携（推荐）

把整个项目文件夹（含 `runtime` 嵌入式 Python）拷入 U 盘，双击：

```
启动.bat
```

无需安装任何东西。U 盘插到任何电脑都能跑，资料目录按盘符自动定位。

### 方式二：本机 Python

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python start.py
```

启动后自动打开浏览器，访问 `http://127.0.0.1:8000`。

## 访问模式

| 脚本 | 用途 |
|------|------|
| `启动.bat` | 本机使用（仅监听 127.0.0.1，安全） |
| `手机访问.bat` | 手机 / 平板连同一 WiFi 访问（监听 0.0.0.0） |
| `外网访问.bat` | 通过 Cloudflare Tunnel 生成临时公网地址，任何网络可访问 |

> 外网隧道说明：需 `tools\cloudflared.exe`；每次启动会生成新网址（`https://xxxx.trycloudflare.com`），窗口关闭即断开，链接请勿外传。

## 配置（环境变量，均可选）

| 变量 | 默认 | 说明 |
|------|------|------|
| `IELTS_ROOT` | 自动发现 | 指定资料根目录；不设置时先找项目同级「雅思」文件夹，再遍历 A–Z 盘符找 `X:\雅思` |
| `IELTS_HOST` | `127.0.0.1` | 设为 `0.0.0.0` 开放局域网访问 |
| `IELTS_PORT` | `8000` | 端口被占用时临时更换 |

## 项目结构

```
├── app.py            # FastAPI 后端与 API 路由
├── scanner.py        # 资料目录扫描与自动定位
├── vocab.py          # CSV 词表解析
├── db.py             # SQLite 存取（增量同步，保留学习记录）
├── watcher.py        # 文件变更监控（自动重建索引）
├── start.py          # 启动器（依赖检查 + 自动开浏览器）
├── static/           # 前端（原生 HTML/CSS/JS）
├── runtime/          # 嵌入式 Python（U 盘便携用，可选）
└── tools/            # cloudflared.exe（外网隧道用，可选）
```

## 数据安全

- 启动时自动备份数据库为 `ielts.db.bak`，防止 U 盘热插拔损坏
- 资料目录未挂载时跳过扫描，**绝不**用空结果覆盖已有索引
- CSV 解析失败时跳过词库同步，保留已有学习记录
- 数据库写入使用事务保证原子性；文件访问有路径穿越防护

## 技术栈

Python 3 · FastAPI · Uvicorn · SQLite · Watchdog · 原生 HTML/CSS/JS · Cloudflare Tunnel
