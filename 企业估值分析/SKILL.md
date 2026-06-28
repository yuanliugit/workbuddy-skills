---

name: "企业估值分析"
description: >
  企业估值分析 Skill —— 采用 DCF（现金流折现）、相对估值（同行市盈率/EV倍数）、SOTP（分部加总）、
  LBO（杠杆收购模型）和 Merger Model（并购增厚/稀释）五法交叉验证，
  输出隐含股价、WACC×增长率敏感性矩阵、IRR/MOIC、Accretion/Dilution、Bull/Base/Bear 情景分析。
  专为银行授信审批场景优化：估值结果直接服务于企业偿债能力评估、抵押物价值判断、持续经营假设验证。
  触发条件：用户提到"估值分析"、"DCF估值"、"企业价值"、"公允价值"、"XX值多少钱"、"这家公司值多少"、"估值建模"、
  "相对估值"、"市盈率对比"、"EV/EBITDA"、"WACC"、"敏感性分析"、"现金流折现"、
  "LBO"、"杠杆收购"、"IRR"、"MOIC"、"并购模型"、"增厚稀释"、"Accretion/Dilution"等。
agent_created: true
version: "1.2.0"
loop_engineered: true
loop_engineered_version: "1.0.0"
---

# 企业估值分析 Skill

## 概述

采用五种估值方法对企业进行交叉验证估值，辅助授信审批中的企业价值判断：

1. **DCF（现金流折现）** — 5年FCFF预测 + 终值 + WACC折现 → 企业内在价值
2. **相对估值** — 同行PE/EV Revenue/EV EBITDA倍数中位数 → 市场参照价值
3. **SOTP（分部加总）** — 多业务分部各自对标纯主业同行 → 分部价值加总
4. **LBO（杠杆收购模型，新增 v1.2.0）** — 债务分层 + LFCF + IRR/MOIC → 杠杆收购回报
5. **Merger Model（并购增厚/稀释，新增 v1.2.0）** — 并表调整 + Accretion/Dilution → 并购影响分析

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

## Step 8：LBO 杠杆收购模型（新增 v1.2.0）

> **适用场景**：私募股权收购、管理层收购(MBO)、杠杆并购交易估值。用于判断收购方在既定债务结构下能否获得合理回报（IRR/MOIC），以及目标企业能否产生足够现金流偿还债务。
>
> **授信审批应用**：评估杠杆收购标的企业的债务承载能力，验证收购后的偿债安全垫。

### 8A. LBO 基本原理

LBO 估值的核心逻辑：用目标企业自身现金流偿还收购债务，通过经营改善或倍数扩张在退出时获得回报。

关键公式：
```
IRR = 使 (期初股权投资 = Σ(期间分配 / (1+r)^t) + 退出价值 / (1+r)^n) 成立的 r
MOIC = 累计回收现金 / 累计投入现金
```

### 8B. 交易结构设计

#### 资金来源与运用（Sources & Uses）

| 资金用途（Uses） | 占比参考 | 资金来源（Sources） | 占比参考 |
|-----------------|:------:|-------------------|:------:|
| 收购股权 | 80-90% 对价 | 优先级银行贷款 | 40-60% |
| 再融资存量债务 | 5-15% | 夹层债务/次级债 | 5-15% |
| 交易费用 | 2-4% | 股权出资（PE自有） | 30-50% |
| 印花税（0.05%股权转让） | <1% | 循环贷款（备付） | 10-20% EBITDA |

**中国市场参数调整**：
- 典型杠杆倍数：3-5x EBITDA（银行主导，低于美国市场的 5-7x）
- 控制权溢价：20-40%（A股并购普遍高于美股的 20-30%）
- A股退市私有化溢价：30-50%
- 交易费用：1.5-3%（含投行、律师、会计师等中介费用）

### 8C. 债务结构建模

```python
# 债务分层参数
senior_leverage = 3.0      # 优先级贷款/EBITDA
spread_senior = 0.02       # LPR + 200bps
total_debt_capacity = ltm_ebitda * senior_leverage

# 债务摊销
mandatory_amort = 0.02     # 年强制摊销 2%（中国银团常见）
cash_sweep_pct = 0.50      # 超额现金 50% 用于提前还款

# 债务成本（参考）
debt_tranches = [
    {"name": "优先级银团贷款", "coupon": "LPR+2%", "tenor": 5, "amort": "2%/年", "share": 0.70},
    {"name": "夹层融资/次级债",  "coupon": "10-15%",   "tenor": 7, "amort": "到期一次还本", "share": 0.15},
    {"name": "循环贷款(备付)",   "coupon": "LPR+1.5%", "tenor": 3, "amort": "循环",        "share": 0.15},
]
```

### 8D. 5年经营预测与现金流

在现有 DCF 预测框架（Step 3）的基础上增加债务相关调整：

```python
# 从 Step 3 的 FCFF 出发 → 调整到 LFCF（杠杆自由现金流）
# LFCF = FCFF - 税后利息支出 - 强制摊销 - 股利

lfcf_list = []
debt_balance = initial_debt
for yr in range(5):
    fcff = fcff_list[yr]

    # 利息 = 期初期末平均余额 × 利率
    interest = (debt_balance + debt_balance * 0.9) / 2 * cost_of_debt
    after_tax_interest = interest * (1 - tax_rate)
    mandatory_paydown = initial_debt * mandatory_amort

    lfcf = fcff - after_tax_interest - mandatory_paydown
    debt_balance -= mandatory_paydown

    # 现金清扫（超额现金还债）
    cash_sweep = max(0, lfcf * cash_sweep_pct)
    debt_balance -= cash_sweep
    lfcf -= cash_sweep

    lfcf_list.append(lfcf)
    print(f"Y{yr+1}: 期末负债={debt_balance/1e6:.1f}M, LFCF={lfcf/1e6:.1f}M")
```

### 8E. 退出与回报计算

```python
# 退出假设
exit_year = 5
exit_ebitda = ebitda_forecast[4]  # 第5年EBITDA
exit_multiple = 10.0               # 目标退出EV/EBITDA倍数（参考同行中位数 ± 折溢价）

# 退出企业价值
exit_ev = exit_ebitda * exit_multiple

# 退出股权价值 = EV - 净负债 + 超额现金
exit_equity = exit_ev - debt_balance + excess_cash

# MOIC = 退出股权价值 / 初始股权投入
moic = exit_equity / initial_equity

# IRR — 使用 numpy.irr 或迭代求解
import numpy as np
# 现金流序列: T0投入(负值), T1-T4中间分配(如有), T5退出
cf_series = [-initial_equity] + [0]*4 + [exit_equity]
irr = np.irr(cf_series)

print(f"MOIC: {moic:.2f}x | IRR: {irr*100:.1f}%")
```

### 8F. 敏感性分析矩阵

交叉变量：
- **进入倍数 vs 退出倍数**（Entry EV/EBITDA 6-12x, Exit EV/EBITDA 8-14x）
- **EBITDA增速 vs 杠杆倍数**（CAGR 0-15%, Leverage 2-6x）

输出格式：5×5 矩阵，标注 Bull/Base/Bear 情景。

### 8G. 中国市场特殊考量

| 维度 | 中国LBO特殊处理 |
|------|---------------|
| 退市路径 | 全面要约收购（超30%需要约）；要约价不低于前6个月最高交易价 |
| 再上市 | 退市后3年方可重新A股上市（创业板/科创板为2年） |
| 债务市场 | 银行银团贷款为主，公司债/中票为辅；LPR为基准 |
| 税务 | 企业所得税 25%（高新15%），股权转让印花税 0.05% |
| 监管审批 | 反垄断审查、经营者集中申报、外资安全审查（如需） |
| 运营惯例 | 应收账款周转慢、存货周转高；净营运资本通常占营收 5-15% |
| 管理层持股 | 常见 管理层持股 + 业绩对赌(Earn-out) 安排 |

### 8H. LBO 闸门检查

- IRR < 15% → 标注：低于PE行业通常要求的 20%+ 门槛
- 期末负债/EBITDA > 4x → 标注：退出时杠杆仍然过高
- 利息覆盖倍数 < 2x 任何一年 → 触发风险预警
- MOIC < 1.5x → 标注：回报偏低，依赖乐观退出假设
- 期末净负债 > 初始负债的 60% → 依赖再融资或到期续贷

---

## Step 9：Merger Model 并购增厚/稀释分析（新增 v1.2.0）

> **适用场景**：两家公司合并（吸收合并/换股合并/资产收购），评估合并后对收购方每股收益(EPS)的影响。
>
> **授信审批应用**：评估并购后企业偿债能力变化；判断并购融资方案是否合理。

### 9A. Accretion/Dilution 基本原理

```
增厚(Accretive)：合并后EPS > 收购方原EPS
稀释(Dilutive) ：合并后EPS < 收购方原EPS
```

关键驱动因素：并购价格（溢价高低）× 支付方式（现金/换股/混合）× 融资成本（利率） × 协同效应

### 9B. 并表假设

```python
# 收购方（Buyer）
buyer_net_income = 1000
buyer_shares = 500
buyer_eps = 2.00

# 标的方（Target）
target_net_income = 200
target_shares = 100

# 交易假设
purchase_premium = 0.30       # 30%溢价
target_market_cap = 2000
purchase_price = target_market_cap * (1 + purchase_premium)  # 2600

# 支付结构
cash_pct = 0.60      # 60%现金
stock_pct = 0.40     # 40%换股

# 融资条件
debt_rate = 0.06     # 债务融资成本 6%
tax_rate = 0.25
```

### 9C. 并表利润调整

```python
# Step 1: 合并净利润
pro_forma_ni = buyer_net_income + target_net_income

# Step 2: 调整项
# 融资成本（现金部分）
cash_financed = purchase_price * cash_pct
after_tax_interest = cash_financed * debt_rate * (1 - tax_rate)
pro_forma_ni -= after_tax_interest

# 收购价格分摊 (Purchase Price Allocation, PPA) — 无形资产摊销
# 假设溢价部分的 50% 归于可辨认无形资产，分 10 年摊销
excess_purchase = purchase_price - target_book_value
intangible_amort = excess_purchase * 0.50 / 10
pro_forma_ni -= intangible_amort * (1 - tax_rate)  # 摊销税盾

# 协同效应（如适用）
synergies = 50  # 年度成本协同
synergy_integration_cost = 30  # 整合费用（一次性）
pro_forma_ni += synergies * (1 - tax_rate)
pro_forma_ni -= synergy_integration_cost * (1 - tax_rate)

# 优先股股息（如使用优先股融资）
preferred_dividend = 0  # 假设无
pro_forma_ni -= preferred_dividend
```

### 9D. 并表股数

```python
# 换股部分产生的新增股份
shares_issued = purchase_price * stock_pct / buyer_share_price
pro_forma_shares = buyer_shares + shares_issued

# 并表 EPS
pro_forma_eps = pro_forma_ni / pro_forma_shares
accretion_pct = (pro_forma_eps - buyer_eps) / buyer_eps * 100

print(f"收购方原EPS: {buyer_eps:.2f}")
print(f"并表EPS:     {pro_forma_eps:.2f}")
print(f"增厚/稀释:    {accretion_pct:+.1f}%")
print(f"{'增厚' if accretion_pct > 0 else '稀释'}交易")
```

### 9E. 多层次增厚/稀释分析

| 分析层次 | 内容 |
|---------|------|
| **EPS 增厚/稀释** | 并表后第一年/第二年 EPS 变化百分比 |
| **现金流增厚/稀释** | 并表后 FCF/股变化（排除PPA等非现金调整） |
| **ROE 影响** | 并表后 ROE 变化（考虑商誉膨胀效应） |
| **杠杆影响** | 并表后负债率变化（现金收购推高杠杆） |

### 9F. 支付方式敏感性

```python
# 现金比例从 0% 到 100% 间隔 20%
for cash_pct in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
    # 重复 9C-9D 计算
    accretion = calc_accretion(cash_pct)
    print(f"现金{cash_pct*100:.0f}% | 增厚/稀释: {accretion:+.1f}%")
```

### 9G. 并购闸门检查

- 增厚/稀释 > -5%（稀释不超过 5%）→ 可接受
- 稀释超过 5% → 标注：支付对价过高或融资成本过大
- 并表后负债率 > 70% → 触发债务风险预警
- 协同效应假设 > EBITDA 的 30% → 标注：过于激进，做情景分析
- 商誉占并表总资产 > 30% → 标注减值风险

### 9H. 中国市场并购特殊考量

| 维度 | 中国市场特殊处理 |
|------|---------------|
| 审批 | 证监会并购重组委审核（重大资产重组）；反垄断审查（经营者集中） |
| 评估方法 | 要求出具资产评估报告（收益法/市场法/资产基础法） |
| 业绩承诺 | 重大资产重组通常要求 3 年业绩承诺（利润补偿协议） |
| 锁定期 | 交易对方股票锁定期通常 12-36 个月 |
| 税务 | 满足特殊性税务处理条件可递延纳税（59号文） |
| 支付工具 | 股份+现金组合最常见，定向可转债逐年增多 |
| 关联交易 | 关联方交易需独立财务顾问出具意见 |

### 9I. 方法选择决策树补充（LBO和Merger Model）

在原有 Step 2 决策树基础上增加：

| 企业类型/场景 | DCF | 相对估值 | SOTP | LBO | Merger Model | 备注 |
|-------------|:---:|:------:|:---:|:---:|:-----------:|------|
| PE收购/私有化 | ✅ | ✅ | ❌ | ✅ 首选 | ❌ | LBO 是核心估值工具 |
| 战略并购（现金） | ✅ | ✅ | 视情况 | ❌ | ✅ 首选 | Accretion/Dilution 驱动 |
| 战略并购（换股） | ✅ | ✅ | 视情况 | ❌ | ✅ 首选 | 稀释控制是核心约束 |
| 杠杆收购（PE） | — | ✅ | ❌ | ✅ 首选 | ❌ | IRR/MOIC 驱动 |
| 管理层收购(MBO) | ✅ | ✅ | ❌ | ✅ 首选 | ❌ | 管理层持股+业绩对赌 |

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

## work-analysis-loop 集成说明（v1.1.0 新增）

本 Skill 从 v1.1.0 起在 **`work-analysis-loop` 护栏**下执行，具体映射：

| 执行阶段 | 对应 Loop Round | 停止条件 |
|---------|---------------|---------|
| 第一阶段：数据获取与校验（财务数据、可比公司列表） | Round 1-2 | 核心财务数据无法获取、可比公司数量 < 3 |
| 第二阶段：DCF 估值（WACC、FCF 预测、终值、敏感性） | Round 3-4 | FCF 预测依赖的盈利数据缺失关键年份 |
| 第三阶段：相对估值（同行市盈率/EV 倍数） | Round 5 | 可比公司筛选结果为空或样本量不足 |
| 第四阶段：SOTP 分部加总（如适用） | Round 6 | 分部数据不披露且无法合理拆分（切换跳转） |
| 第五阶段：综合估值报告与敏感性矩阵 | Round 7 | — |

### 数据层级标注规范（强制）

所有估值参数和结果必须按以下层级标注：

| 层级 | 标注格式 | 适用范围 |
|------|---------|---------|
| `[事实]` | 直接引用年报/金融数据终端原始数字 | FCF 基础数据（收入、利润、资本开支）|
| `[抽数]` | 从来源提取后结构化 | 历史财务指标时间序列 |
| `[计算]` | DCF 终值、隐含股价、EV/EBITDA | 所有估值输出 |
| `[假设]` | WACC 各组件、永续增长率、预测期 | 必须在报告中明确陈述并做敏感性分析 |
| `[推断]` | 估值结果的合理区间判断 | "基于 Bull/Base/Bear 三情景..." |
| `[观点]` | 投资建议（如有）| 明确标注"不构成投资建议" |

### 缺失参数强制规则

- DCF 三法必须独立估值，不得用同一组假设交叉替代
- WACC 各组件缺失时：优先使用 Bloomberg/万得一致预期，次优使用行业研究估计，**必须注明来源层级**
- 可比公司列表为空时：标注 `[缺失：无可比同行]`，说明原因，跳过相对估值，仅使用 DCF + SOTP
- 终值增长率 > 3% 需特别注明假设依据（中国 GDP 长期名义增速约 5-6%）

### 与 credit-review-workbench 的双向路由

- **上行**：被 `credit-review-workbench` 调用时，估值结果直接嵌入审查报告偿债能力评估章节
- **下行**：独立使用时，入口输出任务卡（参照 work-analysis-loop 快速启动模板）
- **交接**：完成后生成交接摘要，包含：估值报告路径 + 关键假设清单 + 敏感性矩阵 + 授信审批提示

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

## Trigger（触发条件）

以下情况**必须触发**本 Skill：


| 编号 | 触发条件 | 优先级 |
|------|---------|---------|
| T1 | 用户说出"估值分析"/"DCF估值"/"企业估值" | P0 |
| T2 | 用户提供了股票代码 + "估值"意图 | P0 |
| T3 | 用户说"相对估值"/"PE估值" | P1 |
| T4 | 用户说"隐含股价"/"目标价" | P1 |

排除条件：
- E1: 未指定是估值分析 → 先询问
- E2: 说"现金流测算"→ 触发现金流测算Skill

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
| `methods_status` | object | 三法各自完成状态 |
| `cross_validation` | object | 三法交叉验证结果 |
| `method_spread` | string | 三法结果差异百分比 |
| `wacc_components` | object | WACC各组件计算状态 |

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

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.2.0 | 2026-06-28 | **投行估值扩展**：①新增 Step 8 LBO 杠杆收购模型（Sources & Uses、债务分层、LFCF、IRR/MOIC、退出回报、敏感性矩阵）；②新增 Step 9 Merger Model 并购增厚/稀释分析（Accretion/Dilution、支付方式敏感性、并表调整、协同效应）；③补充中国市场 LBO/M&A 特殊考量（退市私有化、业绩对赌、证监会审批、税务递延）；④更新方法选择决策树（增加 LBO 和 Merger Model 两列） |
| 1.1.0 | 2026-06-28 | **loop-engineering 改造**：①frontmatter 增加 loop_engineered 标记；②新增 Trigger（触发条件）章节；③新增 State 持久化（断点恢复）章节；④新增 Handoff 格式（交接包）章节；⑤采用统一 State Schema |
| v1.0.0 | 2026-05-31 | 初始版本。DCF + 相对估值 + SOTP 三法交叉验证，WACC×增长率敏感性矩阵，Bull/Base/Bear 情景分析 |
| v1.1.0 | 2026-06-28 | **护栏集成**：①新增 work-analysis-loop 护栏集成映射表（三法→7 Round）；②新增数据层级标注规范（六层分级强制要求）；③缺失参数强制规则（终值增长率上限、可比公司空集处理）；④与 credit-review-workbench 建立双向路由；⑤新增版本历史记录 |

**关联 Skill**：
- `企业公开信息抓取` — 获取A股/港股年报PDF、审计报告、评级报告（数据来源）
- `现金流测算` — 项目偿债现金流测算、DSCR 计算（偿债能力分析下游）
- `盈利质量分析` — 盈利趋势、利润率拆解、分析师预期修正
