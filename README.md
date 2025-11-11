# 需求文档：SUM 文件整合生成 xlsx 总结工具

## 一、工具目标

开发一个 Python 小工具，用于整合`lots`文件夹下所有子文件夹（如 lot1、lot2 等）中的 SUM 文件，提取关键数据并按照指定规则计算、统计，最终生成包含总结信息的 xlsx 文件。

## 二、文件结构与命名规则

- 根目录存在`lots`文件夹，其下包含多个以`lot+数字`命名的子文件夹（如 lot1、lot2）。
- 每个 lot 子文件夹下包含多个 SUM 文件，文件名为`[前缀]_[时间戳].txt`（如 AT1_081125_040616.txt）。
- 时间戳格式为`MMDDYY_HHmmss`，解析为**25 年 MM 月 DD 日\_HH 点 mm 分 ss 秒**（如 081125_040616 表示 25 年 11 月 08 日\_04 点 06 分 16 秒），用于判断文件生成时间的先后顺序，解析需精确到秒以保证排序准确性。

## 三、数据提取与时间判断规则

### （一）关键字段提取要求

1. **TotalPass & TotalFail**：从文件中提取格式为`TotalPass: [整数数值]`、`TotalFail: [整数数值]`的字段，数值为非负整数。
2. **Software Category、Hardware BIN、COUNT**：
   - `Software Category`：为整数编号（如 1、2、3 等）。
   - `Hardware BIN`：为 1-5 的整数等级。
   - `COUNT`：为正整数，三者需在文件中逐行一一对应。

注：**TotalPass/TotalFail 可在全文任意位置**；为避免误取其他列表，**Category/BIN/COUNT 仅在“Site Total Summary”块内解析**，如未找到该块则回退到全文解析。

### （二）文件时间排序

根据文件名中的时间戳（精确到秒），对每个 lot 下的 SUM 文件进行排序，区分“最老文件”（时间最早）和“最新文件”（时间最晚）。

## 四、核心计算逻辑

### （一）Total、TotalPass、TotalFail 计算

- `Total`：取每个 lot 下**最老文件**的`TotalPass + TotalFail`，不再要求各 lot 的 Total 一致。
- `TotalPass`：所有 lot 下**所有 SUM 文件**的`TotalPass`整数数值之和，确保无文件遗漏。
- `TotalFail`：`Total - TotalPass`，结果需为非负整数。

### （二）Category-BIN 统计（Lot_id 格式：`Category_BIN`，仅数字与下划线）

- 当`BIN`为 1 或 4 时，统计对应 lot 下**所有 SUM 文件**中相同`Category`和`BIN`的`COUNT`正整数总和。
- 当`BIN`为 2、3 或 5 时，统计对应 lot 下**最新 SUM 文件**中该`Category`和`BIN`的`COUNT`正整数值。
- 若同一 lot 下**任意两个 SUM 文件**中，相同`Category`的`BIN`等级不一致，该 lot 对应单元格标记为“error”。

## 五、输出 xlsx 格式要求

| 列内容        | 说明                                                                 |
| ------------- | -------------------------------------------------------------------- |
| 第 1 列       | `Lot_id`（格式：`Category_BIN`，示例：`1_5`，不含 `CAT`/`BIN` 前缀） |
| 第 2 列及以后 | 各`lot`名称（如 lot1、lot2）                                         |
| 倒数第 2 列   | `sum`（对应`Lot_id`的跨 lot 总和，为正整数）                         |
| 最后一列      | `rate`（`sum / 所有 lot 的 Total 之和`，百分比，两位小数）          |

| 行内容        | 说明                                                               |
| ------------- | ------------------------------------------------------------------ |
| 第 1 行       | 行头（`Lot_id`、各`lot`名称、`sum`、`rate`）                       |
| 第 2 行       | `Total`（各 lot 的最老文件 Total 值）                               |
| 第 3 行       | `TotalPass`（所有文件 TotalPass 之和，整数）                       |
| 第 4 行       | `TotalFail`（Total - TotalPass，非负整数）                         |
| 第 5 行及以后 | 各`Category_BIN`的统计行（如 `1_5`、`2_1`；数值为正整数或“error”） |

---

# 给 Cursor 的提示词

请生成一个 Python 小工具，用于整合`lots`文件夹下的所有 SUM 文件并生成总结 xlsx。具体需求如下：

1. **文件遍历与时间解析**：遍历`lots`下的所有`lot`文件夹（如 lot1、lot2），对每个`lot`下的 SUM 文件（文件名格式为`[前缀]_[MMDDYY_HHmmss].txt`），**精确到秒解析时间戳为 datetime 对象**，区分最老和最新文件。

2. **数据提取**：从每个 SUM 文件中提取`TotalPass`（非负整数）、`TotalFail`（非负整数），以及`Software Category`（整数）、`Hardware BIN`（1-5 整数）、`COUNT`（正整数）的明细数据，确保三者逐行一一对应。

3. **计算逻辑**：

   - `Total`：每个 lot 最老文件的`TotalPass + TotalFail`，**所有 lot 的 Total 必须数值一致**，否则抛出异常提示。
   - `TotalPass`：所有文件的`TotalPass`整数之和，确保无遗漏。
   - `TotalFail`：`Total - TotalPass`，非负整数。
   - `Category_BIN`统计：
     - BIN 为 1、4 时，统计对应 lot 所有文件的 COUNT 正整数总和；
     - BIN 为 2、3、5 时，统计对应 lot 最新文件的 COUNT 正整数值；
     - 同一 lot 下**任意两个文件**中相同 Category 的 BIN 不一致时，标记该 lot 对应单元格为“error”。

4. **生成 xlsx**：按照指定格式生成 xlsx，列包含各 lot 名称、`sum`（正整数）、`rate`（百分比，保留两位小数）；行包含`Total`（整数）、`TotalPass`（整数）、`TotalFail`（非负整数）及各`Category_BIN`条目（数值为正整数或“error”）。

请使用`pandas`库处理数据，`openpyxl`或`xlsxwriter`处理 Excel 生成，确保代码结构清晰、有必要的注释，并处理可能的异常（如文件读取错误、字段缺失、Total 不一致等）。

---

## 启动指南（小白版，推荐方法优先）

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
- `sum_aggregator.py`：汇总核心逻辑。
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
