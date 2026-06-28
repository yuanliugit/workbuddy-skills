#!/usr/bin/env python3
"""
cninfo_downloader.py — 巨潮网公告批量下载脚本

用法：
  python cninfo_downloader.py --company "华天科技" --code 002185 --org-id 9900003862 \
    --output D:\Workbuddy\企业披露信息抓取工作区\华天科技\00-基础资料
"""

import argparse
import os
import re
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Optional


# ─────────────────────────────────────────────
# 公告类型过滤规则
# ─────────────────────────────────────────────
def classify_announcement(title: str) -> Optional[str]:
    """
    判断公告类型，返回分类名称，无法识别则返回 None。
    """
    t = title.strip()

    # 年度报告（排除摘要/英文版）
    if re.search(r"年度报告|年报", t) and not re.search(r"摘要|英文|更正|补充|修订", t):
        year_m = re.search(r"(20\d{2})", t)
        year = year_m.group(1) if year_m else "未知年度"
        return f"年报_{year}"

    # 年度审计报告（排除内控审计/专项审计）
    if "审计报告" in t and not re.search(r"内部控制|专项|内控|补充", t):
        year_m = re.search(r"(20\d{2})", t)
        year = year_m.group(1) if year_m else "未知年度"
        return f"审计报告_{year}"

    # 季报/半年报
    if re.search(r"第[一二三四]季度报告|半年度报告|三季报", t):
        year_m = re.search(r"(20\d{2})", t)
        year = year_m.group(1) if year_m else "未知年度"
        return f"季报_{year}"

    # 招股说明书
    if re.search(r"招股说明书|招股意向书", t) and not re.search(r"更新|更正", t):
        return "招股说明书"

    # 重大事项
    MAJOR_KWS = ["重大资产重组", "收购报告书", "增发", "配股", "股权转让",
                 "关联交易", "担保公告", "诉讼", "仲裁", "业绩预告",
                 "前期会计差错更正", "重大合同"]
    for kw in MAJOR_KWS:
        if kw in t:
            return f"重大事项"

    return None


# ─────────────────────────────────────────────
# 主下载流程
# ─────────────────────────────────────────────
class CninfoDownloader:
    BASE_URL = "http://www.cninfo.com.cn"
    QUERY_URL = f"{BASE_URL}/new/hisAnnouncement/query"
    STATIC_URL = "http://static.cninfo.com.cn"

    def __init__(self, stock_code: str, org_id: str, exchange: str = "szse"):
        self.stock_code = stock_code
        self.org_id = org_id
        self.exchange = exchange  # szse / sse / bse
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.BASE_URL}/new/disclosure/stock?stockCode={stock_code}&orgId={org_id}"
        })

    def init_session(self):
        """访问个股页面获取 Cookie"""
        url = f"{self.BASE_URL}/new/disclosure/stock?stockCode={self.stock_code}&orgId={self.org_id}"
        self.session.get(url, timeout=15)
        time.sleep(0.5)
        print(f"  已初始化 session（Cookie 已获取）")

    def query_announcements(self, date_start: str = None, date_end: str = None, max_pages: int = 20):
        """
        分页查询公告列表。
        date_start/date_end 格式：YYYY-MM-DD
        """
        all_items = []

        date_range = None
        if date_start and date_end:
            date_range = f"{date_start}~{date_end}"

        for page in range(1, max_pages + 1):
            payload = {
                "pageNum": page,
                "pageSize": 30,
                "tabName": "fulltext",
                "column": self.exchange,
                "stock": f"{self.stock_code},{self.org_id}",
                "isHLtitle": "true"
            }
            if date_range:
                payload["seDate"] = date_range

            try:
                resp = self.session.post(self.QUERY_URL, data=payload, timeout=15)
                data = resp.json()
                items = data.get("announcements", [])
                if not items:
                    print(f"  第{page}页无数据，停止翻页")
                    break
                all_items.extend(items)
                print(f"  第{page}页: {len(items)}条，累计 {len(all_items)} 条")
                time.sleep(0.3)
            except Exception as e:
                print(f"  ⚠️ 第{page}页请求失败: {e}")
                break

        return all_items

    def download_pdf(self, adjunct_url: str, save_path: str) -> bool:
        """下载单个PDF文件"""
        if os.path.exists(save_path):
            print(f"  ⏭️  已存在，跳过: {os.path.basename(save_path)}")
            return True

        url = f"{self.STATIC_URL}/{adjunct_url}"
        try:
            resp = self.session.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_kb = os.path.getsize(save_path) / 1024
            print(f"  ✅ {os.path.basename(save_path)} ({size_kb:.0f}KB)")
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"  ❌ 下载失败: {url} — {e}")
            return False

    def run(self, output_dir: str, years_back: int = 4):
        """
        执行完整下载流程。
        years_back: 向前下载几年（默认4年）
        """
        os.makedirs(output_dir, exist_ok=True)
        self.init_session()

        # 计算时间范围
        now = datetime.now()
        date_start = f"{now.year - years_back}-01-01"
        date_end = now.strftime("%Y-%m-%d")
        print(f"\n查询时间范围: {date_start} ~ {date_end}")

        # 查询所有公告
        print("\n[步骤1] 查询公告列表...")
        all_items = self.query_announcements(date_start, date_end)
        print(f"共获取 {len(all_items)} 条公告")

        # 保存原始查询结果
        with open(os.path.join(output_dir, "_query_results.json"), "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)

        # 按类型过滤并下载
        print("\n[步骤2] 过滤并下载目标文件...")
        downloaded = 0
        skipped = 0

        for item in all_items:
            title = item.get("announcementTitle", "")
            adjunct_url = item.get("adjunctUrl", "")
            ann_date = item.get("announcementTime", "")[:10]  # YYYY-MM-DD

            doc_type = classify_announcement(title)
            if not doc_type or not adjunct_url:
                skipped += 1
                continue

            # 构造文件名
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
            filename = f"{doc_type}_{ann_date}_{safe_title}.pdf"
            save_path = os.path.join(output_dir, filename)

            print(f"\n  [{doc_type}] {title[:50]}")
            if self.download_pdf(adjunct_url, save_path):
                downloaded += 1

        print(f"\n✅ 下载完成: {downloaded} 个文件，跳过 {skipped} 条不相关公告")
        return downloaded


def get_org_id(stock_code: str) -> Optional[str]:
    """自动查询巨潮网 orgId"""
    try:
        resp = requests.post(
            "http://www.cninfo.com.cn/new/information/topSearch/query",
            json={"keyWord": stock_code, "maxSecNum": 10, "maxListNum": 5},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = resp.json()
        stocks = data.get("stockList", [])
        if stocks:
            org_id = stocks[0].get("orgId", "")
            full_name = stocks[0].get("fullName", "")
            print(f"  自动获取 orgId: {org_id}（{full_name}）")
            return org_id
    except Exception as e:
        print(f"  ⚠️ 自动获取 orgId 失败: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description="巨潮网公告批量下载")
    parser.add_argument("--company", required=True, help="公司名称（用于目录命名）")
    parser.add_argument("--code", required=True, help="股票代码（6位）")
    parser.add_argument("--org-id", default="", help="巨潮网 orgId（留空则自动获取）")
    parser.add_argument("--exchange", default="szse", choices=["szse", "sse", "bse"],
                        help="交易所: szse深交所/sse上交所/bse北交所")
    parser.add_argument("--output", required=True, help="输出目录路径")
    parser.add_argument("--years-back", type=int, default=4, help="向前下载几年（默认4年）")
    args = parser.parse_args()

    print(f"=== 巨潮网公告下载器 ===")
    print(f"公司: {args.company}  代码: {args.code}")

    # 获取 orgId
    org_id = args.org_id
    if not org_id:
        print("\n自动查询 orgId...")
        org_id = get_org_id(args.code)
        if not org_id:
            print("❌ 无法获取 orgId，请手动指定 --org-id 参数")
            return

    downloader = CninfoDownloader(args.code, org_id, args.exchange)
    downloader.run(args.output, args.years_back)


if __name__ == "__main__":
    main()
