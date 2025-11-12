#!/usr/bin/env python3
"""
打包发布版脚本：在 dist/ 下生成 fjn-tools-release.zip

只包含必要文件：
- web_launch.py, sum_aggregator.py, sum_tool_launcher.py（CLI 可选）
- README.md, requirements.txt
- client/index.html
- server/manage.py, server/webtools/*（排除 __pycache__ 与 db）
- sumtool/*（排除 __pycache__）

排除：.venv、__pycache__、uploads、exports、result.xlsx、db.sqlite3、dist
"""

import os
import sys
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
ZIP_NAME = DIST_DIR / "fjn-tools-release.zip"


def should_skip(path: Path) -> bool:
    """判断是否跳过文件/目录。"""
    rel = path.relative_to(ROOT)
    parts = rel.parts

    # 目录排除
    if parts[0] in {".venv", "dist", "uploads", "exports", "__pycache__"}:
        return True
    if "__pycache__" in parts:
        return True

    # 文件排除
    if rel.as_posix() == "server/db.sqlite3":
        return True
    if rel.name in {"result.xlsx", ".DS_Store"}:
        return True
    if rel.suffix in {".pyc", ".log"}:
        return True

    return False


def add_file(z: zipfile.ZipFile, file_path: Path):
    rel = file_path.relative_to(ROOT)
    if should_skip(file_path):
        return
    if not file_path.exists():
        return
    z.write(file_path, arcname=rel.as_posix())


def add_dir_filtered(z: zipfile.ZipFile, dir_path: Path):
    if not dir_path.exists():
        return
    for p in dir_path.rglob("*"):
        if p.is_file() and not should_skip(p):
            z.write(p, arcname=p.relative_to(ROOT).as_posix())


def build_release():
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_NAME, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 单文件（可选缺失时跳过）
        for fname in [
            "web_launch.py",
            "sum_tool_launcher.py",
            "README.md",
            "requirements.txt",
            "tools/__init__.py",
            "tools/calcSumXlsx/__init__.py",
            "tools/calcSumXlsx/sum_aggregator.py",
        ]:
            add_file(z, ROOT / fname)

        # 前端静态页：仅 index.html
        add_file(z, ROOT / "client" / "index.html")

        # Django：manage.py 与 webtools 配置
        add_file(z, ROOT / "server" / "manage.py")
        add_dir_filtered(z, ROOT / "server" / "webtools")

        # 应用：sumtool
        add_dir_filtered(z, ROOT / "sumtool")

    print(f"✅ 发布包已生成：{ZIP_NAME}")


if __name__ == "__main__":
    try:
        build_release()
    except Exception as e:
        print(f"❌ 打包失败：{e}")
        sys.exit(1)