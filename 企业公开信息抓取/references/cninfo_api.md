# 巨潮网 API 接口规范

## 1. 获取 orgId — topSearch API

**端点**：`POST http://www.cninfo.com.cn/new/information/topSearch/query`

```python
import requests

resp = requests.post(
    "http://www.cninfo.com.cn/new/information/topSearch/query",
    json={"keyWord": "002185", "maxSecNum": 10, "maxListNum": 5},
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    timeout=10
)
data = resp.json()

# 从 stockList 中提取 orgId
for stock in data.get("stockList", []):
    print(stock.get("orgId"), stock.get("fullName"), stock.get("code"))
```

**返回示例**：
```json
{
  "stockList": [
    {"orgId": "9900003862", "code": "002185", "fullName": "华天科技", "category": "A"}
  ]
}
```

---

## 2. 公告列表查询 — hisAnnouncement API

**端点**：`POST http://www.cninfo.com.cn/new/hisAnnouncement/query`

### 关键调用规范

```python
import requests
import time

def query_cninfo_announcements(stock_code: str, org_id: str, date_range: str = None, max_pages: int = 20):
    """
    查询巨潮网公告列表。

    Args:
        stock_code: 6位股票代码，如 "002185"
        org_id: 巨潮网组织ID，如 "9900003862"
        date_range: 日期范围，格式 "2023-01-01~2026-12-31"（为空则不限）
        max_pages: 最大翻页数

    Returns:
        list: 所有公告记录
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.cninfo.com.cn/new/disclosure/stock?stockCode={stock_code}&orgId={org_id}"
    })

    # 【必须】先访问个股页面获取 cookie
    session.get(
        f"https://www.cninfo.com.cn/new/disclosure/stock?stockCode={stock_code}&orgId={org_id}",
        timeout=15
    )
    time.sleep(0.5)

    all_announces = []
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    for page in range(1, max_pages + 1):
        payload = {
            "pageNum": page,
            "pageSize": 30,
            "tabName": "fulltext",
            "column": "szse",                        # 深交所
            "stock": f"{stock_code},{org_id}",        # 【关键】code,orgId 纯值，无前缀
            "isHLtitle": "true"
            # 【重要】不要设置 category 参数，已废弃，会过滤结果
        }

        # 如有日期范围则加入
        if date_range:
            payload["seDate"] = date_range

        try:
            resp = session.post(url, data=payload, timeout=15)
            data = resp.json()
            items = data.get("announcements", [])
            if not items:
                break
            all_announces.extend(items)
            print(f"  第{page}页: {len(items)}条, 累计{len(all_announces)}条")
        except Exception as e:
            print(f"  第{page}页请求失败: {e}")
            break

        time.sleep(0.3)

    return all_announces
```

### stock 参数格式（常见错误对照）

| 格式 | 示例 | 结果 | 说明 |
|------|------|------|------|
| ✅ 正确 | `002185,9900003862` | 返回全部公告 | code,orgId 纯值 |
| ❌ 错误 | `002185` | 0条 | 缺少 orgId |
| ❌ 错误 | `002185,orgId=9900003862` | 0条 | 多了 `orgId=` 前缀 |
| ❌ 错误 | `sz002185,9900003862` | 0条 | 股票代码加了交易所前缀 |

### column 参数（交易所对应值）

| 交易所 | column 值 |
|--------|----------|
| 深交所（SZSE） | `szse` |
| 上交所（SSE） | `sse` |
| 北交所（BSE） | `bse` |

---

## 3. 公告筛选规则

### 年度报告筛选

```python
def is_annual_report(title: str) -> bool:
    """判断是否为年度报告（排除摘要和英文版）"""
    if "年度报告" not in title and "年报" not in title:
        return False
    exclude = ["摘要", "英文", "更正", "补充", "修订"]
    return not any(kw in title for kw in exclude)

def extract_report_year(title: str) -> str:
    """从标题提取年度"""
    import re
    m = re.search(r"(20\d{2})", title)
    return m.group(1) if m else ""
```

### 审计报告筛选

```python
def is_audit_report(title: str) -> bool:
    """判断是否为年度审计报告（排除内控审计和专项审计）"""
    if "审计报告" not in title:
        return False
    exclude = ["内部控制", "专项", "内控", "补充"]
    return not any(kw in title for kw in exclude)
```

### 重大事项筛选

```python
MAJOR_EVENT_KEYWORDS = [
    "重大资产重组", "收购", "合并", "分立", "股权转让",
    "增发", "配股", "可转债发行", "股权激励",
    "关联交易", "担保公告", "诉讼", "仲裁",
    "前期会计差错更正", "会计政策变更",
    "业绩预告", "业绩修正", "利润分配",
    "停产", "重大合同", "对外投资"
]
```

---

## 4. PDF 下载

### 下载链接构造

```python
# adjunctUrl 示例: finalpage/2026-03-31/1225059984.PDF
pdf_url = f"http://static.cninfo.com.cn/{item['adjunctUrl']}"
```

### 下载函数

```python
import os

def download_pdf(session: requests.Session, url: str, save_path: str) -> bool:
    """下载巨潮网PDF文件"""
    try:
        resp = session.get(url, timeout=30, stream=True)
        resp.raise_for_status()
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

## 5. 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 返回0条公告 | stock 参数格式错误 | 检查是否为 `{code},{orgId}` 纯值 |
| 审计报告找不到 | 只查了第1页（最新30条） | 翻页至第2-5页查找 |
| category_sjdbg_szsh 无效 | 该分类代码已废弃 | 不设置 category 参数 |
| 下载PDF返回403 | Cookie 失效 | 重新访问个股页面后重试 |
| 频率限制返回空 | 请求过于频繁 | 页间间隔 0.3s，PDF下载间隔 0.5s |
