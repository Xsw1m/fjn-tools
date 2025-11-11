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


ROOT = Path(__file__).resolve().parent
SERVER_DIR = ROOT / 'server'
MANAGE = SERVER_DIR / 'manage.py'
VENV_DIR = ROOT / '.venv'


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