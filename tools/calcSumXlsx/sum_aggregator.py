#!/usr/bin/env python3
"""
SUM 汇总小工具

功能：
- 遍历 lots 目录下所有 lot 子目录，解析每个 SUM 文件（文件名包含时间戳 [MMDDYY_HHmmss]）。
- 从文件中提取 TotalPass、TotalFail，以及明细三列（Software Category、Hardware BIN、COUNT）。
- 按规则计算每个 lot 的统计值：
  * Total：取该 lot 最老文件的 TotalPass + TotalFail；所有 lot 的 Total 必须一致，否则抛出异常。
  * TotalPass：该 lot 所有文件的 TotalPass 之和。
  * TotalFail：Total - TotalPass，需为非负整数，否则抛出异常。
  * Category_BIN：
    - BIN 为 1、4：统计该 lot 所有文件的 COUNT 总和；
    - BIN 为 2、3、5：统计该 lot 最新文件的 COUNT 值；
    - 若同一 lot 下任意两个文件中相同 Category 的 BIN 不一致，则该 lot 对应单元格标记为 "error"。
- 生成 xlsx（result.xlsx），列包含各 lot 名称、sum、rate（百分比，两位小数）；
  行包含 Total、TotalPass、TotalFail 及各 Category_BIN 条目（数值或 "error"）。

依赖：pandas、openpyxl（或 xlsxwriter）。

用法：
  python3 sum_aggregator.py /Users/admin/Desktop/fjn-tools/lots /Users/admin/Desktop/fjn-tools/result.xlsx
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Union

import pandas as pd


# -----------------------------
# 解析与模型
# -----------------------------

@dataclass
class SumDetail:
    category: int
    bin: int
    count: int


@dataclass
class SumFile:
    path: str
    timestamp: datetime
    total_pass: int
    total_fail: int
    details: List[SumDetail]


def parse_timestamp_from_filename(filename: str) -> datetime:
    """从文件名中解析 MMDDYY_HHmmss 时间戳为 datetime 对象。

    允许扩展名为 .SUM/.sum/.txt 等，需包含形如 _081125_040616 的时间戳片段。
    """
    m = re.search(r"_(\d{6}_\d{6})(?:\.[^.]*)?$", filename)
    if not m:
        raise ValueError(f"文件名不含有效时间戳: {filename}")
    date_str = m.group(1)
    try:
        return datetime.strptime(date_str, "%m%d%y_%H%M%S")
    except Exception as exc:
        raise ValueError(f"无法解析时间戳 '{date_str}' 于文件: {filename}") from exc


def _search_int_patterns(text: str, patterns: List[str]) -> Union[int, None]:
    """在文本中按模式列表逐个搜索整数值，返回首个匹配的整数。大小写不敏感。"""
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                continue
    return None


def _extract_site_total_summary_text(text: str) -> Union[str, None]:
    """从文本中提取“Site Total Summary”所在的块。

    规则：
    - 找到包含“Site Total Summary”的标题行（大小写不敏感）。
    - 该行之后到下一个以大量 * 组成的标题（例如 "********* ... *********"）之间的内容作为块。
    - 如未找到该块，则返回 None。
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r"Site\s+Total\s+Summary", line, flags=re.IGNORECASE):
            header_idx = i
            break
    if header_idx is None:
        return None

    block_lines: List[str] = []
    for j in range(header_idx + 1, len(lines)):
        # 下一个以大量 * 开始并包含 * 的标题行，认为到此为止
        if re.match(r"^\*{3,}.*\*{3,}\s*$", lines[j]):
            break
        block_lines.append(lines[j])
    block = "\n".join(block_lines).strip()
    return block if block else None


def extract_totals(text: str) -> Tuple[int, int]:
    """提取 TotalPass 与 TotalFail（非负整数）。

    规则：
    - 先在全文中查找 TotalPass/TotalFail；
    - 如未找到，再回退到“Site Total Summary”块中尝试；
    - 两者任一缺失则报错。
    """
    total_pass = _search_int_patterns(
        text,
        [
            r"\bTotalPass\b\s*[:=]?\s*(\d+)",
            r"\bTotal\s*Pass\b\s*[:=]?\s*(\d+)",
        ],
    )
    total_fail = _search_int_patterns(
        text,
        [
            r"\bTotalFail\b\s*[:=]?\s*(\d+)",
            r"\bTotal\s*Fail\b\s*[:=]?\s*(\d+)",
        ],
    )

    if total_pass is None or total_fail is None:
        # 回退到 Site Total Summary 块
        summary_text = _extract_site_total_summary_text(text)
        if summary_text:
            if total_pass is None:
                total_pass = _search_int_patterns(
                    summary_text,
                    [
                        r"\bTotalPass\b\s*[:=]?\s*(\d+)",
                        r"\bTotal\s*Pass\b\s*[:=]?\s*(\d+)",
                    ],
                )
            if total_fail is None:
                total_fail = _search_int_patterns(
                    summary_text,
                    [
                        r"\bTotalFail\b\s*[:=]?\s*(\d+)",
                        r"\bTotal\s*Fail\b\s*[:=]?\s*(\d+)",
                    ],
                )

    if total_pass is None or total_fail is None:
        raise ValueError("文件中缺少 TotalPass 或 TotalFail 字段")
    if total_pass < 0 or total_fail < 0:
        raise ValueError("TotalPass/TotalFail 必须为非负整数")
    return total_pass, total_fail


def extract_details(text: str) -> List[SumDetail]:
    """提取明细三列：Software Category、Hardware BIN、COUNT。

    仅在“Site Total Summary”块中优先解析；若未找到该块，则回退到全文解析。

    尝试两种解析方式：
    1) 表头识别：
       - 单行表头（同一行包含 "Software Category"、"Hardware BIN"、"COUNT"），随后逐行解析三整数；
       - 双行表头（第一行包含 "Software"、"Hardware"、"COUNT"，第二行包含 "Category"、"BIN"），随后逐行解析三整数；
    2) 行内键值模式识别（Category ... BIN ... COUNT ...）。
    """
    details: List[SumDetail] = []
    base_text = _extract_site_total_summary_text(text) or text
    lines = base_text.splitlines()

    # 方式 1：表头后按行解析（支持单行或双行表头）
    single_header_idx = None
    for i, line in enumerate(lines):
        if (
            re.search(r"Software\s*Category", line, re.IGNORECASE)
            and re.search(r"Hardware\s*BIN", line, re.IGNORECASE)
            and re.search(r"COUNT", line, re.IGNORECASE)
        ):
            single_header_idx = i
            break

    pair_header_idx = None
    if single_header_idx is None:
        for i in range(len(lines) - 1):
            l1 = lines[i]
            l2 = lines[i + 1]
            if (
                re.search(r"Software", l1, re.IGNORECASE)
                and re.search(r"Hardware", l1, re.IGNORECASE)
                and re.search(r"COUNT", l1, re.IGNORECASE)
                and re.search(r"Category", l2, re.IGNORECASE)
                and re.search(r"BIN", l2, re.IGNORECASE)
            ):
                pair_header_idx = i
                break

    def _parse_rows(start_idx: int) -> None:
        for j in range(start_idx, len(lines)):
            raw = lines[j].strip()
            if not raw:
                continue
            # 含明显字母且无数字（如分隔符、注释、结束标记）
            if re.search(r"[A-Za-z]", raw) and not re.search(r"\d", raw):
                if details:
                    break
                else:
                    continue

            nums = re.findall(r"\d+", raw)
            if len(nums) >= 3:
                cat, binv, cnt = int(nums[0]), int(nums[1]), int(nums[2])
                if 1 <= binv <= 5 and cnt > 0:
                    details.append(SumDetail(cat, binv, cnt))

    if single_header_idx is not None:
        _parse_rows(single_header_idx + 1)
    elif pair_header_idx is not None:
        _parse_rows(pair_header_idx + 2)

    # 方式 2：行内键值模式（补充解析）
    inline_pat = re.compile(
        r"(?:Software\s*Category|Category)\s*[:=]?\s*(\d+)\D+"
        r"(?:Hardware\s*BIN|BIN)\s*[:=]?\s*(\d+)\D+"
        r"COUNT\s*[:=]?\s*(\d+)",
        re.IGNORECASE,
    )
    if not details:
        for line in lines:
            m = inline_pat.search(line)
            if m:
                cat, binv, cnt = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= binv <= 5 and cnt > 0:
                    details.append(SumDetail(cat, binv, cnt))

    return details


def parse_sum_file(path: str) -> SumFile:
    """解析单个 SUM 文件为结构化对象。"""
    filename = os.path.basename(path)
    ts = parse_timestamp_from_filename(filename)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as exc:
        raise IOError(f"读取文件失败: {path}") from exc

    total_pass, total_fail = extract_totals(text)
    details = extract_details(text)
    return SumFile(path=path, timestamp=ts, total_pass=total_pass, total_fail=total_fail, details=details)


# -----------------------------
# 汇总逻辑
# -----------------------------

@dataclass
class LotSummary:
    lot_name: str
    earliest_total: int
    total_pass_sum: int
    total_fail: int
    cells: Dict[str, Union[int, str]]  # 行键 -> 数值或 "error"


def _row_key(category: int, binv: int) -> str:
    # 行键改为数字下划线格式：Category_BIN，例如 1_5
    return f"{category}_{binv}"


def aggregate_lot(lot_dir: str) -> LotSummary:
    lot_name = os.path.basename(lot_dir.rstrip(os.sep))
    # 允许 .SUM/.sum/.txt 扩展名
    candidates: List[str] = []
    for fname in os.listdir(lot_dir):
        if not os.path.isfile(os.path.join(lot_dir, fname)):
            continue
        if re.search(r"\.(?i:sum|txt)$", fname):
            # 文件名必须包含时间戳
            if re.search(r"_\d{6}_\d{6}", fname):
                candidates.append(os.path.join(lot_dir, fname))

    if not candidates:
        raise ValueError(f"lot '{lot_name}' 下未找到 SUM 文件")

    files: List[SumFile] = [parse_sum_file(p) for p in candidates]
    earliest = min(files, key=lambda x: x.timestamp)
    latest = max(files, key=lambda x: x.timestamp)

    earliest_total = earliest.total_pass + earliest.total_fail
    total_pass_sum = sum(f.total_pass for f in files)
    total_fail = earliest_total - total_pass_sum
    if total_fail < 0:
        raise ValueError(
            f"lot '{lot_name}' 的 TotalPass 汇总超过 Total，TotalFail 计算为负值"
        )

    # 统计各 category 在不同文件出现的 bin，以检测不一致
    category_bins: Dict[int, set] = {}
    for f in files:
        for d in f.details:
            category_bins.setdefault(d.category, set()).add(d.bin)
    inconsistent_categories = {c for c, bins in category_bins.items() if len(bins) > 1}

    # BIN 1、4：所有文件 COUNT 总和；BIN 2、3、5：最新文件 COUNT 值
    cells: Dict[str, Union[int, str]] = {}

    # 先累加 BIN 1/4
    agg_counts: Dict[Tuple[int, int], int] = {}
    for f in files:
        for d in f.details:
            if d.bin in (1, 4):
                key = (d.category, d.bin)
                agg_counts[key] = agg_counts.get(key, 0) + d.count

    # 最新文件 BIN 2/3/5：直接取最新文件中的值
    latest_map: Dict[Tuple[int, int], int] = {}
    for d in latest.details:
        if d.bin in (2, 3, 5):
            latest_map[(d.category, d.bin)] = d.count

    # 合并键集合
    all_keys = set(agg_counts.keys()) | set(latest_map.keys())
    for (cat, binv) in all_keys:
        key = _row_key(cat, binv)
        if cat in inconsistent_categories:
            cells[key] = "error"
        else:
            if binv in (1, 4):
                cells[key] = agg_counts.get((cat, binv), 0)
            else:
                cells[key] = latest_map.get((cat, binv), 0)

    return LotSummary(
        lot_name=lot_name,
        earliest_total=earliest_total,
        total_pass_sum=total_pass_sum,
        total_fail=total_fail,
        cells=cells,
    )


def build_dataframe(lots: List[LotSummary]) -> pd.DataFrame:
    """构建最终 DataFrame，列包含各 lot 名、sum、rate；行包含 Total、TotalPass、TotalFail 及 Category_BIN。

    注意：不再要求所有 lot 的 Total 一致，rate 统一以“所有 lot 的 Total 之和”为分母。
    """
    if not lots:
        raise ValueError("未提供 lot 汇总数据")

    totals = {lt.lot_name: lt.earliest_total for lt in lots}
    sum_total_across_lots = sum(totals.values())  # 所有 lot 的 Total 之和

    # 组织行键
    row_order: List[str] = ["Total", "TotalPass", "TotalFail"]

    # 汇总所有 Category_BIN 行键并排序（按 Category、BIN）
    cat_bin_keys: set = set()
    for lt in lots:
        cat_bin_keys |= set(lt.cells.keys())

    def _parse_row_key(k: str) -> Tuple[int, int]:
        # 解析数字下划线格式的行键：<category>_<bin>
        m = re.match(r"^(\d+)_([1-5])$", k)
        if not m:
            return (999999, 999999)
        return (int(m.group(1)), int(m.group(2)))

    sorted_cat_bin = sorted(cat_bin_keys, key=_parse_row_key)
    row_order.extend(sorted_cat_bin)

    # 列：各 lot 名称 + sum + rate
    columns = [lt.lot_name for lt in lots] + ["sum", "rate"]
    df = pd.DataFrame(index=row_order, columns=columns)

    # 填充三行指标
    # Total
    total_row_sum = 0
    for lt in lots:
        df.at["Total", lt.lot_name] = lt.earliest_total
        total_row_sum += lt.earliest_total
    df.at["Total", "sum"] = total_row_sum
    df.at["Total", "rate"] = f"{(total_row_sum / sum_total_across_lots) * 100:.2f}%"  # 应为 100.00%

    # TotalPass
    total_pass_sum_all = 0
    for lt in lots:
        df.at["TotalPass", lt.lot_name] = lt.total_pass_sum
        total_pass_sum_all += lt.total_pass_sum
    df.at["TotalPass", "sum"] = total_pass_sum_all
    df.at["TotalPass", "rate"] = f"{(total_pass_sum_all / sum_total_across_lots) * 100:.2f}%"

    # TotalFail（用 sum_total_across_lots - total_pass_sum_all 更稳）
    total_fail_sum_all = sum_total_across_lots - total_pass_sum_all
    for lt in lots:
        df.at["TotalFail", lt.lot_name] = lt.total_fail
    df.at["TotalFail", "sum"] = total_fail_sum_all
    df.at["TotalFail", "rate"] = f"{(total_fail_sum_all / sum_total_across_lots) * 100:.2f}%"

    # 填充 Category_BIN 行
    for key in sorted_cat_bin:
        values: List[Union[int, str]] = []
        has_error = False
        for lt in lots:
            v = lt.cells.get(key, 0)  # 缺失视为 0
            if isinstance(v, str):
                has_error = True
            df.at[key, lt.lot_name] = v
            values.append(v)

        if has_error:
            df.at[key, "sum"] = "error"
            df.at[key, "rate"] = "error"
        else:
            numeric_sum = int(sum(int(v) for v in values))
            df.at[key, "sum"] = numeric_sum
            df.at[key, "rate"] = f"{(numeric_sum / sum_total_across_lots) * 100:.2f}%"

    return df


def _unique_output_path(path: str) -> str:
    """若目标文件已存在，则生成不重复的文件名，例如 result(1).xlsx、result(2).xlsx。

    规则：在原文件名的扩展名之前添加“(n)”后缀（无空格），n 从 1 开始递增，直到未存在为止。
    """
    directory = os.path.dirname(path)
    base = os.path.basename(path)
    name, ext = os.path.splitext(base)
    candidate = path
    if os.path.exists(candidate):
        n = 1
        while True:
            candidate = os.path.join(directory, f"{name}({n}){ext}")
            if not os.path.exists(candidate):
                break
            n += 1
    return candidate


def write_excel(df: pd.DataFrame, out_path: str) -> str:
    """写出结果到 Excel，返回最终写出的路径。

    - 先应用不覆盖规则生成唯一文件名；
    - 优先使用 openpyxl，失败时回退到 xlsxwriter。
    """
    final_path = _unique_output_path(out_path)
    try:
        with pd.ExcelWriter(final_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="result")
    except Exception:
        with pd.ExcelWriter(final_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="result")
    return final_path


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("用法: python3 sum_aggregator.py <lots_dir> [output_excel_path]", file=sys.stderr)
        return 2

    lots_dir = argv[1]
    out_path = argv[2] if len(argv) >= 3 else os.path.join(os.getcwd(), "result.xlsx")

    if not os.path.isdir(lots_dir):
        print(f"目录不存在: {lots_dir}", file=sys.stderr)
        return 2

    # 枚举 lot 子目录
    lot_subdirs = [
        os.path.join(lots_dir, d)
        for d in os.listdir(lots_dir)
        if os.path.isdir(os.path.join(lots_dir, d))
    ]
    if not lot_subdirs:
        print(f"lots 目录下未找到任何 lot 子目录: {lots_dir}", file=sys.stderr)
        return 2

    try:
        lot_summaries: List[LotSummary] = [aggregate_lot(ld) for ld in lot_subdirs]
        df = build_dataframe(lot_summaries)
        final_path = write_excel(df, out_path)
        print(f"已生成 Excel: {final_path}")
        return 0
    except Exception as exc:
        print(f"处理失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))