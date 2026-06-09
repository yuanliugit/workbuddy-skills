---
name: "盈利质量分析"
description: >
  盈利质量与趋势分析 Skill —— 融合季报回顾和分析师预期追踪两大能力，
  覆盖：盈利beat/miss分析、利润率趋势拆解、收入增速轨迹、分析师EPS/收入修正方向、
  盈利惊喜历史记录、成长预期vs同行对比。
  专为银行授信审批场景设计：盈利稳定性直接决定偿债能力可持续性，盈利恶化是最早的信用风险预警信号。
  触发条件：用户提到"盈利分析"、"季报回顾"、"盈利趋势"、"beat/miss"、"分析师预期"、
  "EPS修正"、"盈利预测"、"收入增速趋势"、"利润率变化"、"盈利惊喜"、"分析师一致预期"、
  "盈利修正方向"、"成长性分析"、"盈利质量"等。
agent_created: true
version: "1.0.0"
---

# 盈利质量分析 Skill

## 概述

从两个维度全面评估企业盈利质量：

1. **季报回顾（Earnings Recap）** — 实际EPS vs 一致预期、收入增速、利润率变化、市场反应
2. **分析师预期追踪（Estimate Analysis）** — EPS/收入修正方向、修正广度、成长预期vs同行

授信审批场景中，盈利分析用于：
- **偿债可持续性判断**：盈利是否稳定增长？利润率是否被侵蚀？
- **早期预警信号**：盈利修正持续向下是信用恶化的先行指标
- **现金流预测基础**：收入增速和利润率假设是DSCR测算的核心输入
- **行业地位验证**：盈利质量变化反映竞争力和定价权变化

**免责声明**：输出为研究/教育目的，不构成投资建议。数据来源 yfinance，与官方披露可能存在差异。

---

## 依赖环境

使用系统 Python 3.14 虚拟环境（与 `企业估值分析` 共用同一 venv）：

```bash
# 如已安装过依赖，跳过此步
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install yfinance numpy pandas -q
```
```

---

## Part A：季报回顾（Earnings Recap）

### A1. 数据获取

```python
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

TICKER = "AAPL"  # 替换为目标代码

ticker = yf.Ticker(TICKER)

# 盈利历史（实际 vs 预期）
earnings_hist = ticker.earnings_history

# 利润表 — 季度
income_q = ticker.quarterly_income_stmt
cashflow_q = ticker.quarterly_cashflow

# 行情（用于反应分析）
hist_1mo = ticker.history(period="1mo")

# 公司信息
info = ticker.info
news = ticker.news

print(f"✓ {TICKER} 季报数据获取完成")
print(f"  最新盈利日期: {earnings_hist.index[0].strftime('%Y-%m-%d') if len(earnings_hist) > 0 else 'N/A'}")
print(f"  可用季度数据: {len(income_q.columns)} 期")
```

### A2. 盈利beat/miss 分析

```python
if len(earnings_hist) > 0:
    latest = earnings_hist.iloc[0]
    eps_est = latest.get("epsEstimate")
    eps_act = latest.get("epsActual")
    eps_diff = latest.get("epsDifference")
    surprise_pct = latest.get("surprisePercent")  # 百分比

    # 如果字段缺失，手动计算
    if eps_act and eps_est:
        diff_calc = eps_act - eps_est
        surprise_calc = (diff_calc / abs(eps_est)) * 100

    print(f"\n=== 最新季报结果 ===")
    print(f"  EPS 实际: ${eps_act:.2f}" if eps_act else "  EPS: N/A")
    print(f"  EPS 预期: ${eps_est:.2f}" if eps_est else "  预期: N/A")
    if eps_act and eps_est:
        direction = "超预期 ✓" if diff_calc > 0 else ("不及预期 ✗" if diff_calc < 0 else "持平 —")
        print(f"  差值: ${diff_calc:+.2f} ({surprise_calc:+.1f}%) | {direction}")
```

### A3. 盈利历史记录（最近4季）

```python
# 从 earnings_history 提取最近4季
n_quarters = min(4, len(earnings_hist))
print(f"\n=== 最近 {n_quarters} 季盈利记录 ===")
print(f"{'季度':<12} {'EPS预期':>8} {'EPS实际':>8} {'差值':>10} {'惊喜%':>8}")
print("-" * 55)

for i in range(n_quarters):
    q = earnings_hist.iloc[i]
    est = q.get("epsEstimate")
    act = q.get("epsActual")
    if est and act:
        diff = act - est
        surp = (diff / abs(est)) * 100
        quarter_label = q.get("quarter", f"Q-{i}")
        print(f"{str(quarter_label):<12} {est:>8.2f} {act:>8.2f} {diff:>+8.2f} {surp:>+7.1f}%")

# 统计
beats = sum(1 for i in range(n_quarters) if earnings_hist.iloc[i].get("epsActual", 0) > earnings_hist.iloc[i].get("epsEstimate", 0))
avg_surprise = np.mean([(earnings_hist.iloc[i].get("epsActual", 0) - earnings_hist.iloc[i].get("epsEstimate", 0)) / abs(earnings_hist.iloc[i].get("epsEstimate", 1)) * 100
                         for i in range(n_quarters) if earnings_hist.iloc[i].get("epsEstimate", 0) != 0])
print(f"\n  Beat率: {beats}/{n_quarters} ({beats/n_quarters*100:.0f}%)")
print(f"  平均惊喜幅度: {avg_surprise:+.1f}%")
```

### A4. 利润率趋势（最近4个季度）

```python
# 从季度利润表提取最近4季
rev_q = income_q.loc["Total Revenue"].iloc[:4]
gp_q = income_q.loc.get("Gross Profit", pd.Series([0]*4)).iloc[:4]
oi_q = income_q.loc.get("Operating Income", income_q.loc.get("EBIT", pd.Series([0]*4))).iloc[:4]
ni_q = income_q.loc["Net Income"].iloc[:4]
eps_q = income_q.loc.get("Diluted EPS", income_q.loc.get("Basic EPS", pd.Series([0]*4))).iloc[:4]

print(f"\n=== 最近4季度利润趋势 ===")
print(f"{'指标':<18}", end="")
for i in range(4):
    q_date = income_q.columns[i]
    label = f"{q_date.year}Q{(q_date.month-1)//3+1}"
    print(f"{label:>14}", end="")
print()

# 收入
print(f"{'营业收入(百万)':<18}", end="")
for i in range(4):
    print(f"{rev_q.iloc[i]/1e6:>13.1f}B", end="")
print()

# YoY 增速
print(f"{'收入YoY增速':<18}", end="")
for i in range(4):
    if i + 4 < len(income_q.columns):
        prev_rev = income_q.loc["Total Revenue"].iloc[i + 4]
        yoy = (rev_q.iloc[i] / prev_rev - 1) * 100
        print(f"{yoy:>+12.1f}%", end="")
    else:
        print(f"{'N/A':>14}", end="")
print()

# 毛利率
print(f"{'毛利率':<18}", end="")
for i in range(4):
    gm = gp_q.iloc[i] / rev_q.iloc[i] * 100 if rev_q.iloc[i] != 0 else 0
    print(f"{gm:>13.1f}%", end="")
print()

# 营业利润率
print(f"{'营业利润率':<18}", end="")
for i in range(4):
    om = oi_q.iloc[i] / rev_q.iloc[i] * 100 if rev_q.iloc[i] != 0 else 0
    print(f"{om:>13.1f}%", end="")
print()

# 净利率
print(f"{'净利率':<18}", end="")
for i in range(4):
    nm = ni_q.iloc[i] / rev_q.iloc[i] * 100 if rev_q.iloc[i] != 0 else 0
    print(f"{nm:>13.1f}%", end="")
print()

# EPS
print(f"{'稀释EPS':<18}", end="")
for i in range(4):
    print(f"${eps_q.iloc[i]:>12.2f}", end="")
print()
```

### A5. 趋势判断

```python
# 利润率趋势判断
gm_trend = np.polyfit(range(4), [gp_q.iloc[i] / rev_q.iloc[i] for i in range(4) if rev_q.iloc[i] != 0], 1)[0]
om_trend = np.polyfit(range(4), [oi_q.iloc[i] / rev_q.iloc[i] for i in range(4) if rev_q.iloc[i] != 0], 1)[0]

print(f"\n=== 趋势判断 ===")
print(f"  毛利率趋势: {'↑ 改善' if gm_trend > 0.002 else ('↓ 恶化' if gm_trend < -0.002 else '→ 平稳')}")
print(f"  营业利润率趋势: {'↑ 改善' if om_trend > 0.002 else ('↓ 恶化' if om_trend < -0.002 else '→ 平稳')}")

# 惊喜幅度趋势
surprises = []
for i in range(n_quarters):
    est = earnings_hist.iloc[i].get("epsEstimate", 0)
    act = earnings_hist.iloc[i].get("epsActual", 0)
    if est != 0:
        surprises.append((act - est) / abs(est))
if len(surprises) >= 2:
    surp_trend = np.polyfit(range(len(surprises)), surprises, 1)[0]
    print(f"  惊喜幅度趋势: {'↑ 惊喜扩大' if surp_trend > 0.01 else ('↓ 惊喜收窄' if surp_trend < -0.01 else '→ 稳定')}")
    if surp_trend < -0.01:
        print(f"  ⚠ 惊喜幅度持续收窄 — 可能是壁垒在削弱，或一致预期追赶现实")
```

---

## Part B：分析师预期追踪（Estimate Analysis）

### B1. 获取预估数据

```python
# 分析师预估数据
earnings_est = ticker.earnings_estimate   # EPS预估（按期间）
revenue_est = ticker.revenue_estimate     # 收入预估
eps_trend = ticker.eps_trend             # EPS修正历史
eps_revisions = ticker.eps_revisions     # 上修/下修计数
growth_est = ticker.growth_estimates     # 增长预期

print(f"可用预估期间: {list(earnings_est.index) if earnings_est is not None else 'N/A'}")
```

### B2. 当前一致预期

```python
print(f"\n=== 分析师一致预期 ===")

# EPS
if earnings_est is not None:
    print(f"\n EPS预估：")
    for idx in earnings_est.index:
        row = earnings_est.loc[idx]
        avg = row.get("avg") or row.get("growth")
        low = row.get("low")
        high = row.get("high")
        num = row.get("numberOfAnalysts", "?")
        if avg:
            range_str = f"[{low:.2f} - {high:.2f}]" if low and high else ""
            print(f"  {idx}: {avg}  {range_str}  ({num}位分析师)")

# Revenue
if revenue_est is not None:
    print(f"\n 收入预估：")
    for idx in revenue_est.index:
        row = revenue_est.loc[idx]
        avg = row.get("avg") or row.get("growth")
        low = row.get("low")
        high = row.get("high")
        if avg:
            range_str = f"[{low:.1f}M - {high:.1f}M]" if low and high else ""
            print(f"  {idx}: {avg}  {range_str}")
```

### B3. EPS 修正趋势（最关键预警指标）

```python
if eps_trend is not None:
    print(f"\n=== EPS修正趋势 ===")
    # eps_trend 包含 current, 7daysAgo, 30daysAgo, 60daysAgo, 90daysAgo
    time_points = ["current", "7daysAgo", "30daysAgo", "60daysAgo", "90daysAgo"]
    labels = ["当前", "7天前", "30天前", "60天前", "90天前"]

    for period in eps_trend.index:
        row = eps_trend.loc[period]
        values = []
        for tp in time_points:
            v = row.get(tp) if isinstance(row, pd.Series) else None
            values.append(v if v else None)

        if any(values):
            print(f"\n  {period}:")
            for label, v in zip(labels, values):
                if v:
                    print(f"    {label}: {v}")

    # 计算修正幅度
    for period in eps_trend.index:
        row = eps_trend.loc[period]
        current = row.get("current")
        old_90 = row.get("90daysAgo")
        if current and old_90 and old_90 != 0:
            change = (current - old_90) / abs(old_90) * 100
            direction = "↑ 分析师持续上修" if change > 3 else ("↓ 分析师持续下修" if change < -3 else "→ 基本持平")
            print(f"  90天修正幅度 ({period}): {change:+.1f}% | {direction}")
```

### B4. 上修/下修 比值

```python
if eps_revisions is not None:
    print(f"\n=== 修正方向比 ===")
    for period in eps_revisions.index:
        row = eps_revisions.loc[period]
        up_7d = row.get("upLast7days", 0) or 0
        down_7d = row.get("downLast7days", 0) or 0
        up_30d = row.get("upLast30days", 0) or 0
        down_30d = row.get("downLast30days", 0) or 0

        total_7d = up_7d + down_7d
        total_30d = up_30d + down_30d

        if total_7d > 0:
            ratio_7d = up_7d / total_7d
            signal_7d = "🟢 强烈看多" if ratio_7d > 0.7 else ("🔴 看空" if ratio_7d < 0.3 else "🟡 分歧")
            print(f"  {period} 近7天: {up_7d}↑ / {down_7d}↓ (比率 {ratio_7d:.0%}) | {signal_7d}")

        if total_30d > 0:
            ratio_30d = up_30d / total_30d
            signal_30d = "🟢 强烈看多" if ratio_30d > 0.7 else ("🔴 看空" if ratio_30d < 0.3 else "🟡 分歧")
            print(f"  {period} 近30天: {up_30d}↑ / {down_30d}↓ (比率 {ratio_30d:.0%}) | {signal_30d}")
```

**修正比值解读**：

| 比值（上修/总计） | 信号 | 授信审批含义 |
|:---:|:---:|------|
| > 0.7 | 强烈乐观 | 盈利预期改善，偿债能力预期增强 |
| 0.5-0.7 | 温和乐观 | 正常波动，无预警信号 |
| 0.3-0.5 | 分歧较大 | 需关注分歧原因（行业周期？公司特定风险？） |
| < 0.3 | 强烈悲观 | ⚠ 高频预警：分析师集体下修，可能预示盈利恶化 |

### B5. 增长预期 vs 同行

```python
if growth_est is not None:
    print(f"\n=== 增长预期对比 ===")
    for idx in growth_est.index:
        row = growth_est.loc[idx]
        company = row.get("stockSymbol") or row.get("longName") or idx
        q_est = row.get("growth") or row.get("nextQ")
        y_est = row.get("longGrowth") or row.get("nextY")
        ind_est = row.get("industry")
        sec_est = row.get("sector")
        print(f"  {company}: Q季={q_est}, Y年={y_est}, 行业平均={ind_est}, 板块平均={sec_est}")
```

---

## Part C：综合输出（授信审批专用）

### 输出结构

按以下顺序呈现分析结果：

**1. 盈利结论摘要**
一句话总结：最新季度beat/miss情况，利润率方向，分析师修正趋势

**2. 盈利历史记录表**
最近4季 EPS 实际 vs 预期、惊喜幅度、Beat率统计

**3. 利润率趋势表**
最近4季：收入、毛利率、营业利润率、净利率、EPS — 含YoY增速和方向箭头

**4. 分析师一致预期**
EPS/收入预估（当季、下季、当年、明年），含高/低范围和分析师覆盖人数

**5. EPS修正趋<mxfile>（核心预警指标）**
90天修正轨迹表 + 趋势判断。⚠ 持续下修是信用风险先行指标。

**6. 修正方向比（上修/下修）**
近7天和近30天上修占比，含信号灯解释

**7. 增长预期对比**
公司 vs 行业 vs 板块增长预期

**8. 授信审批专项评估**

| 评估维度 | 判断 | 风险等级 |
|---------|------|:------:|
| 盈利稳定性 | Beat率 >75% 且 惊喜幅度稳定 → 稳定 | 低/中/高 |
| 利润率趋势 | 毛利率/营业利润率连续2季改善 → 改善 | 低/中/高 |
| 收入增长 | YoY正增长且无减速信号 → 增长 | 低/中/高 |
| 分析师修正方向 | 90天上修 >3% → 乐观 | 低/中/高 |
| 修正分歧度 | 上修占比 >50% → 一致向好 | 低/中/高 |

**风险预警触发条件**：
- ⚠ 连续2季 EPS miss（低于预期）→ 触发经营恶化预警
- ⚠ 毛利率连续3季下降 → 触发竞争加剧/成本失控预警
- ⚠ EPS修正90天下降 >5% → 触发盈利预期恶化的早期预警
- ⚠ 上修占比持续 <40% → 触发分析师集体悲观预警

---

## 异常处理

| 情况 | 处理方式 |
|------|---------|
| `earnings_hist` 为空 | 说明该公司可能是新上市或数据未覆盖。标注"无盈利历史数据"，仅做分析师预期分析 |
| 季度数据列数不足4季 | 用可用数据，标注数据不完整和置信度 |
| `eps_trend` 为 None | 跳过修正趋势分析，标注无可用数据 |
| `eps_revisions` 为 None 或全0 | 标注无分析师覆盖或覆盖不足，此情况下盈利分析置信度低 |
| `growth_est` 缺失 | 仅以历史增速代替，标注数据源限制 |
| A股/港股数据缺失 | 使用 `企业公开信息抓取` skill 提取年报数据替代季报分析；修正趋势可能不可用 |

---

## 注意事项

- Yahoo Finance 数据有15分钟延迟，分析师预估可能滞后于实时一致预期数小时到数天
- 分析师预估反映的是共识，不是确定性；惊喜/失望本身就说明预测不完美
- 修正趋势是信号而非保证 — 可因单一事件（指引调整、宏观冲击）快速逆转
- 远期（+1y）增长预估本质上可靠性较低
- yfinance 数据非官方；关键决策必须交叉核对原始披露文件
- 不构成投资建议

---

## 使用示例

```
用户："分析一下腾讯最新季报表现"
→ TICKER = "0700.HK"
→ Part A: 盈利beat/miss + 利润率趋势
→ Part B: 分析师预期修正方向
→ Part C: 授信审批评估（关注游戏/广告/金融科技各板块盈利质量）

用户："茅台的盈利质量怎么样？分析师怎么看？"
→ TICKER = "600519.SS"
→ 重点关注：毛利率稳定性（白酒行业核心指标）、收入增速轨迹、分析师修正方向
→ 授信审批：消费龙头盈利高度稳定→偿债能力强，关注批发价/渠道库存对利润率的潜在影响

用户："比亚迪最新季报beat了吗？盈利趋势如何？"
→ TICKER = "002594.SZ" 或 "1211.HK"
→ 关注：汽车业务毛利率趋势、规模效应是否兑现、分析师对价格战的预期修正
```

---

**关联 Skill**：
- `企业公开信息抓取` — A股/港股年报PDF数据提取（替代yfinance缺失数据）
- `企业估值分析` — DCF + 相对估值（盈利预测是DCF的关键输入）
- `现金流测算` — 项目偿债现金流测算（盈利数据用于DSCR模型输入）
