# 需求文档：SUM 文件整合生成 xlsx 总结工具
版本：v1.2.0（2025-11-14）

更新摘要：
- 新增“准备与清理”前置功能说明：支持从网络目录按 lot 名筛选复制 SUM 文件到 `lots/`，以及一键清除 `lots/` 下的子目录。
- 补充后端接口：`POST /api/sum/prepare` 与 `POST /api/sum/clear` 的请求与返回格式。
- 前端交互采用分步流程（SumWizard）：先准备，再生成 xlsx；在步骤一即可清除旧数据。
- 新增可选“TpName 过滤”步骤：可勾选是否按 Program ID（TpName）过滤；启用后仅统计 Program ID 与用户输入 TpName 精确匹配的 SUM 文件。

## 一、工具目标

开发一个 Python 小工具，用于整合`lots`文件夹下所有子文件夹（如 lot1、lot2 等）中的 SUM 文件，提取关键数据并按照指定规则计算、统计，最终生成包含总结信息的 xlsx 文件。

## 二、文件结构与命名规则

- 根目录存在`lots`文件夹，其下包含多个以`lot+数字`命名的子文件夹（如 lot1、lot2）。
- 每个 lot 子文件夹下包含多个 SUM 文件，文件名为`[前缀]_[时间戳].txt`（如 AT1_081125_040616.txt）。
- 时间戳格式为`MMDDYY_HHmmss`，解析为**25 年 MM 月 DD 日\_HH 点 mm 分 ss 秒**（如 081125_040616 表示 25 年 11 月 08 日\_04 点 06 分 16 秒），用于判断文件生成时间的先后顺序，解析需精确到秒以保证排序准确性。

附：准备与清理（前置步骤）
- 准备：根据用户输入的多个 lot 名，从源目录（默认 `\\172.33.10.11\SLT_Summary`，可由环境变量 `SLT_SUMMARY_ROOT` 指定本地挂载路径）递归筛选复制到 `lots/lot_name/`。
  - 仅复制扩展名为 `.SUM` 或 `.txt` 的文件；
  - 文件名需包含任意一个 lot 名（不区分大小写）；
  - 文件名包含 `ENG` 或 `SPC`（不区分大小写）则排除；
  - 若发生重名，目标文件自动添加 `(1)`, `(2)` 等后缀避免覆盖。
- 清理：一键删除 `lots/` 下所有子文件夹及其内容（或按 `lot_names` 指定要清理的子目录）。

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
| 倒数第 3 列   | `sum`（对应`Lot_id`的跨 lot 总和，为正整数）                         |
| 倒数第 2 列   | `rate`（`sum / 所有 lot 的 Total 之和`，百分比，两位小数）           |
| 最后一列      | `remark`（按 `TpName` 映射的 `category → Code Description` 文本）    |

| 行内容        | 说明                                                                                                  |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| 第 1 行       | 行头（`Lot_id`、各`lot`名称、`sum`、`rate`、`remark`）                                                |
| 第 2 行       | `Total`（各 lot 的最老文件 Total 值；`remark` 为空）                                                  |
| 第 3 行       | `TotalPass`（所有文件 TotalPass 之和；`remark` 为空）                                                 |
| 第 4 行       | `TotalFail`（Total - TotalPass；`remark` 为空）                                                       |
| 第 5 行及以后 | 各`Category_BIN`统计行（如 `1_5`、`2_1`；数值为正整数或“error”）；`remark` 为该 `category` 的描述文本 |

---

## 六、remark 列生成规则

- 每个 SUM 文件包含 `Program ID` 字段，其值作为 `TpName` 来源。
- 根据任意 lot 的最新 SUM 文件解析到的 `TpName`，在网络目录 `\\172.33.10.11\3270` 下查找对应 Mapping 文件（支持 zip 包与普通文件夹），解析得到 `category → remark(Code Description)` 对应关系。
- remark 仅与 `category` 相关，与 `BIN` 无关；为保证一致性，若无法解析到映射则置空。

### 异常与兜底（细分）

- 未解析到任意 SUM 文件的 `Program ID`：`remark` 列显示 `没找到 Program ID`。
- 所有 SUM 文件均解析到 `TpName`，但未找到任何 Mapping 文件：`remark` 列显示 `没找到 Mapping`。
- 找到 Mapping，但某一行的 `category` 在 Mapping 中没有对应描述：该行 `remark` 显示 `没找到 Mapping 里面对应 category 的 Remark`。

---

## 七、前置接口与分步流程（新增 v1.1.0）

为保证“lots/”数据来源一致、可控，新增“准备与清理”接口与分步交互（SumWizard）：

- 接口一：`POST /api/sum/prepare`
  - 请求体：`{ lot_names: string[], source_root?: string }`
  - 行为：从源目录递归筛选符合规则的 SUM 文件，按 lot 名复制到 `lots/lot_name/`。
  - 过滤规则：扩展名为 `.SUM`/`.txt`；文件名包含任一 lot 名；排除包含 `ENG` 或 `SPC` 的文件名（不区分大小写）。
  - 返回示例：`{ ok: true, stats: { smx: { copied: 12, dest: ".../lots/smx" } }, source_root: "..." }`

- 接口二：`POST /api/sum/clear`
  - 请求体：`{ lots_dir?: string, lot_names?: string[] }`
  - 行为：删除 `lots_dir`（默认 `lots`）下的所有子文件夹及其内容；若指定 `lot_names`，仅清理匹配的子目录。
  - 返回示例：`{ ok: true, removed: ["lot1","lot2"], deleted_dirs: 3, deleted_files: 42, target: ".../lots" }`

- 前端流程（SumWizard）：
  - 步骤一：输入 lot 名 → 可先“清除 lots” → 执行“准备”（筛选复制）。
  - 步骤二（新增，可选）：勾选“按 TpName 过滤”开关；如勾选，需填写 `TpName`（即 Program ID）。
  - 步骤三：确认 `lots` 路径 → 生成 xlsx 并下载。

> 说明：准备与清理为可选前置步骤；聚合与生成 xlsx 的核心逻辑保持不变，仍按本文档第三～五部分说明执行。

## 八、TpName 过滤规则（新增 v1.2.0）

当用户在步骤二勾选“按 TpName 过滤”并输入 `TpName` 时：
- 过滤范围：仅纳入 Program ID（TpName）与用户输入值相同的 SUM 文件参与统计；不相同的文件全部跳过。
- 匹配规则：去除首尾空格后进行精确匹配（不区分大小写）。
- 数据影响：
  - `Total`：改为取每个 lot 在“匹配集合”中最老文件的 `TotalPass + TotalFail`；若某 lot 无匹配文件，则该 lot 的 `Total` 视为 0（或留空，按实现展示）。
  - `TotalPass`：仅统计“匹配集合”中所有文件的 `TotalPass` 之和。
  - `TotalFail`：`Total - TotalPass`，保持非负。
  - `Category_BIN`：在“匹配集合”范围内适用既有规则（BIN=1/4 汇总所有匹配文件的 COUNT，BIN=2/3/5 取匹配集合中最新文件的 COUNT）。
  - `error` 标记：仍以匹配集合中同一 lot 的文件为准，若同一 `category` 的 BIN 等级在不同匹配文件中不一致，则该 lot 单元格标记为 `error`。
- remark 解析：
  - 优先从“匹配集合”任意 lot 的最新文件获取 `TpName` 用于 Mapping；若过滤后匹配集合为空或缺少 Program ID，`remark` 兜底规则生效（如“没找到 Program ID”）。
- 容错与提示：
  - 若过滤启用但没有任何匹配文件，前端应提示“未找到匹配 Program ID 的文件”，并允许用户返回修改或取消过滤。

当未勾选过滤时：
- 行为与 v1.1.0 保持一致，即不进行 TpName 过滤，统计范围为所有 SUM 文件。

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

4. **生成 xlsx**：按照指定格式生成 xlsx，列包含各 lot 名称、`sum`（正整数）、`rate`（百分比，两位小数）、`remark`（由 `TpName` 的 Mapping 解析得到的 `category` 描述）；行包含`Total`（整数）、`TotalPass`（整数）、`TotalFail`（非负整数）及各`Category_BIN`条目（数值为正整数或“error”，对应行的 `remark` 为该 `category` 的描述）。

请使用`pandas`库处理数据，`openpyxl`或`xlsxwriter`处理 Excel 生成，确保代码结构清晰、有必要的注释，并处理可能的异常（如文件读取错误、字段缺失、Total 不一致等）。

5. **可选 TpName（Program ID）过滤**：
   - 若启用过滤，仅对 Program ID 与用户输入的 `TpName` 精确匹配（不区分大小写，忽略首尾空格）的 SUM 文件进行统计；未匹配的文件跳过。
   - 过滤启用时，所有统计（`Total`/`TotalPass`/`TotalFail` 与 `Category_BIN`）均基于“匹配集合”；若某 lot 无匹配文件，其对应列可视为 0 或留空。
   - remark 的 Mapping 解析优先从“匹配集合”任意 lot 的最新文件获取 `TpName`；若匹配集合为空或缺少 Program ID，则应用兜底提示。
