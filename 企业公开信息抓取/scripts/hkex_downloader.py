#!/usr/bin/env python3
"""
港交所披露易（HKEXnews）公告下载脚本

功能：
  - 通过 titleSearchServlet API 搜索港股上市公司公告
  - 下载年度报告、中期报告、招股说明书、重大事项公告 PDF
  - 支持按股票代码/stockId 筛选
  - 自动跳过"多檔案"（分片PDF）格式

用法：
  python hkex_downloader.py --company "腾讯控股" --code "00700" --stock-id "1000226850" --output "D:\Workbuddy\企业披露信息抓取工作区\腾讯控股\00-基础资料"
  python hkex_downloader.py --company "腾讯控股" --code "00700" --output "./output"  # 无stockId时自动搜索

依赖：
  pip install requests
"""

import argparse
import json
import os
import re
import sys
import time

import requests


# ═══════════════════════════════════════════════════════════
# 常量定义
# ═══════════════════════════════════════════════════════════

SEARCH_URL = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
PDF_BASE = "https://www1.hkexnews.hk/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml",
}

# t2code 二级分类代码
T2CODE_MAP = {
    "announcement": "40100",   # 公告及通函
    "annual_report": "40200",  # 年度报告
    "interim_report": "40300", # 中期报告
    "quarterly_report": "40400",# 季度报告
    "prospectus": "40500",    # 招股章程
    "circular": "40600",      # 通函
}

# 必须下载的文档类型及其搜索参数
REQUIRED_DOCS = [
    {
        "name": "年度报告",
        "t2code": "40200",
        "title_kw": "",
        "filter": lambda t: _is_annual_report(t),
        "filename_tmpl": "年报_{year}.pdf",
    },
    {
        "name": "中期报告",
        "t2code": "40300",
        "title_kw": "",
        "filter": lambda t: _is_interim_report(t),
        "filename_tmpl": "中报_{year}.pdf",
    },
    {
        "name": "招股说明书",
        "t2code": "40500",
        "title_kw": "",
        "filter": lambda t: _is_prospectus(t),
        "filename_tmpl": "招股书_{year}.pdf",
    },
    {
        "name": "重大事项公告",
        "t2code": "40100",
        "title_kw": "",
        "filter": lambda t: _is_major_event(t),
        "filename_tmpl": "重大事项_{year}_{idx}.pdf",
    },
]


# ═══════════════════════════════════════════════════════════
# 筛选函数
# ═══════════════════════════════════════════════════════════

def _is_annual_report(title: str) -> bool:
    kw = ["年度报告", "年報", "年报", "Annual Report"]
    if not any(k in title for k in kw):
        return False
    exclude = ["摘要", "簡要", "英文", "English", "更正", "補充", "补充", "修订", "環境", "ESG", "可持續"]
    return not any(k in title for k in exclude)


def _is_interim_report(title: str) -> bool:
    kw = ["中期报告", "中期報告", "中報", "半年报", "半年報", "Interim Report"]
    if not any(k in title for k in kw):
        return False
    exclude = ["摘要", "英文", "English", "更正", "補充"]
    return not any(k in title for k in exclude)


def _is_prospectus(title: str) -> bool:
    kw = ["招股说明书", "招股章程", "Prospectus"]
    return any(k in title for k in kw)


def _is_major_event(title: str) -> bool:
    kw = [
        "重大交易", "須予公布的交易", "非常重大收购", "Very Substantial",
        "主要交易", "Major Transaction", "收购", "Acquisition",
        "配售", "Placing", "供股", "Rights Issue",
        "关连交易", "Connected Transaction",
        "清盘", "Winding", "接管", "Receivership",
        "债务重组", "Debt Restructuring",
    ]
    return any(k in title for k in kw)


def _extract_year(title: str) -> str:
    """从标题提取年度"""
    m = re.search(r"(20\d{2})", title)
    return m.group(1) if m else "unknown"


# ═══════════════════════════════════════════════════════════
# API 调用
# ═══════════════════════════════════════════════════════════

def search_announcements(stock_id: str, t2code: str, from_date: str, to_date: str,
                         title: str = "", lang: str = "zh") -> list:
    """
    查询港交所公告列表。
    
    Args:
        stock_id: 港交所内部 stockId，"-1" 表示全部
        t2code: 二级分类代码
        from_date: 起始日期 YYYYMMDD
        to_date: 截止日期 YYYYMMDD
        title: 标题关键词
        lang: 语言 zh/EN
    
    Returns:
        公告记录列表
    """
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
        "t1code": "40000",
        "t2Gcode": "-2",
        "t2code": t2code,
        "rowRange": "2000",
        "lang": lang,
    }
    
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        outer = resp.json()
        # 双层 JSON 解析
        inner = json.loads(outer["result"])
        return inner if isinstance(inner, list) else []
    except Exception as e:
        print(f"  ❌ 搜索请求失败: {e}")
        return []


def find_stock_id(stock_code: str, stock_name: str = "") -> str:
    """
    通过股票代码或名称查找港交所内部 stockId。
    搜索全部公告，从结果中匹配目标股票。
    """
    print(f"  正在查找 {stock_code} 的 stockId...")
    
    # 用年报分类搜索，结果通常较少
    items = search_announcements(
        stock_id="-1",
        t2code="40200",
        from_date="20240101",
        to_date="20261231",
        title=stock_name or stock_code,
    )
    
    for item in items:
        sc = str(item.get("STOCK_CODE", ""))
        sn = str(item.get("STOCK_NAME", ""))
        # 匹配股票代码（去掉前导0比较）
        if sc.lstrip("0") == stock_code.lstrip("0"):
            sid = str(item.get("STOCK_ID", ""))
            print(f"  ✅ 找到 stockId={sid} (代码={sc}, 名称={sn})")
            return sid
        # 匹配名称
        if stock_name and stock_name in sn:
            sid = str(item.get("STOCK_ID", ""))
            print(f"  ✅ 找到 stockId={sid} (代码={sc}, 名称={sn})")
            return sid
    
    print(f"  ⚠️ 未找到 {stock_code} 的 stockId，将使用 stockId=-1（搜索全部）")
    return "-1"


def download_pdf(url: str, save_path: str) -> bool:
    """下载港交所 PDF 文件"""
    try:
        resp = requests.get(url, timeout=30, stream=True, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.hkexnews.hk/",
        })
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


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="港交所披露易公告下载")
    parser.add_argument("--company", required=True, help="公司名称")
    parser.add_argument("--code", required=True, help="股票代码（如 00700）")
    parser.add_argument("--stock-id", default="", help="港交所内部 stockId（为空时自动查找）")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--from-year", default="2022", help="起始年度")
    parser.add_argument("--to-year", default="2026", help="截止年度")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  港交所公告下载 — {args.company} ({args.code})")
    print(f"{'='*60}\n")
    
    # 1. 获取 stockId
    stock_id = args.stock_id
    if not stock_id:
        stock_id = find_stock_id(args.code, args.company)
    
    # 2. 逐类型搜索并下载
    from_date = f"{args.from_year}0101"
    to_date = f"{args.to_year}1231"
    
    total_downloaded = 0
    
    for doc_type in REQUIRED_DOCS:
        print(f"\n--- 搜索 {doc_type['name']} (t2code={doc_type['t2code']}) ---")
        
        items = search_announcements(
            stock_id=stock_id,
            t2code=doc_type["t2code"],
            from_date=from_date,
            to_date=to_date,
        )
        
        print(f"  返回 {len(items)} 条记录")
        
        # 筛选 + 去重
        matched = []
        seen_years = set()
        for item in items:
            title = str(item.get("TITLE", ""))
            stock_code = str(item.get("STOCK_CODE", ""))
            
            # 如果指定了stock_id，确保结果匹配
            if stock_id != "-1" and item.get("STOCK_ID") and str(item["STOCK_ID"]) != stock_id:
                continue
            
            if not doc_type["filter"](title):
                continue
            
            # 跳过多档案格式
            file_info = str(item.get("FILE_INFO", ""))
            if "多檔案" in file_info or "multi-file" in file_info.lower():
                print(f"  ⏭ 跳过多档案格式: {title}")
                continue
            
            year = _extract_year(title)
            
            # 年报/中报同年度去重（取最新的）
            if doc_type["name"] in ["年度报告", "中期报告"]:
                if year in seen_years:
                    continue
                seen_years.add(year)
            
            matched.append((item, title, year))
        
        # 下载
        idx = 0
        for item, title, year in matched:
            file_link = str(item.get("FILE_LINK", ""))
            if not file_link:
                continue
            
            pdf_url = f"{PDF_BASE}{file_link}"
            
            # 生成文件名
            if doc_type["name"] in ["年度报告", "中期报告", "招股说明书"]:
                filename = doc_type["filename_tmpl"].format(year=year)
            else:
                idx += 1
                filename = doc_type["filename_tmpl"].format(year=year, idx=idx)
            
            save_path = os.path.join(args.output, filename)
            
            if os.path.exists(save_path):
                print(f"  ⏭ 已存在: {filename}")
                continue
            
            print(f"  📥 下载: {title[:50]}...")
            if download_pdf(pdf_url, save_path):
                total_downloaded += 1
            
            time.sleep(0.5)  # 下载间隔
    
    print(f"\n{'='*60}")
    print(f"  下载完成！共下载 {total_downloaded} 个文件")
    print(f"  输出目录: {args.output}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
