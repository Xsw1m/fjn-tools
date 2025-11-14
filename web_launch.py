#!/usr/bin/env python3
"""
一键启动脚本：创建虚拟环境，安装依赖，启动 Django，并打开页面。

使用方法：
  python web_launch.py

该脚本会：
  1) 在项目根目录创建 .venv（如不存在）并安装依赖
  2) 运行迁移（如有需要）
  3) 启动开发服务器（默认 8000，占用则顺延到 8001）
  4) 自动在浏览器打开首页
"""

import os
import sys
import time
import venv
import socket
import subprocess
import webbrowser
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent
SERVER_DIR = ROOT / 'server'
MANAGE = SERVER_DIR / 'manage.py'
VENV_DIR = ROOT / '.venv'
CONFIG_DIR = ROOT / 'config'
CONFIG_FILE = CONFIG_DIR / 'config.json'
CONFIG_EXAMPLE = CONFIG_DIR / 'config.example.json'


def ensure_config_interactive():
    """确保存在配置文件 config/config.json。

    - 若存在：读取后将同名键注入到当前进程的环境变量（若环境变量未设置）。
    - 若不存在：交互提示用户输入共享盘地址，创建 config.json。
    """
    CONFIG_DIR.mkdir(exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f) or {}
            for k in ('SLT_SUMMARY_ROOT', 'MAPPING_ROOT'):
                if k in cfg and (os.environ.get(k) is None or os.environ.get(k) == ''):
                    os.environ[k] = str(cfg.get(k) or '').strip()
            print('[+] 已读取配置文件 config/config.json。')
        except Exception as exc:
            print('[!] 读取 config/config.json 失败：', exc)
        return

    print('''
[+] 未检测到配置文件 config/config.json。
    该文件用于保存共享盘地址（不提交到仓库，已在 .gitignore 忽略）。
    如果你不清楚，可参考示例：config/config.example.json。
    ''')
    try:
        server = input('请输入 server 共享网络 io 地址，例如: \\\\172.xx.xx.xx\ ').strip()
    except EOFError:
        server = ''

    cfg = {
        'SLT_SUMMARY_ROOT': server + 'SLT_Summary' or '',
        'MAPPING_ROOT': server + '3270' or '',
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print('[+] 已生成配置文件：', CONFIG_FILE)
    except Exception as exc:
        print('[x] 写入配置文件失败：', exc)

    # 同步到当前进程环境变量，便于后续使用
    if cfg.get('SLT_SUMMARY_ROOT'):
        os.environ['SLT_SUMMARY_ROOT'] = cfg['SLT_SUMMARY_ROOT']
    if cfg.get('MAPPING_ROOT'):
        os.environ['MAPPING_ROOT'] = cfg['MAPPING_ROOT']


def ensure_venv():
    """确保虚拟环境存在并安装依赖。"""
    if not VENV_DIR.exists():
        print('[+] 创建虚拟环境 .venv ...')
        venv.create(str(VENV_DIR), with_pip=True)
    if sys.platform == "win32":
        vpy = VENV_DIR / 'Scripts' / 'python.exe'
    else:
        vpy = VENV_DIR / 'bin' / 'python'

    pip = [str(vpy), '-m', 'pip']

    # 先确保 pip 可用（部分系统的 venv 可能未包含 pip）
    print('[+] 检查 pip ...')
    try:
        subprocess.check_call([str(vpy), '-m', 'pip', '--version'])
    except subprocess.CalledProcessError:
        print('[!] 当前虚拟环境未检测到 pip，尝试使用 ensurepip 安装 ...')
        subprocess.check_call([str(vpy), '-m', 'ensurepip', '--upgrade'])

    print('[+] 升级 pip/setuptools/wheel ...')
    subprocess.check_call(pip + ['install', '--upgrade', 'pip', 'setuptools', 'wheel'])

    # 安装后端所需依赖：Django + 跨域 + 表格相关
    deps = [
        'Django>=5.2',
        'django-cors-headers>=4.4',
        'pandas>=2.0',
        'openpyxl>=3.1',
        'XlsxWriter>=3.1',
    ]
    print('[+] 安装依赖 ...')
    req = ROOT / 'requirements.txt'
    if req.exists():
        subprocess.check_call(pip + ['install', '-r', str(req)])
    else:
        subprocess.check_call(pip + ['install'] + deps)
    return str(vpy)


def pick_port(preferred=8000):
    """选择可用端口。"""
    def is_free(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(('127.0.0.1', p)) != 0
    if is_free(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 10):
        if is_free(p):
            return p
    return preferred


def run_migrate(vpy_path: str):
    """运行迁移，忽略失败。"""
    try:
        print('[+] 运行迁移 ...')
        subprocess.check_call([vpy_path, str(MANAGE), 'migrate'])
    except subprocess.CalledProcessError as exc:
        print('[!] migrate 出错（可忽略）：', exc)


def run_server(vpy_path: str, port: int):
    """启动开发服务器。"""
    print(f'[+] 启动服务器 http://127.0.0.1:{port}/ ...')
    # 使用 Popen 保持运行
    proc = subprocess.Popen([vpy_path, str(MANAGE), 'runserver', f'0.0.0.0:{port}'])
    return proc


def main():
    if not MANAGE.exists():
        print('[x] 未找到 server/manage.py，请在项目根目录运行本脚本。')
        sys.exit(1)

    # 在启动前确保配置存在（或注入环境变量）
    ensure_config_interactive()

    vpy = ensure_venv()
    run_migrate(vpy)
    port = pick_port(8000)
    proc = run_server(vpy, port)
    # 等待服务启动输出
    time.sleep(1.5)
    url = f'http://localhost:{port}/'
    print('[+] 打开浏览器：', url)
    try:
        webbrowser.open(url)
    except Exception as exc:
        print('[!] 打开浏览器失败：', exc)

    print('[+] 服务器已启动。按 Ctrl+C 可终止。')
    try:
        proc.wait()
    except KeyboardInterrupt:
        print('\n[+] 收到中断指令，正在退出。')
        proc.terminate()


if __name__ == '__main__':
    main()