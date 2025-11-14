import os
import json
import sys
from pathlib import Path
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt


# 项目根目录（.../fjn-tools）
BASE_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = BASE_ROOT / 'server'
EXPORTS_DIR = BASE_ROOT / 'exports'
EXPORTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = BASE_ROOT / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True)
LOTS_DIR = BASE_ROOT / 'lots'
LOTS_DIR.mkdir(exist_ok=True)

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


def _resolve_slt_summary_root(user_root: str | None = None) -> Path:
    """解析 SLT_Summary 根目录。

    优先顺序：
    1) 用户传入的 `user_root`
    2) 环境变量 `SLT_SUMMARY_ROOT`
    3) 默认 UNC：\\172.33.10.11\SLT_Summary

    说明：在 macOS 上默认 UNC 路径不可直接访问，建议使用 Finder 挂载共享盘，或设置
    环境变量 SLT_SUMMARY_ROOT 指向本地挂载点（例如 /Volumes/SLT_Summary）。
    """
    raw = (user_root or os.environ.get('SLT_SUMMARY_ROOT') or r"\\172.33.10.11\SLT_Summary").strip()
    p = Path(raw)
    return p


def _copy_with_collision(src: Path, dest_dir: Path) -> str:
    """将文件复制到目标目录，若重名则自动添加 (1), (2) ... 后缀，返回最终文件名。"""
    import shutil
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = src.name
    name, ext = os.path.splitext(base)
    candidate = base
    idx = 1
    dest = dest_dir / candidate
    while dest.exists():
        candidate = f"{name}({idx}){ext}"
        dest = dest_dir / candidate
        idx += 1
    shutil.copy2(str(src), str(dest))
    return candidate


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
def api_sum_prepare(request):
    """第一步：根据用户输入的多个 lot 名，从 SLT_Summary 递归筛选 SUM 文件并复制到 lots/ 下。

    请求（POST JSON）：
    {
      "lot_names": ["smx", "lot2"],  // 不区分大小写，作为文件名包含判断
      "source_root": "\\\\172.33.10.11\\SLT_Summary" // 可选，若不传则走环境变量或默认 UNC
    }

    过滤规则：
    - 仅复制扩展名为 .SUM 或 .txt 的文件；
    - 文件名需包含任意一个 lot 名（不区分大小写）；
    - 文件名包含 ENG 或 SPC（不区分大小写）则排除；
    - 递归扫描 source_root 的所有子目录。
    返回：每个 lot 的复制数量与目标目录。
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        body = json.loads(request.body or '{}')
        lot_names = body.get('lot_names') or []
        source_root = body.get('source_root')
        if not isinstance(lot_names, list) or not lot_names:
            return JsonResponse({'ok': False, 'error': '请提供至少一个 lot 名（数组）'})

        # 规范化 lot 名列表：去重、去空格、转小写
        norm_lots = []
        seen = set()
        for ln in lot_names:
            s = str(ln or '').strip()
            if not s:
                continue
            sl = s.lower()
            if sl not in seen:
                seen.add(sl)
                norm_lots.append(sl)
        if not norm_lots:
            return JsonResponse({'ok': False, 'error': 'lot 名列表为空'})

        src_root = _resolve_slt_summary_root(source_root)
        if not src_root.exists() or not src_root.is_dir():
            return JsonResponse({'ok': False, 'error': f'源目录不可访问：{src_root}. 请挂载共享盘或设置环境变量 SLT_SUMMARY_ROOT。'})

        # 结果统计
        stats = {ln: {'copied': 0, 'dest': str(LOTS_DIR / ln)} for ln in norm_lots}

        # 递归扫描并复制
        exclude_pat = ('eng', 'spc')
        valid_ext = ('.sum', '.txt')
        for root, _dirs, files in os.walk(src_root):
            for fname in files:
                lower = fname.lower()
                # 扩展名过滤
                if not lower.endswith(valid_ext):
                    continue
                # 排除 ENG/SPC
                if any(k in lower for k in exclude_pat):
                    continue
                # lot 名包含判断
                matched = None
                for ln in norm_lots:
                    if ln in lower:
                        matched = ln
                        break
                if not matched:
                    continue
                src_file = Path(root) / fname
                dest_dir = LOTS_DIR / matched
                try:
                    final_name = _copy_with_collision(src_file, dest_dir)
                    stats[matched]['copied'] += 1
                except Exception:
                    # 忽略单个复制错误，继续扫描
                    pass

        return JsonResponse({'ok': True, 'stats': stats, 'source_root': str(src_root)})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)})


# --------------------------
# 异步准备：支持进度查询
# --------------------------

PREPARE_JOBS = {}

class PrepareJob:
    def __init__(self, job_id: str, norm_lots: list[str], src_root: Path):
        self.job_id = job_id
        self.norm_lots = norm_lots
        self.src_root = src_root
        self.stats = {ln: {'copied': 0, 'dest': str(LOTS_DIR / ln)} for ln in norm_lots}
        self.scanned_files = 0
        self.matched_files = 0
        self.copied_files = 0
        self.running = True
        self.error = ""
        self.start_ts = time.time()
        self.end_ts = None
        self._lock = threading.Lock()
        self._cancel = False
        self._thread = None

    def to_dict(self):
        with self._lock:
            return {
                'ok': True,
                'job_id': self.job_id,
                'running': self.running,
                'error': self.error,
                'stats': self.stats,
                'scanned_files': self.scanned_files,
                'matched_files': self.matched_files,
                'copied_files': self.copied_files,
                'elapsed_seconds': int((time.time() - self.start_ts) if self.start_ts else 0),
                'source_root': str(self.src_root),
            }

    def cancel(self):
        with self._lock:
            self._cancel = True


def _prepare_worker(job: PrepareJob):
    exclude_pat = ('eng', 'spc')
    valid_ext = ('.sum', '.txt')
    try:
        # 使用 os.scandir 提升目录遍历性能；复制阶段使用线程池并行 I/O
        with ThreadPoolExecutor(max_workers=4) as pool:
            stack = [job.src_root]
            while stack:
                base = stack.pop()
                try:
                    with os.scandir(base) as it:
                        for entry in it:
                            if job._cancel:
                                raise RuntimeError('用户取消')
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            name = entry.name
                            lower = name.lower()
                            # 扩展名过滤
                            if not lower.endswith(valid_ext):
                                continue
                            # 排除 ENG/SPC
                            if any(k in lower for k in exclude_pat):
                                continue
                            matched = None
                            for ln in job.norm_lots:
                                if ln in lower:
                                    matched = ln
                                    break
                            with job._lock:
                                job.scanned_files += 1
                            if not matched:
                                continue
                            with job._lock:
                                job.matched_files += 1

                            src_file = Path(entry.path)
                            dest_dir = LOTS_DIR / matched

                            def _copy_one(src=src_file, dest=dest_dir, ln=matched):
                                try:
                                    final_name = _copy_with_collision(src, dest)
                                    with job._lock:
                                        job.stats[ln]['copied'] += 1
                                        job.copied_files += 1
                                except Exception:
                                    pass

                            pool.submit(_copy_one)
                except Exception:
                    # 忽略单个目录的扫描错误，继续
                    continue
        with job._lock:
            job.running = False
            job.end_ts = time.time()
    except Exception as exc:
        with job._lock:
            job.error = str(exc)
            job.running = False
            job.end_ts = time.time()


@csrf_exempt
def api_sum_prepare_start(request):
    """启动异步准备任务，返回 job_id。"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        body = json.loads(request.body or '{}')
    except Exception:
        body = {}
    lot_names = body.get('lot_names') or []
    source_root = body.get('source_root')
    if not isinstance(lot_names, list) or not lot_names:
        return JsonResponse({'ok': False, 'error': '请提供至少一个 lot 名（数组）'})

    # 规范化 lot 名列表：去重、去空格、转小写
    norm_lots = []
    seen = set()
    for ln in lot_names:
        s = str(ln or '').strip()
        if not s:
            continue
        sl = s.lower()
        if sl not in seen:
            seen.add(sl)
            norm_lots.append(sl)
    if not norm_lots:
        return JsonResponse({'ok': False, 'error': 'lot 名列表为空'})

    src_root = _resolve_slt_summary_root(source_root)
    if not src_root.exists() or not src_root.is_dir():
        return JsonResponse({'ok': False, 'error': f'源目录不可访问：{src_root}. 请挂载共享盘或设置环境变量 SLT_SUMMARY_ROOT。'})

    job_id = uuid.uuid4().hex
    job = PrepareJob(job_id, norm_lots, src_root)
    PREPARE_JOBS[job_id] = job
    t = threading.Thread(target=_prepare_worker, args=(job,), daemon=True)
    job._thread = t
    t.start()
    return JsonResponse({'ok': True, 'job_id': job_id})


def _get_job(job_id: str) -> PrepareJob | None:
    job = PREPARE_JOBS.get(job_id)
    return job


def api_sum_prepare_status(request):
    job_id = request.GET.get('job') or ''
    job = _get_job(job_id)
    if not job:
        return JsonResponse({'ok': False, 'error': 'job 不存在'})
    return JsonResponse(job.to_dict())


@csrf_exempt
def api_sum_prepare_cancel(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        body = json.loads(request.body or '{}')
    except Exception:
        body = {}
    job_id = body.get('job_id') or ''
    job = _get_job(job_id)
    if not job:
        return JsonResponse({'ok': False, 'error': 'job 不存在'})
    job.cancel()
    return JsonResponse({'ok': True})


@csrf_exempt
def api_sum_run(request):
    """执行汇总，返回下载链接。"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'})
    try:
        body = json.loads(request.body or '{}')
        lots_dir = body.get('lots_dir') or str(BASE_ROOT / 'lots')
        use_tp_filter = bool(body.get('use_tp_filter'))
        tp_name = (body.get('tp_name') or '').strip()
        abs_lots = _ensure_safe_path(lots_dir)
        if not abs_lots.exists() or not abs_lots.is_dir():
            return JsonResponse({'ok': False, 'error': 'lots 目录不存在'})

        if sa is None:
            return JsonResponse({'ok': False, 'error': 'tools.calcSumXlsx.sum_aggregator 导入失败'})

        # 聚合并写出到 exports
        lot_subdirs = [str(abs_lots / d) for d in os.listdir(abs_lots) if (abs_lots / d).is_dir()]
        if not lot_subdirs:
            return JsonResponse({'ok': False, 'error': 'lots 目录下没有子目录'})

        tp_filter_value = (tp_name if use_tp_filter and tp_name else None)
        lot_summaries = [sa.aggregate_lot(ld, tp_filter_value) for ld in lot_subdirs]
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


@csrf_exempt
def api_sum_clear(request):
    """
    删除 lots 目录下的子文件夹及其所有内容。

    请求体（JSON）可选字段：
    - lots_dir: 要清理的 lots 根目录，默认 'lots'（相对项目根）
    - lot_names: 仅删除这些 lot 名对应的子目录（列表，可选，不区分大小写）

    返回：
    { ok: true, removed: [lot1, lot2], deleted_dirs: N, deleted_files: M, target: lots_dir }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': '仅支持 POST'}, status=405)

    try:
        body = json.loads(request.body or '{}')
    except Exception:
        body = {}

    lots_dir = body.get('lots_dir') or str(BASE_ROOT / 'lots')
    try:
        abs_lots = _ensure_safe_path(lots_dir)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)})

    if not abs_lots.exists() or not abs_lots.is_dir():
        return JsonResponse({'ok': True, 'removed': [], 'deleted_dirs': 0, 'deleted_files': 0, 'target': str(abs_lots)})

    lot_names = body.get('lot_names') or []
    norm_targets = [str(name).strip().lower() for name in lot_names if str(name).strip()] if lot_names else None

    removed = []
    deleted_dirs = 0
    deleted_files = 0

    for child in abs_lots.iterdir():
        if not child.is_dir():
            continue
        lot_dir_name = child.name.lower()
        if norm_targets is not None and lot_dir_name not in norm_targets:
            continue
        # 统计数量
        for root, dirs, files in os.walk(child):
            deleted_files += len(files)
            deleted_dirs += len(dirs)
        try:
            shutil.rmtree(child)
            removed.append(child.name)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'移除 {child.name} 失败: {e}'}, status=500)

    return JsonResponse({
        'ok': True,
        'removed': removed,
        'deleted_dirs': deleted_dirs,
        'deleted_files': deleted_files,
        'target': str(abs_lots),
    })
