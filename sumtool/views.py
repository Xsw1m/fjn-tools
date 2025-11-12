import os
import json
import sys
from pathlib import Path

from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt


# 项目根目录（.../fjn-tools）
BASE_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = BASE_ROOT / 'server'
EXPORTS_DIR = BASE_ROOT / 'exports'
EXPORTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = BASE_ROOT / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True)

# 让 Python 能导入根目录下的 tools 包（tools/calcSumXlsx/sum_aggregator.py）
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))
try:
    from tools.calcSumXlsx import sum_aggregator as sa
except Exception:
    sa = None


# 已统一为静态页面：请使用 index_static 提供的 client/index.html


def index_static(_request):
    """服务独立静态页面 client/index.html（简化为路径输入+生成按钮）。"""
    index_path = BASE_ROOT / 'client' / 'index.html'
    if not index_path.exists():
        return HttpResponse("前端页面未找到，请创建 client/index.html", status=404)
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content)
    except Exception as exc:
        return HttpResponse(f"读取页面失败: {exc}", status=500)


def _normalize_to_root(p: str) -> Path:
    """将传入路径规范化到项目根目录下：
    - 相对路径：按 BASE_ROOT 拼接
    - 绝对路径：若不在 BASE_ROOT 内，尝试从出现 'lots' 的位置起重定位到 BASE_ROOT
    """
    raw = str(p or '').strip()
    if not raw:
        return BASE_ROOT

    candidate = Path(raw)
    # 相对路径：直接拼接到 BASE_ROOT
    if not candidate.is_absolute():
        return (BASE_ROOT / candidate).resolve()

    # 绝对路径且已经在 BASE_ROOT 内
    try:
        common = os.path.commonpath([str(BASE_ROOT), str(candidate.resolve())])
    except Exception:
        common = ''
    if common == str(BASE_ROOT):
        return candidate.resolve()

    # 尝试从路径中定位 'lots' 段，并以此作为相对路径重定位到 BASE_ROOT
    parts = list(candidate.parts)
    idx = None
    for i, part in enumerate(parts):
        if part.lower() == 'lots':
            idx = i
            break
    if idx is not None:
        rel_parts = parts[idx:]
        return (BASE_ROOT.joinpath(*rel_parts)).resolve()

    # 找不到 lots，保持严格边界
    raise ValueError('越界路径')


def _ensure_safe_path(p: str) -> Path:
    """限制访问在 BASE_ROOT 之内，避免越权访问，并进行路径规范化。"""
    abs_p = _normalize_to_root(p)
    try:
        common = os.path.commonpath([str(BASE_ROOT), str(abs_p)])
    except Exception:
        common = ''
    if common != str(BASE_ROOT):
        raise ValueError('越界路径')
    return abs_p


def _list_dir(p: Path):
    children = []
    try:
        for name in os.listdir(p):
            cp = p / name
            children.append({
                'name': name,
                'is_dir': cp.is_dir(),
                'path': str(cp),
            })
    except Exception:
        pass
    return children


def api_fs_list(request):
    """列出目录内容。默认浏览 lots 目录。"""
    path = request.GET.get('path') or str(BASE_ROOT / 'lots')
    try:
        abs_p = _ensure_safe_path(path)
        if not abs_p.exists():
            return JsonResponse({'ok': False, 'error': '路径不存在', 'path': str(abs_p)})
        if not abs_p.is_dir():
            return JsonResponse({'ok': False, 'error': '不是目录', 'path': str(abs_p)})
        return JsonResponse({'ok': True, 'path': str(abs_p), 'children': _list_dir(abs_p)})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)})


@csrf_exempt
def api_sum_run(request):
    """执行汇总，返回下载链接。"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        body = json.loads(request.body or '{}')
        lots_dir = body.get('lots_dir') or str(BASE_ROOT / 'lots')
        abs_lots = _ensure_safe_path(lots_dir)
        if not abs_lots.exists() or not abs_lots.is_dir():
            return JsonResponse({'ok': False, 'error': 'lots 目录不存在'})

        if sa is None:
            return JsonResponse({'ok': False, 'error': 'tools.calcSumXlsx.sum_aggregator 导入失败'})

        # 聚合并写出到 exports
        lot_subdirs = [str(abs_lots / d) for d in os.listdir(abs_lots) if (abs_lots / d).is_dir()]
        if not lot_subdirs:
            return JsonResponse({'ok': False, 'error': 'lots 目录下没有子目录'})

        lot_summaries = [sa.aggregate_lot(ld) for ld in lot_subdirs]
        df = sa.build_dataframe(lot_summaries)
        final_path = sa.write_excel(df, str(EXPORTS_DIR / 'result.xlsx'))
        rel_name = os.path.basename(final_path)
        return JsonResponse({'ok': True, 'filename': rel_name, 'download_url': f"/api/sum/download/{rel_name}"})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)})


def api_sum_download(_request, filename: str):
    """下载生成的 xlsx。"""
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        return JsonResponse({'ok': False, 'error': '文件不存在'})
    f = open(file_path, 'rb')
    return FileResponse(f, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, filename=os.path.basename(file_path))


@csrf_exempt
def api_sum_upload_run(request):
    """接收浏览器选择的 lots 文件夹（webkitdirectory），在服务端复原目录并生成 xlsx。

    使用方式：FormData 多文件上传，每个文件名使用 webkitRelativePath 保留相对路径。
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'ok': False, 'error': '请先选择 lots 文件夹'})

        # 创建会话目录
        import time
        session_dir = UPLOADS_DIR / f"session-{int(time.time())}"
        base_lots_dir = session_dir / 'lots'
        base_lots_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for uf in files:
            rel = uf.name or 'unknown'
            # 规避越权路径
            rel_path = Path(rel)
            parts = rel_path.parts
            if any(p == '..' for p in parts):
                continue
            dest = base_lots_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, 'wb') as out:
                for chunk in uf.chunks():
                    out.write(chunk)
            count += 1

        # 兼容多种上传结构：
        # 1) webkitRelativePath 可能不包含顶层 lots，造成文件直接位于 base_lots_dir
        # 2) webkitRelativePath 可能包含一个顶层 lots，再嵌套 lotX/
        effective_root = base_lots_dir
        try:
            only_dirs = [p for p in effective_root.iterdir() if p.is_dir()]
            only_files = [p for p in effective_root.iterdir() if p.is_file()]
        except FileNotFoundError:
            only_dirs, only_files = [], []

        # 如果只有一个名为 lots 的子目录，则下钻一层
        lots_like = [p for p in only_dirs if p.name.lower() == 'lots']
        if len(lots_like) == 1 and not [p for p in only_files]:
            effective_root = lots_like[0]
            try:
                only_dirs = [p for p in effective_root.iterdir() if p.is_dir()]
            except FileNotFoundError:
                only_dirs = []

        # 选择作为 lot 的目录：直接子目录中含有 .SUM 文件的
        lot_dirs = []
        for d in only_dirs:
            has_sum = any(child.suffix.lower() == '.sum' for child in d.iterdir() if child.is_file())
            if has_sum:
                lot_dirs.append(str(d))

        # 如果没有 lot 子目录，但 root 本身含有 .SUM，则将 root 视为一个 lot
        if not lot_dirs:
            root_has_sum = any(child.suffix.lower() == '.sum' for child in effective_root.iterdir() if child.is_file())
            if root_has_sum:
                lot_dirs = [str(effective_root)]

        if not lot_dirs:
            # 提供更友好的错误信息，帮助用户选择正确的目录
            example = []
            try:
                for p in effective_root.iterdir():
                    example.append(p.name)
            except Exception:
                pass
            return JsonResponse({
                'ok': False,
                'error': '上传的目录结构不包含 lot 子目录或 SUM 文件。请选择包含多个 lot 子文件夹的 lots 目录，或包含 SUM 文件的单个 lot 目录。',
                'root_preview': example[:10]
            })

        if sa is None:
            return JsonResponse({'ok': False, 'error': 'sum_aggregator 导入失败'})

        # 聚合并写出到 exports
        lot_summaries = [sa.aggregate_lot(ld) for ld in lot_dirs]
        df = sa.build_dataframe(lot_summaries)
        final_path = sa.write_excel(df, str(EXPORTS_DIR / 'result.xlsx'))
        rel_name = os.path.basename(final_path)
        return JsonResponse({'ok': True, 'filename': rel_name, 'download_url': f"/api/sum/download/{rel_name}", 'uploaded_files': count})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)})
