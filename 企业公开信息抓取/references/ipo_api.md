# IPO/聆讯阶段企业 API 规范

> **核心规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。**

## 1. A股IPO申报企业

### 1.1 数据源概览（按板块对应官方平台）

| 板块 | 官方信息源 | URL | 获取方式 |
|------|-----------|-----|---------|
| 沪市（主板+科创板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1010/index.html` | 无API，WebSearch + 浏览器 |
| 深市（主板+创业板） | 证监会信息披露平台 | `http://eid.csrc.gov.cn/ipo/1017/index.html` | 无API，WebSearch + 浏览器 |
| 北交所 | 北交所审核信息披露 | `https://www.bse.cn/audit/audit_disclosure.html` | 无API，WebSearch + 浏览器 |
| 全市场（备选） | 巨潮网IPO专区 | `cninfo.com.cn` | hisAnnouncement API |
| 全市场（兜底） | 东方财富IPO数据中心 | `data.eastmoney.com/xg/ipo` | WebSearch |

### 1.2 证监会信息披露平台 — 沪市（1010）

**入口URL**：`http://eid.csrc.gov.cn/ipo/1010/index.html`

**特点**：
- 证监会官方IPO信息披露平台，覆盖主板+科创板
- 包含所有在审沪市IPO企业的招股说明书、问询函、回复等
- **无公开API**，页面数据为服务端渲染，无法通过JSON接口获取
- 文件列表按时间倒序排列，最新披露在前

**使用方式**：
```python
# 无法直接API调用，使用WebSearch搜索
# 搜索格式：site:eid.csrc.gov.cn {公司名称} 招股说明书
# 搜索格式：site:eid.csrc.gov.cn/ipo/1010 {公司名称} 审计报告

# 或使用agent-browser skill访问页面抓取
# 页面结构：项目列表 → 点击公司名称 → 文件列表 → 下载PDF
```

**页面结构**：
- 主页面显示所有在审IPO项目列表（公司名称、板块、审核进度）
- 点击项目进入详情页，展示全部披露文件
- 文件类型包括：招股说明书（申报稿/上会稿/注册稿）、审计报告、问询函及回复、法律意见书、发行保荐书

### 1.3 证监会信息披露平台 — 深市（1017）

**入口URL**：`http://eid.csrc.gov.cn/ipo/1017/index.html`

**特点**：
- 与沪市同一平台，但入口URL不同（1017 vs 1010）
- 覆盖深市主板+创业板
- 同样**无公开API**

**使用方式**：
```python
# 同沪市，WebSearch搜索
# 搜索格式：site:eid.csrc.gov.cn/ipo/1017 {公司名称} 招股说明书

# 注意深市有"深市主板"和"创业板"两个子分类
# 创业板审核进度通常更快
```

### 1.4 北交所审核信息披露

**入口URL**：`https://www.bse.cn/audit/audit_disclosure.html`

**特点**：
- 北交所官方审核信息披露页面
- 文件分类：**申报稿、上会稿、注册稿、问询与回复**
- **无公开API**，需WebSearch或浏览器访问
- ⚠️ 注意：北交所的分页 pageNum 从 **0** 开始（与证监会平台不同）

**使用方式**：
```python
# WebSearch搜索
# 搜索格式：site:bse.cn {公司名称} 招股说明书
# 搜索格式：site:bse.cn/audit {公司名称} 审核

# 或使用agent-browser skill访问
# 页面可按项目名称搜索，展示审核进度和全部披露文件
```

**页面结构**：
- 顶部筛选栏：全部/申报稿/上会稿/注册稿/问询与回复
- 每个项目展示：公司名称、审核状态、受理日期、最新进展
- 点击项目查看完整文件列表

### 1.5 巨潮网IPO招股书查询（备选，可编程）

使用与上市公司公告相同的 hisAnnouncement 接口，但需使用特定 category：

```python
import requests, json

def search_ipo_prospectus(company_name: str, column: str = "szse") -> list:
    """
    从巨潮网查询IPO招股说明书（申报稿）
    
    Args:
        company_name: 公司全称或关键词
        column: "szse"（深交所）/ "sse"（上交所）/ "bse"（北交所）
    Returns:
        list of dict: [{title, adjunctUrl, announcementId, announcementTime}, ...]
    """
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    results = []
    
    for page in range(1, 10):  # 最多查10页
        resp = requests.post(
            url,
            data={
                "pageNum": page,
                "pageSize": 30,
                "column": column,
                "tabName": "fulltext",
                "plate": "",
                "stock": "",
                "searchkey": company_name,
                "secid": "",
                "category": "category_sc_gk_ssgs",  # 首次公开发行及上市
                "trade": "",
                "seDate": "2022-01-01~2026-12-31",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
            timeout=15
        )
        data = resp.json()
        anns = data.get("announcements", [])
        if not anns:
            break
        
        for ann in anns:
            title = ann.get("announcementTitle", "")
            # 筛选招股说明书（排除补充法律意见等）
            if any(kw in title for kw in ["招股说明书", "招股意向书"]):
                results.append({
                    "title": title,
                    "adjunctUrl": ann.get("adjunctUrl", ""),
                    "announcementId": ann.get("announcementId", ""),
                    "announcementTime": ann.get("announcementTime", ""),
                })
    
    return results

# 下载PDF
def download_cninfo_pdf(adjunct_url: str, save_path: str):
    """下载巨潮网PDF文件"""
    full_url = f"http://static.cninfo.com.cn/{adjunct_url}"
    resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    with open(save_path, "wb") as f:
        f.write(resp.content)
```

### 1.6 东方财富IPO数据中心（兜底）

**网址**：https://data.eastmoney.com/xg/ipo

**特点**：
- 汇总沪深北三所IPO审核进度
- 提供招股说明书PDF下载链接
- 可按公司名称/股票代码搜索

**使用方式**：
```python
# WebSearch搜索格式：
# site:data.eastmoney.com {公司名称} IPO 招股书
# 从搜索结果中提取下载链接
```

### 1.7 同名文件去重规则

**规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。**

```python
def deduplicate_by_name(docs: list, name_key: str = "title", date_key: str = "announcementTime") -> list:
    """
    同名文件去重：如文件名称完全一致，取披露时间最新者。
    
    Args:
        docs: 文件列表，每项包含 name_key 和 date_key
        name_key: 文件名字段
        date_key: 披露时间字段
    Returns:
        去重后的文件列表
    """
    by_name = {}
    for doc in docs:
        name = doc.get(name_key, "")
        date = doc.get(date_key, 0)
        if name not in by_name or date > by_name[name].get(date_key, 0):
            by_name[name] = doc
    return list(by_name.values())
```

### 1.8 IPO问询函及回复获取

```python
def search_inquiry_letters(company_name: str, column: str = "szse") -> list:
    """查询IPO问询函及回复"""
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    results = []
    
    # 问询函类别代码
    inquiry_categories = [
        "category_sc_gk_ssgs",  # 首次公开发行及上市
    ]
    
    for page in range(1, 5):
        resp = requests.post(
            url,
            data={
                "pageNum": page,
                "pageSize": 30,
                "column": column,
                "tabName": "fulltext",
                "searchkey": company_name,
                "category": "category_sc_gk_ssgs",
                "seDate": "2022-01-01~2026-12-31",
                "isHLtitle": "true",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        data = resp.json()
        anns = data.get("announcements", [])
        if not anns:
            break
        
        for ann in anns:
            title = ann.get("announcementTitle", "")
            if any(kw in title for kw in ["问询", "回复", "审核中心意见", "落实函"]):
                results.append({
                    "title": title,
                    "adjunctUrl": ann.get("adjunctUrl", ""),
                })
    
    return results
```

---

## 2. 港股聆讯阶段企业

### 2.0 官方信息源入口

**港交所新上市申请页面**：`https://www1.hkexnews.hk/app/appindex.html?lang=zh`

页面结构：
- 分为主板（MAIN BOARD）和创业板（GEM）两个板块
- 每个板块下有4个标签页：

| 标签 | 页面 | 内容 |
|------|------|------|
| 活跃个案 | SEHKAPPMainIndex.html | 正在审核中的申请 |
| 不活跃个案 | SEHKAPPInactiveCase.html | 已失效或被退回 |
| 已上市 | SEHKAPPListedCase.html | 已成功上市 |
| 已退回 | SEHKAPPReturnedCase.html | 被退回的申请 |

> **注意**：不活跃个案的文件可能被移除，无法下载。同名文件按披露时间取最新版。

### 2.1 港交所AP/PHIP JSON API

港交所通过以下JSON端点发布新上市申请信息（**无需认证，直接GET请求**）：

#### 活跃申请版本（AP）

| 板块 | URL | 说明 |
|------|-----|------|
| 主板 | `https://www1.hkexnews.hk/ncms/json/eds/appactive_app_sehk_e.json` | 英文版 |
| 创业板 | `https://www1.hkexnews.hk/ncms/json/eds/appactive_app_gem_e.json` | 英文版 |

#### 聆讯后资料集（PHIP）

| 板块 | URL | 说明 |
|------|-----|------|
| 主板 | `https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_sehk_c.json` | 中文版 |
| 创业板 | `https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_gem_c.json` | 中文版 |

#### 已上市

| 板块 | URL | 说明 |
|------|-----|------|
| 主板 | `https://www1.hkexnews.hk/ncms/json/eds/applisted_sehk_e.json` | 英文版 |
| 创业板 | `https://www1.hkexnews.hk/ncms/json/eds/applisted_gem_e.json` | 英文版 |

#### JSON数据结构

```json
{
  "app": [
    {
      "a": "公司名称/招股书名称",
      "d": "DD/MM/YYYY",
      "id": "内部ID",
      "ls": [
        {
          "u1": "相对路径（PDF链接）",
          "u2": "显示名称",
          "s": "文件大小"
        }
      ]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 含义 | 示例 |
|------|------|------|------|
| `a` | string | 公司名称/文件标题 | "XX Holdings Limited" |
| `d` | string | 日期（DD/MM/YYYY格式） | "15/05/2026" |
| `id` | string | 港交所内部ID | "25101501235" |
| `ls` | array | 文件列表 | — |
| `ls[].u1` | string | PDF相对路径 | "SEHK/2026/0515/..." |
| `ls[].u2` | string | 文件显示名 | "Application Proof" |
| `ls[].s` | string | 文件大小 | "12.5 MB" |

**PDF完整URL拼接规则**：
```
https://www1.hkexnews.hk/app/ + ls[0].u1
```

#### 使用示例

```python
import requests, json, time

def get_hkex_ap_list(board: str = "sehk", tab: str = "active", include_phip: bool = True) -> list:
    """
    获取港交所新上市申请文件列表
    
    Args:
        board: "sehk"（主板）或 "gem"（创业板）
        tab: "active"（活跃）/"listed"（已上市）
        include_phip: 是否包含PHIP
    """
    results = []
    ts = str(int(time.time() * 1000))
    
    # AP列表
    if tab == "active":
        ap_url = f"https://www1.hkexnews.hk/ncms/json/eds/appactive_app_{board}_e.json?_={ts}"
    elif tab == "listed":
        ap_url = f"https://www1.hkexnews.hk/ncms/json/eds/applisted_{board}_e.json?_={ts}"
    
    resp = requests.get(ap_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    data = resp.json()
    
    for item in data.get("app", []):
        date_str = item.get("d", "")
        parts = date_str.split("/")
        date_fmt = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else date_str
        pdf_url = "https://www1.hkexnews.hk/app/" + item.get("ls", [{}])[0].get("u1", "")
        
        results.append({
            "name": item.get("a", ""),
            "date": date_fmt,
            "id": item.get("id", ""),
            "pdf_url": pdf_url,
            "doc_type": "AP",
            "file_size": item.get("ls", [{}])[0].get("s", ""),
        })
    
    # PHIP列表
    if include_phip and tab == "active":
        phip_url = f"https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_{board}_c.json?_={ts}"
        resp2 = requests.get(phip_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data2 = resp2.json()
        
        for item in data2.get("app", []):
            date_str = item.get("d", "")
            parts = date_str.split("/")
            date_fmt = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else date_str
            pdf_url = "https://www1.hkexnews.hk/app/" + item.get("ls", [{}])[0].get("u1", "")
            
            results.append({
                "name": item.get("a", ""),
                "date": date_fmt,
                "id": item.get("id", ""),
                "pdf_url": pdf_url,
                "doc_type": "PHIP",
                "file_size": item.get("ls", [{}])[0].get("s", ""),
            })
    
    return results


def download_hkex_pdf(pdf_url: str, save_path: str):
    """下载港交所PDF文件（无需cookie）"""
    resp = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    with open(save_path, "wb") as f:
        f.write(resp.content)
    print(f"已下载: {save_path} ({len(resp.content) / 1024 / 1024:.1f} MB)")
```

### 2.2 AP/PHIP页面导航结构

港交所AP/PHIP页面分为4个标签页：

| 标签 | 页面 | 内容 |
|------|------|------|
| 活跃个案 | `SEHKAPPMainIndex.html` | 正在审核中的申请 |
| 不活跃个案 | `SEHKAPPInactiveCase.html` | 已失效或被退回 |
| 已上市 | `SEHKAPPListedCase.html` | 已成功上市 |
| 已退回 | `SEHKAPPReturnedCase.html` | 被退回的申请 |

> **注意**：不活跃个案的文件可能被移除，无法下载。

### 2.3 招股书PDF URL规律（已上市公司）

对于已通过聆讯并上市的公司，其正式招股书PDF遵循以下URL规律：

```
https://www1.hkexnews.hk/listedco/listconews/sehk/{YYYY}/{MMDD}/{YYYYMMDD}{NNNNN}.pdf
```

- 序列号（`NNNNN`）只有**奇数**存在
- 招股书集中在序列号 **1-50**，文件大小通常 **>2MB**

### 2.4 Stock Code映射

通过 `activestock_sehk_e.json` 可将股票代码映射为港交所内部ID（约18,688条记录）：

```python
def load_stock_code_map() -> dict:
    """加载股票代码到港交所内部ID的映射"""
    url = "https://www1.hkexnews.hk/ncms/json/eds/activestock_sehk_e.json"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    data = resp.json()
    
    code_map = {}
    for item in data.get("stock", []):
        code = item.get("sc", "")  # stock code
        sid = item.get("si", "")   # stock id
        name = item.get("n", "")   # name
        code_map[code] = {"id": sid, "name": name}
    
    return code_map
```

---

## 3. IPO企业工作流差异

### 3.1 与已上市企业的关键差异

| 维度 | 已上市企业 | IPO/聆讯企业 |
|------|-----------|-------------|
| 核心文件 | 年报（3年）+ 审计报告 | 招股说明书 + 审计报告附件 |
| 财务数据覆盖 | 报告年度+上年度 | 报告期3年+最近1期 |
| 是否有季报 | 有 | 无（尚未上市） |
| 审计报告 | 独立PDF | 含在招股书附件或单独披露 |
| 问询函 | 无 | 有（多轮问询+回复） |
| 行业信息 | 年报"管理层讨论"章节 | 招股书"业务与技术"章节（更详细） |
| 债券信息 | 可能有 | 通常无 |

### 3.2 IPO企业报告模板调整

IPO企业的审查报告需调整：

| 调整项 | 说明 |
|--------|------|
| 工商信息 | 无股票代码，标注"IPO申报中"/"聆讯阶段" |
| 数据来源 | 标注"招股说明书（申报稿/PHIP）"而非"年度报告" |
| 时间范围 | 报告期3年+1期（如2022-2024+2025H1） |
| 风险因素 | 重点关注招股书"风险因素"章节+问询函回复 |
| 缺少本部报表 | 招股书通常只有合并报表，本部报表可能缺失 |
| 上市进度 | 增加审核进度跟踪（受理→问询→过会→注册→发行） |
