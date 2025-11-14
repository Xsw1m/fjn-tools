---
title: SUM 汇总工具
---

## 启动指南（小白版，推荐方法优先）

⚠️ 省流：直接在根目录运行 `web_launch.py` 即可。

以下步骤适合不懂代码的使用者，照做即可运行小工具：

### 方法一：直接使用已打包的可执行（macOS，推荐）

- 位置：`/Users/admin/Desktop/fjn-tools/dist/sum-tool`
- 操作：在 Finder 中双击 `sum-tool` 即可运行。
- 要求：同目录下要有一个 `lots/` 文件夹（例如 `/Users/admin/Desktop/fjn-tools/lots`）。
- 结果：运行完成后，会在同目录生成 `result.xlsx`。
- 若系统提示“来自不受信任的开发者而被阻止”：
  - 打开 系统设置 → 隐私与安全性 → 找到“sum-tool 已被阻止使用”，点击“仍要打开”。

### 方法二：未安装或不使用 PyInstaller 时的启动方式（跨平台）

不需要安装任何打包工具，直接用自带的 Python 运行启动器：

- 打开 终端（Spotlight 搜索“终端”或“Terminal”）。
- 复制粘贴并回车（默认读取同目录 `lots/` 输出到同目录 `result.xlsx`）：
  - `/Users/admin/Desktop/fjn-tools/.venv/bin/python /Users/admin/Desktop/fjn-tools/sum_tool_launcher.py`
- 如需自定义路径：
  - `/Users/admin/Desktop/fjn-tools/.venv/bin/python /Users/admin/Desktop/fjn-tools/sum_tool_launcher.py /Users/admin/Desktop/fjn-tools/lots /Users/admin/Desktop/fjn-tools/result.xlsx`
- 看到终端打印“已生成 Excel: …/result.xlsx”即成功。
- 若提示缺依赖（一般已安装好）：执行
  - `/Users/admin/Desktop/fjn-tools/.venv/bin/python -m pip install pandas openpyxl xlsxwriter`

### Windows 用户（需在 Windows 上操作）‼️‼️‼️‼️‼️

- 直接运行（不打包）：
  - `python sum_tool_launcher.py <lots_dir> [output_excel_path]`
- 打包为 `.exe`（可选）：
  - 安装：`python -m pip install pyinstaller pandas openpyxl xlsxwriter`
  - 打包：`pyinstaller --onefile --name sum-tool sum_tool_launcher.py`
  - 双击运行：`dist/sum-tool.exe`（`lots/` 放在同目录，输出 `result.xlsx`）。
  - 若同目录没有 `lots/`：双击后会弹出对话框让你选择 `lots` 目录，并选择输出的 `result.xlsx` 保存位置。

### 目录与文件放置规则（通用）

- 默认不传参数时：程序会在“自身所在目录”查找 `lots/` 并生成 `result.xlsx` 到该目录。
- 若输出路径已存在同名文件（例如 `result.xlsx`），会自动生成不重复文件名，例如：`result(1).xlsx`、`result(2).xlsx`（在扩展名前添加 `(n)`，无空格）。
- 你可以传入两个参数：第一个是 `lots` 的路径，第二个是输出的 `xlsx` 路径。
- 示例：
  - `sum-tool /Users/admin/Desktop/fjn-tools/lots /Users/admin/Desktop/fjn-tools/result.xlsx`
  - 或用 Python：`python sum_tool_launcher.py /path/to/lots /path/to/result.xlsx`

### 成功校验

- 运行后应能在终端看到“已生成 Excel: <输出路径>”。
- 打开生成的 `result.xlsx`，列应包含各 `lot` 名称、`sum`、`rate`；行包含 `Total`、`TotalPass`、`TotalFail` 及各 `Category_BIN`（如 `1_5`、`2_1`）。

如需进一步做成图形界面（选择目录、输出路径）或需要直接提供 Windows `.exe` 成品，我可以继续完善并交付对应文件。

---

## 发布与分享（发布版）

### 必需文件（最小集）

- `web_launch.py`：一键启动（创建虚拟环境、安装依赖、迁移数据库、启动服务并打开页面）。
- `server/`（Django 项目）：`manage.py`、`webtools/` 下的 `settings.py`、`local_settings.py`、`urls.py`、`wsgi.py`、`asgi.py`。
- `sumtool/`（Django 应用）：`views.py`、`apps.py`、`migrations/`（保留空目录和 `__init__.py`）。
- `tools/calcSumXlsx/sum_aggregator.py`：汇总核心逻辑（工具包目录）。
- `client/index.html`：前端静态页面（路径输入、服务器目录选择、生成按钮）。
- `README.md`、`requirements.txt`。

### 不要打包的文件

- `.venv/`、`__pycache__/`、`*.pyc`、`.DS_Store`。
- `server/db.sqlite3`、`uploads/`、`exports/`、`result.xlsx`。
- `dist/`（发布包输出目录，打包前可先清空）。

### 一键启动（推荐给接收方）

- 环境要求：安装 `python3`（建议 3.10+）。
- 进入项目根目录，执行：`python web_launch.py`
- 脚本会自动：创建 `.venv` → 安装依赖（`requirements.txt`）→ 迁移数据库 → 启动开发服务器（自动选端口）→ 打开首页。
- 页面操作：点击“默认”或“选择”选取 `lots` 路径 → 点击“生成 xlsx” → 成功后出现下载链接（自动避免重名）。

### 本地打包发布版 zip

- 在项目根目录执行：`python make_release.py`
- 输出文件：`dist/fjn-tools-release.zip`
- 包含内容：上述“必需文件（最小集）”。

### 发布到 GitHub 的步骤

1. 初始化仓库并首次提交：
   - `git init`
   - `git add -A`
   - `git commit -m "release: initial publish"`
2. 在 GitHub 创建一个空仓库（例如 `fjn-tools`）。
3. 添加远程并推送：
   - `git remote add origin https://github.com/<your-username>/fjn-tools.git`
   - `git branch -M main`
   - `git push -u origin main`
4. 可在 Releases 中上传 `dist/fjn-tools-release.zip` 作为发布附件（可选）。

### 版本管理建议

- 使用 `.gitignore`（已内置）避免提交临时产物与环境文件。
- 通过 `requirements.txt` 固定依赖版本，确保他人安装一致。
- 若需要可重复打包，使用 `make_release.py` 统一产出 zip。

---

## 前端使用说明（统一为静态页）

- 前端入口统一为 `client/index.html`，根路径 `/` 直接返回该页面。
- 页面默认路径为相对路径 `lots`，适配任何机器的项目目录。
- 通过“选择”弹窗仅浏览项目根目录内的路径；为安全起见，服务端会拒绝越界路径。
- 传入的绝对路径若包含 `lots` 段，将自动规范为项目内对应位置（例如 `/Users/foo/bar/lots/lot1` → `<项目>/lots/lot1`）。
- 原后端内嵌页面已移除，避免双入口造成混淆。

---

## 配置与地址（请务必填写）

- 统一配置文件：`config/config.json`（真实文件，默认被 `.gitignore` 忽略）
- 示例文件：`config/config.example.json`（已提交到仓库，可复制为真实配置后修改）

需要填写的键：

- `SLT_SUMMARY_ROOT`：SUM 源目录（例如 `//server/SLT_Summary`）。后端准备接口与前端默认都会读取此值。
- `MAPPING_ROOT`：Mapping 根目录（例如 `//server/3270`）。用于 remark 解析工具与脚本。

安全与提交说明：

- 请不要把真实共享地址（例如 `\\172.XX.XX.XX\...`）写在代码里或提交到仓库。
- 真实配置请写入 `config/config.json`，该文件已在 `.gitignore` 中忽略，不会被提交。
- 若不方便创建文件，也可以通过环境变量设置同名键：`SLT_SUMMARY_ROOT`、`MAPPING_ROOT`。

前端与后端行为：

- 前端“源目录”输入留空时，后端会从 `config/config.json` 或环境变量读取 `SLT_SUMMARY_ROOT`。
- 所有涉及 Mapping 的工具脚本（`tools/calcMapping/*`）将读取 `MAPPING_ROOT`。
