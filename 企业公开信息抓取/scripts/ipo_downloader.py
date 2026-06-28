#!/usr/bin/env python3
"""
IPO/聆讯阶段企业资料下载脚本

支持：
- A股IPO招股说明书（巨潮网 hisAnnouncement API + 证监会/北交所WebSearch兜底）
- 港股AP/PHIP文件（港交所JSON端点）

核心规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。

A股IPO官方信息源：
- 沪市：http://eid.csrc.gov.cn/ipo/1010/index.html
- 深市：http://eid.csrc.gov.cn/ipo/1017/index.html
- 北交所：https://www.bse.cn/audit/audit_disclosure.html

港股IPO官方信息源：
- 港交所：https://www1.hkexnews.hk/app/appindex.html?lang=zh

用法：
  python ipo_downloader.py --company "公司名称" --market a --output "./output"
  python ipo_downloader.py --company "公司名称" --market hk --board sehk --output "./output"
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)


# ============================================================
# 同名文件去重：按披露时间取最新
# ============================================================

def deduplicate_by_name(docs: list, name_key: str = "title",
                        date_key: str = "announcementTime") -> list:
    """
    同名文件去重：如文件名称完全一致，取披露时间最新者。

    Args:
        docs: 文件列表
        name_key: 文件名字段
        date_key: 披露时间字段
    Returns:
        去重后的文件列表
    """
    by_name = {}
    for doc in docs:
        name = doc.get(name_key, "")
        date_val = doc.get(date_key, 0)
        if name not in by_name or date_val > by_name[name].get(date_key, 0):
            by_name[name] = doc
    return list(by_name.values())


# ============================================================
# A股IPO信息源配置
# ============================================================

A_SHARE_IPO_SOURCES = {
    "sh": {
        "name": "沪市（主板+科创板）",
        "url": "http://eid.csrc.gov.cn/ipo/1010/index.html",
        "cninfo_column": "sse",
        "has_api": False,  # 证监会平台无API
        "search_hint": "site:eid.csrc.gov.cn/ipo/1010 {公司名称} 招股说明书",
    },
    "sz": {
        "name": "深市（主板+创业板）",
        "url": "http://eid.csrc.gov.cn/ipo/1017/index.html",
        "cninfo_column": "szse",
        "has_api": False,
        "search_hint": "site:eid.csrc.gov.cn/ipo/1017 {公司名称} 招股说明书",
    },
    "bse": {
        "name": "北交所",
        "url": "https://www.bse.cn/audit/audit_disclosure.html",
        "cninfo_column": "bse",
        "has_api": False,
        "search_hint": "site:bse.cn {公司名称} 招股说明书",
    },
}


# ============================================================
# A股IPO招股书下载（巨潮网 + 证监会/北交所WebSearch兜底）
# ============================================================

CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"


def cninfo_search_ipo(company_name: str, column: str = "szse",
                      category: str = "category_sc_gk_ssgs",
                      date_range: str = "2022-01-01~2026-12-31",
                      max_pages: int = 10) -> list:
    """从巨潮网查询IPO相关公告"""
    results = []

    for page in range(1, max_pages + 1):
        try:
            resp = requests.post(
                CNINFO_QUERY_URL,
                data={
                    "pageNum": page,
                    "pageSize": 30,
                    "column": column,
                    "tabName": "fulltext",
                    "plate": "",
                    "stock": "",
                    "searchkey": company_name,
                    "secid": "",
                    "category": category,
                    "trade": "",
                    "seDate": date_range,
                    "sortName": "",
                    "sortType": "",
                    "isHLtitle": "true",
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "application/json",
                },
                timeout=15
            )
            data = resp.json()
        except Exception as e:
            print(f"  [WARN] 巨潮网查询第{page}页失败: {e}")
            break

        anns = data.get("announcements", [])
        if not anns:
            break

        for ann in anns:
            title = ann.get("announcementTitle", "")
            adjunct_url = ann.get("adjunctUrl", "")
            ann_time = ann.get("announcementTime", 0)
            sec_name = ann.get("secName", "")

            results.append({
                "title": title,
                "adjunctUrl": adjunct_url,
                "announcementTime": ann_time,
                "secName": sec_name,
                "source": "cninfo",
            })

        # 检查是否还有下一页
        total_ann = data.get("totalAnnouncement", 0)
        if page * 30 >= total_ann:
            break

        time.sleep(0.3)

    return results


def cninfo_download_pdf(adjunct_url: str, save_path: str) -> bool:
    """下载巨潮网PDF"""
    full_url = f"{CNINFO_DOWNLOAD_BASE}{adjunct_url}"
    try:
        resp = requests.get(
            full_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=60
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            size_mb = len(resp.content) / 1024 / 1024
            print(f"  [OK] 已下载: {os.path.basename(save_path)} ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  [WARN] 下载失败: HTTP {resp.status_code}, size={len(resp.content)}")
            return False
    except Exception as e:
        print(f"  [ERROR] 下载异常: {e}")
        return False


def download_a_share_ipo(company_name: str, output_dir: str, board: str = ""):
    """
    下载A股IPO招股书及相关文件
    
    Args:
        company_name: 公司全称
        output_dir: 输出目录
        board: 指定板块 "sh"/"sz"/"bse"，为空则搜全市场
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  A股IPO资料下载：{company_name}")
    if board:
        src = A_SHARE_IPO_SOURCES.get(board, {})
        print(f"  指定板块：{src.get('name', board)}")
        print(f"  官方平台：{src.get('url', 'N/A')}")
    print(f"{'='*60}")

    # 搜索IPO公告（巨潮网备选）
    print("\n[1/4] 搜索IPO公告（巨潮网API）...")
    all_anns = []
    if board and board in A_SHARE_IPO_SOURCES:
        # 指定板块，仅搜对应交易所
        column = A_SHARE_IPO_SOURCES[board]["cninfo_column"]
        anns = cninfo_search_ipo(company_name, column=column)
        all_anns.extend(anns)
        if anns:
            print(f"  {column}: 找到 {len(anns)} 条公告")
    else:
        # 未指定板块，搜全市场
        for column in ["szse", "sse", "bse"]:
            anns = cninfo_search_ipo(company_name, column=column)
            all_anns.extend(anns)
            if anns:
                print(f"  {column}: 找到 {len(anns)} 条公告")

    if not all_anns:
        print("  [WARN] 巨潮网未找到IPO公告")
        print("  提示：请通过以下官方平台手动查找：")
        for src_key, src_info in A_SHARE_IPO_SOURCES.items():
            print(f"    {src_info['name']}: {src_info['url']}")
            print(f"      搜索格式：{src_info['search_hint'].format(company_name=company_name)}")
        print("  或使用 WebSearch / agent-browser skill 访问上述页面")
        return []

    # 分类筛选
    prospectus_keywords = ["招股说明书", "招股意向书"]
    inquiry_keywords = ["问询", "回复", "审核中心意见", "落实函"]
    audit_keywords = ["审计报告"]
    other_keywords = ["法律意见书", "保荐书", "发行保荐"]

    prospectus = []
    inquiry = []
    audit = []
    other_ipo = []

    for ann in all_anns:
        title = ann["title"]
        if any(kw in title for kw in prospectus_keywords):
            prospectus.append(ann)
        elif any(kw in title for kw in inquiry_keywords):
            inquiry.append(ann)
        elif any(kw in title for kw in audit_keywords):
            audit.append(ann)
        elif any(kw in title for kw in other_keywords):
            other_ipo.append(ann)

    print(f"\n  招股说明书: {len(prospectus)} 份")
    print(f"  问询/回复: {len(inquiry)} 份")
    print(f"  审计报告: {len(audit)} 份")
    print(f"  其他IPO文件: {len(other_ipo)} 份")

    # 同名文件去重：按披露时间取最新版
    print("\n[2/4] 同名文件去重（按披露时间取最新）...")
    prospectus = deduplicate_by_name(prospectus)
    inquiry = deduplicate_by_name(inquiry)
    audit = deduplicate_by_name(audit)
    other_ipo = deduplicate_by_name(other_ipo)
    print(f"  去重后：招股说明书 {len(prospectus)} / 问询 {len(inquiry)} / 审计 {len(audit)} / 其他 {len(other_ipo)}")

    # 下载文件
    print("\n[3/4] 下载文件...")
    downloaded = []

    # 优先下载招股说明书
    for i, ann in enumerate(prospectus):
        if not ann["adjunctUrl"]:
            continue
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', ann["title"])
        save_path = os.path.join(output_dir, f"招股说明书_{safe_title}.pdf")
        if cninfo_download_pdf(ann["adjunctUrl"], save_path):
            downloaded.append(save_path)
        time.sleep(0.3)

    # 下载审计报告
    for ann in audit:
        if not ann["adjunctUrl"]:
            continue
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', ann["title"])
        save_path = os.path.join(output_dir, f"审计报告_{safe_title}.pdf")
        if cninfo_download_pdf(ann["adjunctUrl"], save_path):
            downloaded.append(save_path)
        time.sleep(0.3)

    # 下载问询函（最多5份）
    for ann in inquiry[:5]:
        if not ann["adjunctUrl"]:
            continue
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', ann["title"])
        save_path = os.path.join(output_dir, f"问询函_{safe_title}.pdf")
        if cninfo_download_pdf(ann["adjunctUrl"], save_path):
            downloaded.append(save_path)
        time.sleep(0.3)

    # 下载其他IPO文件（最多3份）
    for ann in other_ipo[:3]:
        if not ann["adjunctUrl"]:
            continue
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', ann["title"])
        save_path = os.path.join(output_dir, f"IPO文件_{safe_title}.pdf")
        if cninfo_download_pdf(ann["adjunctUrl"], save_path):
            downloaded.append(save_path)
        time.sleep(0.3)

    print(f"\n[4/4] 下载完成，共 {len(downloaded)} 个文件")
    return downloaded


# ============================================================
# 港股AP/PHIP下载
# ============================================================

HKEX_AP_ENDPOINTS = {
    "sehk": {
        "active_ap": "https://www1.hkexnews.hk/ncms/json/eds/appactive_app_sehk_e.json",
        "active_phip": "https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_sehk_c.json",
        "listed": "https://www1.hkexnews.hk/ncms/json/eds/applisted_sehk_e.json",
    },
    "gem": {
        "active_ap": "https://www1.hkexnews.hk/ncms/json/eds/appactive_app_gem_e.json",
        "active_phip": "https://www1.hkexnews.hk/ncms/json/eds/appactive_appphip_gem_c.json",
        "listed": "https://www1.hkexnews.hk/ncms/json/eds/applisted_gem_e.json",
    },
}


def hkex_get_doc_list(board: str = "sehk", include_phip: bool = True,
                       include_listed: bool = False) -> list:
    """获取港交所AP/PHIP文件列表"""
    endpoints = HKEX_AP_ENDPOINTS.get(board, HKEX_AP_ENDPOINTS["sehk"])
    results = []
    ts = str(int(time.time() * 1000))

    # 活跃申请版本（AP）
    ap_url = f"{endpoints['active_ap']}?_={ts}"
    try:
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
    except Exception as e:
        print(f"  [WARN] AP列表获取失败: {e}")

    # PHIP（聆讯后资料集）
    if include_phip:
        phip_url = f"{endpoints['active_phip']}?_={ts}"
        try:
            resp = requests.get(phip_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
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
                    "doc_type": "PHIP",
                    "file_size": item.get("ls", [{}])[0].get("s", ""),
                })
        except Exception as e:
            print(f"  [WARN] PHIP列表获取失败: {e}")

    # 已上市
    if include_listed:
        listed_url = f"{endpoints['listed']}?_={ts}"
        try:
            resp = requests.get(listed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
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
                    "doc_type": "Listed_Prospectus",
                    "file_size": item.get("ls", [{}])[0].get("s", ""),
                })
        except Exception as e:
            print(f"  [WARN] 已上市列表获取失败: {e}")

    return results


def hkex_download_pdf(pdf_url: str, save_path: str) -> bool:
    """下载港交所PDF（无需cookie）"""
    try:
        resp = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            size_mb = len(resp.content) / 1024 / 1024
            print(f"  [OK] 已下载: {os.path.basename(save_path)} ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  [WARN] 下载失败: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [ERROR] 下载异常: {e}")
        return False


def download_hk_ipo(company_name: str, board: str = "sehk",
                     include_phip: bool = True, output_dir: str = "."):
    """下载港股AP/PHIP文件"""
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  港股AP/PHIP资料下载：{company_name}")
    print(f"  板块: {'主板' if board == 'sehk' else '创业板'}")
    print(f"  官方页面: https://www1.hkexnews.hk/app/appindex.html?lang=zh")
    print(f"{'='*60}")

    # 获取文件列表
    print("\n[1/4] 获取AP/PHIP文件列表...")
    all_docs = hkex_get_doc_list(board=board, include_phip=include_phip)
    print(f"  共获取 {len(all_docs)} 个文件")

    # 按公司名称筛选
    target_docs = []
    name_lower = company_name.lower()
    for doc in all_docs:
        doc_name_lower = doc["name"].lower()
        # 匹配公司名称（支持部分匹配）
        if any(kw in doc_name_lower for kw in name_lower.split()):
            target_docs.append(doc)
        elif name_lower in doc_name_lower:
            target_docs.append(doc)

    if not target_docs:
        print(f"  [WARN] 未找到与 '{company_name}' 匹配的AP/PHIP文件")
        print(f"  当前活跃申请列表（前10个）：")
        for i, doc in enumerate(all_docs[:10]):
            print(f"    {i+1}. [{doc['doc_type']}] {doc['name']} ({doc['date']})")
        print(f"  请确认公司名称是否正确，或尝试英文名称")
        print(f"  也可直接访问官方页面查找：https://www1.hkexnews.hk/app/appindex.html?lang=zh")
        return []

    print(f"  匹配到 {len(target_docs)} 个文件：")
    for doc in target_docs:
        print(f"    [{doc['doc_type']}] {doc['name']} ({doc['date']})")

    # 同名文件去重：按披露时间取最新版
    print("\n[2/4] 同名文件去重（按披露时间取最新）...")
    target_docs = deduplicate_by_name(target_docs, name_key="name", date_key="date")
    print(f"  去重后：{len(target_docs)} 个文件")

    # 下载文件
    print("\n[3/4] 下载文件...")
    downloaded = []

    for doc in target_docs:
        if not doc["pdf_url"]:
            continue
        # 生成安全文件名
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', doc["name"])
        doc_type = doc["doc_type"]
        date = doc["date"]
        save_path = os.path.join(output_dir, f"{doc_type}_{safe_name}_{date}.pdf")

        if hkex_download_pdf(doc["pdf_url"], save_path):
            downloaded.append(save_path)
        time.sleep(0.5)

    print(f"\n[4/4] 下载完成，共 {len(downloaded)} 个文件")
    return downloaded


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="IPO/聆讯阶段企业资料下载\n\n"
        "A股IPO官方信息源：\n"
        "  沪市: http://eid.csrc.gov.cn/ipo/1010/index.html\n"
        "  深市: http://eid.csrc.gov.cn/ipo/1017/index.html\n"
        "  北交所: https://www.bse.cn/audit/audit_disclosure.html\n"
        "港股IPO官方信息源：\n"
        "  港交所: https://www1.hkexnews.hk/app/appindex.html?lang=zh\n"
        "\n"
        "核心规则：如文件名称完全一致，则按照披露时间选择时效性强的文件作为抓取对象。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--company", required=True, help="公司名称")
    parser.add_argument("--market", required=True, choices=["a", "hk"],
                       help="市场：a=A股IPO，hk=港股聆讯")
    parser.add_argument("--board", default="",
                       choices=["sehk", "gem", "sh", "sz", "bse", ""],
                       help="板块：港股 sehk=主板/gem=创业板；A股 sh=沪市/sz=深市/bse=北交所；留空=全市场")
    parser.add_argument("--output", default="./output", help="输出目录")
    parser.add_argument("--include-phip", action="store_true", default=True,
                       help="包含PHIP文件（默认开启）")
    parser.add_argument("--include-listed", action="store_true",
                       help="包含已上市招股书")

    args = parser.parse_args()

    if args.market == "a":
        # A股IPO：board参数映射到 sh/sz/bse
        a_board = ""
        if args.board in ("sh", "sz", "bse"):
            a_board = args.board
        download_a_share_ipo(args.company, args.output, board=a_board)
    elif args.market == "hk":
        # 港股：board参数映射到 sehk/gem
        hk_board = args.board if args.board in ("sehk", "gem") else "sehk"
        download_hk_ipo(args.company, board=hk_board,
                        include_phip=args.include_phip,
                        output_dir=args.output)


if __name__ == "__main__":
    main()
