---
name: "企业估值分析"
description: >
  企业估值分析 Skill —— 采用 DCF（现金流折现）、相对估值（同行市盈率/EV倍数）和 SOTP（分部加总）三法交叉验证，
  输出隐含股价、WACC×增长率敏感性矩阵、Bull/Base/Bear 情景分析。
  专为银行授信审批场景优化：估值结果直接服务于企业偿债能力评估、抵押物价值判断、持续经营假设验证。
  触发条件：用户提到"估值分析"、"DCF估值"、"企业价值"、"公允价值"、"XX值多少钱"、"这家公司值多少"、"估值建模"、
  "相对估值"、"市盈率对比"、"EV/EBITDA"、"WACC"、"敏感性分析"、"现金流折现"等。
agent_created: true
version: "1.0.0"
---

# 企业估值分析 Skill

## 概述

采用三种估值方法对企业进行交叉验证估值，辅助授信审批中的企业价值判断：

1. **DCF（现金流折现）** — 5年FCFF预测 + 终值 + WACC折现 → 企业内在价值
2. **相对估值** — 同行PE/EV Revenue/EV EBITDA倍数中位数 → 市场参照价值
3. **SOTP（分部加总）** — 多业务分部各自对标纯主业同行 → 分部价值加总

授信审批场景中，估值结果用于：
- **偿债能力基准**：企业价值能否覆盖有息负债
- **抵押物价值参考**：股权价值是否提供足够安全垫
- **持续经营判断**：DCF是否支持企业正常经营假设
- **压力测试输入**：敏感性分析揭示关键风险变量

**免责声明**：输出为研究/教育目的，不构成投资建议。数据来源 yfinance，与官方披露可能存在差异。

---

## 依赖环境

使用系统 Python 3.14 虚拟环境（托管 Python 3.13 存在 numpy 代码签名兼容性问题）。

```bash
# 首次使用前安装依赖（创建于当前工作区 .venv）
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install yfinance numpy pandas -q
```

运行时使用：
```bash
.venv/bin/python3 -c "..."
```

---

## 数据获取

使用 yfinance 获取财务数据。以下为完整数据获取代码模板：

```python
import yfinance as yf
import numpy as np
import pandas as pd

TICKER = "AAPL"  # 替换为目标股票代码（A股加后缀 .SZ/.SS，港股加 .HK）

t = yf.Ticker(TICKER)

# 基本信息
info       = t.info
price      = info.get("currentPrice") or info.get("regularMarketPrice")
market_cap = info.get("marketCap")
shares_out = info.get("sharesOutstanding")
total_debt = info.get("totalDebt") or 0
cash       = info.get("totalCash") or 0
beta_raw   = info.get("beta") or None
sector     = info.get("sector", "Unknown")
industry   = info.get("industry", "Unknown")

# 三大报表 — 年度
income_a   = t.income_stmt      # 利润表（年度）
cashflow_a = t.cashflow          # 现金流量表（年度）
balance_a  = t.balance_sheet     # 资产负债表（年度）

# 三大报表 — 季度
income_q   = t.quarterly_income_stmt
cashflow_q = t.quarterly_cashflow

# 分析师预测
earnings_est = t.earnings_estimate  # EPS预测
revenue_est  = t.revenue_estimate   # 收入预测

print(f"✓ {TICKER} 数据获取完成 | 市值: {market_cap/1e9 if market_cap else 0:.1f}B | 最新价: {price}")
```

**关键财务科目名称**（yfinance 标签）：

| 需求 | yfinance Row Name |
|------|------------------|
| 营业收入 | `Total Revenue` |
| 营业利润/EBIT | `Operating Income` |
| 净利润 | `Net Income` |
| 折旧与摊销 | `Depreciation And Amortization`（现金流量表） |
| 资本性支出 | `Capital Expenditure`（现金流量表，通常为负值） |
| 营运资本变动 | `Change In Working Capital`（现金流量表） |
| 股权激励 | `Stock Based Compensation`（现金流量表） |
| 稀释EPS | `Diluted EPS`（利润表） |

**港股/A股注意**：yfinance 对部分港股/A股财务数据支持有限。如数据缺失，使用 `企业公开信息抓取` skill 获取年报PDF后提取，或用户手动提供关键财务数据。

---

## Step 1：设定估值参数

### 1.1 默认参数表

每个参数在计算前**必须**有值。以下为默认值，用户可覆盖：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| 预测期 | 5年 | 标准显式预测窗口 |
| 终值永续增长率 `g` | 2.5%（美国）/ 3.5%（中国） | 不超过长期名义GDP |
| 无风险利率 `rf` | 从 ^TNX 实时获取，失败则 4.5% | 10年期国债收益率 |
| 权益风险溢价 `erp` | 5.5%（美国）/ 7.5%（中国） | Damodaran中位值 |
| Beta | `info['beta']`，失败则用行业默认 | 从下表查找 |
| 债务成本 `kd` | 利息支出/总债务，否则 5.5% | 有效利率 |
| 税率 `tax_rate` | 3年中位数有效税率，下限15%，上限30% | 剔除一次性影响 |
| 利润率假设 | 各比率3年中位数 | 平滑周期波动 |
| 同行数量 | 4-6家 | 信号vs噪声平衡 |
| 同行倍数 | 中位数（非均值） | 抗异常值干扰 |
| 方法权重（无SOTP） | DCF 50% / 相对估值 50% | 等权交叉验证 |
| 方法权重（有SOTP） | DCF 40% / 相对 30% / SOTP 30% | SOTP获得合理权重 |
| 敏感性矩阵 | WACC ±1%，步长0.5% × g 1.5%-3.5%，步长0.5% | 5×5矩阵 |

### 1.2 行业Beta默认值

当 yfinance 返回 `None` 或异常值时使用：

| 行业/板块 | 默认Beta | 说明 |
|----------|:-------:|------|
| 公用事业 | 0.55 | 低波动，高负债 |
| 必需消费品 | 0.70 | 防御性 |
| 电信（大型） | 0.85 | 重资产 |
| 医疗/制药 | 0.90 | 中低波动 |
| REITs | 0.90 | — |
| 工业 | 1.05 | 周期波动 |
| 金融（银行） | 1.15 | — |
| 可选消费 | 1.20 | 周期波动 |
| 能源（一体化） | 1.10 | — |
| 能源（勘探开发） | 1.40 | — |
| 科技（大型） | 1.15 | — |
| 科技（SaaS高增长） | 1.35 | — |
| 半导体 | 1.45 | — |
| 生物科技（临床阶段） | 1.60 | — |
| 电动车（纯电） | 1.80 | — |

### 1.3 WACC 行业合理区间

如有计算出的 WACC 超出以下区间，应回溯检查输入：

| 行业 | WACC 区间 | 备注 |
|------|:---------:|------|
| 公用事业 | 5-7% | 高负债，低beta |
| 必需消费品 | 7-9% | 低beta，中等杠杆 |
| 电信 | 7-9% | 重负债 |
| 医疗/制药 | 8-10% | — |
| REITs | 6-8% | — |
| 工业 | 8-11% | 周期波动 |
| 金融 | 9-12% | 高beta，负债是经营性的 |
| 可选消费 | 9-11% | — |
| 能源（大型） | 8-10% | — |
| 能源（勘探） | 10-12% | — |
| 科技（大型） | 8-11% | 低负债，中等beta |
| SaaS高增长 | 10-13% | 高beta，几乎无负债 |
| 半导体 | 10-12% | — |
| 生物科技 | 11-14% | 极高beta |

### 1.4 终值增长率上限

| 经济体 | 长期名义GDP | 最大可接受 g |
|--------|:---------:|:----------:|
| 美国 | 4.0-4.5% | 3.0% |
| 欧洲（发达） | 3.0-4.0% | 2.5% |
| 日本 | 1.5-2.5% | 1.5% |
| 中国 | 5.0-6.0% | 4.0% |
| 印度 | 7.0-9.0% | 5.0% |

---

## Step 2：方法选择决策树

| 企业类型 | DCF | 相对估值 | SOTP | 备注 |
|---------|:---:|:------:|:---:|------|
| 成熟现金流（消费/电信/公用） | ✅ 首选 | ✅ | ❌ | — |
| 高增长SaaS/软件 | ✅ 谨慎 | ✅ 首选 | ❌ | 搭配 EV/Revenue + Rule of 40 |
| 多业务分部集团 | ✅ | ✅ | ✅ 首选 | 分部对标纯主业同行 |
| 银行/保险 | ❌ | ✅ (P/B, P/TBV) | ❌ | 用 DDM 或超额收益模型 |
| 尚未盈利 | ❌ | EV/Revenue 仅 | ❌ | 置信度低，需标注 |
| REITs | ❌ | ✅ (P/FFO, P/AFFO) | ❌ | NAV 基础 |
| 周期性（能源/半导体/工业） | ✅ 周期中位 | ✅ | 视情况 | 跨周期标准化 |

> **授信审批特别提示**：对于尚未盈利或大额亏损企业，DCF 可信度极低，应优先使用相对估值和资产基础法，并对此明确标注。

---

## Step 3：DCF 估值模型

### 3A. 收入增速路径

从第一年分析师一致预期（或历史CAGR）逐渐衰减至终值增长率。

```python
import numpy as np

# 历史CAGR
rev_last3 = income_a.loc["Total Revenue"].iloc[:3]
hist_cagr = (rev_last3.iloc[0] / rev_last3.iloc[-1]) ** (1/2) - 1 if len(rev_last3) >= 2 else 0.05

# Year 1 growth: 优先使用分析师预测
try:
    y1_growth = float(earnings_est.loc["+1y", "growth"]) / 100 if "+1y" in earnings_est.index else hist_cagr
except:
    y1_growth = hist_cagr

g_terminal = 0.025  # 或 0.035 for China — 确保不超过 Step 1.4 上限

# 线性衰减
growth_path = np.linspace(y1_growth, g_terminal + 0.01, 5)
# 或使用指数衰减: growth_path = [y1_growth * decay**i for i in range(5)] where decay = (g_terminal/g1)**(1/4)
```

### 3B. 利润率假设 — 3年中位数

```python
# 从利润表取最近3年数据
rev_3y = income_a.loc["Total Revenue"].iloc[:3]
ebit_3y = income_a.loc["Operating Income"].iloc[:3]

ebit_margin = float((ebit_3y / rev_3y).median())

# 从现金流量表取 D&A 和 CapEx（CapEx 通常为负值）
da_3y  = cashflow_a.loc["Depreciation And Amortization"].iloc[:3]
capex_3y = cashflow_a.loc["Capital Expenditure"].iloc[:3].abs()  # 取绝对值
nwc_3y = cashflow_a.loc.get("Change In Working Capital", pd.Series([0,0,0])).iloc[:3].abs()

da_pct    = float((da_3y / rev_3y).median())
capex_pct = float((capex_3y / rev_3y).median())
nwc_pct   = float((nwc_3y / rev_3y).median())

# 有效税率 — 3年中位数，下限15%，上限30%
tax_expense_3y = income_a.loc.get("Tax Provision", income_a.loc.get("Income Tax Expense"))
pretax_3y = income_a.loc.get("Pretax Income", income_a.loc.get("Income Before Tax"))
if tax_expense_3y is not None and pretax_3y is not None:
    etr = (tax_expense_3y.iloc[:3] / pretax_3y.iloc[:3]).median()
    tax_rate = max(0.15, min(0.30, float(etr)))
else:
    tax_rate = 0.21  # 默认 US 联邦税率，中国用 0.25
```

### 3C. 逐期FCFF计算

```python
# 基准收入（最近一期）
rev_base = float(income_a.loc["Total Revenue"].iloc[0])
rev_fcst = [rev_base]

# 预测 FCFF
fcff_list = []
for yr in range(5):
    g = growth_path[yr]
    rev_next = rev_fcst[-1] * (1 + g)
    rev_fcst.append(rev_next)

    ebit = rev_next * ebit_margin
    nopat = ebit * (1 - tax_rate)
    da = rev_next * da_pct
    capex = rev_next * capex_pct
    nwc = rev_next * nwc_pct

    fcff = nopat + da - capex - nwc
    fcff_list.append(fcff)

print("FCFF预测（百万）：")
for i, f in enumerate(fcff_list):
    print(f"  Year {i+1}: {f/1e6:.1f}")
```

### 3D. WACC 计算

```python
# 无风险利率 — 优先实时获取
try:
    rf = yf.Ticker("^TNX").fast_info.last_price / 100
    print(f"  10Y Treasury: {rf*100:.2f}%")
except:
    rf = 0.045
    print(f"  10Y Treasury: 获取失败，使用默认 {rf*100:.2f}%")

erp = 0.055  # 美股5.5%，中国用 0.075

# Beta
if beta_raw and beta_raw > 0:
    beta = beta_raw
else:
    # 从 Step 1.2 表查找行业默认 beta
    # 如 sector == "Technology" -> 1.15
    sector_beta_defaults = {
        "Utilities": 0.55, "Consumer Defensive": 0.70,
        "Communication Services": 0.85, "Healthcare": 0.90,
        "Real Estate": 0.90, "Industrials": 1.05,
        "Financial Services": 1.15, "Consumer Cyclical": 1.20,
        "Energy": 1.10, "Technology": 1.15,
    }
    beta = sector_beta_defaults.get(sector, 1.0)
    print(f"  Beta (行业默认): {beta}")

ke = rf + beta * erp     # CAPM 权益成本
e_v = market_cap / (market_cap + total_debt) if market_cap else 0.8
d_v = 1 - e_v
kd = 0.055  # 默认投资级，可用利息支出/总债务覆盖

wacc = e_v * ke + d_v * kd * (1 - tax_rate)

print(f"WACC = {wacc*100:.2f}% (ke={ke*100:.2f}%, kd={kd*100:.2f}%, D/V={d_v*100:.1f}%)")
```

**WACC 闸门检查**：
- 若 `wacc <= g_terminal` → 停止，g 过于激进
- 若 WACC 超出行业合理区间（见 Step 1.3）→ 标注
- 若 `beta` 为行业默认值（非实时获取）→ 标注数据源

### 3E. 终值 — 双法取中点

```python
import math

# Gordon 永续增长模型
tv_gordon = fcff_list[-1] * (1 + g_terminal) / (wacc - g_terminal) if wacc > g_terminal else 0

# 退出倍数法（同行 EV/EBITDA 中位数 × 15）
ebitda_last = rev_fcst[-1] * ebit_margin + rev_fcst[-1] * da_pct
tv_exit = ebitda_last * 15  # 15 = 默认 EV/EBITDA 倍数，后续用相对估值步骤的结果覆盖

if tv_gordon > 0:
    tv_base = 0.5 * tv_gordon + 0.5 * tv_exit
else:
    tv_base = tv_exit  # Gordon 不可用时只用退出倍数

# 折现
pv_fcff = sum(f / (1 + wacc)**(i+1) for i, f in enumerate(fcff_list))
pv_tv   = tv_base / (1 + wacc)**5

# EV → 股权价值
ev_dcf = pv_fcff + pv_tv
equity_dcf = ev_dcf + cash - total_debt
implied_price_dcf = equity_dcf / shares_out if shares_out else None

print(f"企业价值(EV): {ev_dcf/1e9:.2f}B | 股权价值: {equity_dcf/1e9:.2f}B | 隐含股价: ${implied_price_dcf:.2f}")
print(f"PV(FCFF): {pv_fcff/1e9:.2f}B ({pv_fcff/ev_dcf*100:.0f}%) | PV(TV): {pv_tv/1e9:.2f}B ({pv_tv/ev_dcf*100:.0f}%)")

# 闸门
if pv_tv / ev_dcf > 0.85 and tv_gordon > 0:
    print("⚠ 终值占比 >85%，估值高度依赖终值假设，置信度低")
elif pv_tv / ev_dcf < 0.45:
    print("⚠ 终值占比 <45%，可能预测期过短或增速过低")
```

---

## Step 4：相对估值

### 4A. 同行选择

根据目标公司的行业和业务特征，选择 4-6 家可比的上市公司。

```python
# 示例：科技/软件行业
PEERS = ["MSFT", "ORCL", "CRM", "NOW", "SAP", "WDAY"]

multiples = {}
for p in PEERS:
    pi = yf.Ticker(p).info
    multiples[p] = {
        "name": pi.get("shortName", p),
        "pe_fwd": pi.get("forwardPE"),
        "ev_rev": pi.get("enterpriseToRevenue"),
        "ev_ebitda": pi.get("enterpriseToEbitda"),
        "ps": pi.get("priceToSalesTrailing12Months"),
        "pb": pi.get("priceToBook"),
        "gross_margin": pi.get("grossMargins"),
        "rev_growth": pi.get("revenueGrowth"),
        "market_cap": pi.get("marketCap"),
    }

# 中位数（抗异常值）
med_pe     = np.nanmedian([v["pe_fwd"] for v in multiples.values() if v["pe_fwd"]])
med_ev_rev = np.nanmedian([v["ev_rev"] for v in multiples.values() if v["ev_rev"]])
med_ev_eb  = np.nanmedian([v["ev_ebitda"] for v in multiples.values() if v["ev_ebitda"]])
med_ps     = np.nanmedian([v["ps"] for v in multiples.values() if v["ps"]])
med_pb     = np.nanmedian([v["pb"] for v in multiples.values() if v["pb"]])
```

### 4B. 计算隐含股价

```python
# TTM 数据
eps_ttm    = float(income_q.loc["Diluted EPS"].iloc[:4].sum())  # 滚动12个月
rev_ttm    = float(income_q.loc["Total Revenue"].iloc[:4].sum())
# EBIT + D&A（简化处理）
ebit_ttm   = float(income_q.loc.get("Operating Income", income_q.loc.get("EBIT")).iloc[:4].sum())
da_ttm     = float(cashflow_q.loc["Depreciation And Amortization"].iloc[:4].sum())
ebitda_ttm = ebit_ttm + da_ttm

net_debt = total_debt - cash

# 各倍数隐含股价
implied_pe      = med_pe * eps_ttm if med_pe and eps_ttm > 0 else None
implied_ev_rev  = (med_ev_rev * rev_ttm - net_debt) / shares_out if med_ev_rev else None
implied_ev_ebit = (med_ev_eb  * ebitda_ttm - net_debt) / shares_out if med_ev_eb and ebitda_ttm > 0 else None
implied_ps      = med_ps * rev_ttm / shares_out if med_ps else None
implied_pb      = med_pb * info.get("bookValue", 0) if med_pb and info.get("bookValue", 0) > 0 else None

# 有效值取中位数
valid_prices = [p for p in [implied_pe, implied_ev_rev, implied_ev_ebit, implied_ps, implied_pb] if p]
implied_price_rel = np.nanmedian(valid_prices) if valid_prices else None
```

**倍数调整规则**：
- 若目标公司收入增速显著高于/低于同行中位数（±20%），对应倍数可上调/下调 10-30%
- 若毛利率显著高于同行（+10pp），溢价 15-25% 可能合理
- 务必在输出中说明调整原因和幅度

### 4C. 行业专用倍数

| 行业 | 首选倍数 | 备选倍数 | 排除 |
|------|---------|---------|------|
| 银行/保险 | P/B, P/TBV | P/E | EV/EBITDA |
| SaaS/软件 | EV/Revenue | P/S（Rule of 40 锚定） | — |
| REITs | P/FFO, P/AFFO | P/B (NAV) | P/E |
| 工业/制造 | EV/EBITDA | P/E | — |
| 矿业/能源 | EV/EBITDA（周期中位） | EV/Reserves | — |
| 零售/消费 | P/E | EV/EBITDA | — |
| 生物科技 | EV/Revenue | — | P/E |
| 电信 | EV/EBITDA | P/E (DPS) | — |

---

## Step 5：SOTP 分部加总（仅多分部企业）

> **前提**：公司年报中披露 2+ 独立业务分部且财务数据可分。yfinance **不**提供分部数据，需用户从年报/招股书提供或使用 `企业公开信息抓取` skill 提取。

操作步骤：
1. 识别各业务分部 + 各自纯主业可比公司
2. 对每个分部应用同行中位数 EV/EBITDA（增长分部可用 EV/Revenue）
3. 扣除未分配公司费用（未知时按收入的 2-5%）
4. 减去净债务、少数股东权益；除以总股本 = SOTP 隐含股价
5. 计算"集团折价"：`(SOTP价 - 市价) / SOTP价`，若 >20% 说明市场对集团折价明显

---

## Step 6：交叉验证 + 敏感性分析

### 6A. 综合隐含股价

```python
if 'sotp_price' in dir() and sotp_price:
    blended = 0.4 * implied_price_dcf + 0.3 * implied_price_rel + 0.3 * sotp_price
else:
    blended = 0.5 * implied_price_dcf + 0.5 * implied_price_rel

upside = (blended - price) / price * 100 if price else 0
print(f"综合公允价值: ${blended:.2f} | 当前市价: ${price:.2f} | 上行/下行空间: {upside:+.1f}%")
```

### 6B. WACC × g 敏感性矩阵（5×5）

```python
wacc_grid = [wacc + dx for dx in (-0.01, -0.005, 0, 0.005, 0.01)]
g_grid    = [0.015, 0.020, 0.025, 0.030, 0.035]

print("\n=== 敏感性矩阵 (WACC × g) === 隐含股价 (美元)")
print(f"{'WACC↓ g→':<10}", end="")
for g in g_grid:
    print(f"{g*100:>7.1f}%", end="")
print()

for w in wacc_grid:
    print(f"{w*100:<8.1f}%", end=" ")
    for g_term in g_grid:
        if w <= g_term:
            print(f"{'N/A':>7}", end=" ")
        else:
            tv_g = fcff_list[-1] * (1 + g_term) / (w - g_term)
            pv_g = sum(f / (1 + w)**(i+1) for i, f in enumerate(fcff_list)) + tv_g / (1 + w)**5
            eq = pv_g + cash - total_debt
            ip = eq / shares_out
            print(f"{ip:>7.1f}", end=" ")
    print()
```

### 6C. 情景分析 (Bull / Base / Bear)

| 情景 | 收入增速 | EBIT利润率 | WACC | 终值g | 适用场景 |
|------|:-------:|:--------:|:----:|:----:|------|
| **Bull** | +300bps | +200bps | -100bps | 3.0% | 乐观：行业上行周期、竞争壁垒强化 |
| **Base** | 基准值 | 基准值 | 基准值 | 2.5% | 中性：当前趋势延续 |
| **Bear** | -300bps | -200bps | +100bps | 1.5% | 悲观：经济下行、竞争加剧、监管收紧 |

> **授信审批应用**：Bear情景下的估值是偿债能力压力测试的关键输入。若Bear情景的EV已接近或低于有息负债总额，则触发风险预警。

---

## Step 7：输出格式（授信审批专用）

按以下顺序输出：

### 7.1 结论摘要
一句话结论：综合公允价值 vs 当前市价，上行/下行空间百分比，最乐观和最悲观方法的估值。

### 7.2 公司快照
行业、市值、当前股价、3个月/12个月股价变动、LTM收入增速、有息负债/EV比率。

### 7.3 三法对照表
| 方法 | 隐含股价 | 权重 | 简要理由 |

### 7.4 DCF 详细构建
- 关键假设表（增速路径、利润率、WACC组成、终值方法）
- 5年FCFF预测表
- EV→股权价值桥梁

### 7.5 同行对比表
同行 PE fwd / EV/Rev / EV/EBITDA / 毛利率 / 收入增速表，底部中位数行，标注目标公司溢/折价。

### 7.6 SOTP（如适用）
分部表格 + 调整项 + 每股权益价值

### 7.7 敏感性矩阵
WACC × g 5×5 网格，基准情景高亮

### 7.8 情景分析
Bull / Base / Bear 表：各情景杠杆参数 + 隐含股价 + 授信风险评估

### 7.9 关键风险
3-5条，聚焦：哪个假设对结果影响最大，什么会打破估值逻辑

### 7.10 授信审批专项提示
- **偿债安全垫**：EV / 有息负债倍数（Bear情景）
- **抵押物价值**：Bear情景股权价值能否覆盖贷款敞口
- **估值合理性**：当前市值是否反映了基本面（市场情绪 vs 内在价值偏差）
- **关键变量监测**：哪些指标恶化会显著削弱偿债能力

---

## 异常处理

| 缺失/边缘情况 | 处理方式 |
|-------------|---------|
| yfinance 返回 `None` 的 beta | 使用行业默认 Beta（Step 1.2 表） |
| LTM EBITDA 为负 | 跳过 EV/EBITDA 倍数，仅用 EV/Revenue + DCF |
| LTM EPS 为负 | 跳过 PE 倍数，使用 Forward PE（若有且为正），否则跳过 |
| Gordon 模型中 g ≥ WACC | 将 g 限制为 `wacc - 0.5%`，标注异常 |
| 财务数据不足 3 年 | 使用可用数据，置信度标注为"低"；授信审批中需附加资产基础法 |
| 同行数据获取失败 | 从同行列表中剔除该标的，缩减至最低 3 家；不足 3 家时使用行业平均倍数 |
| 无分部数据需 SOTP | 跳过 Step 5，仅用 DCF + 相对估值 |
| A股/港股数据缺失 | 使用 `企业公开信息抓取` skill 补全，或请用户提供关键财务数据 |

---

## 注意事项

- TTM数据落后于实时行情；同行倍数反映市场情绪（可能超调）
- DCF 是 garbage-in-garbage-out；敏感性分析比点估计更有意义
- yfinance 数据非官方；关键决策必须交叉核对原始披露文件
- **授信审批特别提醒**：估值仅为偿债能力判断的辅助工具，不能替代全面的信贷分析（包括经营稳定性、行业周期、管理层质量、担保措施等维度）
- 不构成投资建议

---

## 参考数据速查

### 权益风险溢价（ERP）

| 市场 | 默认ERP | 说明 |
|------|:-----:|------|
| 美国 | 5.5% | Damodaran隐含ERP |
| 中国 | 7.5% | 含国家风险溢价 |
| 发达欧洲 | 6.0-6.5% | — |
| 日本 | 6.0% | — |
| 印度 | 7.5% | — |
| 新兴市场 | 8.0-10.0% | — |

### 规模溢价

| 市值规模 | 规模溢价 |
|----------|:------:|
| > 200亿美元（超大） | 0% |
| 100-200亿（大型） | 0% |
| 20-100亿（中型） | 0.5-1.0% |
| 5-20亿（小型） | 1.5-2.5% |
| 1-5亿（微型） | 2.5-4.0% |
| < 1亿（纳米） | 4.0%+ |

### 债务成本评级对照

| 信用评级 | 风险溢价（对rf） | 示例 Kd（rf=4.5%） |
|:-------:|:------------:|:-----------------:|
| AAA | 0.5-0.8% | 5.0-5.3% |
| AA | 0.8-1.2% | 5.3-5.7% |
| A | 1.2-1.8% | 5.7-6.3% |
| BBB | 1.8-2.5% | 6.3-7.0% |
| BB | 3.5-5.0% | 8.0-9.5% |
| B | 5.5-7.5% | 10.0-12.0% |
| CCC+ | 9.0%+ | 13.5%+ |

---

## 使用示例

```
用户："分析茅台的估值"
→ 触发本 Skill
→ TICKER = "600519.SS"
→ 获取数据 → DCF + 相对估值（消费行业PE/EV EBITDA）
→ 输出综合估值报告
→ 附授信审批专项提示（偿债安全垫、抵押物覆盖率等）

用户："做一下比亚迪的DCF估值，终值增长率用3%"
→ 触发本 Skill，用户覆盖终值增长率参数
→ TICKER = "002594.SZ" 或 "1211.HK"
→ 重点关注：新能源车行业增长衰减路径、电池业务资本开支假设
```

---

**关联 Skill**：
- `企业公开信息抓取` — 获取A股/港股年报PDF、审计报告、评级报告（数据来源）
- `现金流测算` — 项目偿债现金流测算、DSCR 计算（偿债能力分析下游）
- `盈利质量分析`（待创建） — 盈利趋势、利润率拆解、分析师预期修正
