#!/usr/bin/env python3
"""
pdf_extractor.py — 从年报PDF中提取三大财务报表数据

用法：
  python pdf_extractor.py \
    --pdf-dir D:\Workbuddy\企业披露信息抓取工作区\华天科技\00-基础资料 \
    --output D:\Workbuddy\企业披露信息抓取工作区\华天科技\01-财务报表\data.json
"""

import argparse
import os
import re
import json
from typing import Optional, Dict, Any


# ─────────────────────────────────────────────
# 科目映射表
# ─────────────────────────────────────────────
BALANCE_SHEET_MAPPING = {
    "货币资金": "monetary_funds",
    "交易性金融资产": "trading_financial_assets",
    "应收票据": "notes_receivable",
    "应收账款": "accounts_receivable",
    "预付款项": "prepaid_expenses",
    "其他应收款": "other_receivables",
    "存货": "inventory",
    "流动资产合计": "current_assets",
    "固定资产": "fixed_assets",
    "在建工程": "construction_in_progress",
    "无形资产": "intangible_assets",
    "长期股权投资": "long_term_equity_investment",
    "非流动资产合计": "non_current_assets",
    "资产总计": "total_assets",
    "短期借款": "short_term_loan",
    "应付票据": "notes_payable",
    "应付账款": "accounts_payable",
    "预收款项": "advance_receipts",
    "合同负债": "contract_liabilities",
    "应付职工薪酬": "employee_benefits_payable",
    "应交税费": "taxes_payable",
    "一年内到期的非流动负债": "current_portion_lt_debt",
    "流动负债合计": "current_liabilities",
    "长期借款": "long_term_loan",
    "应付债券": "bonds_payable",
    "长期应付款": "long_term_payables",
    "非流动负债合计": "non_current_liabilities",
    "负债合计": "total_liabilities",
    "实收资本": "paid_in_capital",
    "股本": "share_capital",
    "资本公积": "capital_surplus",
    "盈余公积": "surplus_reserve",
    "未分配利润": "retained_earnings",
    "归属于母公司所有者权益合计": "equity_attributable_to_parent",
    "少数股东权益": "minority_interest",
    "所有者权益合计": "total_equity",
}

INCOME_MAPPING = {
    "营业收入": "revenue",
    "营业成本": "cost_of_revenue",
    "税金及附加": "taxes_and_surcharges",
    "销售费用": "selling_expenses",
    "管理费用": "admin_expenses",
    "研发费用": "rd_expenses",
    "财务费用": "financial_expenses",
    "利息费用": "interest_expense",
    "资产减值损失": "asset_impairment_loss",
    "信用减值损失": "credit_impairment_loss",
    "投资收益": "investment_income",
    "营业利润": "operating_profit",
    "营业外收入": "non_operating_income",
    "营业外支出": "non_operating_expenses",
    "利润总额": "profit_before_tax",
    "所得税费用": "income_tax",
    "净利润": "net_profit",
    "归属于母公司所有者的净利润": "net_profit_attributable_to_parent",
    "少数股东损益": "minority_profit",
}

CASH_FLOW_MAPPING = {
    "销售商品、提供劳务收到的现金": "cash_from_sales",
    "经营活动现金流入小计": "operating_cash_inflow",
    "购买商品、接受劳务支付的现金": "cash_paid_for_goods",
    "支付给职工以及为职工支付的现金": "cash_paid_to_employees",
    "支付的各项税费": "cash_paid_for_taxes",
    "经营活动现金流出小计": "operating_cash_outflow",
    "经营活动产生的现金流量净额": "net_cash_from_operations",
    "购建固定资产、无形资产和其他长期资产支付的现金": "capex",
    "投资活动产生的现金流量净额": "net_cash_from_investing",
    "取得借款收到的现金": "proceeds_from_borrowings",
    "偿还债务支付的现金": "repayment_of_debt",
    "分配股利、利润或偿付利息支付的现金": "dividends_and_interest_paid",
    "筹资活动产生的现金流量净额": "net_cash_from_financing",
    "现金及现金等价物净增加额": "net_increase_in_cash",
    "期末现金及现金等价物余额": "cash_at_end",
}


# ─────────────────────────────────────────────
# 数值解析
# ─────────────────────────────────────────────
def parse_number(text: str) -> Optional[float]:
    """解析财务数值，返回万元单位的浮点数"""
    if not text:
        return None
    text = str(text).strip().replace(",", "").replace(" ", "").replace("\u3000", "")
    if text in ["—", "-", "－", "——", "", "N/A", "n/a"]:
        return 0.0

    is_negative = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
    if is_negative and text.startswith("("):
        text = text[1:-1]
    elif is_negative:
        text = text[1:]

    multiplier = 1.0
    if text.endswith("亿元") or text.endswith("亿"):
        text = text.rstrip("亿元").rstrip("亿")
        multiplier = 10000.0
    elif text.endswith("万元") or text.endswith("万"):
        text = text.rstrip("万元").rstrip("万")
        multiplier = 1.0

    try:
        val = float(text) * multiplier
        return -val if is_negative else val
    except ValueError:
        return None


# ─────────────────────────────────────────────
# PDF提取核心
# ─────────────────────────────────────────────
def extract_tables_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    使用 pdfplumber 从PDF提取三大财务报表。
    返回结构化字典。
    """
    try:
        import pdfplumber
    except ImportError:
        print("  安装 pdfplumber: pip install pdfplumber")
        raise

    result = {
        "balance_sheet_consolidated": {},   # 合并资产负债表
        "income_consolidated": {},           # 合并利润表
        "cash_flow_consolidated": {},        # 合并现金流量表
        "balance_sheet_parent": {},          # 本部资产负债表
        "income_parent": {},                 # 本部利润表
        "cash_flow_parent": {},              # 本部现金流量表
        "source": "pdfplumber",
        "warnings": []
    }

    current_table = None
    current_scope = None   # consolidated / parent

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"  PDF共 {total_pages} 页，开始提取...")

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""

            # 识别报表类型和范围
            if re.search(r"合并资产负债表", text) and "附注" not in text[:50]:
                current_table = "balance_sheet"
                current_scope = "consolidated"
            elif re.search(r"母公司资产负债表|本公司资产负债表", text) and "附注" not in text[:50]:
                current_table = "balance_sheet"
                current_scope = "parent"
            elif re.search(r"合并(损益表|利润表|综合收益表)", text) and "附注" not in text[:50]:
                current_table = "income"
                current_scope = "consolidated"
            elif re.search(r"母公司(损益表|利润表)|本公司利润表", text) and "附注" not in text[:50]:
                current_table = "income"
                current_scope = "parent"
            elif re.search(r"合并现金流量表", text) and "附注" not in text[:50]:
                current_table = "cash_flow"
                current_scope = "consolidated"
            elif re.search(r"母公司现金流量表|本公司现金流量表", text) and "附注" not in text[:50]:
                current_table = "cash_flow"
                current_scope = "parent"

            if not current_table:
                continue

            # 提取表格
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                _parse_table(table, current_table, current_scope, result)

    # 数据校验
    issues = validate_data(result)
    if issues:
        result["warnings"].extend(issues)
        for issue in issues:
            print(f"  ⚠️ {issue}")

    return result


def _parse_table(table, table_type: str, scope: str, result: dict):
    """解析一个表格，将识别到的科目写入result"""
    mapping = {
        "balance_sheet": BALANCE_SHEET_MAPPING,
        "income": INCOME_MAPPING,
        "cash_flow": CASH_FLOW_MAPPING,
    }.get(table_type, {})

    key_prefix = f"{table_type}_{scope}"

    for row in table:
        if not row or len(row) < 2:
            continue
        cell0 = str(row[0] or "").strip()
        # 科目名称模糊匹配
        for cn_name, en_key in mapping.items():
            if cn_name in cell0:
                # 尝试第二列（当前年度）
                for col_idx in range(1, min(len(row), 4)):
                    val = parse_number(str(row[col_idx] or ""))
                    if val is not None:
                        result[key_prefix][en_key] = val
                        break
                break


def validate_data(result: dict) -> list:
    """基础数据校验"""
    issues = []
    bs = result.get("balance_sheet_consolidated", {})

    total_assets = bs.get("total_assets", 0)
    total_liab = bs.get("total_liabilities", 0)
    total_equity = bs.get("total_equity", 0)

    if total_assets and total_liab and total_equity:
        diff = abs(total_assets - total_liab - total_equity)
        if diff > 1:
            issues.append(f"合并报表资产负债表不平衡: 差异 {diff:.2f} 万元")
    elif not total_assets:
        issues.append("未提取到合并资产负债表数据")

    return issues


# ─────────────────────────────────────────────
# GLM-4V 兜底提取
# ─────────────────────────────────────────────
def extract_via_glm_vision(pdf_path: str, page_num: int, table_type: str) -> dict:
    """使用 GLM-4V 视觉模型从PDF截图中提取财务数据（兜底方案）"""
    try:
        import fitz  # PyMuPDF
        import base64
        import requests
        import os

        api_key = os.environ.get("GLM_API_KEY", "")
        if not api_key:
            print("  ⚠️ GLM_API_KEY 未设置，跳过视觉兜底")
            return {}

        # 将PDF页面转为图片
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode()

        prompt = f"""请从图片中提取{table_type}的所有科目和金额数据，以JSON格式返回。
要求：
- 每行格式："科目名称": 数值（万元）
- 若原始单位为元，请除以10000转换为万元
- 括号内数值为负数
- 只返回JSON对象，不要其他说明文字
"""
        payload = {
            "model": "glm-4v-plus",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]}]
        }
        resp = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60
        )
        content = resp.json()["choices"][0]["message"]["content"]

        import json as json_mod
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            raw = json_mod.loads(json_match.group())
            # 将中文科目映射到英文键
            result = {}
            all_mappings = {**BALANCE_SHEET_MAPPING, **INCOME_MAPPING, **CASH_FLOW_MAPPING}
            for cn_name, val in raw.items():
                en_key = all_mappings.get(cn_name.strip())
                if en_key:
                    result[en_key] = float(val) if val else 0.0
            return result
    except Exception as e:
        print(f"  ⚠️ GLM-4V 提取失败: {e}")
    return {}


# ─────────────────────────────────────────────
# 扫描目录，匹配年报PDF
# ─────────────────────────────────────────────
def find_annual_report_pdfs(pdf_dir: str) -> list:
    """扫描目录，找到所有年报PDF"""
    pdfs = []
    for fname in sorted(os.listdir(pdf_dir)):
        fpath = os.path.join(pdf_dir, fname)
        if not fname.lower().endswith(".pdf"):
            continue
        fname_lower = fname.lower()
        # 匹配年报和审计报告
        if any(kw in fname for kw in ["年报", "年度报告", "审计报告"]):
            year_m = re.search(r"(20\d{2})", fname)
            year = year_m.group(1) if year_m else "未知"
            pdfs.append({
                "path": fpath,
                "filename": fname,
                "year": year,
                "is_audit": "审计报告" in fname,
                "is_annual": "年报" in fname or "年度报告" in fname
            })
    return pdfs


# ─────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="从年报PDF提取财务数据")
    parser.add_argument("--pdf-dir", required=True, help="包含PDF的目录")
    parser.add_argument("--output", required=True, help="输出JSON文件路径")
    parser.add_argument("--use-vision", action="store_true", help="启用GLM-4V视觉兜底")
    args = parser.parse_args()

    print("=== PDF 财务数据提取器 ===")

    pdfs = find_annual_report_pdfs(args.pdf_dir)
    if not pdfs:
        print(f"❌ 未在 {args.pdf_dir} 找到年报PDF文件")
        return

    print(f"找到 {len(pdfs)} 个年报/审计报告文件:")
    for p in pdfs:
        print(f"  {p['year']} {'[审计]' if p['is_audit'] else '[年报]'} {p['filename']}")

    all_data = {}
    for p in pdfs:
        print(f"\n处理: {p['filename']}")
        try:
            data = extract_tables_from_pdf(p["path"])

            # 判断是否需要视觉兜底
            bs = data.get("balance_sheet_consolidated", {})
            if args.use_vision and not bs.get("total_assets"):
                print("  pdfplumber 提取失败，尝试GLM-4V视觉兜底...")
                # 简单兜底：尝试第1-10页
                import pdfplumber
                with pdfplumber.open(p["path"]) as pdf:
                    for i, page in enumerate(pdf.pages[:20], 1):
                        text = page.extract_text() or ""
                        if "资产负债表" in text:
                            vision_data = extract_via_glm_vision(p["path"], i, "资产负债表")
                            if vision_data:
                                data["balance_sheet_consolidated"].update(vision_data)
                                data["source"] = "glm-4v (fallback)"
                                break

            all_data[p["year"]] = data
            print(f"  提取完成: 资产总计={bs.get('total_assets', '?')} 万元")

        except Exception as e:
            print(f"  ❌ 提取失败: {e}")
            all_data[p["year"]] = {"error": str(e)}

    # 保存输出
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已保存至: {args.output}")


if __name__ == "__main__":
    main()
