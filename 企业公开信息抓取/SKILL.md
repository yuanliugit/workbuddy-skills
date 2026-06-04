---
name: "企业公开信息抓取"
description: >
  自动抓取A股/港股上市公司、IPO申报/聆讯阶段企业、债券发行企业的公开披露资料，从年报PDF精准提取财务数据，生成授信审查报告。
  覆盖：近三年年度报告+最新季报、年度审计报告及财务报表、信用评级报告、债券募集说明书、招股说明书、重大事项公告。
  A股数据来源：巨潮资讯网（cninfo.com.cn）、证监会信息披露平台（eid.csrc.gov.cn）、中国货币网、上海清算所、上交所/深交所债券平台、孔雀开屏系统。
  港股数据来源：港交所披露易（hkexnews.hk），含AP申请版本和PHIP聆讯后资料集。
  报告引擎：DeepSeek双模型路由（Flash补数据/Pro写分析）+ Node.js docx-js排版。
  输出：PDF资料包 + JSON结构化数据 + Word审查报告（7表6板块）。
  适用于银行授信审批、债券投资研究、信用风险评估等场景。
  触发条件：用户提到"分析XX公司"、"抓取XX公司年报"、"生成XX审查报告"、"下载年报/审计报告/评级报告"、
  "获取公开披露信息"、"企业信息抓取"、"债券募集说明书"、"审查报告"、"港股分析"、"IPO申报"、"聆讯"、"招股书"等。
agent_created: true
version: "3.3.0"
workspace: "D:\\Workbuddy\\企业披露信息抓取工作区"
---

# 企业公开信息抓取工作流

## 概述

本 Skill 在 WorkBuddy 本地环境中运行（Python 3.12 + Node.js 22 + PowerShell），自动完成：

1. **巨潮网公告下载** — A股年报、季报、审计报告、重大事项公告
2. **港交所披露易下载** — 港股年报、中报、招股书、重大事项公告
3. **A股IPO申报资料获取** — 招股说明书（申报稿）、问询函及回复（未上市企业）
4. **港股AP/PHIP下载** — 申请版本、聆讯后资料集（聆讯阶段企业）
5. **债券平台资料获取** — 评级报告、募集说明书（适用于发债企业）
6. **年报/招股书PDF精准提取** — pdfplumber 科目分类器 + GLM-4V 视觉兜底（支持A股简体+港股繁体科目）
7. **DeepSeek LLM 报告生成** — 双模型路由（Flash补数据/Pro写分析）
8. **Node.js 排版引擎** — docx-js 生成7表6板块专业Word报告
9. **Excel 财务底稿** — 标准化多 Sheet 输出
10. **迭代式交付** — 首次交付→检查验证→修订完善→对比评估→最终交付

---

## 数据时间范围标准（CRITICAL）

> **核心规则：所有资料及分析的时间范围统一为「近三个完整年度 + 近一期」。**

### 完整年度定义

- **近三个完整年度**：以当前日期所在年份的前三个完整会计年度为准。
  - 例如当前为 2026 年 6 月：完整年度为 2023、2024、2025 年度。
  - 例如当前为 2026 年 3 月（年报尚未大量披露）：完整年度为 2022、2023、2024 年度。
- **自动判定规则**：如果当前日期在每年 4 月 30 日之前，最新完整年度为上上年度；4 月 30 日起，最新完整年度为去年。

### 近一期定义

- **近一期**：最近一期已披露的季度/半年度/三季度报告。
  - 例：当前 2026 年 6 月，近一期为 2026 年一季报（如已披露）。

### 各资料类型时间要求

| 资料类型 | 时间范围 | 说明 |
|---------|---------|------|
| **年度报告** | 近三个完整年度 + 最新已披露年度 | 如 2026 年 6 月：2023/2024/2025 年度 + 2026 年一季报 |
| **年度审计报告** | **近三个完整年度** | ⚠️ 必须为审计报告（含审计意见），不可用年报替代 |
| **最新季报/中报/三季报** | **近一期** | 一季报（4月）、半年报（8月）、三季报（10月）取最新 |
| **信用评级报告** | 最新一期 + 近三个完整年度跟踪评级 | 含主体评级和债项评级 |
| **债券募集说明书** | 最新一期 | 优先选择最新发行批次的募集说明书 |
| **招股说明书** | 最新版（同名取披露时间最新者） | 含近三个完整年度+近一期财务数据 |
| **重大事项公告** | 近 2 年 | 含重大诉讼、重组、担保、股权质押等 |
| **财务指标计算** | 近三个完整年度 + 近一期的年化指标 | 趋势分析需覆盖完整年度 |

### 财务数据特殊要求

- **所有财务数据必须来自审计报告或经审计的年度报告**，不得使用未经审计的季报数据替代。
- **近一期数据（季报/中报）可以未经审计**，但需在报告中注明「未经审计」。
- **IPO企业**：招股说明书包含近三个完整年度+近一期审计数据，审计报告作为附件单独成册。

---

## 工作流路由

| 企业类型 | 判定条件 | 使用路径 |
|---------|---------|---------|
| A股上市公司 | 股票代码6位数字（0/3/6开头），交易所为上交所/深交所/北交所 | 标准路径（步骤1-8，跳过步骤2.5），第2步用巨潮网 |
| 港股上市公司 | 股票代码5位数字（0开头），交易所为港交所（HKEX） | 标准路径（步骤1-8，跳过步骤2.5），第2步用港交所披露易 |
| **A股IPO申报企业** | **无正式股票代码，在证监会/交易所审核中，有招股说明书（申报稿）** | **IPO路径（步骤1→2C→3→4-8），核心资料为招股说明书+审计报告** |
| **港股聆讯阶段企业** | **无正式股票代码或代码尚未生效，有AP/PHIP文件** | **IPO路径（步骤1→2D→3→4-8），核心资料为PHIP+审计报告** |
| 发债企业（含上市）| 有公司债/中票/短融/企业债等记录 | 完整路径（步骤1-8，含步骤2.5） |
| 仅分析现有PDF | 用户已提供本地PDF文件 | 快速路径（步骤3-8） |
| 仅下载资料 | 用户只需要PDF，不需要报告 | 下载路径（步骤1-2） |

---

## 工作流程

### 总览：四阶段迭代式交付

```
┌─────────────────────────────────────────────────────────────────┐
│  第一阶段：资料采集与初稿生成                                      │
│  确认公司信息 → 公告下载 → PDF提取 → GLM兜底 → 数据合并           │
│  → LLM报告生成 → Node.js排版 → 【首次交付 V1】                    │
├─────────────────────────────────────────────────────────────────┤
│  第二阶段：检查验证                                               │
│  完整性检查（资料/数据/章节覆盖）→ 准确性验证（关键科目交叉比对）    │
│  → 编制问题清单 → 【验证报告】                                    │
├─────────────────────────────────────────────────────────────────┤
│  第三阶段：修订完善                                               │
│  按问题清单逐项修正 → 缺失数据补采 → 重新生成报告                  │
│  → 【修订交付 V2】                                                │
├─────────────────────────────────────────────────────────────────┤
│  第四阶段：对比评估与最终交付                                      │
│  V1 ↔ V2 差异对比 → 质量评估（完整性/准确性/一致性）               │
│  → 判断是否需进一步优化 → 【最终交付 V-final】                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 步骤详解

### 第1步：收集公司基本信息

**1A — 判断上市/申报状态并获取公司基本信息**

首先判断企业处于哪个阶段：

| 股票代码格式 | 阶段 | 市场 | 示例 |
|-------------|------|------|------|
| 6位，0/3开头 | 已上市 | 深交所 | 002185、301357 |
| 6位，6开头 | 已上市 | 上交所 | 601398 |
| 6位，8/4开头 | 已上市 | 北交所 | 830799 |
| 5位，0开头 | 已上市 | 港交所（HKEX） | 00700、09988 |
| **无正式代码，有申报稿** | **IPO申报中** | **A股** | **证监会/交易所审核阶段** |
| **无正式代码或代码未生效，有AP/PHIP** | **聆讯阶段** | **港交所** | **披露易AP/PHIP列表中** |

使用 WebSearch 查询：
- A股已上市搜索格式：`{公司名称} 股票代码 注册资本 法定代表人 主营业务`
- 港股已上市搜索格式：`{公司名称} stock code 注册地 主营业务`
- **A股IPO企业搜索格式**：`{公司名称} 招股说明书 申报 IPO 审核 首次公开发行`
- **港股聆讯企业搜索格式**：`{公司名称} listing application hearing prospectus HKEX IPO`
- 确认：公司全称、股票代码（如有）、上市/IPO状态、交易所、注册资本/股本、实控人/控股股东、主营业务

**1B — 获取数据源标识（必须）**

根据企业阶段选择不同路径：

| 阶段 | 标识类型 | 获取方式 | 用途 |
|------|---------|---------|------|
| A股已上市 | 巨潮网 orgId | 调用 topSearch API（见下方） | 巨潮网公告查询必需参数 |
| 港股已上市 | 港交所 stockId | 调用 find_stock_id（见下方）或 WebSearch | 披露易公告查询必需参数 |
| A股IPO | 按板块指定 | 按板块选择：沪市1010/深市1017/北交所 | 招股说明书查询 |
| 港股聆讯 | AP列表索引 | 调用 AP JSON API（见下方） | AP/PHIP文件定位 |

**A股 — 获取巨潮网 orgId：**

```python
import requests, json

resp = requests.post(
    "http://www.cninfo.com.cn/new/information/topSearch/query",
    json={"keyWord": "{股票代码}", "maxSecNum": 10, "maxListNum": 5},
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10
)
data = resp.json()
# 从 data['stockList'] 中提取 orgId
# orgId 格式示例：9900003862
```

> **⚠️ 关键**：orgId 是巨潮网 API 的必需参数，缺少时返回0条。必须在此步骤获取并保存。
>
> **兜底方案**：如果 topSearch API 返回空，用 WebSearch 搜索 `site:cninfo.com.cn {股票代码}` 从 URL 中提取 orgId。

**港股 — 获取港交所 stockId：**

```python
import requests, json

def find_stock_id(stock_code: str, stock_name: str = "") -> str:
    """通过股票代码或名称查找港交所内部 stockId"""
    base_url = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    params = {
        "sortDir": "0", "sortByOptions": "DateTime",
        "category": "0", "market": "SEHK",
        "stockId": "-1", "documentType": "-1",
        "fromDate": "20240101", "toDate": "20261231",
        "title": stock_name or stock_code,
        "searchType": "1", "t1code": "40000",
        "t2Gcode": "-2", "t2code": "40200",
        "rowRange": "10", "lang": "zh",
    }
    resp = requests.get(base_url, params=params,
                       headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    outer = resp.json()
    inner = json.loads(outer["result"])
    for item in inner:
        if str(item.get("STOCK_CODE","")).lstrip("0") == stock_code.lstrip("0"):
            return str(item.get("STOCK_ID", ""))
    return "-1"
```

> **兜底方案**：如果 API 返回空，用 WebSearch 搜索 `site:hkexnews.hk {股票代码} {公司名称}` 从 URL 中提取 stockId。

**A股IPO — 获取招股说明书（申报稿）：**

**按板块选择官方信息源：**

| 板块 | 官方平台 | URL | WebSearch格式 |
|------|---------|-----|--------------|
| 沪市（主板+科创板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1010/index.html` | `site:eid.csrc.gov.cn/ipo/1010 {公司名称} 招股说明书` |
| 深市（主板+创业板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1017/index.html` | `site:eid.csrc.gov.cn/ipo/1017 {公司名称} 招股说明书` |
| 北交所 | 北交所审核信息披露 | `https://www.bse.cn/audit/audit_disclosure.html` | `site:bse.cn {公司名称} 招股说明书` |

> **⚠️ 核心规则**：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。

> **⚠️ 证监会平台无API**：eid.csrc.gov.cn 和 bse.cn 均无公开JSON API，需通过 WebSearch 或 agent-browser skill 访问。

**巨潮网备选查询（可编程，全市场覆盖）：**

```python
# 证监会信息披露平台（eid.csrc.gov.cn）无法直接API调用
# 使用 WebSearch 查找招股说明书下载源
# 搜索关键词：site:cninfo.com.cn {公司名称} 招股说明书 申报稿
# 或：site:eid.csrc.gov.cn {公司名称} 招股说明书

# 巨潮网也可查IPO招股书（hisAnnouncement接口，category=category_sc_gk_ssgs）
import requests, json

resp = requests.post(
    "http://www.cninfo.com.cn/new/hisAnnouncement/query",
    data={
        "pageNum": 1, "pageSize": 30,
        "column": "szse",  # 或 sse
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": "{公司名称}",
        "secid": "",
        "category": "category_sc_gk_ssgs",  # 首次公开发行及上市类别
        "trade": "",
        "seDate": "2024-01-01~2026-12-31",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    },
    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    timeout=15
)
data = resp.json()
# 从 data['announcements'] 中筛选包含"招股说明书"的公告
# 下载链接拼接：http://static.cninfo.com.cn/{adjunctUrl}
```

> **备选数据源**：东方财富网IPO数据中心（data.eastmoney.com/xg/ipo）提供IPO审核进度和招股书下载链接。
>
> **兜底方案**：如果API均不可用，使用 WebSearch 搜索 `site:cninfo.com.cn {公司名称} 招股说明书` 或 `site:eastmoney.com {公司名称} IPO 招股书` 获取下载链接。

**港股聆讯 — 获取AP/PHIP文件列表：**

```python
import requests, json, time

def get_hkex_ap_list(board: str = "sehk", include_phip: bool = True) -> list:
    """
    获取港交所活跃申请版本（AP）和聆讯后资料集（PHIP）列表。
    
    Args:
        board: "sehk"（主板）或 "gem"（创业板）
        include_phip: 是否包含PHIP文件
    Returns:
        list of dict: [{name, date, id, pdf_url, doc_type}, ...]
    """
    results = []
    ts = str(int(time.time() * 1000))  # 防缓存时间戳
    
    # 活跃申请版本（AP）
    ap_url = f"https://www1.hkexnews.hk/ncms/json/eds/appactive_app_{board}_e.json?_={ts}"
    resp = requests.get(ap_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    data = resp.json()
    for item in data.get("app", []):
        date_str = item.get("d", "")
        # 日期格式 DD/MM/YYYY → YYYY-MM-DD
        parts = date_str.split("/")
        if len(parts) == 3:
            date_fmt = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            date_fmt = date_str
        pdf_url = "https://www1.hkexnews.hk/app/" + item.get("ls", [{}])[0].get("u1", "")
        results.append({
            "name": item.get("a", ""),
            "date": date_fmt,
            "id": item.get("id", ""),
            "pdf_url": pdf_url,
            "doc_type": "AP",  # Application Proof
        })
    
    # PHIP（聆讯后资料集）
    if include_phip:
        phip_url = f"https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_{board}_c.json?_={ts}"
        resp2 = requests.get(phip_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data2 = resp2.json()
        for item in data2.get("app", []):
            date_str = item.get("d", "")
            parts = date_str.split("/")
            if len(parts) == 3:
                date_fmt = f"{parts[2]}-{parts[1]}-{parts[0]}"
            else:
                date_fmt = date_str
            pdf_url = "https://www1.hkexnews.hk/app/" + item.get("ls", [{}])[0].get("u1", "")
            results.append({
                "name": item.get("a", ""),
                "date": date_fmt,
                "id": item.get("id", ""),
                "pdf_url": pdf_url,
                "doc_type": "PHIP",
            })
    
    return results

# 使用示例：按公司名称筛选
all_docs = get_hkex_ap_list("sehk", include_phip=True)
target = [d for d in all_docs if "目标公司名称" in d["name"]]
```

> **⚠️ 注意**：AP/PHIP文件为PDF格式，**可直接下载无需cookie/session**（免责弹窗仅为客户端JS实现）。
>
> **港交所AP/PHIP JSON端点完整列表：**
> | 端点 | 内容 |
> |------|------|
> | `appactive_app_sehk_e.json` | 主板活跃申请（AP） |
> | `appactive_app_gem_e.json` | 创业板活跃申请（AP） |
> | `appactive_appphip_sehk_c.json` | 主板聆讯后资料集（PHIP） |
> | `appactive_appphip_gem_c.json` | 创业板聆讯后资料集（PHIP） |
> | `applisted_sehk_e.json` | 主板已上市 |
> | `applisted_gem_e.json` | 创业板已上市 |

**1C — 判断是否为发债企业**

使用 WebSearch 搜索：`{公司名称} 债券发行 中期票据 短期融资券 公司债`

若在中国货币网、上交所、深交所等平台有债券记录 → 执行第2.5步（发债扩展流程）。

---

### 第2步：下载公告PDF

根据上市市场选择不同下载源：

---

#### 2A — A股：从巨潮网下载

详细 API 规范见 [references/cninfo_api.md](references/cninfo_api.md)。

**下载脚本调用：**
```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "C:\Users\LY\.workbuddy\skills\企业公开信息抓取\scripts\cninfo_downloader.py" `
  --company "{公司全称}" --code "{股票代码}" --org-id "{orgId}" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\00-基础资料"
```

**必须下载的文件清单：**

| 类型 | 数量 | 搜索关键词 | 排除 |
|------|------|-----------|------|
| 年度报告 | 近3年 + 最新已披露年度 | `{代码} 年度报告` | 摘要、英文版 |
| 年度审计报告 | 近3年 | `{代码} 年度审计报告` | 内控审计、专项审计 |
| 最新季报 | 最新已披露 | `{代码} 季度报告` | — |
| 重大事项公告 | 近2年重大事项 | `{代码} 重大事项 重组 担保 诉讼` | — |
| 招股说明书 | 最新版（如有） | `{代码} 招股说明书` | 更新版 |

**时间范围（按数据时间范围标准动态计算）：**
- 年度报告：近三个完整年度 + 最新已披露年度
- 审计报告：近三个完整年度
- 季报/中报/三季报：近一期（取最新已披露）
- 重大事项公告：近2年

> **⚠️ 禁止硬编码年份**：时间范围必须根据当前日期按「数据时间范围标准」章节的规则**动态计算**，确保任何时候调用 Skill 都获取正确的年份范围。

---

#### 2B — 港股：从港交所披露易下载

详细 API 规范见 [references/hkex_api.md](references/hkex_api.md)。

**下载脚本调用：**
```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "C:\Users\LY\.workbuddy\skills\企业公开信息抓取\scripts\hkex_downloader.py" `
  --company "{公司名称}" --code "{股票代码如00700}" --stock-id "{stockId}" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\00-基础资料"
```

> stockId 为空时脚本会自动搜索查找。

**必须下载的文件清单：**

| 类型 | 数量 | t2code 分类 | 说明 |
|------|------|------------|------|
| 年度报告 | 近3年 | `40200` | 排除摘要、ESG报告、英文版 |
| 中期报告 | 近2年 | `40300` | 半年报 |
| 招股说明书 | 最新版（如有） | `40500` | IPO招股书 |
| 重大事项公告 | 近2年 | `40100` | 非常重大收购/关连交易等 |

**⚠️ 港股注意事项：**
- 港交所年报格式为"多檔案"（PDF拆分多个片段）时需逐片下载后合并
- 港股无独立审计报告PDF（审计意见含在年报内）
- 港股公告标题为繁体中文，筛选时需同时匹配简繁体

---

#### 2C — A股IPO申报：按板块从官方平台下载

> 适用于尚未上市、正在IPO申报审核阶段的企业。
> **核心规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。**

**数据源（按板块指定，优先使用证监会官方平台）：**

| 板块 | 官方信息源 | URL | 获取方式 |
|------|-----------|-----|---------|
| 沪市（主板+科创板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1010/index.html` | 无API，WebSearch + 浏览器下载 |
| 深市（主板+创业板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1017/index.html` | 无API，WebSearch + 浏览器下载 |
| 北交所 | 北交所审核信息披露 | `https://www.bse.cn/audit/audit_disclosure.html` | 无API，WebSearch + 浏览器下载 |
| 全市场（备选） | 巨潮网IPO专区 | `cninfo.com.cn` | hisAnnouncement API（category=category_sc_gk_ssgs） |
| 全市场（兜底） | 东方财富IPO数据中心 | `data.eastmoney.com/xg/ipo` | WebSearch + 链接提取 |

> **⚠️ 选择策略**：证监会平台是官方第一来源，信息最权威最全。巨潮网可作为备选（API可编程）。如两者均不可用，使用东方财富。
>
> **⚠️ 证监会平台特点**：eid.csrc.gov.cn 无公开API接口，需通过 WebSearch 搜索 `site:eid.csrc.gov.cn {公司名称} 招股说明书` 或使用浏览器手动访问。

**沪市IPO — 证监会平台（1010）：**

```
页面入口：http://eid.csrc.gov.cn/ipo/1010/index.html
包含内容：主板 + 科创板 IPO申报企业
文件类型：招股说明书（申报稿）、问询函及回复、审计报告、法律意见书、发行保荐书
```

**深市IPO — 证监会平台（1017）：**

```
页面入口：http://eid.csrc.gov.cn/ipo/1017/index.html
包含内容：深市主板 + 创业板 IPO申报企业
文件类型：同上
注意：深市分"深市主板"和"创业板"两个子分类
```

**北交所IPO — 北交所审核信息披露：**

```
页面入口：https://www.bse.cn/audit/audit_disclosure.html
包含内容：北交所公开发行并上市审核项目
文件分类：申报稿、上会稿、注册稿、问询与回复
注意：pageNum 从0开始（与证监会平台不同）
```

**巨潮网备选查询（可编程）：**

```python
import requests, json

resp = requests.post(
    "http://www.cninfo.com.cn/new/hisAnnouncement/query",
    data={
        "pageNum": 1, "pageSize": 30,
        "column": "szse",  # 沪市用 "sse"，北交所用 "bse"
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": "{公司名称}",
        "secid": "",
        "category": "category_sc_gk_ssgs",  # 首次公开发行及上市类别
        "trade": "",
        "seDate": "2024-01-01~2026-12-31",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    },
    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    timeout=15
)
data = resp.json()
# 从 data['announcements'] 中筛选包含"招股说明书"的公告
# 下载链接拼接：http://static.cninfo.com.cn/{adjunctUrl}
```

**必须下载的文件清单：**

| 类型 | 数量 | 说明 |
|------|------|------|
| 招股说明书（申报稿） | 最新版（同名文件取披露时间最新者） | 核心文件，含财务数据 |
| 审计报告 | 最近3年 | 随招股书一同披露，也可单独下载 |
| 问询函及回复 | 全部轮次 | 交易所审核问询 + 发行人回复 |
| 法律意见书 | 最新版 | 律师出具 |
| 发行保荐书 | 最新版 | 保荐机构出具 |

**⚠️ IPO企业特殊处理：**
- 招股说明书（申报稿）包含**最近3年+最近1期**财务数据，是核心资料
- 无年报、季报（未上市），审计报告包含在招股书附件或单独披露
- 问询函及回复是重要的补充信息源（揭示监管关注点）
- 如果企业已过会但尚未挂牌，可能有"招股说明书（注册稿）"
- **同名文件去重规则**：如有多版同名文件（如多次更新的招股说明书），**按披露时间取最新版**

---

#### 2D — 港股聆讯：从港交所下载AP/PHIP

> 适用于尚未在港交所上市、正在聆讯或等待上市阶段的企业。
> **核心规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。**

**官方信息源：**

| 来源 | URL | 获取方式 |
|------|-----|---------|
| 港交所新上市申请页面 | `https://www1.hkexnews.hk/app/appindex.html?lang=zh` | JSON API端点（见下方） + PDF直下 |

> **⚠️ 注意**：页面入口为 `https://www1.hkexnews.hk/app/appindex.html?lang=zh`，分为主板(MAIN BOARD)和创业板(GEM)两个板块，每个板块下有：活跃个案、不活跃个案、已上市、已退回。

**下载脚本调用：**
```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "C:\Users\LY\.workbuddy\skills\企业公开信息抓取\scripts\ipo_downloader.py" `
  --company "{公司名称}" --market hk --board sehk `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\00-基础资料"
```

**必须下载的文件清单：**

| 类型 | JSON端点 | 说明 |
|------|---------|------|
| 申请版本（AP） | `appactive_app_sehk_e.json` | 最初提交的招股书草稿 |
| 聆讯后资料集（PHIP） | `appactive_appphip_sehk_c.json` | 接近定稿的招股书（更重要） |
| 整体协调人公告 | titleSearchServlet | 保荐人委任等公告 |

**⚠️ AP vs PHIP 选择优先级：**
1. **PHIP > AP**：PHIP是聆讯后的更新版本，数据更准确
2. 如果只有AP（尚未聆讯），使用AP
3. PHIP可能有多版（每次更新都会发布新PHIP），**取披露时间最新者**

**⚠️ 港股IPO注意事项：**
- AP/PHIP文件含"申请版本"或"聆讯后资料集"标记，并非最终招股书
- 港交所AP页面（`https://www1.hkexnews.hk/app/appindex.html?lang=zh`）分为：活跃个案（ACTIVE）、不活跃个案（Inactive）、已上市（Listed）、已退回（Returned）
- "不活跃"个案的文件可能被移除，需及时下载
- AP/PHIP PDF可直接访问，无需cookie（免责弹窗仅为客户端实现）
- **同名文件去重规则**：如有多版同名文件（如多次更新的PHIP），**按披露时间取最新版**

---

### 第2.5步：发债企业信息获取（扩展流程）

> 仅对判定为发债企业的目标执行。

详细 API 规范见 [references/bond_info_api.md](references/bond_info_api.md)。

**覆盖平台及下载内容：**

| 平台 | 网址 | 获取内容 |
|------|------|---------|
| 中国货币网 | chinamoney.com.cn | 主体/债项/跟踪评级报告、银行间债券发行公告、募集说明书 |
| 上海清算所 | shclearing.com.cn | 发行公告、申购区间说明、付息兑付公告 |
| 上交所债券平台 | bond.sse.com.cn | 公司债/企业债发行公告、上市公告、存续期公告 |
| 深交所固收平台 | bond.szse.cn | 固收项目文件 |
| 孔雀开屏系统 | zhuce.nafmii.org.cn | 银行间债务融资工具注册文件 |
| 北交所 | bse.cn | 公司债发行公告（如有） |

---

### 第3步：从年报/招股书PDF精准提取财务数据

这是本 Skill 的核心技术环节，采用**三层提取架构**：

> **IPO/聆讯企业适配**：招股说明书（申报稿/PHIP）与年报的财务报表格式一致，提取算法通用。差异在于：
> - 招股书通常包含**最近3年+最近1期**（如2022/2023/2024 + 2025H1）数据
> - 招股书审计报告可能作为附件单独成册，需额外提取
> - 招股书行业分析章节更详细（"业务与技术"章节）

#### 三层架构

| 优先级 | 方法 | 适用场景 | 可靠度 |
|--------|------|---------|--------|
| 第一层 | pdfplumber 科目分类器 | 原生电子PDF（绝大多数A股年报） | ★★★★★ |
| 第二层 | pdfminer 纯文本行匹配 | pdfplumber表格解析失败时 | ★★★ |
| 第三层 | GLM-4V 视觉模型截图 | 前两层均失败或数据严重缺失 | ★★★ |

#### 核心算法：科目名自动分类器（v4）

**设计原理**：不再按页码范围分割报表（旧v3的根本缺陷：同一页上BS末尾+IS开头混在一起），改为提取BS到权益变动表之间所有表格行，按科目名特征词自动分类。

```python
# 科目名特征词库（A股简体 + 港股繁体）
BS_ITEM_PATTERNS = [
    # A股简体
    '货币资金', '交易性金融资产', '应收票据', '应收账款', '应收款项融资',
    '预付款项', '其他应收款', '存货', '合同资产', '其他流动资产', '流动资产合计',
    '长期股权投资', '固定资产', '在建工程', '使用权资产', '无形资产', '商誉',
    '长期待摊费用', '递延所得税资产', '其他非流动资产', '非流动资产合计', '资产总计',
    '短期借款', '应付票据', '应付账款', '合同负债', '应付职工薪酬',
    '应交税费', '其他应付款', '一年内到期的非流动负债', '其他流动负债', '流动负债合计',
    '长期借款', '应付债券', '租赁负债', '预计负债', '递延收益',
    '非流动负债合计', '负债合计',
    '股本', '资本公积', '盈余公积', '未分配利润', '少数股东权益',
    '归属于母公司所有者权益合计', '所有者权益合计', '负债和所有者权益总计',
    # 港股繁体
    '現金及現金等價物', '應收賬款', '應收票據', '預付款項',
    '物業、廠房及設備', '使用權資產', '商譽', '遞延稅項資產',
    '應付賬款', '借款', '股本', '儲備',
    '綜合財務狀況表', '財務狀況表', '非流動資產', '流動資產',
]

IS_ITEM_PATTERNS = [
    # A股简体
    '营业总收入', '营业收入', '营业总成本', '营业成本', '税金及附加',
    '销售费用', '管理费用', '研发费用', '财务费用', '利息费用', '利息收入',
    '其他收益', '投资收益', '公允价值变动收益', '信用减值损失', '资产减值损失',
    '资产处置收益', '营业利润', '营业外收入', '营业外支出',
    '利润总额', '所得税费用', '净利润', '持续经营净利润',
    '归属于母公司', '少数股东损益', '综合收益总额', '每股收益',
    '其他综合收益', '其他权益工具', '重新计量设定受益计划',
    '权益法下可转损益', '企业自身信用风险',
    # 港股繁体
    '收入', '銷售成本', '毛利', '銷售及分銷成本', '行政開支',
    '研發開支', '融資成本', '除稅前盈利', '所得稅開支', '年內溢利',
    '本公司擁有人應佔', '綜合損益表', '綜合全面收益表',
]

CF_ITEM_PATTERNS = [
    # A股简体
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
    # 港股繁体
    '經營活動', '投資活動', '融資活動', '綜合現金流量表',
]

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

#### 报表定位算法：3轮递进

```python
# 第1轮：精确标题匹配（A股 + 港股）
REPORT_MARKERS = {
    "1、资产负债表": "bs_consolidated",
    "2、利润表": "is_consolidated",
    "3、现金流量表": "cf_consolidated",
    "4、所有者权益变动表": "equity_change",
    # 港股报表标题
    "綜合財務狀況表": "bs_consolidated",
    "財務狀況表": "bs_consolidated",
    "綜合損益表": "is_consolidated",
    "綜合全面收益表": "is_consolidated",
    "綜合現金流量表": "cf_consolidated",
}

# 第2轮：宽松关键词匹配
FALLBACK_MARKERS = {
    "资产负债表": "bs_consolidated",
    "利润表": "is_consolidated",
    "现金流量表": "cf_consolidated",
    "所有者权益变动表": "equity_change",
    # 港股
    "財務狀況表": "bs_consolidated",
    "損益表": "is_consolidated",
    "現金流量表": "cf_consolidated",
}

# 第3轮：表格表头辅助定位
TABLE_HEADER_KEYWORDS = {
    "bs_consolidated": ["期末余额", "期初余额", "12月31日", "1月1日",
                        "於年底", "於年初", "於年終", "年結日"],  # 港股
    "is_consolidated": ["本期金额", "上期金额", "本年累计", "上年同期",
                        "本年度", "上年度", "截至年底"],  # 港股
    "cf_consolidated": ["本期金额", "上期金额",
                        "本年度", "上年度"],  # 港股
}
```

#### 多列格式自适应

A股年报PDF常见4种列格式，必须自动检测：

| 列数 | 科目名列 | 本期值列 | 上期值列 | 常见年份 |
|------|---------|---------|---------|---------|
| 3列 | 0 | 1 | 2 | 2025新版 |
| 5列 | 1 | 3 | 4 | 简化版 |
| 7列 | 0 | 3 | 6 | 2023版 |
| 9列 | 1 | 3 | 6 | 2022-2024版 |

```python
def _detect_col_layout(n_cols: int) -> tuple:
    """根据列数自动检测科目名/本期值/上期值所在列"""
    if n_cols == 3:
        return (0, 1, 2)
    elif n_cols == 5:
        return (1, 3, 4)
    elif n_cols == 7:
        return (0, 3, 6)
    elif n_cols == 9:
        return (1, 3, 6)
    else:
        return (0, n_cols - 2, n_cols - 1)
```

**⚠️ 9列/7列格式特殊处理**：
- 科目名有时在col0（如"股本"），有时在col1（如"流动资产"），必须双检
- 当科目名在col0时，值从col3/col6取（而非col1后面的位置）

#### 单位转换

```python
def convert_to_wanyuan(value: float, source_unit: str, hk_rate: float = 0.92) -> float:
    """
    统一转换为万元（人民币），保留两位小数。
    
    Args:
        value: 原始数值
        source_unit: 原始单位（元/万元/亿元/HK$'000/HK$M 等）
        hk_rate: 港币兑人民币汇率（默认0.92），仅港股使用
    """
    if source_unit == "元":
        return round(value / 10000, 2)
    elif source_unit == "万元":
        return round(value, 2)
    elif source_unit == "亿元":
        return round(value * 10000, 2)
    # 港股单位
    elif source_unit in ("HK$'000", "千港元"):
        return round(value * 0.1 * hk_rate, 2)       # 千港元 → 万元人民币
    elif source_unit in ("HK$M", "百万港元"):
        return round(value * 100 * hk_rate, 2)        # 百万港元 → 万元人民币
    elif source_unit in ("RMB'000", "千人民币"):
        return round(value * 0.1, 2)
    elif source_unit in ("RMBM", "百万人民币"):
        return round(value * 100, 2)
    return round(value, 2)
```

#### 数据输出格式

提取结果保存为 JSON，每个科目的值为**对象格式**（兼容数组和对象两种读取方式）：

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

---

### 第3.5步：GLM视觉兜底（条件执行）

**触发条件**：pdfplumber 提取后关键科目缺失超过3个。

```python
import os, base64, requests

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
- 只返回JSON，不要其他文字"""

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
    import json, re
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(json_match.group()) if json_match else {}
```

#### 数据合并策略

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
            # 都是对象格式，逐字段合并
            if isinstance(p, dict) and isinstance(s, dict):
                merged[key] = {**s, **p}  # p 覆盖 s
            else:
                merged[key] = p
        else:
            merged[key] = p or s
    return merged
```

---

### 第4步：计算关键财务指标

详细公式见 [references/financial_indicators.md](references/financial_indicators.md)。

| 类别 | 指标 |
|------|------|
| 偿债能力 | 资产负债率、有息负债率、流动比率、速动比率、利息保障倍数、净负债率 |
| 盈利能力 | 毛利率、净利率、ROE（加权）、ROA、EBITDA、EBITDA利润率 |
| 营运能力 | 总资产周转率、存货周转率、应收账款周转率 |
| 现金流质量 | 经营现金流/净利润、自由现金流、收现比、EBITDA偿债倍数 |
| 成长能力 | 营收增长率、净利润增长率、总资产增长率 |

---

### 第5步：搜索经营与行业信息

**5A — 经营数据补充（WebSearch）：**
- 主营业务结构：`{公司} 年报 主营业务 收入结构 毛利率`
- 产能产销：`{公司} 产能 产量 在建工程 扩产`
- 重大事项：`{公司} 重组 增发 股权质押 担保 诉讼`
- 股东变动：`{公司} 股东 持股比例 增减持`

**5B — 行业分析（从年报原文提取 + 搜索补充）：**

从最新年报的"报告期内公司所处行业情况"章节提取：
1. 行业定义与监管分类
2. 产业链结构（上下游）
3. 公司在行业中的定位
4. 竞争格局（主要竞争对手、市场集中度）
5. 政策环境与发展趋势
6. 对比近2-3年变化

---

### 第6步：DeepSeek LLM 报告生成

**核心管道**：`report_pipeline.py`（Python）→ `generate_report_v3.js`（Node.js）

#### 6.1 Python LLM 管道（report_pipeline.py）

```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"

# 必须显式设置环境变量（PowerShell不会自动加载User级env vars）
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
$env:DEEPSEEK_FLASH_API_KEY = [Environment]::GetEnvironmentVariable("DEEPSEEK_FLASH_API_KEY", "User")

# 运行管道
& $python "D:\Workbuddy\2026-05-07-task-2\report_pipeline.py" `
  --input "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\extracted_data.json" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\report_data.json"
```

**双模型路由策略**：

| 任务 | 模型 | 用途 |
|------|------|------|
| 财务数据补全 | DeepSeek V4 Flash | 快速补全缺失数值、计算指标 |
| 分析文本撰写 | DeepSeek V4 Pro | 经营分析、风险评估、行业研判 |

**管道阶段**：
1. Phase1：上下文构建（从JSON提取结构化财务数据 + 文本段落）
2. Phase2：Flash补全（缺失数据填充、指标计算）
3. Phase3：Pro分析（六大经营板块、风险因素、行业分析）
4. Phase4：结构化输出（report_data.json）

#### 6.2 Node.js 排版引擎（generate_report_v3.js）

```powershell
$node = "C:\Users\LY\.workbuddy\binaries\node\versions\22.12.0\node.exe"

# 必须清除 NODE_OPTIONS（含 --use-system-ca 会导致node报错）
Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue

# 必须设置 NODE_PATH
$env:NODE_PATH = "C:\Users\LY\.workbuddy\binaries\node\workspace\node_modules"

& $node "D:\Workbuddy\2026-05-07-task-2\generate_report_v3.js" `
  "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\report_data.json" `
  "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\report_data_报告.docx"
```

**报告结构（7表6板块）**：

| 编号 | 表格 | 内容 |
|------|------|------|
| ① | 产品收入构成 | 分产品收入+成本+毛利率 |
| ①-b | 地区收入构成 | 分地区收入（如有） |
| ② | 合并资产负债表 | 期末/期初双列 |
| ③ | 本部资产负债表 | 期末/期初双列 |
| ④ | 利润表 | 本期/上期双列 |
| ⑤ | 现金流量表 | 本期/上期双列 |
| ⑥ | 有息负债明细 | 短借+长借+应付债券+一年内到期 |
| ⑦ | 可比企业对比 | 同行业主要指标对比 |

| 编号 | 经营板块 | 内容 |
|------|---------|------|
| 1 | 工商信息 | 公司全称、代码、法人、实控人等 |
| 2 | 主营业务 | 业务描述、核心产品/服务 |
| 3 | 经营分析 | 产能产销、竞争力、收入结构 |
| 4 | 财务分析 | 三张报表摘要、关键指标趋势 |
| 5 | 风险因素 | 经营/财务/行业/政策风险 |
| 6 | 行业分析 | 行业定位、竞争格局、发展趋势 |

**排版规范**：
- 单位统一为**万元**，保留**两位小数**
- 风险编号用**(1)(2)(3)**半角括号
- 表格蓝色表头（#2B5BAE）、白色字体
- 不含"审查结论"章节（银行审查结论由审查员自行撰写）

#### 6.3 getStmtVal 兼容性（CRITICAL）

报告引擎的 `getStmtVal()` 函数必须同时支持**数组格式**和**对象格式**：

```javascript
function getStmtVal(yr, stmtKey, itemKeys) {
  const stmt = (by_year[yr]?.statements || {})[stmtKey] || {};
  // 构建归一化键映射（去除序号前缀、"其中："前缀、括号后缀）
  const normKeyMap = {};
  for (const [rawKey, rawVal] of Object.entries(stmt)) {
    const nk = rawKey.replace(/^[一二三四五六七八九十]+、/, '')
                     .replace(/^其中：/, '')
                     .replace(/（.*/, '')
                     .replace(/\(.*/, '')
                     .trim();
    normKeyMap[nk] = rawVal;
    normKeyMap[rawKey] = rawVal;
  }
  for (const k of itemKeys) {
    const vals = stmt[k] || normKeyMap[k];
    if (vals === null || vals === undefined) continue;
    // 数组格式：[v1, v2]
    if (Array.isArray(vals) && vals.length > 0 && vals[0] !== null) return vals[0];
    // 对象格式：{"期末": v1, "期初": v2}
    if (typeof vals === 'object' && !Array.isArray(vals)) {
      for (const ck of ['期末', '本期', '本年金额', '本年数']) {
        if (vals[ck] !== null && vals[ck] !== undefined) return vals[ck];
      }
    }
  }
  return null;
}
```

---

### 第7步：生成Excel财务底稿

```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "C:\Users\LY\.workbuddy\skills\企业公开信息抓取\scripts\excel_generator.py" `
  --data "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\extracted_data.json" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\01-财务报表\财务数据底稿_{日期}.xlsx"
```

**Sheet 结构（上市公司标准版）：**

| # | Sheet名称 | 内容 |
|---|-----------|------|
| 1 | 封面 | 企业名称、数据年度、单位说明、数据来源 |
| 2 | 合并报表 | **三段式**：资产负债表→利润表→现金流量表 |
| 3 | 本部报表 | **三段式**：同上（本部口径） |
| 4 | 关键财务指标 | 合并+本部对比，含五类指标 |
| 5 | 业务板块收入 | 分产品/分业务线收入、毛利率 |
| 6 | 产能产销情况 | 产量、销量、库存、产能利用率 |

---

### 第8步：收入构成专项注入（可选）

若年报提取数据中包含收入构成（产品+地区），需额外注入到 report_data.json：

```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\inject_revenue.py"
```

该脚本从 extracted_data.json 的 `chapters.revenue_breakdown` 中解析分产品+分地区收入数据，注入到 report_data.json 的对应位置。

---

### 第9步：首次成果交付（V1）

**在完成步骤 1-8 后，必须进行首次交付**，不得跳过直接进入验证。

#### 9.1 交付物清单

| # | 交付物 | 路径 | 检查要点 |
|---|--------|------|---------|
| 1 | Word 审查报告 | `02-分析报告/report_data_报告.docx` | 7表6板块是否完整生成 |
| 2 | Excel 财务底稿 | `01-财务报表/财务数据底稿_{日期}.xlsx` | 6个Sheet是否齐全 |
| 3 | 结构化数据 | `01-财务报表/extracted_data_merged.json` | JSON 格式是否合法 |
| 4 | 年度报告 PDF | `00-基础资料/年报_*.pdf` | 是否覆盖近三个完整年度 |
| 5 | 审计报告 PDF | `00-基础资料/审计报告_*.pdf` | 是否覆盖近三个完整年度 |
| 6 | 近一期报告 | `00-基础资料/` | 季报/中报/三季报是否存在 |

#### 9.2 交付前自检

```python
# V1 交付前自检清单
V1_CHECKLIST = {
    "完整性": {
        "年报覆盖": "近三个完整年度（如2023/2024/2025）",
        "审计报告覆盖": "近三个完整年度（不可用年报替代）",
        "近一期报告": "最新季报/中报/三季报已包含",
        "7张表格": "产品收入①+地区收入①b+合并BS②+本部BS③+IS④+CF⑤+有息负债⑥+可比企业⑦",
        "6大板块": "工商信息+主营业务+经营分析+财务分析+风险因素+行业分析",
    },
    "准确性": {
        "数据来源": "全部来自审计报告/经审计年报PDF提取",
        "单位统一": "万元，两位小数",
        "关键科目交叉验证": "资产总计=负债合计+所有者权益合计",
        "同比环比": "本期/上期数据完整，无遗漏",
    },
    "格式规范": {
        "风险编号": "(1)(2)(3)半角括号",
        "表格表头": "蓝色#2B5BAE，白色字体",
        "无审查结论": "不含审查结论章节",
    }
}
```

#### 9.3 交付确认

向用户明确告知：**「V1 初稿已生成，即将进入检查验证阶段。」**

---

### 第10步：检查验证完整性及准确性

**本步骤必须在 V1 交付后进行，对成果进行全面审查。**

#### 10.1 完整性检查

| 检查维度 | 检查方法 | 通过标准 | 不通过处理 |
|---------|---------|---------|-----------|
| **资料完整性** | 核对 `00-基础资料/` 目录文件清单 | 所有必需 PDF 已下载且可正常打开 | 标记缺失文件，进入补采队列 |
| **数据完整性** | 逐一审查 7 张表格，确认每张表关键科目有值 | 关键科目缺失率 < 5% | 标记缺失科目，回溯 PDF 重新提取 |
| **章节覆盖** | 逐一审查 6 大经营板块是否有内容 | 每个板块文字叙述 ≥ 200字 | 标记空白板块，补充 LLM 生成 |
| **风险覆盖** | 审查风险因素章节编号段落数 | ≥ 5 个风险编号段落 | 补充缺失风险类别 |

#### 10.2 准确性验证

**关键科目交叉比对（必须执行）：**

```python
# 资产负债表平衡校验
assert abs(assets_total - (liabilities_total + equity_total)) < 1.0, \
    f"资产负债表不平衡！差额：{assets_total - liabilities_total - equity_total} 万元"

# 跨表勾稽
# 1. 资产负债表 "货币资金" ≈ 现金流量表 "期末现金及现金等价物余额"
# 2. 资产负债表 "未分配利润" 变动 ≈ 利润表 "净利润" - 分红
# 3. 合并报表 vs 本部报表关键科目差异合理
# 4. 三年数据趋势连续（无异常跳变）
```

**数据源比对（抽查 ≥ 20% 关键科目）：**
- 从 PDF 提取的原始值 ↔ 报告表格中的值
- 允许差异：舍入误差（±0.01 万元）

**单位一致性验证：**
- 所有表格数值单位为万元
- 小数点保留两位
- 无亿元/元混入

#### 10.3 编制验证报告

生成 `02-分析报告/验证报告_V1.md`，包含：

```markdown
# V1 验证报告 — {公司名称}

## 完整性问题清单
| 问题编号 | 类型 | 描述 | 严重程度 |
|---------|------|------|---------|
| C-001 | 资料缺失 | 缺少2024年度审计报告 | 高 |
| C-002 | 数据缺失 | 现金流量表"期末现金余额"为空 | 中 |
| C-003 | 章节空 | 行业分析板块内容不足100字 | 低 |

## 准确性问题清单
| 问题编号 | 类型 | 描述 | 差异值 |
|---------|------|------|--------|
| A-001 | 平衡校验 | 2024年BS不平衡 | +12.35万 |
| A-002 | 跨表勾稽 | 货币资金≠现金等价物余额 | 差异5,000万 |
| A-003 | 单位混乱 | 2023年营收显示120亿（应为万元） | — |

## 检查统计
- 完整性检查项：__ / __ 通过
- 准确性检查项：__ / __ 通过
- 格式规范检查项：__ / __ 通过
- 关键问题数：__（高）、__（中）、__（低）
```

---

### 第11步：根据检查结果修订完善交付成果（V2）

**根据 V1 验证报告的问题清单，逐项修正后生成 V2。**

#### 11.1 修订优先级

| 优先级 | 问题类型 | 处理方式 | 时限 |
|--------|---------|---------|------|
| **P0** | 资料缺失（审计报告/年报） | 重新爬取下载缺失 PDF | 立即 |
| **P1** | 数据缺失/错误（关键科目） | 回溯 PDF 重新提取 → 重新生成 | 立即 |
| **P2** | 章节内容不足 | 补充 LLM 生成 → 重新排版 | 本阶段 |
| **P3** | 格式偏差 | 修正排版参数 | 本阶段 |
| **P4** | 优化建议 | 记录但不阻塞 V2 交付 | 下阶段 |

#### 11.2 修订执行流程

```
V1 验证报告 → [P0:补采资料] → [P1:重提取数据] → [P2:补充LLM]
→ 更新 extracted_data_merged.json → 重新运行 report_pipeline.py
→ 重新运行 generate_report_v3.js → V2 生成
```

```powershell
# 修订后重新生成 V2
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"

# 重新运行 LLM 管道（使用更新后的数据）
& $python "D:\Workbuddy\2026-05-07-task-2\report_pipeline.py" `
  --input "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\01-财务报表\extracted_data_merged.json" `
  --output "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\01-财务报表\report_data_v2.json"

# 重新排版
$node = "C:\Users\LY\.workbuddy\binaries\node\versions\22.12.0\node.exe"
Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
$env:NODE_PATH = "C:\Users\LY\.workbuddy\binaries\node\workspace\node_modules"
& $node "D:\Workbuddy\2026-05-07-task-2\generate_report_v3.js" `
  "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\01-财务报表\report_data_v2.json" `
  "D:\Workbuddy\企业披露信息抓取工作区\{公司名}\02-分析报告\report_data_报告_V2.docx"
```

#### 11.3 V2 交付物

| # | 交付物 | 与 V1 差异 |
|---|--------|-----------|
| 1 | `report_data_报告_V2.docx` | 根据验证报告修订版 |
| 2 | `验证报告_V1.md` | 问题清单与处理状态 |
| 3 | `修订说明.md` | 逐条说明修订内容 |

> **修订说明模板**：
> ```markdown
> # V1 → V2 修订说明
> | 问题编号 | 处理状态 | 修订内容 |
> |---------|---------|---------|
> | C-001 | ✅ 已修复 | 已补下载2024年度审计报告 |
> | A-001 | ✅ 已修复 | BS平衡校验通过，差异已修正 |
> | C-003 | ✅ 已修复 | 行业分析已补充至350字 |
> | P4-001 | ⬜ 延后 | 可比企业数据待下阶段补充 |
> ```

---

### 第12步：对比两次交付成果并检验评估

**V1 ↔ V2 系统对比，量化改进幅度，避免主观判断。**

#### 12.1 自动对比脚本

```python
# compare_v1_v2.py — 自动对比两次交付
import json, os

def compare_deliveries(v1_dir: str, v2_dir: str) -> dict:
    """对比 V1 和 V2 交付成果，输出差异报告"""
    
    # 1. 对比 extracted_data JSON
    v1_data = json.load(open(f"{v1_dir}/extracted_data_merged.json"))
    v2_data = json.load(open(f"{v2_dir}/extracted_data_merged.json"))
    
    # 2. 统计指标
    v1_item_count = count_financial_items(v1_data)
    v2_item_count = count_financial_items(v2_data)
    
    # 3. 对比报告 page 数/段落数/表格数
    # (需用 python-docx 读取 Word 文件)
    
    return {
        "v1_data_points": v1_item_count,
        "v2_data_points": v2_item_count,
        "new_data_points": v2_item_count - v1_item_count,
        "data_completeness_v1": f"{v1_item_count / expected_max * 100:.1f}%",
        "data_completeness_v2": f"{v2_item_count / expected_max * 100:.1f}%",
        "issues_fixed": [],   # 从修订说明提取
        "issues_outstanding": [], # 尚未修复的问题
        "regression_items": [], # V2 比 V1 更差的项
    }
```

#### 12.2 对比评估维度

| 评估维度 | 指标 | V1 值 | V2 值 | 变化 | 判定 |
|---------|------|------|------|------|------|
| **完整性** | 缺失报表数 | | | | ← / ↑ / → |
| **完整性** | 缺失关键科目数 | | | | |
| **准确性** | 平衡校验通过率 | | | | |
| **准确性** | 跨表勾稽差异项数 | | | | |
| **丰富度** | 经营分析段落数 | | | | |
| **丰富度** | 风险编号段落数 | | | | |
| **合规性** | 单位规范达标率 | | | | |
| **合规性** | 格式规范达标率 | | | | |

**判定图标**：
- ✅ ↑ 改进：V2 明显优于 V1
- ⬜ → 持平：V1 和 V2 无显著差异
- ❌ ↓ 回退：V2 反而不如 V1（需排查原因）

#### 12.3 编制对比报告

输出 `02-分析报告/对比评估报告_V1vsV2.md`。

---

### 第13步：判断是否需要进一步优化

**根据 V1↔V2 对比结果，做出最终交付决策。**

#### 13.1 决策矩阵

| 条件 | 决策 | 后续动作 |
|------|------|---------|
| **V2 所有维度 ≥ V1，且无 P0/P1 问题** | ✅ **V2 即为最终版** | 交付 V2，归档 |
| **V2 所有维度 ≥ V1，但有 P2/P3 问题** | ⚠️ **V2 可交付，但建议优化** | 先交付 V2，标注已知待优化项，择机 V3 |
| **V2 存在 P0/P1 问题** | 🔄 **需进一步优化** | 回到第 11 步，再次修订后生成 V3 |
| **V2 存在 ↓ 回退（V2 不如 V1）** | 🔄 **需排查回退原因** | 检查修订过程是否引入新错误，回退并重做 |
| **V2 改进不明显（→ 持平）但无新问题** | ✅ **V2 即为最终版** | 交付 V2，注明改进有限 |

#### 13.2 最终交付

当决策为「V2 即为最终版」时：

1. 将最终版 Word 报告重命名为 `{公司名}_审查报告_最终版_{YYYYMMDD}.docx`
2. 更新 `验证报告_V1.md` 状态为「已关闭」
3. 归档所有中间文件（V1/V2/验证/对比报告）

```powershell
# 最终交付归档
$companyDir = "D:\Workbuddy\企业披露信息抓取工作区\{公司名}"
$date = Get-Date -Format "yyyyMMdd"

# 最终版报告
Copy-Item "$companyDir\02-分析报告\report_data_报告_V2.docx" `
  "$companyDir\02-分析报告\{公司名}_审查报告_最终版_$date.docx"

# 归档历史版本
New-Item -ItemType Directory -Path "$companyDir\03-历史版本" -Force
Move-Item "$companyDir\02-分析报告\report_data_报告.docx" `
  "$companyDir\03-历史版本\report_data_报告_V1_$date.docx"
Move-Item "$companyDir\02-分析报告\report_data_报告_V2.docx" `
  "$companyDir\03-历史版本\report_data_报告_V2_$date.docx"
```

#### 13.3 最终交付确认

向用户明确告知：
- **最终版路径**
- **V1→V2 改进摘要**（修复了多少问题、新增了多少数据点）
- **已知局限**（如有 P2/P3 问题延后处理）
- **建议下一步**（如需人工复核的关键科目、是否需补充其他信息源）

---

## 文件输出结构

```
D:\Workbuddy\企业披露信息抓取工作区\
└── {公司名称}\
    ├── 00-基础资料\
    │   ├── 年报_{YYYY}.pdf              ← 近三个完整年度
    │   ├── 年报_{YYYY+1}.pdf            ← 最新已披露年度（如有）
    │   ├── 审计报告_{YYYY}.pdf          ← 近三个完整年度
    │   ├── 季报_{YYYY}Q{N}.pdf          ← 近一期
    │   ├── 招股说明书_*.pdf             ← 如有
    │   ├── 评级报告_*.pdf               ← 发债企业
    │   ├── 募集说明书_*.pdf             ← 发债企业
    │   └── 重大事项公告_*.pdf
    ├── 01-财务报表\
    │   ├── extracted_data.json          ← pdfplumber精准提取（主数据）
    │   ├── extracted_data_glm.json     ← GLM视觉兜底（辅数据）
    │   ├── extracted_data_merged.json   ← 合并后数据
    │   ├── report_data.json            ← LLM管道输出（V1）
    │   ├── report_data_v2.json         ← LLM管道输出（V2，修订后）
    │   └── 财务数据底稿_{YYYYMMDD}.xlsx
    ├── 02-分析报告\
    │   ├── report_data_报告.docx        ← V1 Word审查报告
    │   ├── report_data_报告_V2.docx     ← V2 Word审查报告（修订版）
    │   ├── {公司名}_审查报告_最终版_{YYYYMMDD}.docx  ← 最终交付版
    │   ├── 验证报告_V1.md              ← V1完成后的验证问题清单
    │   ├── 修订说明.md                  ← V1→V2逐条修订记录
    │   └── 对比评估报告_V1vsV2.md       ← V1↔V2系统对比评估
    └── 03-历史版本\
        ├── report_data_报告_V1_{YYYYMMDD}.docx  ← V1归档
        └── report_data_报告_V2_{YYYYMMDD}.docx  ← V2归档
```

---

## 代理执行指南

当用户触发此 Skill 时，按以下**四阶段**流程执行：

### 第一阶段：资料采集与初稿生成（步骤 1-9）

#### 1. 确认目标

向用户确认（或从已有信息推断）：
- 目标公司全称 + 股票代码（或统一社会信用代码）
- 企业阶段：已上市 / IPO申报 / 聆讯 / 发债
- 是否为发债企业（需要下载评级报告/募集说明书）
- 报告年度范围：**按「数据时间范围标准」动态计算**，不可硬编码
- 是否有自定义分析提纲

#### 2. 动态计算时间范围

```python
from datetime import datetime

def calculate_time_range():
    """动态计算近三个完整年度 + 近一期"""
    now = datetime.now()
    # 每年4月30日前，年报尚未大量披露
    if now.month < 5 and now.day < 30:
        latest_full_year = now.year - 2  # 上月年报截至
    else:
        latest_full_year = now.year - 1
    full_years = [latest_full_year - 2, latest_full_year - 1, latest_full_year]
    # 近一期：当前季度-1
    return {
        "full_years": full_years,  # [2023, 2024, 2025]
        "latest_period": f"{now.year}Q{((now.month-1)//3)}",  # 2026Q1
    }
```

#### 3. 检查/创建工作区目录

```powershell
$workDir = "D:\Workbuddy\企业披露信息抓取工作区\{公司名}"
New-Item -ItemType Directory -Path "$workDir\00-基础资料" -Force
New-Item -ItemType Directory -Path "$workDir\01-财务报表" -Force
New-Item -ItemType Directory -Path "$workDir\02-分析报告" -Force
New-Item -ItemType Directory -Path "$workDir\03-历史版本" -Force
```

#### 4. 安装依赖（首次运行）

```powershell
$python = "C:\Users\LY\AppData\Local\Programs\Python\Python312\python.exe"
& $python -m pip install pdfplumber openpyxl python-docx requests Pillow --quiet
```

#### 5. 按步骤 1→9 顺序执行，每步完成后报告进度

**⚠️ 必须全部完成步骤 1-8 后才进入步骤 9（V1 交付）**，不得跳过任何步骤。

#### 6. 首次交付（V1）

使用 `deliver_attachments` 推送 V1 文件给用户，并明确告知进入验证阶段。

---

### 第二阶段：检查验证（步骤 10）

1. 执行完整性检查（资料/数据/章节）
2. 执行准确性验证（关键科目交叉比对、平衡校验）
3. 编制 `验证报告_V1.md`
4. 向用户呈报验证结果，说明发现的问题严重程度

---

### 第三阶段：修订完善（步骤 11）

1. 按优先级（P0→P1→P2→P3）逐项修复问题
2. 如涉及 PDF 重新提取，重新运行步骤 3-6
3. 重新生成报告 → **V2 交付**
4. 编制 `修订说明.md`（逐条说明修订内容）
5. 使用 `deliver_attachments` 推送 V2 文件

---

### 第四阶段：对比评估与最终交付（步骤 12-13）

1. 执行 V1 ↔ V2 系统对比
2. 编制 `对比评估报告_V1vsV2.md`
3. 按决策矩阵判断是否需要进一步优化
4. 如需进一步优化 → 回到步骤 11（生成 V3）
5. 如达到最终交付标准 → **最终归档**
6. 使用 `deliver_attachments` 推送最终版文件
7. 向用户呈报：
   - 最终版路径
   - V1→V2 改进摘要
   - 已知局限
   - 建议下一步

---

### 阶段间用户交互要求

| 阶段 | 互动方式 | 需要用户确认 |
|------|---------|------------|
| 第一阶段→第二阶段 | 告知用户"V1 已生成，进入验证" | 否（自动进行） |
| 第二阶段→第三阶段 | 呈报验证报告，说明待修复问题 | 否（自动进行） |
| 第三阶段→第四阶段 | 告知用户"V2 已生成，进入对比评估" | 否（自动进行） |
| 第四阶段→最终交付 | 呈报最终对比评估结果 | **是（询问是否满意，或需 V3）** |

---

## 异常处理与兜底方案

| 异常场景 | 处理方式 |
|---------|---------|
| 巨潮网 topSearch 返回空 | 用 WebSearch 搜索 `site:cninfo.com.cn {代码}` 从URL提取orgId |
| 巨潮网 hisAnnouncement 返回0条 | 检查 stock 参数格式（必须为 `{code},{orgId}` 纯值，无前缀）；不设置 category 参数（已废弃） |
| PDF 下载 403/404 | 重新访问个股页面获取cookie后重试；页间间隔0.3s |
| pdfplumber 表格解析全空 | 切换到 pdfminer 纯文本行匹配；或调用 GLM-4V |
| 跨页数据泄漏（BS末尾+IS开头混在同一页） | 使用科目名分类器 classify_item()，不再依赖页码范围分割 |
| 9列/7列格式科目名在col0 | 双检 col0/col1，当科目名在col0时值从col3/col6取 |
| 利润表/现金流量表跨页截断 | 提取范围扩大到 equity_change 页（`end_page = eq_page`） |
| 2023年后年报无"2、利润表"标题 | 3轮递进定位：精确→宽松→表头辅助 |
| 报告表格全显示"—" | 检查 getStmtVal 是否支持对象格式（`{"期末": v1, "期初": v2}`） |
| 科目名不匹配（带序号前缀） | getStmtVal 模糊匹配：去除"一、"、"其中："、括号后缀 |
| Node.js 运行报错 | 清除 `$env:NODE_OPTIONS`；设置 `$env:NODE_PATH` |
| DeepSeek API 调用失败 | PowerShell 需显式设置 `$env:DEEPSEEK_API_KEY`（从User级环境变量读取） |
| 中国货币网无评级记录 | 确认企业是否为发债企业；尝试上海清算所 |
| **港股：titleSearchServlet 返回空** | **stockId 可能错误，使用 find_stock_id() 或 WebSearch 搜索 `site:hkexnews.hk {代码}` 查找** |
| **港股：年报为"多檔案"格式** | **需逐片下载后合并，或使用 GLM-4V 逐片提取** |
| **港股：繁体科目名不匹配** | **classify_item() 已扩展繁体特征词；或使用 HK_STOCK_ITEM_MAP 映射** |
| **港股：金额单位非万元** | **使用 convert_to_wanyuan 的港股分支（含汇率转换）** |
| **港股：找不到"资产负债表"** | **港股叫"財務狀況表"/"綜合財務狀況表"，REPORT_MARKERS 已加入** |
| **A股IPO：巨潮网无IPO招股书** | **按板块访问官方平台：沪市 eid.csrc.gov.cn/ipo/1010 / 深市 /ipo/1017 / 北交所 bse.cn/audit** |
| **A股IPO：证监会平台无法API访问** | **使用 WebSearch `site:eid.csrc.gov.cn {公司名称} 招股说明书` 或 agent-browser skill** |
| **A股IPO：招股书PDF为扫描件** | **同年报扫描件处理：先pdfplumber→失败则GLM-4V** |
| **A股IPO：问询函无法API获取** | **WebSearch搜索 `site:cninfo.com.cn {公司} 问询函 回复` 获取链接** |
| **港股聆讯：AP JSON返回空** | **公司可能已在"Inactive"或"Listed"列表，切换对应端点查询** |
| **港股聆讯：AP/PHIP文件被移除** | **非活跃个案文件会下线，需及时下载；或从WebArchive查找缓存** |
| **港股聆讯：只有AP无PHIP** | **公司尚未聆讯，使用AP（申请版本）即可，数据时效性稍差** |
| **IPO企业：无年报/季报** | **正常现象，IPO企业以招股书+审计报告替代年报** |
| **IPO企业：财务数据仅最近3年** | **招股书通常覆盖报告期3年+1期，比年报少历史数据，属正常** |

---

## 依赖说明

```
Python 3.12+
pdfplumber >= 0.10.0          # PDF 表格提取（主力）
pdfminer.six >= 20221105       # PDF 纯文本提取（备用）
openpyxl >= 3.1.0             # Excel 生成
python-docx >= 1.1.0          # Word 生成
requests >= 2.31.0            # HTTP 请求
Pillow >= 10.0.0              # 图片处理（GLM视觉兜底）

Node.js 22.12.0+
docx-js                        # Word排版引擎
```

---

## 质量标杆

金钼股份报告为本 Skill 的质量标杆：
- **92段叙述 + 14张表格**
- 全自动生成，无手工内容
- 数据全部来自PDF提取 + LLM生成
- 所有金额单位为万元、两位小数

---

## 参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 巨潮网API规范 | [references/cninfo_api.md](references/cninfo_api.md) | A股公告查询与PDF下载完整API |
| 港交所API规范 | [references/hkex_api.md](references/hkex_api.md) | 港股公告查询与PDF下载完整API |
| IPO/聆讯API规范 | [references/ipo_api.md](references/ipo_api.md) | A股IPO申报+港股AP/PHIP数据源与API |
| 债券信息API规范 | [references/bond_info_api.md](references/bond_info_api.md) | 7个债券平台API规范 |
| PDF提取规范 | [references/pdf_extraction.md](references/pdf_extraction.md) | 财务报表识别与提取规则 |
| 财务指标公式 | [references/financial_indicators.md](references/financial_indicators.md) | 五类指标计算公式 |
| 报告模板 | [references/report_template.md](references/report_template.md) | Word报告章节模板 |

---

## 与"巨潮公告审查"Skill的关系

本 Skill 是原"企业披露信息抓取"与"巨潮公告审查"的整合升级版：

| 维度 | 旧版（分别） | 新版（整合） |
|------|------------|------------|
| PDF提取 | GLM视觉为主 | pdfplumber分类器为主 + GLM视觉兜底 |
| 报告生成 | 两个独立管道 | 统一V3管道（DeepSeek双模型+Node.js排版） |
| 排版 | 简单表格 | 7表6板块专业排版 |
| 数据合并 | 无 | pdfplumber+GLM合并策略 |
| 格式兼容 | 仅数组 | 数组+对象双格式 |

> **迁移说明**：旧版"企业披露信息抓取"和"巨潮公告审查"Skill 已于2026-05-22删除。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 3.0.0 | 2026-05-22 | 初始整合版：合并"企业披露信息抓取"+"巨潮公告审查"，融入V3管道+pdfplumber v4分类器 |
| 3.1.0 | 2026-05-26 | 增加港股上市公司支持：港交所披露易API（titleSearchServlet）、港股下载脚本、繁体科目分类器、港股货币单位转换、A股/港股路由分支 |
| 3.2.0 | 2026-05-26 | 增加IPO申报/聆讯阶段企业支持：A股IPO招股书下载（巨潮网+证监会平台+东方财富）、港股AP/PHIP下载（JSON端点）、IPO企业路由分支、招股书提取适配 |
| 3.2.1 | 2026-05-26 | 按用户指定4个官方信息源更新IPO路径：沪市1010/深市1017/北交所审核/港交所appindex；增加同名文件按披露时间取最新规则 |
| 3.3.0 | 2026-06-05 | **重大完善**：①新增「数据时间范围标准」章节，明确近三个完整年度+近一期规则，含动态计算算法和各类资料时间要求表；②新增四阶段迭代式交付流程（步骤9-13）：首次交付V1→检查验证（完整性+准确性）→修订交付V2→V1↔V2对比评估→决策矩阵判断是否需要进一步优化；③更新代理执行指南为四阶段交互式流程；④更新文件输出结构支持多版本归档；⑤新增自动对比脚本和验证报告模板 |
