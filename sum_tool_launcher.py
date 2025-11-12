#!/usr/bin/env python3
"""
sum_aggregator 的简易启动器。

用途：
- 提供可点击/一键运行的入口，默认读取同目录下的 lots 目录，输出到同目录的 result.xlsx。
- 支持命令行参数：
  * 用法：sum_tool_launcher <lots_dir> [output_excel_path]

该文件用于打包为可执行文件（macOS/Linux 二进制或 Windows .exe）。
"""

import os
import sys


def _reexec_with_venv_if_available() -> None:
    """当依赖缺失导致导入失败时，尝试用项目本地虚拟环境重新执行自身。

    查找当前目录下 `.venv/bin/python`，若存在则使用 `os.execv` 直接切换到该解释器
    运行当前启动器，并透传命令行参数。
    """
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        venv_python = os.path.join(base, ".venv", "bin", "python")
        if os.path.isfile(venv_python):
            print(f"检测到虚拟环境，切换为: {venv_python}")
            os.execv(venv_python, [venv_python, os.path.abspath(__file__), *sys.argv[1:]])
    except Exception:
        pass


try:
    from tools.calcSumXlsx.sum_aggregator import main as aggregator_main
except ModuleNotFoundError as e:
    missing = getattr(e, "name", "")
    # 依赖缺失：尝试使用虚拟环境重新执行
    if missing in ("pandas", "openpyxl", "xlsxwriter"):
        _reexec_with_venv_if_available()
        print(
            f"缺少依赖: {missing}。请使用项目虚拟环境安装：\n"
            f"  ./.venv/bin/python -m pip install pandas openpyxl xlsxwriter",
            file=sys.stderr,
        )
        sys.exit(2)
    # 文件本身缺失
    if missing in ("sum_aggregator", "tools", "tools.calcSumXlsx", "tools.calcSumXlsx.sum_aggregator"):
        print(
            "无法导入工具模块：tools.calcSumXlsx.sum_aggregator。\n"
            "请确认已存在 tools/calcSumXlsx/sum_aggregator.py，并且当前目录是项目根目录。",
            file=sys.stderr,
        )
        sys.exit(2)
    # 其他导入问题
    _reexec_with_venv_if_available()
    print(f"导入失败: {e}", file=sys.stderr)
    sys.exit(2)
except Exception as e:
    _reexec_with_venv_if_available()
    print(f"导入 sum_aggregator 失败: {e}", file=sys.stderr)
    sys.exit(2)


def _base_dir() -> str:
    """获取运行时所在目录：
    - 若为打包后的可执行（sys.frozen），使用可执行所在目录；
    - 否则使用当前文件所在目录。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _default_paths() -> tuple[str, str]:
    base = _base_dir()
    lots_dir = os.path.join(base, "lots")
    out_path = os.path.join(base, "result.xlsx")
    return lots_dir, out_path


def _choose_paths_gui(base: str) -> tuple[str | None, str | None]:
    """在无参数且默认 lots 不存在时，弹出对话框让用户选择。"""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return None, None
    try:
        root = tk.Tk()
        root.withdraw()
        lots_dir = filedialog.askdirectory(title="请选择 lots 文件夹", initialdir=base)
        if not lots_dir:
            return None, None
        out_path = filedialog.asksaveasfilename(
            title="选择输出 Excel 文件",
            defaultextension=".xlsx",
            initialfile="result.xlsx",
            initialdir=base,
        )
        if not out_path:
            out_path = os.path.join(base, "result.xlsx")
        try:
            messagebox.showinfo("SUM 汇总", f"开始处理：{lots_dir}\n输出到：{out_path}")
        except Exception:
            pass
        return lots_dir, out_path
    except Exception:
        return None, None


def main() -> int:
    if len(sys.argv) >= 2:
        lots_dir = sys.argv[1]
        out_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.join(os.getcwd(), "result.xlsx")
    else:
        lots_dir, out_path = _default_paths()
        if not os.path.isdir(lots_dir):
            chosen_lots, chosen_out = _choose_paths_gui(_base_dir())
            if chosen_lots:
                lots_dir, out_path = chosen_lots, chosen_out

    print(f"启动 SUM 汇总：lots_dir={lots_dir} -> out={out_path}")
    return aggregator_main(["sum_aggregator.py", lots_dir, out_path])


if __name__ == "__main__":
    sys.exit(main())