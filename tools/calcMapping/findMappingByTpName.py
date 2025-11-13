import os
import re
import zipfile

def _validate_mapping_name(name: str) -> bool:
    return bool(re.compile(r'^OVT FT\+SLT_A V[3-4]\.0_[a-zA-Z0-9]{7}_(Nor|New[0-4])\.mapping$').match(name))

def _rank_mapping_name(name: str) -> tuple:
    v = 3
    m = re.search(r'V([3-4])\.0', name)
    if m:
        v = int(m.group(1))
    new_tag = -1
    nm = re.search(r'_(Nor|New[0-4])\.mapping$', name)
    if nm:
        tag = nm.group(1)
        new_tag = 1 if tag.startswith('New') else 0
    return (v, new_tag, name)

def _parse_category_remark(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if not re.match(r'^\d', raw):
            continue
        m = re.match(r'^(\d+)\s+(\d+)\s+(.*?)\s+(\d+)\s*$', raw)
        if not m:
            nums = re.findall(r'\d+', raw)
            if len(nums) < 2:
                continue
            head = raw
            tail_num = re.search(r'(\d+)\s*$', raw)
            if not tail_num:
                continue
            middle = head[:tail_num.start()].strip()
        else:
            middle = m.group(3).strip()
            cat = int(m.group(1))
            s = re.sub(r'^\d+\s+', '', middle).strip()
            if s:
                result.setdefault(cat, s)
            continue
        nums2 = re.findall(r'^\d+', raw)
        if not nums2:
            continue
        cat = int(nums2[0])
        s = re.sub(r'^\d+\s+', '', middle).strip()
        if s:
            result.setdefault(cat, s)
    return result

def get_category_remark_map(tp: str) -> dict:
    directory_path = r"\\172.21.10.201\3270"
    candidates = [f for f in os.listdir(directory_path) if tp in f]
    for entry in candidates:
        if '.zip' in entry:
            zip_path = os.path.join(directory_path, entry)
            target_path = 'Image/ProductFile/Category/'
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    names = []
                    for info in zf.infolist():
                        if not info.is_dir() and info.filename.startswith(target_path) and info.filename.endswith('.mapping'):
                            name = info.filename.split(target_path)[1]
                            if _validate_mapping_name(name):
                                names.append(name)
                    if names:
                        best = sorted(names, key=_rank_mapping_name, reverse=True)[0]
                        target = target_path + best
                        try:
                            data = zf.read(target).decode('utf-8', errors='ignore')
                            return _parse_category_remark(data)
                        except Exception:
                            continue
            except zipfile.BadZipFile:
                continue
        else:
            cat_dir = os.path.join(directory_path, entry, 'ProductFile', 'Category')
            if not os.path.isdir(cat_dir):
                continue
            names = [n for n in os.listdir(cat_dir) if n.endswith('.mapping') and _validate_mapping_name(n)]
            if names:
                best = sorted(names, key=_rank_mapping_name, reverse=True)[0]
                path = os.path.join(cat_dir, best)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        return _parse_category_remark(f.read())
                except Exception:
                    continue
    return {}

if __name__ == '__main__':
    import sys
    tp = sys.argv[1] if len(sys.argv) > 1 else ''
    m = get_category_remark_map(tp) if tp else {}
    for k in sorted(m.keys()):
        print(f'{k}: {m[k]}')
