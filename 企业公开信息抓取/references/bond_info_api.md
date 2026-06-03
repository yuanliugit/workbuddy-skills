# 债券信息平台 API 接口规范

本文档覆盖7个主流债券信息披露平台的查询与下载规范。

---

## 平台1：中国货币网（chinamoney.com.cn）

### 1A — 评级报告查询

**页面入口**：`https://www.chinamoney.com.cn/chinese/scggxdjgs/?tab=3`

**搜索 API**（模拟表单提交）：
```python
import requests

def search_chinamoney_rating(company_name: str):
    """查询中国货币网主体评级报告"""
    url = "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/getXdjgsPage.do"
    payload = {
        "pageNo": 1,
        "pageSize": 20,
        "issuerName": company_name,
        "ratingAgency": "",
        "noticeType": "3",   # 3=评级报告
        "startDate": "",
        "endDate": ""
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.chinamoney.com.cn/chinese/scggxdjgs/?tab=3",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    resp = requests.post(url, data=payload, headers=headers, timeout=15)
    return resp.json()
```

**返回字段说明**：
- `issuerName`：发行人名称
- `ratingAgency`：评级机构
- `mainRating`：主体评级（如 AA、AA+）
- `ratingOutlook`：评级展望
- `noticeDate`：报告日期
- `fileUrl`：PDF 下载地址

### 1B — 债券发行查询

```python
def search_chinamoney_bond(company_name: str):
    """查询中国货币网银行间债券发行信息"""
    url = "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/getBondIssuePage.do"
    payload = {
        "pageNo": 1,
        "pageSize": 20,
        "issuerName": company_name,
        "bondType": "",   # 空=全部类型
        "startDate": "",
        "endDate": ""
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.chinamoney.com.cn/chinese/ywts/"
    }
    resp = requests.post(url, data=payload, headers=headers, timeout=15)
    return resp.json()
```

---

## 平台2：上海清算所（shclearing.com.cn）

### 债券检索

```python
def search_shclearing(company_name: str):
    """上海清算所债券检索"""
    url = "https://www.shclearing.com.cn/shchapp/pages/client/search/bond_do_search.jsp"
    params = {"issuerName": company_name, "bondType": ""}
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    # 返回 HTML，需解析
    return resp.text
```

### 发行披露下载

各类债券的发行披露页面格式：
```
https://www.shclearing.com.cn/xxpl/fxpl/{券种}/
```

券种代码：
- `cyzq`：超短期融资券（SCP）
- `dqrzzq`：短期融资券（CP）
- `znpn`：中期票据（MTN）
- `ppn`：定向工具（PPN）

---

## 平台3：上交所债券项目信息平台（bond.sse.com.cn）

### 项目查询

```python
def search_sse_bond(company_name: str):
    """上交所债券项目查询"""
    url = "https://bond.sse.com.cn/bridge/information/progress_search/"
    params = {
        "ISSUERNAME": company_name,
        "BONDTYPE": "",
        "APPLICATIONSTATUS": "",
        "pageHelp.pageSize": 50,
        "pageHelp.pageNo": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://bond.sse.com.cn/information/progress_search/",
        "X-Requested-With": "XMLHttpRequest"
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    return resp.json()
```

### 公告文件下载

```python
# 上交所公告下载链接格式
# https://bond.sse.com.cn/disclosure/bondsDisclosure/view/{文件ID}
```

---

## 平台4：深交所固定收益信息平台（bond.szse.cn）

### 公告查询

```python
def search_szse_bond(company_name: str):
    """深交所债券信息查询"""
    url = "http://bond.szse.cn/api/search/bond/project"
    payload = {
        "keyword": company_name,
        "pageNo": 1,
        "pageSize": 20
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Referer": "http://bond.szse.cn/disclosure/bond/notice/index.html"
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    return resp.json()
```

---

## 平台5：孔雀开屏系统 / 交易商协会（zhuce.nafmii.org.cn）

### 公众查询入口

**页面**：`http://zhuce.nafmii.org.cn/fans/publicQuery/manager`

> ⚠️ 孔雀开屏系统需要通过 Playwright 进行浏览器自动化操作，不支持纯 API 调用。

**Playwright 操作流程**：
```python
# 需要 agent-browser skill 支持
# 1. 打开公众查询页面
# 2. 在"发行人名称"输入框填入公司名称
# 3. 点击"查询"按钮
# 4. 提取注册项目列表
# 5. 逐项点击查看注册材料并下载
```

**可获取内容**：
- 注册项目基本信息（债券类型、注册规模、注册期限）
- 注册进度状态
- 注册材料文件（募集说明书、评级报告、财务报表等）
- 交易商协会评议反馈

---

## 平台6：北交所（bse.cn）

### 债券公告查询

```python
def search_bse_bond(company_name: str):
    """北交所债券公告查询"""
    url = "https://www.bse.cn/nq/gzzqnotice.html"
    # 主要通过 WebSearch 搜索 "{公司名称} site:bse.cn 债券"
    # 或直接访问北交所公告列表页面
```

---

## 平台7：中国债券信息网（chinabond.com.cn）

**适用场景**：发改委体系的企业债、项目收益债查询。

```
https://www.chinabond.com.cn/
搜索关键词: {公司名称} 企业债
```

---

## 综合搜索策略

对于发债企业，按以下顺序依次查询：

```python
BOND_SEARCH_SEQUENCE = [
    # (平台名称, 搜索函数, 适用债券类型)
    ("中国货币网-评级",    search_chinamoney_rating, "评级报告"),
    ("中国货币网-发行",    search_chinamoney_bond,   "银行间市场债券"),
    ("上交所",             search_sse_bond,          "公司债/企业债（交易所）"),
    ("深交所",             search_szse_bond,          "公司债/企业债（交易所）"),
    ("孔雀开屏",           None,                      "银行间注册文件（需Playwright）"),
    ("上海清算所",         search_shclearing,         "银行间清算债券"),
    ("北交所",             search_bse_bond,           "公司债（北交所）"),
]
```

---

## 文件命名规范

下载文件统一命名格式：

```
{文件类型}_{发行人}_{年份}_{序号}.pdf

示例：
评级报告_北方长龙建设投资_2025_001.pdf
募集说明书_北方长龙建设投资_2024MTN001.pdf
债券发行公告_北方长龙建设投资_2024_001.pdf
跟踪评级报告_北方长龙建设投资_2025_001.pdf
```
