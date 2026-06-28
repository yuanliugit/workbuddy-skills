# 财务指标计算公式

## 单位说明

所有财务数据统一为**万元**，比率类指标保留4位小数（展示时转为百分比）。

---

## 一、偿债能力指标

| 指标 | 计算公式 | 说明 |
|------|---------|------|
| 资产负债率 | 负债合计 / 资产总计 | 衡量总体负债水平 |
| 有息负债率 | 有息负债合计 / 资产总计 | 有息负债 = 短借 + 长借 + 应付债券 + 一年内到期非流动负债 |
| 流动比率 | 流动资产合计 / 流动负债合计 | 短期偿债能力，≥1为基准 |
| 速动比率 | (流动资产 - 存货 - 预付账款) / 流动负债合计 | 剔除变现较慢资产 |
| 利息保障倍数 | EBIT / 利息费用 | EBIT = 利润总额 + 利息费用 |
| 净负债率 | (有息负债 - 货币资金) / 所有者权益合计 | 净有息负债对净资产覆盖 |

```python
def calc_solvency(data: dict) -> dict:
    bs = data["balance_sheet"]      # 资产负债表
    is_ = data["income_statement"]   # 利润表

    total_assets = bs.get("total_assets", 0)
    total_liab = bs.get("total_liabilities", 0)
    current_assets = bs.get("current_assets", 0)
    current_liab = bs.get("current_liabilities", 0)
    inventory = bs.get("inventory", 0)
    prepaid = bs.get("prepaid_expenses", 0)
    cash = bs.get("monetary_funds", 0)
    equity = bs.get("total_equity", 0)

    # 有息负债
    interest_bearing_debt = (
        bs.get("short_term_loan", 0) +
        bs.get("long_term_loan", 0) +
        bs.get("bonds_payable", 0) +
        bs.get("current_portion_lt_debt", 0)
    )

    profit_before_tax = is_.get("profit_before_tax", 0)
    interest_expense = is_.get("interest_expense", 0)
    ebit = profit_before_tax + interest_expense

    return {
        "资产负债率": total_liab / total_assets if total_assets else None,
        "有息负债率": interest_bearing_debt / total_assets if total_assets else None,
        "流动比率": current_assets / current_liab if current_liab else None,
        "速动比率": (current_assets - inventory - prepaid) / current_liab if current_liab else None,
        "利息保障倍数": ebit / interest_expense if interest_expense else None,
        "净负债率": (interest_bearing_debt - cash) / equity if equity else None,
    }
```

---

## 二、盈利能力指标

| 指标 | 计算公式 |
|------|---------|
| 毛利率 | (营业收入 - 营业成本) / 营业收入 |
| 净利率 | 净利润 / 营业收入 |
| ROE（加权） | 净利润 / 加权平均净资产 |
| ROA | 净利润 / 平均总资产 |
| EBITDA | EBIT + 折旧摊销 |
| EBITDA利润率 | EBITDA / 营业收入 |

```python
def calc_profitability(data: dict, prior_data: dict = None) -> dict:
    is_ = data["income_statement"]
    bs = data["balance_sheet"]

    revenue = is_.get("revenue", 0)
    cost = is_.get("cost_of_revenue", 0)
    net_profit = is_.get("net_profit", 0)
    profit_before_tax = is_.get("profit_before_tax", 0)
    interest_expense = is_.get("interest_expense", 0)
    da = is_.get("depreciation_amortization", 0)

    equity = bs.get("total_equity", 0)
    total_assets = bs.get("total_assets", 0)

    # 加权平均净资产（简化：期初期末均值）
    prior_equity = prior_data["balance_sheet"].get("total_equity", equity) if prior_data else equity
    avg_equity = (equity + prior_equity) / 2

    prior_assets = prior_data["balance_sheet"].get("total_assets", total_assets) if prior_data else total_assets
    avg_assets = (total_assets + prior_assets) / 2

    ebit = profit_before_tax + interest_expense
    ebitda = ebit + da

    return {
        "毛利率": (revenue - cost) / revenue if revenue else None,
        "净利率": net_profit / revenue if revenue else None,
        "ROE加权": net_profit / avg_equity if avg_equity else None,
        "ROA": net_profit / avg_assets if avg_assets else None,
        "EBITDA": ebitda,
        "EBITDA利润率": ebitda / revenue if revenue else None,
    }
```

---

## 三、营运能力指标

| 指标 | 计算公式 |
|------|---------|
| 总资产周转率 | 营业收入 / 平均总资产 |
| 存货周转率 | 营业成本 / 平均存货 |
| 应收账款周转率 | 营业收入 / 平均应收账款 |
| 应收账款周转天数 | 365 / 应收账款周转率 |
| 存货周转天数 | 365 / 存货周转率 |

---

## 四、现金流质量指标

| 指标 | 计算公式 | 说明 |
|------|---------|------|
| 收现比 | 销售商品收到的现金 / 营业收入 | >1 说明回款质量好 |
| 经营现金流/净利润 | 经营活动现金流净额 / 净利润 | 验证利润含金量 |
| 自由现金流 | 经营现金流净额 - 资本支出 | 资本支出 = 购建固定资产现金 |
| EBITDA偿债倍数 | EBITDA / 有息负债合计 | 衡量债务可持续性 |

---

## 五、成长能力指标

| 指标 | 计算公式 |
|------|---------|
| 营收增长率 | (本期营收 - 上期营收) / 上期营收 |
| 净利润增长率 | (本期净利 - 上期净利) / \|上期净利\| |
| 总资产增长率 | (本期总资产 - 上期总资产) / 上期总资产 |

---

## 六、异常检测规则

```python
ANOMALY_RULES = {
    "资产负债率":     {"min": 0, "max": 1.2,  "warn": "超过120%，高杠杆风险"},
    "流动比率":       {"min": 0.5, "max": 10,  "warn": "低于0.5，短期流动性风险"},
    "毛利率":         {"min": -0.5, "max": 1.0, "warn": "超出正常范围"},
    "净利率":         {"min": -1.0, "max": 1.0, "warn": "超出正常范围"},
    "收现比":         {"min": 0.3, "max": 3.0,  "warn": "收现比异常"},
    "营收增长率_YoY": {"threshold": 0.5,        "warn": "同比变动超50%，需关注"},
}
```
