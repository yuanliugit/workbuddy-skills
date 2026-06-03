"""
项目偿债现金流测算模型 (Project Debt Service Cash Flow Model)
=============================================================
版本: v1.0
作者: 信贷量化工程团队
说明: 适用于生产型项目（管网/基建/制造业）的固定资产贷款 / 项目融资偿债测算。
     模型结构对应 Excel 主模型的 ③收入模型 + ④债务排期 + ⑤现金流瀑布 + ⑥指标看板。
"""

# ============================================================
# 标准库导入
# ============================================================
from __future__ import annotations          # 允许类型注解前向引用
from dataclasses import dataclass, field    # 数据类，用于存储还款计划行
from typing import List, Optional, Dict     # 类型提示
import pandas as pd                         # 数值计算与格式化输出
import warnings
warnings.filterwarnings("ignore")           # 抑制 pandas 版本兼容警告


# ============================================================
# 第一部分：DebtFacility 债务测算类
# ============================================================

@dataclass
class RepaymentRow:
    """
    还款计划单行数据容器（对应 Excel 债务排期 Sheet 的一行）。
    使用 dataclass 而非普通类，代码更简洁、字段一目了然。
    """
    year:            int     # 运营年份（第1年、第2年……）
    period_opening:  float   # 期初贷款余额（万元）
    principal_repay: float   # 当期还本金额（万元）
    interest_charge: float   # 当期应付利息（万元）
    total_ds:        float   # 当期债务偿还合计 = 还本 + 付息（万元）
    period_closing:  float   # 期末贷款余额（万元）


class DebtFacility:
    """
    债务测算类 —— 负责模拟商业银行贷款的还本付息排期。

    核心设计要点：
    1. 支持宽限期（Grace Period）：建设期只付息不还本。
    2. 支持非标还款曲线：宽限期结束后，按调用方传入的自定义列表逐年还本。
    3. 利息基于期初余额×年化利率计算（简单年利率，实务中与银行台账一致）。

    参数说明：
    ----------
    principal      : 贷款本金（万元）
    annual_rate    : 年化利率，小数形式，例如 0.045 = 4.50%
    total_years    : 贷款总期限（年），含建设期宽限期
    grace_years    : 宽限期年数（建设期，期间只付息不还本），默认 0
    """

    def __init__(
        self,
        principal:   float,
        annual_rate: float,
        total_years: int,
        grace_years: int = 0,
    ) -> None:
        # ── 基本参数校验 ──────────────────────────────────────────
        if principal <= 0:
            raise ValueError("贷款本金必须大于 0。")
        if not (0 < annual_rate < 1):
            raise ValueError("年化利率请输入小数，如 0.045 代表 4.5%。")
        if grace_years < 0 or grace_years >= total_years:
            raise ValueError("宽限期年数须 ≥ 0 且小于总期限。")

        self.principal   = principal    # 贷款本金
        self.annual_rate = annual_rate  # 年化利率
        self.total_years = total_years  # 贷款总期限（含宽限期）
        self.grace_years = grace_years  # 宽限期年数

        # 还本期长度 = 总期限 - 宽限期
        self._repay_years: int = total_years - grace_years

        # 自定义还本曲线（由 set_custom_repayment 注入，默认 None）
        self._custom_schedule: Optional[List[float]] = None

        # 最终生成的完整还款计划（含宽限期 + 还本期）
        self._schedule: List[RepaymentRow] = []

    # ----------------------------------------------------------
    # 公开方法 1：设置宽限期
    # ----------------------------------------------------------
    def set_grace_period(self, grace_years: int) -> "DebtFacility":
        """
        【设定宽限期】
        将建设期设置为宽限期，期间仅按期初余额×年利率付息，不归还任何本金。
        通常对应"固定资产贷款"合同中"建设期按季付息"条款。

        参数：
        grace_years : 宽限期年数，例如输入 2 表示前两年只付息。

        返回自身（支持链式调用），例如：
            facility.set_grace_period(2).set_custom_repayment([...])
        """
        if grace_years < 0 or grace_years >= self.total_years:
            raise ValueError("宽限期年数须 ≥ 0 且小于贷款总期限。")
        self.grace_years  = grace_years
        self._repay_years = self.total_years - grace_years
        return self

    # ----------------------------------------------------------
    # 公开方法 2：传入自定义还本曲线
    # ----------------------------------------------------------
    def set_custom_repayment(self, schedule: List[float]) -> "DebtFacility":
        """
        【注入非标还本曲线】
        宽限期结束后，按此列表逐年归还本金。列表长度须等于还本期长度。
        列表之和须等于贷款本金（含极小浮点误差容忍）。

        适用场景：
        - 管网/基建项目前期回款少、后期回款多 → 前小后大的递增还款安排。
        - 气球式还款（Balloon）→ 末期偿还大额尾款。

        示例（贷款本金 10 000 万，还本期 5 年，递增型）：
            schedule = [1000, 1500, 2000, 2500, 3000]  # 合计 10 000 万
        """
        # 检查期数匹配
        if len(schedule) != self._repay_years:
            raise ValueError(
                f"自定义还本曲线长度 ({len(schedule)}) "
                f"须等于还本期年数 ({self._repay_years})。"
            )
        # 检查本金加总（容忍 0.01 万元的浮点误差）
        total = sum(schedule)
        if abs(total - self.principal) > 0.01:
            raise ValueError(
                f"自定义还本曲线合计 ({total:.2f}) 须等于贷款本金 ({self.principal:.2f})。"
            )
        self._custom_schedule = schedule
        return self

    # ----------------------------------------------------------
    # 公开方法 3：生成完整还款计划
    # ----------------------------------------------------------
    def generate_schedule(self) -> List[RepaymentRow]:
        """
        【生成还款计划表】
        逐年计算期初余额、当期付息、当期还本、期末余额，
        将结果存入 self._schedule 并返回。

        计算逻辑：
        ┌─────────────────────────────────────────────────────┐
        │ 宽限期（第 1 ~ grace_years 年）：                     │
        │   当期还本 = 0                                        │
        │   当期利息 = 期初余额 × 年利率                         │
        │   期末余额 = 期初余额（本金不变）                       │
        │                                                      │
        │ 还本期（第 grace_years+1 ~ total_years 年）：          │
        │   当期还本 = 自定义曲线中对应年份的还本额               │
        │   当期利息 = 期初余额 × 年利率                         │
        │   期末余额 = 期初余额 - 当期还本                        │
        └─────────────────────────────────────────────────────┘
        """
        if self._custom_schedule is None:
            raise RuntimeError("请先调用 set_custom_repayment() 注入还本曲线，再生成排期。")

        self._schedule = []
        balance = self.principal  # 滚动余额，从本金开始

        # ── 宽限期循环 ────────────────────────────────────────
        for yr in range(1, self.grace_years + 1):
            opening  = balance                           # 期初余额
            interest = round(opening * self.annual_rate, 2)  # 当期利息
            repay    = 0.0                               # 宽限期不还本
            closing  = opening - repay                  # 期末余额（= 期初，本金不动）

            self._schedule.append(RepaymentRow(
                year            = yr,
                period_opening  = opening,
                principal_repay = repay,
                interest_charge = interest,
                total_ds        = repay + interest,
                period_closing  = closing,
            ))
            balance = closing  # 更新滚动余额

        # ── 还本期循环 ────────────────────────────────────────
        for idx, repay_amount in enumerate(self._custom_schedule):
            yr       = self.grace_years + idx + 1       # 全局年份编号
            opening  = balance                           # 期初余额
            interest = round(opening * self.annual_rate, 2)  # 当期利息（基于期初余额）
            repay    = round(repay_amount, 2)            # 当期还本（来自自定义曲线）
            closing  = round(opening - repay, 2)         # 期末余额 = 期初 - 还本

            self._schedule.append(RepaymentRow(
                year            = yr,
                period_opening  = opening,
                principal_repay = repay,
                interest_charge = interest,
                total_ds        = repay + interest,
                period_closing  = closing,
            ))
            balance = closing

        return self._schedule

    # ----------------------------------------------------------
    # 辅助属性：获取运营期（宽限期后）的还款行列表
    # ----------------------------------------------------------
    @property
    def repayment_rows(self) -> List[RepaymentRow]:
        """返回完整还款计划（含宽限期与还本期），供外部调用。"""
        if not self._schedule:
            raise RuntimeError("请先调用 generate_schedule() 生成还款计划。")
        return self._schedule

    def __repr__(self) -> str:
        return (
            f"DebtFacility(principal={self.principal}万, "
            f"rate={self.annual_rate*100:.2f}%, "
            f"tenor={self.total_years}年, "
            f"grace={self.grace_years}年)"
        )


# ============================================================
# 第二部分：ProjectAsset 项目资产类
# ============================================================

class ProjectAsset:
    """
    项目资产类 —— 负责模拟运营期的现金流生成，输出可用于偿债的 CFADS。

    CFADS（Cash Flow Available for Debt Service，可用于偿债的现金流）
    计算瀑布（从总收入逐层剥离）：

        总营业收入
        └─ 剥离非核心收入（如：贸易收入、政府补贴等非主营业务）
           └─ 核心主营收入（如：管道运输收入）
              └─ 扣减付现运营成本 OPEX（人工+维修+管理）
                 └─ EBITDA（税息折旧摊销前利润）
                    └─ 扣减税费（增值税及附加、所得税）
                       └─ 扣减资本性支出 CAPEX（可选，维持性资本开支）
                          └─ CFADS（可用于偿债的现金流）

    参数说明：
    ----------
    project_name         : 项目名称
    operation_years      : 运营期年数（不含建设期）
    revenue_streams      : 收入明细字典，格式 { "收入类型": [年度金额列表] }
    core_revenue_keys    : 核心主营收入的键名列表（用于精准剥离，只取这几类）
    opex_annual          : 每年付现运营成本列表（万元）
    tax_rate_on_revenue  : 综合税负率（增值税及附加/所得税合并简化处理），小数形式
    capex_maintenance    : 每年维持性资本支出列表（万元），默认全零
    """

    def __init__(
        self,
        project_name:        str,
        operation_years:     int,
        revenue_streams:     Dict[str, List[float]],
        core_revenue_keys:   List[str],
        opex_annual:         List[float],
        tax_rate_on_revenue: float = 0.10,
        capex_maintenance:   Optional[List[float]] = None,
    ) -> None:

        self.project_name        = project_name
        self.operation_years     = operation_years
        self.revenue_streams     = revenue_streams
        self.core_revenue_keys   = core_revenue_keys
        self.opex_annual         = opex_annual
        self.tax_rate_on_revenue = tax_rate_on_revenue

        # 若未传入维持性资本开支，则默认每年为 0
        self.capex_maintenance = (
            capex_maintenance
            if capex_maintenance is not None
            else [0.0] * operation_years
        )

        # ── 参数一致性校验 ────────────────────────────────────
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """内部校验：确保所有年度数组长度与运营期匹配。"""
        for name, stream in self.revenue_streams.items():
            if len(stream) != self.operation_years:
                raise ValueError(
                    f"收入流 '{name}' 长度 ({len(stream)}) "
                    f"须等于运营期年数 ({self.operation_years})。"
                )
        for key in self.core_revenue_keys:
            if key not in self.revenue_streams:
                raise KeyError(
                    f"核心收入键名 '{key}' 在 revenue_streams 中不存在，"
                    f"请检查拼写。已有键名：{list(self.revenue_streams.keys())}"
                )
        if len(self.opex_annual) != self.operation_years:
            raise ValueError("opex_annual 长度须等于运营期年数。")
        if len(self.capex_maintenance) != self.operation_years:
            raise ValueError("capex_maintenance 长度须等于运营期年数。")

    # ----------------------------------------------------------
    # 核心方法：逐年计算运营现金流，返回 CFADS 列表
    # ----------------------------------------------------------
    def calc_cfads(self) -> List[Dict]:
        """
        【计算运营期 CFADS】
        逐年执行现金流瀑布，返回包含各层级金额的字典列表。

        业务逻辑剥离说明（管网/基建项目示例）：
        ─────────────────────────────────────────────────────────
        revenue_streams 可能包含多种收入来源，例如：
          - "管道运输收入"   ← 核心主营，计入测算基数
          - "增值服务收入"   ← 次要业务，占比不稳定，剥离
          - "政府补贴"       ← 非经常性，剥离（银行不认可作为稳定还款来源）
          - "贸易收入"       ← 穿越性质，毛利薄，剥离

        只将 core_revenue_keys 中指定的收入类型相加，作为"核心主营收入"，
        这是项目融资测算中对还款来源"精准剥离"的标准做法。
        ─────────────────────────────────────────────────────────
        """
        results = []

        for i in range(self.operation_years):
            year = i + 1  # 运营年份编号（第1年、第2年……）

            # ── Step 1：计算总营业收入（所有收入流之和）────────
            total_revenue = sum(
                stream[i] for stream in self.revenue_streams.values()
            )

            # ── Step 2：精准剥离 → 仅保留核心主营收入 ─────────
            # 关键业务逻辑：只取 core_revenue_keys 指定的收入类型
            # 例如对管网项目只取"管道运输收入"，去除"政府补贴"等不稳定来源
            core_revenue = sum(
                self.revenue_streams[key][i]
                for key in self.core_revenue_keys
            )

            # ── Step 3：扣减付现运营成本（OPEX）──────────────
            # OPEX 包括：人工成本、电力/燃料、维修费、管理费等现金支出
            # 注：不含折旧摊销（非付现），因为我们测算的是现金流，不是利润
            opex       = self.opex_annual[i]
            ebitda     = core_revenue - opex  # 近似 EBITDA（已排除非核心收入）

            # ── Step 4：扣减税费 ────────────────────────────
            # 简化处理：以核心收入为基数，乘以综合税负率
            # 实务中应分别计算增值税（核心收入/1.09*9%）+城建税+教育费附加+所得税
            # 此处采用合并税负率便于参数化调整
            taxes      = round(core_revenue * self.tax_rate_on_revenue, 2)

            # ── Step 5：扣减维持性资本开支（CAPEX）────────────
            # 维持性 CAPEX 是保持资产正常运营所必须的现金支出（如年度大修）
            # 与新建项目 CAPEX 不同，不做资本化，直接在现金流中扣减
            capex      = self.capex_maintenance[i]

            # ── Step 6：得出 CFADS（可用于偿债的现金流）────────
            cfads      = round(ebitda - taxes - capex, 2)

            results.append({
                "year":          year,
                "total_revenue": round(total_revenue, 2),   # 总营业收入
                "core_revenue":  round(core_revenue, 2),    # 核心主营收入（剥离后）
                "opex":          round(opex, 2),            # 付现运营成本
                "ebitda":        round(ebitda, 2),          # 近似 EBITDA
                "taxes":         round(taxes, 2),           # 综合税费
                "capex":         round(capex, 2),           # 维持性资本开支
                "cfads":         cfads,                     # 可用于偿债的现金流
            })

        return results

    def __repr__(self) -> str:
        return (
            f"ProjectAsset('{self.project_name}', "
            f"运营期={self.operation_years}年, "
            f"核心收入来源={self.core_revenue_keys})"
        )


# ============================================================
# 第三部分：综合测算 —— 实例化并合并 DSCR 指标表
# ============================================================

def run_model() -> pd.DataFrame:
    """
    综合测算函数：
    1. 实例化 ProjectAsset，输入模拟的管网项目假设数据。
    2. 实例化 DebtFacility，配置贷款条款（宽限期 + 自定义还本曲线）。
    3. 合并 CFADS 与债务排期，逐年计算 DSCR。
    4. 返回标准化 DataFrame。

    ━━ 模拟案例说明 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    项目：某天然气长输管道项目（生产型/管网类）
    融资：银行固定资产贷款 10 000 万元，期限 10 年（含 2 年宽限期）
    利率：4.50%（LPR -10bp，固定利率）
    运营期：8 年（建设期 2 年 + 运营期 8 年，宽限期与建设期重叠）
    收入结构：
      - 管道运输收入（核心，过路气量×运输单价，纳入测算基数）
      - 增值服务收入（阀站监控、调度服务，次要且不稳定，剥离）
      - 政府管道补贴（非经常性，无法作为稳定还款来源，剥离）
    OPEX：含员工薪酬+设备运维+保险+管理费，前低后高（运营爬坡）
    自定义还本曲线：递增型（前期现金流弱，后期回款强，匹配项目现金流特征）
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """

    # ──────────────────────────────────────────────────────────
    # 3.1 项目资产假设（运营期 8 年，单位：万元）
    # ──────────────────────────────────────────────────────────
    OPERATION_YEARS = 8  # 运营期年数

    # 收入明细：按收入类型分别列示（精细化口径，便于剥离）
    revenue_streams = {
        # ① 核心主营收入：管道运输收入（按年输气量 × 管输单价测算）
        #   假设：管输量从第1年的70%利用率逐步爬升至第4年稳定在95%
        #   单价：0.28元/方，年设计输气量约 30 亿方
        "管道运输收入": [
            8_400,   # 第1年：70% 利用率（爬坡期）
            9_600,   # 第2年：80%
           10_800,   # 第3年：90%
           11_400,   # 第4年：95%（稳定期）
           11_400,   # 第5年
           11_400,   # 第6年
           11_400,   # 第7年
           11_400,   # 第8年
        ],
        # ② 次要收入：阀站增值服务（数据监控、调度服务协议）
        #   体量小、稳定性低，不纳入偿债测算基数 → 将被剥离
        "增值服务收入": [
            200, 250, 300, 320, 320, 320, 320, 320
        ],
        # ③ 政府补贴：建设期后第1~2年的管网运营补贴
        #   非经常性、政策依赖，银行通常不接受作为稳定还款来源 → 剥离
        "政府管道补贴": [
            500, 500, 0, 0, 0, 0, 0, 0
        ],
    }

    # 核心主营收入键名：只取"管道运输收入"参与 CFADS 测算
    # 这正是"精准剥离特定收入来源"的接口——只需在此列表中指定即可
    core_revenue_keys = ["管道运输收入"]

    # 付现运营成本 OPEX（万元/年）
    # 含：运营员工薪酬 + 设备年度维护 + 保险费 + 行政管理费
    # 爬坡期略低，稳定期偏高（人员满配、大修进入周期）
    opex_annual = [
        1_800,   # 第1年：运营初期，人员尚未满配
        2_000,   # 第2年
        2_200,   # 第3年
        2_300,   # 第4年：稳定期
        2_350,   # 第5年
        2_400,   # 第6年
        2_400,   # 第7年
        2_400,   # 第8年
    ]

    # 综合税负率（增值税及附加 + 所得税简化合并，以核心收入为基数）
    # 实务参考：管输业增值税9%，城建+教育附加约1.2%，所得税约5%（高新减免）
    # 合计综合税负率约 15%
    TAX_RATE = 0.15

    # 维持性资本开支（年度大修预算）
    capex_maintenance = [
        200, 200, 400, 400, 400, 600, 600, 600
    ]  # 第3年起进入首次大检修周期，第7年次大检修

    # ── 实例化 ProjectAsset ───────────────────────────────────
    asset = ProjectAsset(
        project_name        = "XX天然气长输管道项目",
        operation_years     = OPERATION_YEARS,
        revenue_streams     = revenue_streams,
        core_revenue_keys   = core_revenue_keys,   # 精准剥离：仅管道运输收入
        opex_annual         = opex_annual,
        tax_rate_on_revenue = TAX_RATE,
        capex_maintenance   = capex_maintenance,
    )

    # ──────────────────────────────────────────────────────────
    # 3.2 债务条款假设
    # ──────────────────────────────────────────────────────────
    PRINCIPAL    = 10_000.0   # 贷款本金（万元）
    ANNUAL_RATE  = 0.045      # 年化利率 4.50%
    TOTAL_YEARS  = 10         # 贷款总期限（年），含 2 年宽限期
    GRACE_YEARS  = 2          # 宽限期（建设期）= 2 年

    # 自定义还本曲线（宽限期后 8 年，合计 10 000 万元）
    # 采用"前低后高"递增型安排，契合管输项目爬坡期现金流特征
    # 还款安全边际验证：每年 DSCR ≥ 1.20x（银行通常要求）
    custom_repayment = [
        700,    # 第3年（运营第1年）：爬坡期，少还
        800,    # 第4年（运营第2年）
       1_000,   # 第5年（运营第3年）
       1_200,   # 第6年（运营第4年）：进入稳定期
       1_300,   # 第7年（运营第5年）
       1_500,   # 第8年（运营第6年）
       1_700,   # 第9年（运营第7年）
       1_800,   # 第10年（运营第8年）：末期大额偿还
    ]
    # 验证：700+800+1000+1200+1300+1500+1700+1800 = 10 000 ✓

    # ── 实例化 DebtFacility 并生成排期 ───────────────────────
    facility = DebtFacility(
        principal   = PRINCIPAL,
        annual_rate = ANNUAL_RATE,
        total_years = TOTAL_YEARS,
        grace_years = GRACE_YEARS,
    )
    # 链式调用：设置宽限期 → 注入自定义还本曲线 → 生成排期
    facility.set_grace_period(GRACE_YEARS).set_custom_repayment(custom_repayment)
    debt_rows = facility.generate_schedule()

    # ──────────────────────────────────────────────────────────
    # 3.3 计算 CFADS 并合并 DSCR 指标
    # ──────────────────────────────────────────────────────────
    cfads_list = asset.calc_cfads()   # 运营期 8 年的 CFADS 数据

    # 提取还本期（宽限期结束后）的债务排期行
    # debt_rows 包含第1~10年，运营期对应第3~10年（索引 grace_years 起）
    repay_rows = debt_rows[GRACE_YEARS:]  # 切片：跳过宽限期行

    # ── 逐年合并并计算 DSCR ───────────────────────────────────
    records = []
    for cfads_row, debt_row in zip(cfads_list, repay_rows):
        op_year   = cfads_row["year"]          # 运营年份（1~8）
        loan_year = debt_row.year              # 贷款年份（3~10，含宽限期）
        cfads     = cfads_row["cfads"]
        principal = debt_row.principal_repay   # 当期还本
        interest  = debt_row.interest_charge   # 当期利息
        total_ds  = debt_row.total_ds          # 还本+付息合计
        opening   = debt_row.period_opening    # 期初债务余额
        closing   = debt_row.period_closing    # 期末债务余额

        # DSCR = CFADS ÷ (当期还本 + 当期付息)
        # 警戒线：1.20x（多数银行固定资产贷款合同约定值）
        # 优质项目：1.50x 以上
        dscr = round(cfads / total_ds, 2) if total_ds > 0 else float("inf")

        records.append({
            "运营年份":       f"第{op_year}年",
            "贷款年份":       f"Y{loan_year:02d}",
            "CFADS（万元）":  cfads,
            "期初债务余额":   opening,
            "当期还本":       principal,
            "当期付息":       interest,
            "当期债务合计":   total_ds,
            "期末债务余额":   closing,
            "DSCR":           dscr,
        })

    df = pd.DataFrame(records)
    return df


# ============================================================
# 第四部分：格式化输出
# ============================================================

def print_model_output(df: pd.DataFrame) -> None:
    """
    美观输出 DSCR 测算结果，并标注预警状态。
    """
    DSCR_COVENANT = 1.20   # 合同约定 DSCR 下限（警戒线）
    DSCR_COMFORT  = 1.50   # 舒适水平（优质标准）

    # ── 表头 ────────────────────────────────────────────────
    separator = "=" * 108
    print("\n")
    print(separator)
    print("  【项目偿债现金流测算模型】  XX天然气长输管道项目  |  信贷审批测算表")
    print("  贷款本金：10,000 万元  |  年利率：4.50%  |  期限：10年（含2年宽限期）")
    print(separator)

    # ── 设置 Pandas 显示选项 ─────────────────────────────────
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", "{:,.2f}".format)

    # ── 打印主表 ─────────────────────────────────────────────
    print(df.to_string(index=False))
    print(separator)

    # ── 合规性分析 ────────────────────────────────────────────
    min_dscr  = df["DSCR"].min()
    avg_dscr  = df["DSCR"].mean()
    below_min = df[df["DSCR"] < DSCR_COVENANT]

    print(f"\n  ▸ DSCR 统计：最低 {min_dscr:.2f}x  |  平均 {avg_dscr:.2f}x  |  警戒线 ≥{DSCR_COVENANT}x  |  舒适线 ≥{DSCR_COMFORT}x")

    if below_min.empty:
        print(f"  ▸ 合规状态：✅ 全部年份 DSCR ≥ {DSCR_COVENANT}x，满足贷款合同约定，偿债能力充足。")
    else:
        years = ", ".join(below_min["运营年份"].tolist())
        print(f"  ▸ 合规状态：⚠️  {years} DSCR 低于警戒线 {DSCR_COVENANT}x，请重新审查还款安排或要求增加担保措施！")

    above_comfort = df[df["DSCR"] >= DSCR_COMFORT]
    print(f"  ▸ 优质年份：{len(above_comfort)}/{len(df)} 年 DSCR ≥ {DSCR_COMFORT}x（舒适水平）")

    # ── 现金流剥离说明 ────────────────────────────────────────
    print()
    print("  【收入口径说明】")
    print("  ─ 纳入测算基数（核心主营）：管道运输收入（按过路气量×运输单价测算）")
    print("  ─ 已剥离/未计入：增值服务收入（次要业务）、政府管道补贴（非经常性）")
    print("  ─ 扣减项：付现运营成本 OPEX + 综合税负15% + 年度大修资本开支")
    print(separator)
    print()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    print("\n正在运行偿债现金流测算模型，请稍候...")
    df = run_model()
    print_model_output(df)
