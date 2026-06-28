# 港交所披露易（HKEXnews）API 接口规范

## 概述

港交所披露易网站（https://www.hkexnews.hk）是港股上市公司公告的官方发布平台。
与巨潮网不同，港交所无公开正式API，以下接口均通过逆向分析网页请求获得。

**⚠️ 重要提示**：
- 港交所部分接口使用 **HTTP/2.0** 协议，标准 `requests` 库可能无法访问，需使用 `httpx` 或 `hyper` 库
- 披露易搜索页面为 JavaScript 动态渲染，`WebFetch` 无法获取完整表单参数
- 建议用浏览器 F12 → Network 面板抓包验证实际请求

---

## 1. 公告标题搜索 — titleSearchServlet

**端点**：`GET https://www1.hkexnews.hk/search/titleSearchServlet.do`

### 请求参数

| 参数 | 必填 | 说明 | 示例值 |
|------|------|------|--------|
| `sortDir` | 是 | 排序方向 | `0`（升序）/ `1`（降序） |
| `sortByOptions` | 是 | 排序字段 | `DateTime` |
| `category` | 是 | 公告大类 | `0`（全部），参见下方分类代码 |
| `market` | 是 | 市场 | `SEHK`（主板）/ `GEM`（创业板） |
| `stockId` | 是 | 股票内部ID | `-1`（全部）或具体ID，如 `1000226850` |
| `documentType` | 是 | 文档类型 | `-1`（全部），参见下方类型代码 |
| `fromDate` | 是 | 起始日期 | `20220101`（YYYYMMDD） |
| `toDate` | 是 | 截止日期 | `20261231`（YYYYMMDD） |
| `title` | 否 | 标题关键词 | `年度报告` |
| `searchType` | 是 | 搜索类型 | `1` |
| `t1code` | 是 | 一级分类代码 | `40000`（上市公司），参见下方代码表 |
| `t2Gcode` | 是 | 二级分组代码 | `-2`（全部） |
| `t2code` | 是 | 二级分类代码 | `40100`（公告及通函），参见下方代码表 |
| `rowRange` | 是 | 每次返回行数 | `2000` |
| `lang` | 是 | 语言 | `zh`（中文）/ `EN`（英文） |

### 请求示例

```python
import requests
import json

def search_hkex_announcements(stock_id="-1", from_date="20220101", to_date="20261231",
                                t1code="40000", t2code="40100", title=""):
    """查询港交所公告列表"""
    base_url = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": stock_id,
        "documentType": "-1",
        "fromDate": from_date,
        "toDate": to_date,
        "title": title,
        "searchType": "1",
        "t1code": t1code,
        "t2Gcode": "-2",
        "t2code": t2code,
        "rowRange": "2000",
        "lang": "zh",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml",
    }
    resp = requests.get(base_url, params=params, headers=headers, timeout=15)
    outer = resp.json()
    # 响应为双层JSON：外层 {"result": "...内层JSON字符串..."}
    inner = json.loads(outer["result"])
    return inner
```

### 响应格式

返回双层 JSON，需两次解析：

```python
outer = resp.json()                    # 第一层
inner = json.loads(outer["result"])    # 第二层
```

**内层每条记录字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `STOCK_CODE` | 股票代码 | `00700` |
| `STOCK_NAME` | 股票名称 | `騰訊控股` |
| `TITLE` | 公告标题 | `二零二四年年報` |
| `FILE_LINK` | PDF 相对路径 | `listco/tencent/2025/.../annual.pdf` |
| `FILE_INFO` | 文件信息 | `多檔案` 时跳过（多文件包裹，非单一PDF） |
| `DATE_TIME` | 发布日期时间 | `2025/03/28` |

---

## 2. PDF 下载

### 下载链接构造

```python
pdf_url = f"https://www1.hkexnews.hk/{item['FILE_LINK']}"
```

### 下载函数

```python
def download_hkex_pdf(url: str, save_path: str) -> bool:
    """下载港交所PDF文件"""
    try:
        resp = requests.get(url, timeout=30, stream=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = os.path.getsize(save_path) / 1024
        print(f"  ✅ 已下载: {os.path.basename(save_path)} ({size_kb:.1f} KB)")
        return True
    except Exception as e:
        print(f"  ❌ 下载失败: {url} — {e}")
        return False
```

---

## 3. 分类代码参考

### t1code — 一级分类

| 代码 | 含义 |
|------|------|
| `40000` | 上市公司（Listed Companies） |

### t2code — 二级分类

| 代码 | 含义 | 对应类型 |
|------|------|---------|
| `40100` | 公告及通函（Announcements and Notices） | 日常公告 |
| `40200` | 年度报告（Annual Reports） | ⭐ 年报 |
| `40300` | 中期报告（Interim Reports） | 半年报 |
| `40400` | 季度报告（Quarterly Reports） | 季报 |
| `40500` | 招股章程（Prospectuses） | IPO招股书 |
| `40600` | 通函（Circulars） | 股东通函 |

> **⚠️ 注意**：以上代码来自逆向分析开源项目，港交所可能随时调整。建议通过浏览器 F12 抓包验证。

---

## 4. stockId 查找

港交所使用内部 `stockId`（纯数字，如 `1000226850`）而非股票代码（如 `00700`）进行查询。

### 方法一：通过高级搜索页面 URL

直接在浏览器中访问：
```
https://www1.hkexnews.hk/search/titlesearch.xhtml?market=SEHK&stockId={stockId}&category=0
```

### 方法二：通过搜索 API 反查

```python
def find_stock_id(stock_code: str, stock_name: str = "") -> str:
    """
    通过股票代码或名称查找港交所内部 stockId。
    
    方法：搜索该股票的公告，从返回结果中提取 stockId。
    """
    # 尝试用 titleSearchServlet 搜索
    base_url = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": "-1",
        "documentType": "-1",
        "fromDate": "20250101",
        "toDate": "20261231",
        "title": stock_name or stock_code,
        "searchType": "1",
        "t1code": "40000",
        "t2Gcode": "-2",
        "t2code": "40100",
        "rowRange": "10",
        "lang": "zh",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(base_url, params=params, headers=headers, timeout=15)
    outer = resp.json()
    inner = json.loads(outer["result"])
    
    for item in inner:
        if item.get("STOCK_CODE", "").endswith(stock_code.lstrip("0")) or \
           stock_name in item.get("STOCK_NAME", ""):
            return str(item.get("STOCK_ID", ""))
    return "-1"
```

### 方法三：WebSearch 兜底

若 API 无法获取 stockId，使用 WebSearch：
```
site:hkexnews.hk {股票代码} {公司名称}
```
从搜索结果 URL 中提取 stockId 参数。

---

## 5. 港股年报筛选规则

### 年度报告筛选

```python
def is_hkex_annual_report(title: str) -> bool:
    """判断是否为港股年度报告（排除摘要和英文版）"""
    # 匹配中文标题
    zh_keywords = ["年度报告", "年報", "年报"]
    if not any(kw in title for kw in zh_keywords):
        return False
    # 排除
    exclude = ["摘要", "簡要", "英文", "English", "更正", "補充", "补充", "修订"]
    return not any(kw in title for kw in exclude)
```

### 招股说明书筛选

```python
def is_hkex_prospectus(title: str) -> bool:
    """判断是否为招股说明书"""
    keywords = ["招股说明书", "招股章程", "Prospectus"]
    return any(kw in title for kw in keywords)
```

### 重大事项公告筛选

```python
HKEX_MAJOR_EVENT_KEYWORDS = [
    "重大交易", "須予公布的交易", "非常重大收购", "Very Substantial Acquisition",
    "主要交易", "Major Transaction", "收购", "Acquisition",
    "配售", "Placing", "供股", "Rights Issue",
    "关连交易", "Connected Transaction",
    "股价敏感信息", "Price Sensitive Information",
    "债务重组", "Debt Restructuring",
    "清盘", "Winding Up", "接管", "Receivership",
]
```

---

## 6. 港股年报PDF提取注意事项

### 与A股年报的关键差异

| 维度 | A股年报 | 港股年报 |
|------|---------|---------|
| **语言** | 简体中文 | 繁体中文为主，部分有英文 |
| **货币单位** | 人民币（元/万元/亿元） | 港币/人民币（千港元/百万港元） |
| **报表格式** | 标准化三表格式 | IFHKFRS/HKAS 格式，科目名有差异 |
| **PDF结构** | 通常为单一完整PDF | 可能拆分为"多檔案"（多个PDF片段） |
| **财报章节** | 在固定页码范围 | 无固定位置，需关键词搜索 |
| **科目名差异** | "应收账款" | "應收賬款"（繁体） |
| **合并报表标注** | "合并资产负债表" | "綜合財務狀況表" |
| **利润表名** | "利润表" | "綜合損益表" / "綜合全面收益表" |

### 港股科目名映射（简繁+命名差异）

```python
HK_STOCK_ITEM_MAP = {
    # 资产负债表
    "綜合財務狀況表": "bs",
    "財務狀況表": "bs",
    "非流動資產": "bs",
    "流動資產": "bs",
    "現金及現金等價物": "bs",        # 对应A股 "货币资金"
    "應收賬款": "bs",                 # 对应A股 "应收账款"
    "應收票據": "bs",                 # 对应A股 "应收票据"
    "存貨": "bs",                      # 对应A股 "存货"
    "物業、廠房及設備": "bs",          # 对应A股 "固定资产"
    "使用權資產": "bs",               # 对应A股 "使用权资产"
    "商譽": "bs",                     # 对应A股 "商誉"
    "應付賬款": "bs",                 # 对应A股 "应付账款"
    "借款": "bs",                      # 对应A股 "短期借款+长期借款"
    "股本": "bs",                     # 对应A股 "股本"
    "儲備": "bs",                     # 对应A股 "资本公积+盈余公积等"
    
    # 利润表
    "綜合損益表": "is",
    "綜合全面收益表": "is",
    "收入": "is",                      # 对应A股 "营业收入"
    "銷售成本": "is",                  # 对应A股 "营业成本"
    "毛利": "is",                     # 对应A股 "毛利"
    "銷售及分銷成本": "is",            # 对应A股 "销售费用"
    "行政開支": "is",                  # 对应A股 "管理费用"
    "研發開支": "is",                  # 对应A股 "研发费用"
    "融資成本": "is",                  # 对应A股 "财务费用"
    "除稅前盈利": "is",               # 对应A股 "利润总额"
    "所得稅開支": "is",               # 对应A股 "所得税费用"
    "年內溢利": "is",                  # 对应A股 "净利润"
    "本公司擁有人應佔": "is",          # 对应A股 "归属于母公司"
    
    # 现金流量表
    "綜合現金流量表": "cf",
    "現金流量表": "cf",
    "經營活動": "cf",                  # 对应A股 "经营活动"
    "投資活動": "cf",                  # 对应A股 "投资活动"
    "融資活動": "cf",                  # 对应A股 "筹资活动"
}
```

### 单位处理

港股年报常见单位：千港元（HK$'000）、百万港元（HK$M）、千人民币（RMB'000）

```python
HK_UNIT_CONVERSION = {
    "HK$'000": 0.1,          # 千港元 → 万元（乘以0.1，因为1000港元≈1000人民币/10=100万元... 不对）
    "HK$M": 100,             # 百万港元 → 万元（×100）
    "RMB'000": 0.1,           # 千人民币 → 万元
    "RMBM": 100,              # 百万人民币 → 万元
    "千元": 0.1,              # 千元 → 万元
    "百万元": 100,            # 百万元 → 万元
}

def convert_hk_to_wanyuan(value: float, source_unit: str, hk_rate: float = 0.92) -> float:
    """
    港股金额单位转换。
    
    Args:
        value: 原始数值
        source_unit: 原始单位（如 "HK$'000"）
        hk_rate: 港币兑人民币汇率，默认0.92
    
    Returns:
        万元人民币
    """
    # 先转为基础单位（元）
    multiplier = HK_UNIT_CONVERSION.get(source_unit, 1)
    value_wanyuan = value * multiplier  # 已转为万元
    
    # 如果是港币，需乘汇率转为人民币
    if "HK" in source_unit or "港" in source_unit:
        value_wanyuan *= hk_rate
    
    return round(value_wanyuan, 2)
```

---

## 7. 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| titleSearchServlet 返回空 | stockId 参数错误 | 使用 find_stock_id() 或 WebSearch 查找正确 stockId |
| FILE_INFO 为 "多檔案" | 年报被拆分为多个PDF | 需下载所有分片后合并，或使用 GLM-4V 逐片提取 |
| PDF 无法下载（连接超时） | 港交所使用 HTTP/2.0 | 使用 `httpx` 库替代 `requests`：`pip install httpx` |
| 繁体中文科目名不匹配 | pdfplumber 分类器特征词为简体 | 需扩展 BS/IS/CF_ITEM_PATTERNS 加入繁体关键词 |
| 金额单位非万元 | 港股常用千港元/百万港元 | 使用 convert_hk_to_wanyuan 转换 |
| 年报中找不到"资产负债表" | 港股叫"財務狀況表" | 使用 HK_STOCK_ITEM_MAP 映射 |

---

## 8. 港股专用下载脚本调用

```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "C:\Users\LY\.workbuddy\skills\企业公开信息抓取\scripts\hkex_downloader.py" `
  --company "{公司名称}" --code "{股票代码如00700}" --stock-id "{stockId}" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\00-基础资料"
```

---

## 9. 补充信息源

### 港交所年报浏览器（ARE）
- URL: https://are.hkex.com.hk/home/zh
- 提供可视化的年报关键数据提取，可辅助验证

### 港交所简单搜索（近7天公告）
- URL: https://www1.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main_c.aspx
- 适合快速查找最新公告

### 沪深港通持股数据
- URL: https://www.hkexnews.hk/sdw/search/mutualmarket.aspx
- 查询北水持仓变动
