"""
loop-engineering Handoff 管理器
统一封装 .handoff.json 和 HANDOFF.md 的生成与读取

用法：
    from loop_engineering.handoff_manager import HandoffManager
    hm = HandoffManager(workspace="./credit-review-001")
    hm.generate(state, stop_reason="S1", deliverables=[...])
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional


class HandoffManager:
    """
    Handoff 生成管理器
    """

    HANDOFF_JSON = ".handoff.json"
    HANDOFF_MD = "HANDOFF.md"

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.handoff_json_path = os.path.join(self.workspace, self.HANDOFF_JSON)
        self.handoff_md_path = os.path.join(self.workspace, self.HANDOFF_MD)
        os.makedirs(self.workspace, exist_ok=True)

    def generate(self, state: Any, stop_reason: str,
                 deliverables: list = None,
                 open_issues: list = None,
                 next_steps: list = None,
                 evidence_summary: dict = None) -> dict:
        """
        生成 Handoff 包（.handoff.json + HANDOFF.md）

        Args:
            state: State 对象（需有 task_id, skill, skill_version, stage, iteration 等属性）
            stop_reason: 停止原因（S1-S7 或自定义）
            deliverables: 交付物列表 [{"name": "", "path": "", "status": ""}]
            open_issues: 未解决问题列表 [str]
            next_steps: 后续步骤建议 [str]
            evidence_summary: 证据概况 {"total_sources": N, "total_evidence_lines": N, "data_completeness": "92%"}

        Returns:
            生成的 handoff 字典
        """
        handoff_id = self._generate_handoff_id()
        timestamp = self._now_iso()

        # Normalize state to dict
        if hasattr(state, "to_dict"):
            state_dict = state.to_dict()
        elif isinstance(state, dict):
            state_dict = state
        else:
            raise TypeError("state must be a dict or have to_dict() method")

        handoff = {
            "handoff_id": handoff_id,
            "timestamp": timestamp,
            "task_id": state_dict.get("task_id", "UNKNOWN"),
            "skill": state_dict.get("skill", "UNKNOWN"),
            "skill_version": state_dict.get("skill_version", ""),
            "stop_reason": stop_reason,
            "state_snapshot": {
                "stage": state_dict.get("stage", ""),
                "iteration": state_dict.get("iteration", 0),
                "stages_completed": state_dict.get("stages_completed", []),
                "stages_pending": state_dict.get("stages_pending", []),
            },
            "deliverables": deliverables or [],
            "evidence_summary": evidence_summary or {
                "total_sources": 0,
                "total_evidence_lines": 0,
                "data_completeness": "N/A",
            },
            "open_issues": open_issues or [],
            "next_steps": next_steps or [],
            "verification_results": state_dict.get("verification_results", {}),
        }

        # Write .handoff.json
        with open(self.handoff_json_path, "w", encoding="utf-8") as f:
            json.dump(handoff, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Write HANDOFF.md
        md_content = self._generate_markdown(handoff, state_dict)
        with open(self.handoff_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            f.flush()
            os.fsync(f.fileno())

        return handoff

    def load(self) -> Optional[dict]:
        """
        读取 .handoff.json
        """
        if not os.path.exists(self.handoff_json_path):
            return None
        with open(self.handoff_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_md(self) -> Optional[str]:
        """
        读取 HANDOFF.md
        """
        if not os.path.exists(self.handoff_md_path):
            return None
        with open(self.handoff_md_path, "r", encoding="utf-8") as f:
            return f.read()

    def exists(self) -> bool:
        return os.path.exists(self.handoff_json_path)

    def _generate_markdown(self, handoff: dict, state_dict: dict) -> str:
        """
        生成人类可读的 HANDOFF.md
        """
        task_id = handoff["task_id"]
        skill = handoff["skill"]
        stop_reason = handoff["stop_reason"]
        timestamp = handoff["timestamp"]
        snapshot = handoff["state_snapshot"]
        deliverables = handoff["deliverables"]
        evidence = handoff["evidence_summary"]
        issues = handoff["open_issues"]
        next_steps = handoff["next_steps"]

        # Deliverables table
        if deliverables:
            deliv_rows = "\n".join(
                f"| {d.get('name', '')} | `{d.get('path', '')}` | {d.get('status', '')} |"
                for d in deliverables
            )
            deliv_table = f"""| 文件 | 路径 | 状态 |
|------|------|------|
{deliv_rows}"""
        else:
            deliv_table = "（无交付物）"

        # Evidence
        evidence_text = (
            f"- 来源数量：`{evidence.get('total_sources', 0)}`\n"
            f"- 证据条数：`{evidence.get('total_evidence_lines', 0)}`\n"
            f"- 数据完整度：`{evidence.get('data_completeness', 'N/A')}`"
        )

        # Issues
        if issues:
            issues_text = "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues))
        else:
            issues_text = "（无未解决问题）"

        # Next steps
        if next_steps:
            next_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(next_steps))
        else:
            next_text = "（无后续步骤）"

        # Completed stages
        completed = snapshot.get("stages_completed", [])
        pending = snapshot.get("stages_pending", [])
        stages_text = " → ".join(completed) if completed else "（无）"
        if pending:
            stages_text += f" → [待执行: {', '.join(pending)}]"

        return f"""# Handoff — {task_id}

**交接ID**：{handoff["handoff_id"]}
**任务ID**：{task_id}
**Skill**：{skill} v{handoff["skill_version"]}
**时间**：{timestamp}
**停止原因**：{stop_reason}

---

## 当前状态

- 阶段：`{snapshot.get('stage', '')}`
- 迭代轮次：`{snapshot.get('iteration', 0)}`
- 执行链路：{stages_text}

---

## 交付物

{deliv_table}

---

## 证据概况

{evidence_text}

---

## 未解决问题

{issues_text}

---

## 后续步骤

{next_text}

---

**交接人**：WorkBuddy Agent
**交接给**：用户 / 下一个 Agent
"""

    def _generate_handoff_id(self) -> str:
        date_part = datetime.now().strftime("%m%d")
        seq = 1
        while os.path.exists(os.path.join(self.workspace, f"HANDOFF-{date_part}-{seq:03d}.md")):
            seq += 1
        return f"HO-{date_part}-{seq:03d}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()


# ---- Convenience functions ----

def quick_handoff(workspace: str, state: Any, stop_reason: str, **kwargs) -> dict:
    """
    快速生成 Handoff（一行代码）
    """
    hm = HandoffManager(workspace)
    return hm.generate(state, stop_reason, **kwargs)
