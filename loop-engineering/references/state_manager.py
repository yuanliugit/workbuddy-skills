"""
loop-engineering State 管理器
统一封装 .state.json 的读写、备份、恢复、原子写入

用法：
    from loop_engineering.state_manager import StateManager, State
    from loop_engineering import quick_init, quick_load

    # 初始化新任务
    state = quick_init("./workspace", skill="enterprise-public-disclosure", stage="COLLECTING")

    # 每轮更新
    state.iteration += 1
    state.stages_completed.append("COLLECTING")
    state.save()

    # 断点恢复
    state = quick_load("./workspace")
    if state:
        print(f"从第 {state.iteration} 轮继续")
"""

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StateCorruptedError(Exception):
    """State 文件损坏异常"""
    pass


class State:
    """
    State 数据对象
    封装统一 State Schema，提供便捷的属性访问
    """

    REQUIRED_FIELDS = ["task_id", "skill", "skill_version", "stage", "iteration", "status"]

    def __init__(self, data: Optional[Dict] = None):
        self._data = data or {}

    # ---- 便捷属性访问 ----

    @property
    def task_id(self) -> str:
        return self._data.get("task_id", "")

    @task_id.setter
    def task_id(self, value: str):
        self._data["task_id"] = value

    @property
    def skill(self) -> str:
        return self._data.get("skill", "")

    @skill.setter
    def skill(self, value: str):
        self._data["skill"] = value

    @property
    def skill_version(self) -> str:
        return self._data.get("skill_version", "")

    @skill_version.setter
    def skill_version(self, value: str):
        self._data["skill_version"] = value

    @property
    def stage(self) -> str:
        return self._data.get("stage", "INIT")

    @stage.setter
    def stage(self, value: str):
        self._data["stage"] = value

    @property
    def iteration(self) -> int:
        return self._data.get("iteration", 0)

    @iteration.setter
    def iteration(self, value: int):
        self._data["iteration"] = value

    @property
    def status(self) -> str:
        return self._data.get("status", "INIT")

    @status.setter
    def status(self, value: str):
        self._data["status"] = value

    @property
    def stages_completed(self) -> List[str]:
        return self._data.setdefault("stages_completed", [])

    @property
    def stages_pending(self) -> List[str]:
        return self._data.setdefault("stages_pending", [])

    @property
    def evidence_index(self) -> Dict[str, Any]:
        return self._data.setdefault("evidence_index", {})

    @property
    def data_gaps(self) -> List[Dict]:
        return self._data.setdefault("data_gaps", [])

    @property
    def warnings(self) -> List[str]:
        return self._data.setdefault("warnings", [])

    @property
    def updated_at(self) -> str:
        return self._data.get("updated_at", "")

    @property
    def workspace(self) -> str:
        return self._data.get("workspace", "")

    # ---- 核心方法 ----

    def add_evidence(self, source_name: str, lines: List[int]):
        """添加证据来源"""
        self.evidence_index[source_name] = lines

    def add_data_gap(self, field: str, reason: str, action: str = "标注为缺失"):
        """添加缺失数据记录"""
        self.data_gaps.append({
            "field": field,
            "reason": reason,
            "action": action,
        })

    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)

    def touch(self):
        """更新时间戳"""
        self._data["updated_at"] = self._now_iso()

    def to_dict(self) -> Dict:
        """转为字典"""
        self.touch()
        return dict(self._data)

    def validate(self) -> bool:
        """验证必填字段"""
        missing = [f for f in self.REQUIRED_FIELDS if not self._data.get(f)]
        return len(missing) == 0

    def is_complete(self) -> bool:
        """检查任务是否完成（无待执行阶段）"""
        return len(self.stages_pending) == 0

    def next_stage(self) -> Optional[str]:
        """获取下一个待执行阶段"""
        if self.stages_pending:
            return self.stages_pending[0]
        return None

    def complete_stage(self, stage_name: str):
        """标记阶段完成"""
        if stage_name in self.stages_pending:
            self.stages_pending.remove(stage_name)
        if stage_name not in self.stages_completed:
            self.stages_completed.append(stage_name)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()

    def __repr__(self):
        return f"State(task_id={self.task_id}, stage={self.stage}, iter={self.iteration})"


class StateManager:
    """
    State 文件管理器
    负责 .state.json 的读写、备份、恢复
    """

    STATE_FILE = ".state.json"
    STATE_TMP = ".state.json.tmp"
    STATE_ARCHIVED = ".state.json.archived"

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.state_path = os.path.join(self.workspace, self.STATE_FILE)
        self.tmp_path = os.path.join(self.workspace, self.STATE_TMP)
        self.archived_path = os.path.join(self.workspace, self.STATE_ARCHIVED)
        os.makedirs(self.workspace, exist_ok=True)

    def init(self, skill: str, skill_version: str = "",
             stage: str = "INIT",
             stages_pending: List[str] = None,
             extra: Dict = None) -> State:
        """
        初始化新任务的 State
        """
        task_id = self._generate_task_id(skill)

        data = {
            "task_id": task_id,
            "skill": skill,
            "skill_version": skill_version,
            "stage": stage,
            "iteration": 0,
            "status": "RUNNING",
            "stages_completed": [],
            "stages_pending": stages_pending or [],
            "evidence_index": {},
            "data_gaps": [],
            "warnings": [],
            "updated_at": self._now_iso(),
            "workspace": self.workspace,
        }

        if extra:
            data.update(extra)

        state = State(data)
        self._write(state.to_dict())
        return state

    def load(self) -> Optional[State]:
        """
        读取 State。如果文件不存在或损坏，返回 None。
        """
        if not os.path.exists(self.state_path):
            return None

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise StateCorruptedError(f"State 文件损坏: {e}")

        return State(data)

    def save(self, state: State) -> None:
        """
        保存 State（原子写入）
        """
        if not state.validate():
            missing = [f for f in State.REQUIRED_FIELDS if not state._data.get(f)]
            raise ValueError(f"State 必填字段缺失: {missing}")

        self._write(state.to_dict())

    def backup(self) -> str:
        """
        备份当前 State 为 .state.json.archived
        返回备份文件路径
        """
        if os.path.exists(self.state_path):
            shutil.copy2(self.state_path, self.archived_path)
        return self.archived_path

    def exists(self) -> bool:
        """检查 State 文件是否存在"""
        return os.path.exists(self.state_path)

    def delete(self) -> None:
        """删除 State 文件"""
        for path in [self.state_path, self.tmp_path, self.archived_path]:
            if os.path.exists(path):
                os.remove(path)

    def resume_prompt(self) -> Optional[str]:
        """
        生成恢复提示语（如果存在未完成的 State）
        """
        state = self.load()
        if not state:
            return None

        completed = ", ".join(state.stages_completed) if state.stages_completed else "无"
        pending = ", ".join(state.stages_pending) if state.stages_pending else "无"

        return (
            f"检测到未完成任务 **{state.task_id}**（{state.skill}）\n"
            f"- 当前阶段：`{state.stage}`\n"
            f"- 已完成：{completed}\n"
            f"- 待执行：{pending}\n"
            f"- 上次更新：{state.updated_at}\n"
            f"\n是否继续？"
        )

    def _write(self, data: Dict) -> None:
        """原子写入 State 文件"""
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(self.tmp_path, self.state_path)

        # Sync directory to ensure rename is persisted
        dir_fd = os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _generate_task_id(self, skill: str) -> str:
        """生成 task_id（格式：PREFIX-MMDD-XXX）"""
        prefix_map = {
            "credit-review-workbench": "CR",
            "enterprise-public-disclosure": "EPD",
            "cashflow-model": "CFM",
            "valuation-analysis": "VAL",
            "profit-quality": "PQ",
            "investment-industry-research": "IIR",
            "work-analysis-loop": "WAL",
        }
        prefix = prefix_map.get(skill, "TSK")
        date_part = datetime.now().strftime("%Y%m%d")

        # Find next sequence number
        seq = 1
        while os.path.exists(os.path.join(self.workspace, f"{prefix}-{date_part}-{seq:03d}")):
            seq += 1

        return f"{prefix}-{date_part}-{seq:03d}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()


# ---- 便捷函数 ----

def quick_init(workspace: str, skill: str, **kwargs) -> State:
    """
    快速初始化新 State（一行代码）
    """
    sm = StateManager(workspace)
    return sm.init(skill, **kwargs)


def quick_load(workspace: str) -> Optional[State]:
    """
    快速读取 State（一行代码）
    """
    sm = StateManager(workspace)
    return sm.load()
