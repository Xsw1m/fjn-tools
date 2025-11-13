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
