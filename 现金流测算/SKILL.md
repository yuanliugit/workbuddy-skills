---

name: "现金流测算"
description: >
  面向银行信贷审批场景的项目偿债现金流测算全流程 Skill。
  核心能力：读取项目评估文档（docx/xlsx）→ 参数提取 → Python OOP模型（DebtFacility债务测算类+ProjectAsset现金流类）→ DSCR计算 → 带公式的Excel交付。
  支持：宽限期（建设期仅付息）、非标自定义还本曲线（前低后高/气球型/等额）、特定收入精准剥离（仅提取核心主营收入）、逐年差异化税率（如三免三减半）。
  适用项目类型：风电/光伏/管网/基建/制造业固定资产贷款、项目融资（Project Finance）。
  输出：①控制台DSCR测算表（Pandas DataFrame）②带Excel公式的标准财务模型（4个Sheet：假设参数/CFADS瀑布/债务排期/DSCR综合）。
  触发条件：用户提到"偿债测算"、"DSCR测算"、"还款计划"、"现金流测算"、"项目融资建模"、"CFADS"、"信贷审批测算"、"项目评估"、"风电/管网/基建贷款分析"等。
agent_created: true
version: "1.0.0"
loop_engineered: true
loop_engineered_version: "1.0.0"
workspace: "D:\\Workbuddy"
---

# 项目偿债现金流测算 Skill

## 概述

本 Skill 在 WorkBuddy 本地环境（Python 3.12 + openpyxl + Pandas）中运行，完整流程：

1. **读取项目材料** — 解析用户提供的 `.docx` / `.xlsx` 项目评估文件，提取关键假设参数
2. **实例化 DebtFacility** — 配置宽限期、自定义还本曲线，生成完整债务排期
3. **实例化 ProjectAsset** — 定义收入流、精准剥离非核心收入、逐年计算 CFADS
4. **合并 DSCR 指标** — 生成 Pandas DataFrame 表格，控制台输出并分析合规状态
5. **生成 Excel 模型** — openpyxl 构建带 Excel 公式的 4-Sheet 标准财务模型（假设参数改动后全表自动联动重算）
6. **交付与审查意见** — 输出文件 + 关键审查发现（DSCR低于警戒线的原因分析与整改建议）

---

## 核心脚本路径

| 文件 | 路径 | 说明 |
|------|------|------|
| 基础类库 | `D:\Workbuddy\debt_cashflow_model.py` | `DebtFacility` + `ProjectAsset` 两个核心类，已验证可用 |
| 风电案例脚本 | `D:\Workbuddy\wind_power_case.py` | 子洲县10万千瓦风电项目实跑案例，含MWh换算修正 |
| Excel构建脚本 | `D:\Workbuddy\build_excel_model.py` | openpyxl 生成4-Sheet带公式Excel模型 |
| 输出Excel | `D:\Workbuddy\wind_power_dscr_model.xlsx` | 已验证的Excel模型示例 |

**CRITICAL**: 创建新项目时，以上述文件为模板复制修改，不要直接编辑原文件。

---

## 工作流路由

| 用户输入 | 处理路径 |
|---------|---------|
| 提供 `.docx` 项目评估文件 | 步骤1→2→3→4→5→6 完整流程 |
| 提供 `.xlsx` 参数表 | 步骤1（直接读表）→2→3→4→5→6 |
| 口述参数（文字描述） | 整理参数确认表 → 步骤2→3→4→5→6 |
| 只要Python测算结果 | 步骤2→3→4（跳过Excel生成） |
| 只要Excel模型 | 基于已有Python结果，直接步骤5→6 |

---

## 步骤详解

### 第1步：读取项目材料并提取假设参数

**1A — 读取 docx 文件**

```python
import docx
doc = docx.Document(r"路径\项目评估.docx")
# 读取正文段落
for para in doc.paragraphs:
    if para.text.strip():
        print(para.text)
# 读取表格（重要：财务数据通常在表格中）
for i, table in enumerate(doc.tables):
    print(f"--- 表格 {i+1} ---")
    for row in table.rows:
        cells = [c.text.strip() for c in row.cells]
        if any(cells):
            print(" | ".join(cells))
```

**1B — 必须提取的参数清单**

| 参数类别 | 必提参数 | 备注 |
|---------|---------|------|
| 融资结构 | 总投资、资本金比例、贷款本金 | 注意：贷款本金 = 总投资 × (1 - 资本金比例) |
| 债务条款 | 贷款期限（年）、利率（LPR/固定）、宽限期、还款安排 | 还款方式：等额/递增/气球型 |
| 发电/运营 | 装机规模、年设计发电量或上网电量 | 风电/光伏用MWh，管网用亿方 |
| 电价/运价 | 上网电价（含税/不含税）或管输费率 | 注意含税/不含税区分 |
| 运营成本 | OPEX分项（维修/人工/保险/土地租金）、大修CAPEX | 区分保内/保外、不同年段 |
| 税率优惠 | 所得税优惠（三免三减半/高新15%/西部大开发）、增值税率 | 风电/光伏：增值税9% |
| 达产率 | 年综合折减系数（不含尾流的综合折减） | 风电一般90%-96%，光伏略高 |

**1C — 常见单位陷阱**

```
⚠️ MWh → kWh 换算：年上网电量通常用 MWh，电价通常用 元/kWh
   收入(万元) = 年上网电量(MWh) × 达产率 × 电价(元/kWh) × 1000(kWh/MWh) / 10000(元→万元)
   
⚠️ 不要写成：年上网电量(MWh) × 达产率 × 电价(元/kWh) / 10000  ← 少算1000倍！

⚠️ 含税/不含税区分：
   - CFADS测算用含税收入（实际收到的钱）
   - 所得税测算用不含税收入作为收入基数
   - 不含税价 = 含税价 / (1 + 增值税率)
```

---

### 第2步：实例化 DebtFacility（债务测算类）

**基础类已定义在** `D:\Workbuddy\debt_cashflow_model.py`，使用时直接 import：

```python
import sys
sys.path.insert(0, r"D:\Workbuddy")
from debt_cashflow_model import DebtFacility, ProjectAsset
```

**实例化模板：**

```python
# 参数说明：
# principal   = 贷款本金（万元）
# annual_rate = 年化利率，小数形式（如 0.0345 = 3.45%）
# total_years = 贷款总期限（年），含宽限期
# grace_years = 宽限期年数（建设期，期间只付息不还本）

facility = DebtFacility(
    principal   = 45_780.0,   # 万元
    annual_rate = 0.0345,     # LPR 3.45%
    total_years = 13,         # 13年
    grace_years = 1,          # 建设期宽限1年
)

# 还本曲线：等额还本示例（12年×3815万=45780万）
REPAY_YEARS = 12
custom_schedule = [3_815.0] * REPAY_YEARS  # 等额

# 非标还本示例（递增型）
# custom_schedule = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5000, 5000, 5000, 3640, 2640]

# 验证合计
assert abs(sum(custom_schedule) - facility.principal) < 0.1

# 链式调用：设置宽限期 → 注入还本曲线 → 生成排期
facility.set_grace_period(1).set_custom_repayment(custom_schedule)
debt_rows = facility.generate_schedule()
repay_rows = debt_rows[1:]  # 跳过宽限期行，仅取还款期
```

**还本曲线类型参考：**

| 还款类型 | 适用项目 | 构造方式 |
|---------|---------|---------|
| 等额本金 | 稳定现金流（管网稳定期） | `[本金/年数] * 年数` |
| 前低后高递增型 | 爬坡期项目（管网建设初期） | 手动构造递增数列，合计=本金 |
| 气球式（Balloon） | 并购贷款/再融资预期明确 | `[小额]*n + [大额尾款]` |
| 半年还本（转年） | 银行实际还款安排 | `[半年额×2] * 还本年数` |

---

### 第3步：实例化 ProjectAsset（收入/CFADS测算类）

**逐年差异化税率处理模板（三免三减半）：**

```python
# 当税率逐年不同时，逐年独立实例化 ProjectAsset
cfads_list = []
for i in range(OPERATION_YEARS):
    single_year = ProjectAsset(
        project_name        = f"项目名-第{i+1}年",
        operation_years     = 1,
        revenue_streams     = {"核心收入": [annual_income_by_year[i]]},
        core_revenue_keys   = ["核心收入"],
        opex_annual         = [opex_by_year[i]],
        tax_rate_on_revenue = tax_rates_by_year[i],  # 逐年税率
        capex_maintenance   = [capex_by_year[i]],
    )
    row = single_year.calc_cfads()[0]
    row["year"] = i + 1
    cfads_list.append(row)
```

**收入剥离模板（管网/多元收入项目）：**

```python
revenue_streams = {
    # 核心主营：纳入偿债测算基数
    "管道运输收入": [8400, 9600, 10800, 11400, 11400, 11400, 11400, 11400],
    
    # 以下均被剥离（不在 core_revenue_keys 中）
    "增值服务收入": [200, 250, 300, 320, 320, 320, 320, 320],  # 次要业务
    "政府补贴":     [500, 500, 0,   0,   0,   0,   0,   0  ],  # 非经常性
}
core_revenue_keys = ["管道运输收入"]  # 只取这一项
```

**OPEX 成本构建模板：**

```python
# 分项列示，便于审查追溯
maintenance = [100, 100, 100, 100, 300, 300, 400, 400, 500, 500, 500, 500]
other_cost  = [100, 100, 100, 100, 200, 200, 250, 250, 300, 300, 300, 300]
land_rent   = 18    # 万元/年（固定）
labor       = 200   # 万元/年
insurance   = 140   # 万元/年

opex_annual = [
    round(maintenance[i] + other_cost[i] + land_rent + labor + insurance, 2)
    for i in range(OPERATION_YEARS)
]
```

---

### 第4步：计算 DSCR 并输出

```python
import pandas as pd

DSCR_COVENANT = 1.20  # 警戒线
records = []
for cfads_row, debt_row in zip(cfads_list, repay_rows):
    cfads    = cfads_row["cfads"]
    total_ds = debt_row.total_ds
    dscr     = round(cfads / total_ds, 2) if total_ds > 0 else float("inf")
    
    if dscr >= 1.50:
        status = "✅ 充裕"
    elif dscr >= DSCR_COVENANT:
        status = "🟡 合格"
    else:
        status = "🔴 预警"
    
    records.append({
        "运营年份": f"第{cfads_row['year']:02d}年",
        "CFADS（万元）": cfads,
        "期初余额": debt_row.period_opening,
        "当期还本": debt_row.principal_repay,
        "当期付息": debt_row.interest_charge,
        "偿债合计": total_ds,
        "期末余额": debt_row.period_closing,
        "DSCR": dscr,
        "状态": status,
    })

df = pd.DataFrame(records)
print(df.to_string(index=False))

# 统计摘要
min_dscr = df["DSCR"].min()
avg_dscr = df["DSCR"].mean()
below    = df[df["DSCR"] < DSCR_COVENANT]
print(f"\nDSCR：最低 {min_dscr:.2f}x，平均 {avg_dscr:.2f}x，警戒线 ≥{DSCR_COVENANT}x")
if below.empty:
    print("✅ 全部年份DSCR达标")
else:
    print(f"⚠️ {len(below)}个年份DSCR低于警戒线：{', '.join(below['运营年份'].tolist())}")
```

---

### 第5步：生成带公式的 Excel 模型

**以** `D:\Workbuddy\build_excel_model.py` **为蓝本修改**，4个Sheet结构：

| Sheet名 | 内容 | 关键设计 |
|--------|------|---------|
| 假设参数 | 所有硬编码输入（蓝色单元格） | 含税收入公式需加×1000换算（MWh→kWh） |
| CFADS现金流瀑布 | 核心收入→OPEX→税费→CAPEX→CFADS | 公式引用假设参数Sheet，逐列12年 |
| 债务偿还排期 | 期初余额→还本→利息→期末余额 | 宽限期行还本=0，利息=期初×利率 |
| DSCR综合测算 | CFADS÷偿债合计=DSCR | IF嵌套显示状态，最低/平均汇总区 |

**颜色编码规则：**
- 蓝色字体：可修改的硬编码输入参数（仅「假设参数」Sheet 中直接写入数值的单元格）
- 黑色字体：由公式计算的结果（**严禁直接写数值**）
- 黄色底色：关键假设单元格（标识修改高敏区域）

---

#### ⚠️ CRITICAL：Excel 公式完整性强制规范

**所有计算单元格必须写 Excel 公式，禁止将 Python 计算结果硬编码为数值写入。**

具体要求如下：

**① 假设参数 Sheet（唯一允许写硬编码数值的 Sheet）**

```python
# 只有这一层写死数字，后续所有Sheet全部用公式引用此Sheet
ws_param["B10"] = 45780.0       # 贷款本金（万元）—— 蓝色字体
ws_param["E10"] = 0.0345        # 年利率 —— 蓝色字体
ws_param["B16"] = 243569.5      # 年上网电量（MWh）—— 蓝色字体
ws_param["B17"] = 0.96          # 达产率 —— 蓝色字体
ws_param["B18"] = 0.265         # 含税电价（元/kWh）—— 蓝色字体

# 年核心收入：假设参数Sheet内部也用公式，不写死计算结果
ws_param["B20"] = "=B16*B17*B18*1000/10000"  # 年上网收入（万元），MWh×1000→kWh
```

**② CFADS现金流瀑布 Sheet（全部公式，无硬编码数值）**

```python
# 每列代表一个运营年度（B列=第1年，C列=第2年，...）
# 行1：年份标题（文本，可写死）
# 行2：OPEX  —— 从假设参数读取，或写计算公式
# 行3：税率  —— 从假设参数读取
# 行4：核心收入（引用假设参数，固定值年份可直接引用）
ws_cfads["B4"] = "=假设参数!$B$20"              # 核心收入：引用假设参数
ws_cfads["B5"] = "=假设参数!$B$37"              # OPEX：引用假设参数中对应年段OPEX
ws_cfads["B6"] = "=B4/(1+假设参数!$B$27)*假设参数!$B$27*1.12+MAX(B4/1.09-B5-假设参数!$E$37,0)*假设参数!$B$29"
                                                 # 税费：增值税+附加+所得税（公式）
ws_cfads["B7"] = "=假设参数!$B$43"              # 大修CAPEX：引用假设参数
ws_cfads["B8"] = "=B4-B5-B6-B7"                # CFADS = 收入 - OPEX - 税费 - CAPEX

# 后续列（C、D...）用相对引用自动偏移，避免逐列手写
# OPEX/CAPEX 如有分年段差异，在假设参数Sheet建辅助行，用INDEX/CHOOSE引用
```

**③ 债务偿还排期 Sheet（全部公式，期初余额用滚动引用）**

```python
# 宽限期行（Y01）
ws_debt["C3"] = "=假设参数!$B$10"               # 期初余额=贷款本金
ws_debt["D3"] = "=0"                             # 宽限期还本=0（公式形式，勿写数字0）
ws_debt["E3"] = "=C3*假设参数!$E$10"             # 利息=期初余额×年利率
ws_debt["F3"] = "=D3+E3"                         # 偿债合计=还本+利息
ws_debt["G3"] = "=C3-D3"                         # 期末余额=期初-还本

# 还款期各行（Y02起，用滚动公式，期初余额引用上一行期末余额）
# 第4行起：期初余额=上一行期末余额
ws_debt["C4"] = "=G3"                            # 期初余额←上行期末余额（滚动）
ws_debt["D4"] = "=假设参数!$D$53"                # 还本额←假设参数中当年还本列
ws_debt["E4"] = "=C4*假设参数!$E$10"             # 利息=期初余额×年利率
ws_debt["F4"] = "=D4+E4"
ws_debt["G4"] = "=C4-D4"
# 后续行：C列公式 =G上一行，其余列公式相同（相对引用自动偏移）
```

**④ DSCR综合测算 Sheet（全部公式，跨Sheet引用）**

```python
# 跨Sheet引用，修改假设参数后自动重算
ws_dscr["B3"] = "=债务偿还排期!C4"              # 期初余额（运营第1年=排期Y02行）
ws_dscr["C3"] = "=CFADS现金流瀑布!B8"           # CFADS
ws_dscr["D3"] = "=债务偿还排期!D4"              # 当期还本
ws_dscr["E3"] = "=债务偿还排期!E4"              # 当期利息
ws_dscr["F3"] = "=债务偿还排期!F4"              # 偿债合计
ws_dscr["G3"] = "=债务偿还排期!G4"              # 期末余额
ws_dscr["H3"] = "=C3/F3"                        # DSCR = CFADS / 偿债合计
ws_dscr["I3"] = '=IF(H3>=1.5,"充裕",IF(H3>=1.2,"合格","预警"))'  # 状态（纯文字，勿用emoji避免文件损坏）

# 汇总区（置于数据区下方，用MIN/AVERAGE/COUNTIF函数）
ws_dscr["C17"] = "=MIN(H3:H14)"                 # 最低DSCR
ws_dscr["C18"] = "=AVERAGE(H3:H14)"             # 平均DSCR
ws_dscr["C19"] = '=COUNTIF(H3:H14,"<1.2")'      # 预警年数
```

**⑤ 还本曲线辅助行（假设参数Sheet中建辅助区，供债务排期引用）**

```python
# 在假设参数Sheet建还本曲线辅助行，每个年度还本额单独一列
# 例：D53=第1还款年还本，E53=第2还款年还本，...
# 这样债务排期中的还本额可用 =INDEX(假设参数!$D$53:$O$53,1,当前列序号) 引用
# 切勿把 Python 计算出的每年还本数字直接写死进排期Sheet
repayment_row = 53   # 假设参数Sheet中的还本曲线辅助行
for col_idx, repay in enumerate(custom_repayment, start=4):  # D列起
    cell = ws_param.cell(row=repayment_row, column=col_idx)
    cell.value = repay   # 这里写数字：这是假设参数，允许硬编码
    cell.font = Font(color="0000FF")  # 蓝色字体标识可改
```

**⑥ 禁止事项（违反则 Excel 失去财务模型价值）**

```
❌ 禁止：ws_cfads["B8"] = 5111.72      ← Python算好的CFADS直接贴入，修改参数不重算
❌ 禁止：ws_debt["E4"]  = 1579.41      ← 利息数值写死，利率变更后不联动
❌ 禁止：ws_dscr["H3"]  = 0.95         ← DSCR写死，完全失去公式驱动意义

✅ 正确：ws_cfads["B8"] = "=B4-B5-B6-B7"        ← 公式
✅ 正确：ws_debt["E4"]  = "=C4*假设参数!$E$10"  ← 公式引用利率参数
✅ 正确：ws_dscr["H3"]  = "=C3/F3"              ← 公式
```

**⑦ openpyxl 代码级避坑规范（基于实战5轮修复）**

以下陷阱均来自实际项目反复调试中发现的 openpyxl 行为与 Excel/WPS 渲染器之间的差异，全是血泪教训。

---

#### 陷阱1：跨表引用公式值缺少 `=` 前缀 → Excel 当成纯文本

```
❌ 错误：cell.value = "'假设参数'!B21"
   结果：Excel 中显示为纯文本字符串，无法计算

✅ 正确：cell.value = "='假设参数'!B21"
   结果：Excel 识别为公式，自动计算
```

**规范做法**：定义两套辅助函数，分场景使用：
```python
def asm_ref(col_letter, row_num):
    """返回可嵌入大公式的引用片段（不含前置=，供 f-string 拼接）"""
    return f"'{SHEET_NAME}'!{col_letter}{row_num}"

def asm_ref_eq(col_letter, row_num):
    """返回带 = 的完整跨表公式（直接作为单元格值）"""
    return f"='{SHEET_NAME}'!{col_letter}{row_num}"

# 场景A：直接作单元格值 → 用 asm_ref_eq
cell.value = asm_ref_eq("B", 21)  # ='假设参数'!B21 ✓

# 场景B：嵌入大型公式 → 用 asm_ref
cell.value = f"={asm_ref('B',21)}/2+100"  # ='假设参数'!B21/2+100 ✓
```

**规则**：凡 final value string 不以 `=` 开头 → Excel 当文本。凡以 `=` 开头 → 公式。

---

#### 陷阱2：merge_cells 后对非首单元格写属性 → WPS 渲染乱码

```
❌ 错误：
ws.merge_cells("A1:J1")
set_cell(ws, 1, 1, "标题", ...)
for cc in range(2, 11):
    ws.cell(row=1, column=cc).border = thin_border()  # 对已合并的非首单元格写border
    ws.cell(row=1, column=cc).fill   = hdr_fill()     # 对已合并的非首单元格写fill
→ WPS/部分Excel版本中渲染异常，Sheet内容显示为空白或乱码
```

**根本原因**：openpyxl 在合并区域的非首单元格上单独设置 `border`/`fill` 等属性，某些 Excel 渲染器（尤其是 WPS）无法正确处理这些 "幽灵" 属性，导致整个 Sheet 渲染崩溃。

```
✅ 正确做法：
ws.merge_cells("A1:J1")
cell = ws.cell(row=1, column=1)
cell.value = "标题"
cell.font = title_font
cell.fill = hdr_fill
cell.alignment = center_alignment
cell.border = thin_border
# 仅设置首单元格的所有属性，不对 A1:J1 中其他单元格做任何操作
```

**适用范围**：所有 `merge_cells` 调用点，包括：
- Sheet 主标题行（`merge_title`）
- Section 分段标题（`section_hdr`）
- 各 Sheet 顶部合并标题行

**检查方法**：代码中搜索 `merge_cells`，确保紧随其后的 for 循环不会对已合并区域的非首单元格（col ≥ start_col+1 或 row ≥ start_row+1）写属性。

---

#### 陷阱3：跨Sheet引用的行号对应错误

当多个Sheet的同一"行号"代表不同含义时，跨Sheet公式必须准确定位目标Sheet的行号：

```
❌ 错误（敏感性分析Sheet→DSCR Sheet的CFADS引用）：
   ws_sens.cell(row=28, column=7).value = f"='DSCR综合测算'!C{row}"
   # row=28 是敏感性分析表当前行，但 DSCR 表第28行是空行！
   # DSCR 数据在 Row3-Row10（第01年→Row3, 第08年→Row10）

✅ 正确：明确映射
   dscr_data_row = op_yr + 2  # DSCR表：第1年=Row3, 第2年=Row4, ...
   ws_sens.cell(row=28, column=7).value = f"='DSCR综合测算'!C{dscr_data_row}"
```

**规范**：任何跨Sheet公式引用，必须在注释中标注目标Sheet的数据起始行号：
```python
# DSCR表：列标题Row2，数据从Row3开始（Y03运营第1年）
dscr_row = op_yr + 2  # op_yr=1 → Row3
```

---

#### 陷阱4：年份表头"合计"列标签错误

双行年份表头（Row1: Y03-Y07, Row2: Y08-Y10 + 空 + 合计）如果逻辑不严谨，J列容易被覆盖为错误值：

```
❌ 错误：
  labels_odd = ["科目", "Y03", "Y04", "Y05", "Y06", "Y07"]
  set_cell(ws, r1, end_col, labels_odd[-1], ...)
  # labels_odd[-1] = "Y07" → J列显示 "Y07" 而非 "合计"

✅ 正确：
  set_cell(ws, r1, end_col, "合计", ...)
  # 合计列始终写死"合计"，不依赖列表最后一个元素
```

---

#### 陷阱5：write_kv_row / write_year_data_row 遗漏 A 列标签

```
❌ 错误：set_cell仅写入B列（值）和C列（备注），未写A列标签
   结果：Excel中A列空白，整行看起来像是"无标签的裸数值"

✅ 正确：函数第一行必须写 set_cell(ws, row, 1, label, ...)
```

**通用函数模板**：
```python
def write_kv_row(ws, row, label, value, note="", fmt=None):
    """所有行：A列=标签（必写），B列=值，C列=备注"""
    set_cell(ws, row, 1, label, font=label_font, align=left_align, border=thin_border)
    set_cell(ws, row, 2, value, font=value_font, align=right_align, border=thin_border, fmt=fmt)
    set_cell(ws, row, 3, note,  font=note_font,  align=left_align,  border=thin_border)
```

---

#### 陷阱6：write_year_data_row 中数值 0 被跳过

```
❌ 错误：set_cell 中对 value==0 做了条件判断导致跳过
   结果：0值单元格为空，公式 SUM/引用可能出错

✅ 正确：c.value = val 直接赋值，0 也是有效数据
```

---

#### 陷阱7：增值税进项税公式用含税额而非不含税额

```
❌ 错误：进项税 = 含税材料额   →  -B4
✅ 正确：进项税 = 含税材料额/(1+税率)*税率  →  -B4/(1+0.13)*0.13
```

**标准增值税公式模板**：
```
增值税 = 销项 - 进项
      = 含税收入/(1+税率)*税率 - 含税材料/(1+税率)*税率
      = (含税收入 - 含税材料) / (1+税率) * 税率
```

**EBIT 完整公式模板**：
```
EBIT = 不含税收入 - 不含税变动成本 - 其他费用 - 修理费 - 折旧摊销
     = 含税收入/(1+增值税率) 
       - (原辅材料+人工成本)/(1+增值税率)
       - 其他费用 - 修理费 - 折旧摊销
     
⚠️ 五项缺一不可：其他费用(收入×费率)、修理费(固定)、折旧摊销(非付现)
```

---

#### 陷阱完整性检查清单

生成 Excel 后，必须逐项过检：

```
□ 所有跨表引用公式以 = 开头（asm_ref 调用点逐一检查）
□ 所有 merge_cells 后无对非首单元格的单独属性写入
□ 所有跨Sheet引用行号正确（源Sheet数据从第几行开始？）
□ 年份表头 J 列 = "合计"（不是某个年份标签）
□ 所有数据行的 A 列标签完整无缺失
□ 所有 0 值单元格均有数值（非空白）
□ EBIT 公式含全部五项：收入不含税、变动成本不含税、其他费用、修理费、折旧摊销
□ 增值税 = (含税收入-含税材料)/(1+税率)*税率（不是含税额直接相减）
□ 还本合计 = SUM(还本列) = 贷款本金（±0.01 万容差）
```

---

### 第6步：审查意见输出规范

完成测算后，必须输出以下结构化审查意见：

**①数据核验**
- 还款曲线合计是否等于贷款本金（误差 < 0.01万）
- 文件中建设期利息与模型计算值是否一致（差异来源：分批放款 vs 全额提用假设）

**②DSCR合规分析**
- 最低DSCR / 平均DSCR / 是否全年高于警戒线（1.20x）
- DSCR最低年份的原因（OPEX增加/大修CAPEX/收入下滑）

**③压力测试建议**
- 核心变量敏感性：电价↓5%/达产率↓5%/利率上浮50bp/OPEX增加10% 对DSCR的影响
- 建议关注点：延长期限/增加资本金/差额补足措施

**④收入口径说明**
- 已剥离哪些收入来源及剥离理由
- 核心收入认定依据（合同支撑/电网协议/核准文件）

---

## 行业参数参考库

### 风电项目

| 参数 | 典型值范围 | 说明 |
|------|-----------|------|
| 综合折减系数（不含尾流） | 90%~96% | 陕西/内蒙古弃风率低的地区可取95%~96% |
| 增值税率 | 9% | 售电收入适用税率 |
| 税负综合率（三免三减半期） | 8.5% / 10.5% / 12.5% | 一免段/减半段/正常段 |
| 维修费（保内） | 100~150万/年 | 厂商包修期（通常前5年） |
| 维修费（保外） | 300~600万/年 | 保外逐年递增 |
| 保险费 | 总资产×0.2%~0.3% | |
| 大检修CAPEX（保外） | 500~800万/次 | 每5~8年一次叶片/主轴/齿轮箱大修 |
| DSCR警戒线 | 1.20x | 银行固定资产贷款合同标准 |
| DSCR舒适线 | 1.50x | 优质项目评级标准 |

### 管网/基建项目

| 参数 | 典型值范围 | 说明 |
|------|-----------|------|
| 综合税负率 | 13%~17% | 增值税9%+附加+所得税 |
| 利用率爬坡期 | 2~3年 | 第1年60%~70%，第3年达稳定 |
| 稳定期利用率 | 85%~95% | 取决于管线战略地位 |
| OPEX增长率 | 3%~5%/年 | 通胀+人工成本上升 |

### 光伏项目

| 参数 | 典型值范围 | 说明 |
|------|-----------|------|
| 综合折减系数 | 78%~85% | 含直流侧衰减+逆变器效率+线损等 |
| 增值税率 | 9% | 与风电相同 |
| 组件衰减率 | 0.5%~0.7%/年 | 单晶硅第一年2.5%，后续0.5%/年 |

---

## 常见报错与解决方案

### 报错1：还款曲线合计校验失败

```
AssertionError: 还款计划合计 45800 ≠ 本金 45780
```

**原因**：尾款计算错误，通常出现在气球式还款时末期尾款计算有误。

**解决**：
```python
# 手动计算尾款
regular_sum = sum(custom_schedule[:-1])
custom_schedule[-1] = round(PRINCIPAL - regular_sum, 2)  # 精确到分
```

### 报错2：MWh单位导致收入偏低

**症状**：年收入算出来只有几万元而非几千万。

**检查**：
```python
# 确认公式中有 × 1000
annual_income = MWh × factor × price_per_kwh × 1000 / 10000
```

### 报错3：tax_rate_on_revenue 与实际税负不一致

**原因**：增值税是价外税，应先除以(1+税率)再计算增值税额，简化处理可能有偏差。

**解决（精确法）**：
```python
VAT_RATE = 0.09
vat = round(core_revenue / (1 + VAT_RATE) * VAT_RATE * 1.12, 2)  # 含城建教育附加12%
income_tax = round(max(ebitda_approx - depreciation - interest, 0) * effective_cit_rate, 2)
taxes = vat + income_tax
```

### 报错4：Excel文件打开提示"发现不可读取内容"

**原因**：openpyxl写入某些特殊字符（如emoji表情）时可能损坏文件。

**解决**：
```python
# 状态列改用纯文字，不用emoji
status = "达标" if dscr >= 1.2 else "预警"
```

---

## 文件交付标准

每次测算完成后，交付物应包含：

1. **Python脚本** — `{项目名}_case.py`，完整参数注释，可独立运行
2. **Excel模型** — `{项目名}_dscr_model.xlsx`，4个Sheet，带公式
3. **控制台输出截图或文字结果** — DSCR汇总表 + 审查意见

交付代码：
```python
from deliver_attachments import deliver_attachments
deliver_attachments([
    r"D:\Workbuddy\{项目名}_case.py",
    r"D:\Workbuddy\{项目名}_dscr_model.xlsx",
])
```

---

## 项目类型快速适配指南

### 切换到光伏项目

```python
# 修改项
ANNUAL_GENERATION_MWH = 装机MW × 年利用小时h  # 例如50MW × 1200h = 60000 MWh
CAPACITY_FACTOR = 0.80  # 光伏综合折减约80%（含组件衰减）
ON_GRID_PRICE_TAX_INCL = 0.35  # 当地含税电价（元/kWh），集中式光伏参考上网电价

# 收入逐年递减（组件衰减）
annual_income_list = [
    round(ANNUAL_GENERATION_MWH * (1 - 0.025 - 0.005*i) * CAPACITY_FACTOR * ON_GRID_PRICE_TAX_INCL * 1000 / 10000, 2)
    for i in range(OPERATION_YEARS)
]
```

### 切换到管网/基建项目

```python
# 收入口径
revenue_streams = {
    "管道运输收入": [yr_volume_bcm * unit_fee_per_bcm for yr_volume_bcm in volumes],  # 亿方×费率
    "增值服务收入": [200, 250, 300, ...],  # 剥离
    "政府补贴":    [500, 500, 0, ...],   # 剥离
}
core_revenue_keys = ["管道运输收入"]

# 税率（管网适用）
TAX_RATE = 0.15  # 增值税9% + 城建附加 + 所得税（统一税负率）
```

### 切换到并购贷款

```python
# 目标公司EBITDA替换发电收入
ebitda_projection = [5000, 5500, 6000, 6500, 7000]  # 万元/年
revenue_streams = {"EBITDA": ebitda_projection}
core_revenue_keys = ["EBITDA"]
# OPEX = 0（EBITDA已扣减），税率单独处理
opex_annual = [0] * OPERATION_YEARS
TAX_RATE = 0.0  # 已内含在EBITDA中
```

---

## work-analysis-loop 集成说明（v1.2.0 新增）

本 Skill 从 v1.2.0 起在 **`work-analysis-loop` 护栏**下执行，具体映射：

| 执行阶段 | 对应 Loop Round | 停止条件 |
|---------|---------------|---------|
| 第一阶段：参数提取（读取项目文档） | Round 1-2 | 关键参数缺失且用户无法提供 |
| 第二阶段：DebtFacility 债务建模 | Round 3 | 还款计划不明确、资本金比例未知 |
| 第三阶段：ProjectAsset 现金流建模 | Round 4-5 | 收入/OPEX/税率任一主参数无法确定 |
| 第四阶段：DSCR 计算与验证 | Round 6 | DSCR 计算结果出现异常（<0.8 或 >3.0）需人工确认假设 |
| 第五阶段：敏感性分析 | Round 7 | — |
| 第六阶段：Excel 交付 | Round 8 | 用户确认无需进一步迭代 |

### 数据层级标注规范（强制）

所有建模参数必须按以下层级标注：

| 层级 | 标注格式 | 适用范围 |
|------|---------|---------|
| `[事实]` | 直接引用评估报告/文档原文数字 | 项目总投资额、建设期、还款计划 |
| `[抽数]` | 从文档提取后结构化 | 逐年收入/成本/OPEX 数据 |
| `[计算]` | DSCR、利息保障倍数等 | 所有模型输出指标 |
| `[假设]` | 参数缺失时的替代值 | 单位费率、上网小时数、EBITDA 替代收入 |
| `[推断]` | 对结果的分析 | 偿债压力判断、敏感性结论 |
| `[观点]` | 风险判断 | 授信风险评估（谨慎使用）|

### 缺失参数强制规则

- **绝对禁止**：将缺失参数当作 0，用"默认值"或"经验值"替代后不注明
- 缺失参数必须标注：`[假设：原因（如"评估报告未提供，按行业均值替代"）]`
- 敏感性分析必须覆盖缺失参数的可能范围（±20% 区间）
- 超过 3 个关键参数为假设时，在模型中显著标注 **⚠️ 高不确定度**

### 与 credit-review-workbench 的双向路由

- **上行**：被 `credit-review-workbench` 调用时自动进入 work-analysis-loop 六元迭代
- **下行**：独立使用时，入口输出任务卡（参照 work-analysis-loop 快速启动模板），列出拟分解步骤
- **交接**：完成后生成交接摘要，包含：模型文件路径 + 关键假设清单 + DSCR 关键节点 + 遗留问题

---

## Trigger（触发条件）

以下情况**必须触发**本 Skill：


| 编号 | 触发条件 | 优先级 |
|------|---------|---------|
| T1 | 用户说出"项目融资模型"/"现金流测算"/"DSCR" | P0 |
| T2 | 用户上传了项目评估文档（docx/xlsx） | P0 |
| T3 | 用户说"偿债现金流"/"还款来源分析" | P1 |
| T4 | 用户说"敏感性分析"/"情景分析" | P1 |

排除条件：
- E1: 未指定项目 → 先询问
- E2: 说"估值分析"→ 触发企业估值分析Skill

触发后动作：
1. 识别任务类型、企业/项目/行业、交付物要求
2. 输出任务卡（参考 `work-analysis-loop` 的「快速启动模板」）
3. 请用户确认任务分解
4. 用户确认后，创建 `.state.json`，开始第一轮执行

---

## State 持久化（断点恢复）

每轮执行结束后，必须将状态写入工作区 `.state.json`，支持中断恢复。

### 写入时机

| 时机 | 说明 |
|------|------|
| 每轮 Round 结束后 | 验证完成、状态已更新 → 写入 |
| 人工决策后 | 用户确认后立即写入 |
| 触发停止条件时 | 写入最终状态 → 生成 Handoff |

### 读取恢复逻辑

启动 Skill 时：
```
  if .state.json 存在：
    → 读取 state，检查 updated_at
    → 输出："检测到未完成任务，是否继续？"
    → 用户确认 → 从 state.current_step 或 stages_pending[0] 继续执行
    → 用户拒绝 → 备份 .state.json 为 .state.json.archived，从头开始
  else：
    → 从头开始，生成新 task_id
```

### State Schema

使用统一 State Schema（参见 `loop-engineering` 的 `references/state-schema.json`）。


### State 字段（本 Skill 特定扩展）

| 字段 | 类型 | 说明 |
|-------|------|------|
| `current_sheet` | string | 当前正在生成的Excel Sheet名 |
| `current_row` | int | 当前正在写入的行号 |
| `excel_path` | string | 已生成的Excel文件路径 |
| `dscr_results` | object | DSCR计算结果缓存 |
| `sensitivity_done` | bool | 敏感性分析是否完成 |

### 写入原子性

写入序列：
  1. 将 State 写入 `.state.json.tmp`
  2. `os.replace('.state.json.tmp', '.state.json')`
  3. 确保写入成功（fsync）

---

## Handoff 格式（停止时生成）

每次触发停止条件（S1-S7）时，必须生成两个文件：

### 1. `.handoff.json`（机器可读）

结构参见 `loop-engineering` Skill 的 Handoff 格式说明。

关键字段：
- `handoff_id`：格式 `HO-MMDD-XXX`
- `stop_reason`：停止原因（S1-S7）
- `state_snapshot`：当前状态快照
- `deliverables`：交付物清单（路径 + 状态）
- `evidence_summary`：证据概况
- `open_issues`：未解决问题列表
- `next_steps`：后续步骤建议

### 2. `HANDOFF.md`（人类可读）

包含：
- 交接ID、时间、停止原因
- 当前状态（阶段、迭代轮次、完成度）
- 交付物清单（表格形式）
- 证据概况（来源数、证据条数、完整度）
- 未解决问题（带建议）
- 后续步骤

### 交接后动作

| 停止原因 | 动作 |
|---------|------|
| S1（完成） | 归档 .state.json，保留 .handoff.json |
| S2/S3/S4/S5 | 保留 .state.json（可恢复），生成 .handoff.json |
| S6（破坏性操作） | 不执行，等待用户显式确认 |
| S7（用户主动停止） | 保留 .state.json（可恢复） |


---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0.0 | 2026-05-28 | 初始版本。基于子洲县10万千瓦风电项目实跑案例验证，包含DebtFacility+ProjectAsset核心类、Excel4-Sheet模板、MWh换算修正说明、三免三减半税率处理 |
| v1.1.0 | 2026-05-29 | **新增 openpyxl 代码级避坑规范**。基于空天发动机零组件项目5轮修复实战经验，补充7大陷阱：跨表引用缺=号、merge_cells非首单元格属性冲突(WPS乱码)、跨Sheet行号对应错误、年份表头合计列、A列标签缺失、零值跳过、增值税/EBIT公式缺陷。附完整性检查清单。 |
| v1.2.0 | 2026-06-28 | **护栏集成**：①新增 work-analysis-loop 护栏集成映射表（三阶段→8 Round）；②新增数据层级标注规范（六层分级强制要求）；③缺失参数强制规则（假设必须注明理由、敏感性覆盖）；④与 credit-review-workbench 建立双向路由关系 |
