# PDF财务报表精准提取规范（v4）

## 概述

财务报表PDF提取采用**三层架构** + **科目名自动分类器**：

1. **第一层**：pdfplumber 科目分类器（v4） — 主力方案，按科目名特征词自动分类
2. **第二层**：pdfminer 纯文本行匹配 — 备用方案
3. **第三层**：GLM-4V 视觉模型截图识别 — 兜底方案

### v3→v4 核心改进

| 维度 | v3（旧版） | v4（当前） |
|------|-----------|-----------|
| 报表分割 | 按页码范围 | 按科目名特征词自动分类 |
| 跨页数据泄漏 | 严重（BS末尾+IS开头同页） | 已解决（classify_item分类） |
| 列格式 | 仅9列 | 3/5/7/9列自适应 |
| 科目名位置 | 仅col1 | col0/col1双检 |
| 提取范围 | 到equity_change前一页 | 含equity_change页 |
| 报表定位 | 单轮匹配 | 3轮递进（精确→宽松→表头） |

---

## 一、科目名自动分类器

### 设计原理

不再按页码范围分割报表（同一页上BS末尾+IS开头混在一起），改为提取BS到权益变动表之间所有表格行，按科目名特征词自动分类。

### 特征词库

```python
BS_ITEM_PATTERNS = [
    '货币资金', '交易性金融资产', '应收票据', '应收账款', '应收款项融资',
    '预付款项', '其他应收款', '存货', '合同资产', '其他流动资产', '流动资产合计',
    '长期股权投资', '固定资产', '在建工程', '使用权资产', '无形资产', '商誉',
    '长期待摊费用', '递延所得税资产', '其他非流动资产', '非流动资产合计',
    '资产总计',
    '短期借款', '应付票据', '应付账款', '合同负债', '应付职工薪酬',
    '应交税费', '其他应付款', '一年内到期的非流动负债', '其他流动负债', '流动负债合计',
    '长期借款', '应付债券', '租赁负债', '预计负债', '递延收益',
    '非流动负债合计', '负债合计',
    '股本', '资本公积', '盈余公积', '未分配利润', '少数股东权益',
    '归属于母公司所有者权益合计', '所有者权益合计', '负债和所有者权益总计',
]

IS_ITEM_PATTERNS = [
    '营业总收入', '营业收入', '营业总成本', '营业成本', '税金及附加',
    '销售费用', '管理费用', '研发费用', '财务费用', '利息费用', '利息收入',
    '其他收益', '投资收益', '公允价值变动收益', '信用减值损失', '资产减值损失',
    '资产处置收益', '营业利润', '营业外收入', '营业外支出',
    '利润总额', '所得税费用', '净利润', '持续经营净利润',
    '归属于母公司', '少数股东损益', '综合收益总额', '每股收益',
    '其他综合收益', '其他权益工具', '重新计量设定受益计划',
    '权益法下可转损益', '企业自身信用风险',
]

CF_ITEM_PATTERNS = [
    '销售商品、提供劳务收到的现金', '收到的税费返还', '收到其他与经营活动',
    '经营活动现金流入小计', '购买商品、接受劳务支付的现金',
    '支付给职工以及为职工支付的现金', '支付的各项税费',
    '经营活动现金流出小计', '经营活动产生的现金流量净额',
    '收回投资收到的现金', '取得投资收益收到的现金',
    '购建固定资产、无形资产和其他长期资产支付的现金',
    '投资活动产生的现金流量净额',
    '取得借款收到的现金', '偿还债务支付的现金',
    '分配股利、利润或偿付利息支付的现金', '筹资活动产生的现金流量净额',
    '现金及现金等价物净增加额', '期末现金及现金等价物余额',
    '客户存款和同业存放', '向中央银行借款', '吸收存款',
    '存放中央银行款项', '拆入资金', '回购业务资金',
    '收到的保险费', '赔付支出', '保单红利支出', '分保费用',
    '支付的手续费及佣金',
]
```

### 分类函数

```python
def classify_item(name: str) -> str:
    """根据科目名特征词自动分类到 BS/IS/CF"""
    n = name.strip().lstrip('　 ')
    for pat in BS_ITEM_PATTERNS:
        if pat in n:
            return 'bs'
    for pat in IS_ITEM_PATTERNS:
        if pat in n:
            return 'is'
    for pat in CF_ITEM_PATTERNS:
        if pat in n:
            return 'cf'
    return 'unknown'
```

---

## 二、报表定位算法：3轮递进

### 第1轮：精确标题匹配

```python
REPORT_MARKERS = {
    "1、资产负债表": "bs_consolidated",
    "2、利润表": "is_consolidated",
    "3、现金流量表": "cf_consolidated",
    "4、所有者权益变动表": "equity_change",
}
```

### 第2轮：宽松关键词匹配

适用于标题格式不标准的年报（如2023年部分年报无"2、利润表"标题）：

```python
FALLBACK_MARKERS = {
    "资产负债表": "bs_consolidated",
    "利润表": "is_consolidated",
    "现金流量表": "cf_consolidated",
    "所有者权益变动表": "equity_change",
    "所有者权益变动": "equity_change",
}
```

### 第3轮：表格表头辅助定位

当无明确报表标题时，通过识别表格表头关键词定位：

```python
TABLE_HEADER_KEYWORDS = {
    "bs_consolidated": ["期末余额", "期初余额", "12月31日", "1月1日"],
    "is_consolidated": ["本期金额", "上期金额", "本年累计", "上年同期"],
    "cf_consolidated": ["本期金额", "上期金额"],
    "equity_change": ["上年期末余额", "本年期初余额"],
}
```

---

## 三、多列格式自适应

A股年报PDF常见4种列格式，必须自动检测：

| 列数 | 科目名列 | 本期值列 | 上期值列 | 常见年份 | 备注 |
|------|---------|---------|---------|---------|------|
| 3列 | 0 | 1 | 2 | 2025新版 | 简化单期格式 |
| 5列 | 1 | 3 | 4 | 部分公司 | 含行号列 |
| 7列 | 0 | 3 | 6 | 2023版 | 科目名在col0 |
| 9列 | 1 | 3 | 6 | 2022-2024版 | 标准双期格式 |

### 列格式检测函数

```python
def _detect_col_layout(n_cols: int) -> tuple:
    """根据列数自动检测科目名/本期值/上期值所在列"""
    if n_cols == 3:
        return (0, 1, 2)
    elif n_cols == 5:
        return (1, 3, 4)
    elif n_cols == 7:
        return (0, 3, 6)   # 科目名在col0
    elif n_cols == 9:
        return (1, 3, 6)   # 科目名在col1（默认）
    else:
        return (0, n_cols - 2, n_cols - 1)
```

### 9列/7列格式特殊处理

**CRITICAL**：9列/7列格式中，科目名有时在col0（如"股本"、"资本公积"），有时在col1（如"流动资产："），必须双检：

```python
def _parse_row(row, name_col, val_col, prev_col, n_cols):
    """解析单行，支持科目名在col0或col1的情况"""
    # 双检科目名位置
    name = row[name_col] or ""
    if not name.strip() and n_cols >= 7:
        # 9列/7列格式：科目名可能在col0
        alt_col = 0 if name_col == 1 else 1
        name = row[alt_col] or ""
        if name.strip():
            # 科目名在col0，值直接从col3/col6取
            pass

    # 提取本期值和上期值
    val_str = row[val_col] if val_col < len(row) else ""
    prev_str = row[prev_col] if prev_col < len(row) else ""

    return name.strip(), parse_number(val_str), parse_number(prev_str)
```

---

## 四、数值解析函数

```python
def parse_number(text: str) -> Optional[float]:
    """
    解析财务数值，统一转换为万元。
    支持格式：
    - 元级别数值（自动除以10000）
    - 万元数值（直接使用）
    - 亿元数值（乘以10000）
    - 带括号的负数：(123,456.78) → -123456.78
    - 破折号 — 表示0
    """
    if not text or text.strip() in ["—", "-", "－", "——", ""]:
        return 0.0

    text = text.strip().replace(",", "").replace(" ", "")

    # 括号负数
    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1]

    # 去除单位文字
    if text.endswith("亿元"):
        text = text[:-2]
        multiplier = 10000  # 亿元 → 万元
    elif text.endswith("万元"):
        text = text[:-2]
        multiplier = 1
    else:
        multiplier = 1  # 假定已为万元

    try:
        value = float(text) * multiplier
        return -value if is_negative else value
    except ValueError:
        return None
```

---

## 五、合并报表 vs 本部报表识别

```python
def identify_report_scope(text: str) -> str:
    """识别报表范围：合并 or 本部（母公司）"""
    if any(kw in text for kw in ["合并资产负债表", "合并利润表", "合并现金流量表"]):
        return "consolidated"
    elif any(kw in text for kw in ["母公司资产负债表", "本公司资产负债表", "母公司利润表"]):
        return "parent"
    return "unknown"
```

---

## 六、GLM-4V 视觉兜底方案

**触发条件**：pdfplumber 提取后关键科目缺失超过3个。

```python
import os, base64, requests, json, re

def extract_via_glm_vision(page_image_path: str, table_type: str) -> dict:
    """使用 GLM-4V 视觉模型从截图中提取财务表格"""
    api_key = os.environ.get("GLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("GLM_API_KEY 未配置")

    with open(page_image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = f"""请从图片中提取{table_type}的所有数据，以JSON格式返回。
格式要求：
- 每行包含 "科目名称" 和 "金额（万元）" 两个字段
- 如原始单位为元，请除以10000转换为万元
- 括号数值表示负数
- 只返回JSON，不要其他文字

示例格式：
{{"货币资金": 12345.67, "应收账款": 23456.78, ...}}
"""

    payload = {
        "model": "glm-4v-plus",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    }
    resp = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60
    )
    content = resp.json()["choices"][0]["message"]["content"]
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(json_match.group()) if json_match else {}
```

---

## 七、数据合并策略

```python
def merge_extracted_data(primary: dict, supplementary: dict) -> dict:
    """
    合并 pdfplumber（主） + GLM视觉（辅）数据。
    规则：主数据优先，辅数据仅补缺。
    """
    merged = {}
    for key in set(list(primary.keys()) + list(supplementary.keys())):
        p = primary.get(key)
        s = supplementary.get(key)
        if p and s:
            if isinstance(p, dict) and isinstance(s, dict):
                merged[key] = {**s, **p}  # p 覆盖 s
            else:
                merged[key] = p
        else:
            merged[key] = p or s
    return merged
```

---

## 八、数据输出格式

提取结果保存为 JSON，每个科目的值为**对象格式**：

```json
{
  "2024": {
    "statements": {
      "bs_consolidated": {
        "货币资金": {"期末": 12345.67, "期初": 23456.78},
        "应收账款": {"期末": 3456.78, "期初": 4567.89}
      },
      "is_consolidated": {
        "营业收入": {"本期": 56789.01, "上期": 45678.90}
      },
      "cf_consolidated": {
        "经营活动产生的现金流量净额": {"本期": -13435.82, "上期": -584.67}
      }
    }
  }
}
```

> **兼容性说明**：报告引擎的 getStmtVal() 必须同时支持数组格式 `[v1, v2]` 和对象格式 `{"期末": v1, "期初": v2}`。详见 SKILL.md 第6步。

---

## 九、数据校验

```python
def validate_financial_data(data: dict) -> list:
    """执行财务数据合理性校验，返回问题列表"""
    issues = []
    bs = data.get("balance_sheet", {})

    # 校验1: 资产 = 负债 + 权益
    total_assets = bs.get("total_assets", 0)
    total_liab = bs.get("total_liabilities", 0)
    total_equity = bs.get("total_equity", 0)
    if abs(total_assets - total_liab - total_equity) > 1:
        issues.append(f"资产负债表不平衡: 资产{total_assets}≠负债{total_liab}+权益{total_equity}")

    # 校验2: 净利润合理性
    is_ = data.get("income_statement", {})
    net_profit = is_.get("net_profit", 0)
    profit_before_tax = is_.get("profit_before_tax", 0)
    income_tax = is_.get("income_tax", 0)
    if profit_before_tax and abs(net_profit - (profit_before_tax - income_tax)) / abs(profit_before_tax) > 0.1:
        issues.append(f"净利润异常: {net_profit} vs 利润总额{profit_before_tax}-所得税{income_tax}")

    # 校验3: 关键科目是否缺失
    required_bs = ["total_assets", "total_liabilities", "total_equity", "current_assets", "current_liabilities"]
    required_is = ["revenue", "net_profit", "profit_before_tax"]
    for key in required_bs:
        if not bs.get(key):
            issues.append(f"资产负债表缺失科目: {key}")
    for key in required_is:
        if not is_.get(key):
            issues.append(f"利润表缺失科目: {key}")

    return issues
```

---

## 十、常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| BS末尾科目混入IS | 同一页包含BS负债侧+IS标题 | 使用 classify_item() 按科目名分类 |
| 科目名在col0取不到 | 9列格式中"股本"等在col0 | 双检 col0/col1 |
| 2023年无"2、利润表" | 年报格式变更 | 3轮递进定位 |
| CF末尾截断 | end_page 设为 eq_page-1 | 改为 end_page = eq_page |
| 7列格式误判为9列 | n>5 统一走9列逻辑 | 新增7列分支 (0,3,6) |
| GLM提取数据与pdfplumber冲突 | 两套数据同一科目值不同 | pdfplumber优先，GLM仅补缺 |
