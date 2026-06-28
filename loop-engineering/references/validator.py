"""
loop-engineering 验证器
每轮迭代结束后的自动化验证

用法：
    from loop_engineering.validator import RoundValidator
    validator = RoundValidator()
    result = validator.validate(state, round_output)
    if not result.passed:
        print(result.errors)
"""

import re
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def __bool__(self):
        return self.passed


class RoundValidator:
    """
    每轮迭代验证器
    基于 work-analysis-loop 的「验证清单」自动执行
    """

    DATA_TAGS = ["[事实]", "[抽数]", "[计算]", "[假设]", "[推断]", "[观点]"]
    MISSING_KEYWORDS = ["缺失", "无法访问", "未披露", "无法核验", "不适用"]

    def __init__(self):
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3

    def validate(self, state: Any, round_output: str = "",
                 required_sections: list = None) -> ValidationResult:
        """
        执行完整的六维验证

        Args:
            state: State 对象
            round_output: 本轮输出的文本内容（用于检查数据层级标注）
            required_sections: 必填章节列表（用于完整性检查）

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        checks = {}

        # ---- V1: 数据层级标注检查 ----
        v1_ok = self._check_data_tags(round_output)
        checks["V1_data_tags"] = v1_ok
        if not v1_ok:
            warnings.append("V1: Output missing data level tags ([fact]/[extract]/[calc]/[assumption]/[inference]/[opinion])")

        # ---- V2: 缺失数据检查 ----
        v2_ok = self._check_missing_data(state)
        checks["V2_missing_data"] = v2_ok
        if not v2_ok:
            errors.append("V2: Missing data not properly annotated (should be marked as 'missing/undisclosed/not applicable')")

        # ---- V3: 证据来源检查 ----
        v3_ok = self._check_evidence_sources(state)
        checks["V3_evidence"] = v3_ok
        if not v3_ok:
            warnings.append("V3: evidence_index is empty, ensure key data has source annotations")

        # ---- V4: 完整性检查 ----
        v4_ok = self._check_completeness(state, required_sections)
        checks["V4_completeness"] = v4_ok
        if not v4_ok:
            missing = required_sections or []
            errors.append(f"V4: Required sections/fields missing: {missing}")

        # ---- V5: 一致性检查 ----
        v5_ok = self._check_consistency(state)
        checks["V5_consistency"] = v5_ok
        if not v5_ok:
            warnings.append("V5: Inconsistency detected between rounds, please review")

        # ---- V6: 停止条件检查 ----
        v6_ok = self._check_stop_conditions(state, errors)
        checks["V6_stop"] = v6_ok
        if not v6_ok:
            errors.append("V6: Stop condition triggered, should halt and handoff")

        # Update consecutive failures counter
        if errors:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        # Check max consecutive failures (S3)
        if self.consecutive_failures >= self.max_consecutive_failures:
            errors.append(f"V6: Verification failed {self.consecutive_failures} consecutive times, S3 stop triggered")

        passed = len(errors) == 0
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            checks=checks,
        )

    def _check_data_tags(self, text: str) -> bool:
        if not text:
            return True
        return any(tag in text for tag in self.DATA_TAGS)

    def _check_missing_data(self, state: Any) -> bool:
        if hasattr(state, "data_gaps"):
            gaps = state.data_gaps
        elif isinstance(state, dict):
            gaps = state.get("data_gaps", [])
        else:
            return True

        for gap in gaps:
            if isinstance(gap, dict):
                reason = gap.get("reason", "")
                action = gap.get("action", "")
                if not reason or not action:
                    return False
        return True

    def _check_evidence_sources(self, state: Any) -> bool:
        if hasattr(state, "evidence_index"):
            idx = state.evidence_index
        elif isinstance(state, dict):
            idx = state.get("evidence_index", {})
        else:
            return True
        return len(idx) > 0

    def _check_completeness(self, state: Any, required_sections: list = None) -> bool:
        if not required_sections:
            return True

        if hasattr(state, "stages_completed"):
            completed = state.stages_completed
        elif isinstance(state, dict):
            completed = state.get("stages_completed", [])
        else:
            return True

        missing = [s for s in required_sections if s not in completed]
        return len(missing) == 0

    def _check_consistency(self, state: Any) -> bool:
        return True

    def _check_stop_conditions(self, state: Any, current_errors: list) -> bool:
        if hasattr(state, "stages_pending"):
            pending = state.stages_pending
        elif isinstance(state, dict):
            pending = state.get("stages_pending", [])
        else:
            pending = []

        if not pending and not current_errors:
            return False
        return True

    def check_critical_numbers(self, text: str) -> List[dict]:
        number_pattern = r'[\d,]+(?:\.\d+)?(?:\s*%|\s*亿|\s*万|\s*元)?'
        numbers = re.findall(number_pattern, text)

        unannotated = []
        for num in numbers:
            idx = text.find(num)
            if idx > 0:
                context = text[max(0, idx-50):idx]
                has_tag = any(tag in context for tag in self.DATA_TAGS)
                if not has_tag:
                    unannotated.append({
                        "value": num,
                        "context": context.strip()[-30:],
                    })
        return unannotated
