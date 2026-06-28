---
name: "loop-engineering"
version: "1.1.0"
description: "将一次性 Skill 改造为可循环执行、可验证、可交接、有停止条件的工作流型 Skill。提供 Trigger→State→Iteration→Verification→Stop Conditions→Handoff 六元改造框架。"
trigger: "用户说「把某 skill 改造成循环工作流」、「为某 skill 增加迭代能力」、「优化某 skill 的执行流程」；或 Agent 识别到某 skill 执行结果不稳定、需要多轮验证、存在人工交接点时"
---

# loop-engineering — Skill 循环工程化改造指南

## 核心理念

一次性 Skill 的问题：
- 执行完就结束，无法验证质量
- 长任务中途失败，无法从断点恢复
- 复杂任务一步做完，错误难以定位
- 人工/Agent 交接时无状态传递，上下文丢失

循环工程化改造目标：
- **可复现**：相同输入 → 相同执行路径
- **可验证**：每轮有明确验证标准
- **可恢复**：任意轮次中断 → 从 State 恢复
- **可交接**：Handoff 包含完整上下文

---

## 六元改造框架

### 1. Trigger（触发条件）

明确：「什么情况下应该启动这个 Skill？」

**改造前（模糊）**：
```
用户：帮我分析这家公司
→ 直接执行
```

**改造后（精确）**：
```
Trigger 命中条件（满足任一即触发）：
  [T1] 用户明确说出：「授信审查」/「公开披露」/「项目融资模型」/「行业研究」
  [T2] 用户上传了年报 PDF / 招股书 / 债券募集说明书
  [T3] 用户提供了股票代码 + 分析意图（估值/盈利/现金流）
  [T4] 上下文中有企业名称 + 金融分析类动词

Trigger 排除条件（满足则不直接触发，先澄清）：
  [E1] 用户仅说「分析一下」但未指定企业/项目 → 先询问目标
  [E2] 用户说的是「帮我写个模板」→ 触发模板生成，不是分析
```

**写入 SKILL.md 的格式**：
```markdown
## Trigger（触发条件）

| 编号 | 触发条件 | 优先级 |
|------|---------|---------|
| T1 | 用户说出「授信审查」/「credit review」 | P0 |
| T2 | 上传年报PDF/招股书 | P0 |
| T3 | 提供股票代码+分析意图 | P1 |
| T4 | 上下文有企业名称+金融分析动词 | P2 |

排除条件：
- E1: 未指定企业 → 先询问
- E2: 仅要模板 → 触发模板生成 Skill
```

---

### 2. State（状态追踪）

明确：「执行过程中需要持久化哪些信息？」

**必须追踪的 State 字段**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `task_id` | string | 唯一任务ID | `CR-2026-0601-001` |
| `stage` | enum | 当前阶段 | `COLLECTING`/`ANALYZING`/`VERIFYING`/`HANDOFF` |
| `iteration` | int | 当前迭代轮次 | `3` |
| `completed_steps` | list[string] | 已完成步骤 | `["下载年报", "提取财务数据"]` |
| `pending_steps` | list[string] | 待执行步骤 | `["DCF估值", "敏感性分析"]` |
| `evidence_index` | dict | 证据索引 `{来源: [行号列表]}` | `{"年报P45": [120, 135]}` |
| `data_gaps` | list[string] | 缺失数据列表 | `["2023年经营现金流", "担保人评级"]` |
| `warnings` | list[string] | 当前警告 | `["WACC假设高于行业均值"]` |
| `human_decisions` | dict | 需要人工决策的点 | `{"growth_rate": "用户确认3%"}` |

**State 持久化方式**：

在任务工作区创建 `.state.json`：
```json
{
  "task_id": "CR-2026-0601-001",
  "skill": "enterprise-public-disclosure",
  "stage": "ANALYZING",
  "iteration": 2,
  "completed_steps": ["download_annual_report", "extract_financials"],
  "pending_steps": ["dcf_valuation", "sensitivity"],
  "evidence_index": {
    "年报2023_P45": [120, 135, 142],
    "招股书_CH8": [88, 91]
  },
  "data_gaps": [
    {"field": "2023年经营现金流", "reason": "未披露", "action": "标注为缺失"}
  ],
  "warnings": [],
  "human_decisions": {},
  "updated_at": "2026-06-01T14:30:00+08:00"
}
```

**写入 SKILL.md 的格式**：
```markdown
## State（状态追踪）

每次执行前读取 `.state.json`，执行后更新。

| 字段 | 必填 | 说明 |
|------|------|------|
| `stage` | ✅ | COLLECTING → ANALYZING → VERIFYING → HANDOFF |
| `iteration` | ✅ | 从1开始，每轮+1 |
| `completed_steps` | ✅ | 用于断点恢复 |
| `evidence_index` | ✅ | 所有关键数据的来源索引 |
| `data_gaps` | ✅ | 缺失数据绝不跳过，必须记录 |

断点恢复逻辑：
  如果 `.state.json` 存在且 `stage` ≠ `HANDOFF`：
    → 从 `completed_steps` 最后一个步骤之后继续执行
    → 如果 `data_gaps` 非空 → 先处理缺失数据标注
```

---

### 3. Iteration（迭代循环）

明确：「每一轮做什么？什么时候进入下一轮？」

**标准迭代模式**：

```
Round N 开始
  │
  ├─ 步骤1：状态同步
  │   读取 .state.json
  │   检查 evidence_index 是否完整
  │
  ├─ 步骤2：执行本轮任务
  │   从 pending_steps 取下一个步骤
  │   执行（调用子 Skill 或直接处理）
  │
  ├─ 步骤3：验证
  │   对照 Verification 清单检查本轮输出
  │   如果验证失败 → 记录 warning → 本轮重做或停止
  │
  ├─ 步骤4：更新 State
  │   completed_steps.append(当前步骤)
  │   pending_steps.remove(当前步骤)
  │   evidence_index 更新
  │   写入 .state.json
  │
  └─ 步骤5：停止条件检查
      如果满足 Stop Conditions → 进入 Handoff
      否则 → Round N+1
```

**Iteration 配置参数**（写入 SKILL.md）：

```markdown
## Iteration（迭代配置）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | 10 | 最大迭代轮次，防止无限循环 |
| `verify_each_round` | true | 每轮强制验证 |
| `allow_human_interrupt` | true | 允许人工在任意轮次介入 |
| `state_persist_interval` | 1 | 每N轮写入一次 State（1=每轮都写） |
| `rollback_on_verify_fail` | true | 验证失败时回滚本轮 State |

迭代策略：
- 如果 pending_steps 为空 → 自动进入 VERIFYING 阶段
- 如果验证连续失败 3 次 → 停止并 Handoff（标注失败原因）
- 如果人工介入 → 更新 human_decisions → 继续迭代
```

---

### 4. Verification（验证清单）

明确：「每轮结束后，怎样确认做得对？」

**分层验证**：

| 验证层级 | 验证内容 | 方法 | 失败处理 |
|---------|---------|------|---------|
| **V0：格式验证** | 输出文件存在、格式正确 | 文件存在性检查、格式校验 | 重做 |
| **V1：数据验证** | 关键数字有来源、单位正确 | 对照 evidence_index 逐条检查 | 标注缺失、回滚 |
| **V2：逻辑验证** | 计算逻辑正确、公式无误 | 重新计算交叉验证 | 修复公式、重做 |
| **V3：业务验证** | 结果符合行业常识 | 与行业基准对比 | 标注异常、提示用户 |
| **V4：完整性验证** | 所有 required 字段已填写 | 对照交付物清单检查 | 补充缺失项 |

**写入 SKILL.md 的验证清单模板**：

```markdown
## Verification（验证清单）

每轮结束后，逐项检查：

### V0：格式验证（自动）
- [ ] 输出文件存在：`.state.json`
- [ ] 输出文件格式正确：JSON 可解析
- [ ] 时间戳已更新

### V1：数据验证（半自动）
- [ ] evidence_index 中每条记录都有来源文件+页码
- [ ] 财务数据单位一致（万元/亿元 不混用）
- [ ] 缺失数据已标注（不用0代替）

### V2：逻辑验证（手动+自动）
- [ ] DSCR = CFADS / 当期还本付息额（公式复核）
- [ ] 资产负债表：资产 = 负债 + 所有者权益
- [ ] 增长率计算：本期/上期 - 1

### V3：业务验证（手动）
- [ ] 毛利率在行业合理范围内
- [ ] 有息负债/总资产 < 行业警戒线
- [ ] 现金流符号合理（经营现金流通常为正）

### V4：完整性验证（自动）
- [ ] 交付物清单中所有文件已生成
- [ ] 所有 required 章节已填写
- [ ] 数据溯源声明已添加

验证失败处理：
- V0/V1 失败 → 自动重做本轮
- V2 失败 → 提示用户确认后重做
- V3 失败 → 标注异常，继续（不阻塞）
- V4 失败 → 补充缺失项，不进入下一轮
```

---

### 5. Stop Conditions（停止条件）

明确：「什么时候必须停下来？」

**强制停止条件矩阵**：

| 条件 | 优先级 | 动作 | 交接格式 |
|------|--------|------|---------|
| **S1：任务完成** | P0 | 正常停止 | 完整交付物 + Handoff 摘要 |
| **S2：达到 max_iterations** | P0 | 强制停止 | 当前 State + 未完成任务列表 |
| **S3：验证连续失败 3 次** | P0 | 强制停止 | 失败步骤 + 错误日志 |
| **S4：证据不足** | P1 | 停止并提示 | 缺失数据清单 + 建议获取途径 |
| **S5：需要权限/人工确认** | P1 | 停止并等待 | 待确认问题列表 |
| **S6：可能产生破坏性操作** | P0 | 立即停止 | 危险操作清单 + 请求显式确认 |
| **S7：用户主动停止** | P0 | 保存 State 后停止 | 当前进度摘要 |

**停止条件判断逻辑**（伪代码）：

```python
def should_stop(state, config):
    # P0 条件：立即检查
    if state["stage"] == "COMPLETED":
        return ("S1", "任务完成", state)
    
    if state["iteration"] >= config["max_iterations"]:
        return ("S2", f"达到最大迭代轮次 {config['max_iterations']}", state)
    
    if state.get("consecutive_verify_failures", 0) >= 3:
        return ("S3", "验证连续失败3次", state)
    
    if state.get("pending_destructive_action"):
        return ("S6", "检测到可能的破坏性操作", state)
    
    # P1 条件：检查 evidence/scope
    evidence_completeness = len(state["evidence_index"]) / max(1, len(state["required_evidence"]))
    if evidence_completeness < 0.5:
        return ("S4", f"证据不足（完整度 {evidence_completeness:.0%}），建议先补充资料", state)
    
    if state.get("needs_human_approval"):
        return ("S5", "需要人工确认", state)
    
    # 用户主动停止（通过信号）
    if state.get("user_abort"):
        return ("S7", "用户主动停止", state)
    
    return (None, None, None)  # 继续迭代
```

**写入 SKILL.md 的格式**：

```markdown
## Stop Conditions（停止条件）

以下情况**必须停止**并生成 Handoff：

| 编号 | 条件 | 处理 |
|------|------|------|
| S1 | `pending_steps` 为空 且 验证通过 | 正常完成 → Handoff |
| S2 | `iteration` ≥ `max_iterations` | 强制停止 → 保存 State |
| S3 | 连续验证失败 3 次 | 强制停止 → 输出错误日志 |
| S4 | 关键证据缺失且无法获取 | 停止 → 输出缺失清单 |
| S5 | 需要人工决策且等待超过 10 分钟 | 停止 → 输出待确认问题 |
| S6 | 检测到破坏性操作（删除/覆盖） | 立即停止 → 请求显式确认 |
| S7 | 用户说「停止」/「够了」/「先到这」 | 保存 State → 可恢复 |

停止后动作：
  S1 → 生成最终交付物，删除 .state.json（任务完成）
  S2/S3/S4/S5 → 保留 .state.json（可恢复）
  S6 → 不执行破坏性操作，等待用户显式确认
  S7 → 保留 .state.json（用户可稍后恢复）
```

---

### 6. Handoff（交接格式）

明确：「停止时，向下一个人/Agent 传递什么？」

**Handoff 包结构**：

```json
{
  "handoff_id": "HO-2026-0601-001",
  "timestamp": "2026-06-01T15:30:00+08:00",
  "skill": "enterprise-public-disclosure",
  "stop_reason": "S1: 任务完成",
  "state_snapshot": { /* 完整 State */ },
  "deliverables": [
    "/path/to/财务数据底稿.xlsx",
    "/path/to/授信审查报告.docx"
  ],
  "evidence_summary": {
    "total_sources": 5,
    "total_evidence_lines": 47,
    "data_completeness": "92%"
  },
  "open_issues": [
    "2023年Q3季报未获取，经营现金流数据缺失"
  ],
  "next_steps": [
    "如需更新数据，重新运行本 Skill 并传入更新后的年报PDF"
  ],
  "warnings": [],
  "human_decisions_log": []
}
```

**Handoff 写入位置**：
- 工作区根目录：`HANDOFF.md`（人类可读版本）
- 工作区根目录：`.handoff.json`（机器可读版本）

**HANDOFF.md 模板**：

```markdown
# Handoff — {任务名称}

**交接ID**：HO-2026-0601-001  
**时间**：2026-06-01 15:30  
**停止原因**：S1 任务完成  

---

## 当前状态

- 阶段：`ANALYZING → VERIFYING → COMPLETED`
- 迭代轮次：`7`
- 已完成步骤：`下载年报 → 提取财务数据 → DCF估值 → 敏感性分析 → 验证`

---

## 交付物

| 文件 | 路径 | 说明 |
|------|------|------|
| 财务底稿 | `01-底稿/财务数据底稿.xlsx` | 含公式链接 |
| 授信报告 | `04-报告/授信审查报告.docx` | V1.0 |
| 证据索引 | `00-工作区/evidence_index.xlsx` | 所有数据来源 |

---

## 证据概况

- 来源数量：`5`（年报2021-2023、季报2024Q1、评级报告）
- 证据条数：`47`
- 数据完整度：`92%`（缺失2023Q3经营现金流）

---

## 未解决问题

1. 2023年Q3季报未获取，经营现金流数据缺失 → 建议用户补充

---

## 后续步骤

1. 如需更新数据 → 重新运行 `enterprise-public-disclosure`，传入更新后的年报
2. 如需调整假设 → 修改 `.state.json` 中的 `human_decisions`，从第3轮恢复

---

## 验证记录

| 轮次 | 验证项 | 结果 | 备注 |
|------|--------|------|------|
| 1 | V0-V4 | ✅ 通过 | - |
| 2 | V0-V4 | ✅ 通过 | - |
| ... | ... | ... | ... |
| 7 | V0-V4 | ✅ 通过 | 最终验证 |

---

## 人工决策记录

（本任务无需人工决策）

---

**交接人**：WorkBuddy Agent  
**交接给**：用户 / 下一个 Agent  
```

**写入 SKILL.md 的格式**：

```markdown
## Handoff（交接格式）

每次停止时，生成两个文件：

1. `.handoff.json`（机器可读，用于 Agent 间接续执行）
2. `HANDOFF.md`（人类可读，用于人工交接）

Handoff 包必须包含：
- ✅ 完整 State 快照（用于恢复）
- ✅ 交付物清单（含路径）
- ✅ 证据概况（来源数、证据条数、完整度）
- ✅ 未解决问题列表
- ✅ 验证记录（每轮的 V0-V4 结果）
- ✅ 人工决策日志

交接后动作：
  - 如果 `stop_reason` 是 S1（完成）→ 归档 .state.json，保留 .handoff.json
  - 如果 `stop_reason` 是 S2/S3/S4/S5 → 保留 .state.json，下次可从断点恢复
  - 如果 `stop_reason` 是 S7（用户主动停止）→ 保留 .state.json
```

---

## 改造工作流

### 阶段一：诊断（Diagnose）

对目标 Skill 执行以下检查：

```
诊断清单：
  [ ] Skill 是否有明确的 Trigger（什么时候该触发）？
  [ ] Skill 执行过程中是否有状态持久化？
  [ ] Skill 是否支持断点恢复？
  [ ] 每步执行后是否有验证？
  [ ] 是否有明确的停止条件？
  [ ] 停止时是否有结构化交接包？

如果以上任意一项为「否」→ 需要改造
```

### 阶段二：设计（Design）

填写改造设计表：

```markdown
## 改造设计 — {Skill 名称}

### Trigger 设计
| 触发条件 | 优先级 | 排除条件 |
|---------|--------|---------|
| ... | ... | ... |

### State 设计
| 字段 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| ... | ... | ... | ... |

### Iteration 设计
执行阶段划分：
  1. COLLECTING（收集资料）
  2. ANALYZING（分析处理）
  3. VERIFYING（验证校验）
  4. HANDOFF（交接停止）

每阶段 Steps：
  COLLECTING: [step1, step2, ...]
  ANALYZING: [step3, step4, ...]
  ...

### Verification 设计
每阶段验证清单：
  COLLECTING → [V0, V1]
  ANALYZING → [V0, V1, V2]
  VERIFYING → [V0, V1, V2, V3, V4]

### Stop Conditions 设计
强制停止条件：
  - S1: 所有步骤完成且验证通过
  - S2: iteration ≥ 10
  - ...

### Handoff 设计
交付物清单：
  - 文件1：路径、格式、说明
  - ...
```

### 阶段三：实施（Implement）

按设计修改 SKILL.md：

1. 在 SKILL.md 顶部 `---` frontmatter 中增加：
   ```yaml
   loop_engineered: true
   loop_version: "1.0"
   max_iterations: 10
   ```

2. 在 SKILL.md 中新增章节（如果缺失）：
   - `## Trigger（触发条件）`
   - `## State（状态追踪）`
   - `## Iteration（迭代循环）`
   - `## Verification（验证清单）`
   - `## Stop Conditions（停止条件）`
   - `## Handoff（交接格式）`

3. 修改执行流程描述，使其符合 Iteration 模式

### 阶段四：验证（Validate）

用测试任务验证改造后的 Skill：

```
测试用例：{企业名称} + {任务类型}
  Round 1: 正常执行 → 检查 State 写入
  Round 2: 人工中断 → 检查 State 可恢复
  Round 3: 故意提供错误数据 → 检查验证是否捕获
  Round 4: 达到 max_iterations → 检查是否停止
  Round 5: 任务完成 → 检查 Handoff 包完整性
```

---

## 与其他 Skill 的关系

```
loop-engineering（本 Skill）
    │
    ├── 改造目标 ───→ work-analysis-loop（通用分析循环护栏）
    │                  loop-engineering 负责「改造流程」
    │                  work-analysis-loop 负责「执行时的循环结构」
    │                  两者叠加：改造后的 Skill 在执行时自动启用分析循环
    │
    ├── 改造对象 ───→ credit-review-workbench（总入口）
    │                  → 为总入口增加 Trigger 精确匹配
    │                  → 为子任务增加 State 追踪
    │                  → 为长任务增加 Stop Conditions
    │
    ├── 改造对象 ───→ enterprise-public-disclosure（公开披露）
    │                  → 四阶段交付流程 → 四轮 Iteration
    │                  → 每阶段有 Verification 清单
    │                  → 阶段间有 Stop Conditions
    │
    └── 改造输出 ───→ 所有改造后的 Skill 的 SKILL.md
                       → 增加六元框架章节
                       → 增加 .state.json 规范
                       → 增加 HANDOFF.md 模板
```

---

## 示例：改造前后对比

### 改造前（`enterprise-public-disclosure` v3.3.0）

```
执行模式：一次性执行
  1. 用户上传年报 PDF
  2. Skill 执行：下载 → 解析 → 提取 → 生成报告
  3. 输出报告
  4. 结束

问题：
  - 如果解析失败 → 从头重新执行
  - 无法知道执行到哪一步
  - 报告质量无验证
  - 人工无法在中间介入
```

### 改造后（`enterprise-public-disclosure` v3.4.0+loop-engineering）

```
执行模式：循环迭代
  Round 1: COLLECTING 阶段
    - 步骤：识别企业 → 下载年报 → 校验文件
    - 验证：V0（文件存在）V1（来源正确）
    - State: {stage: COLLECTING, completed: [识别企业, 下载年报], pending: [解析PDF]}
    - 停止检查：继续 → Round 2

  Round 2: ANALYZING 阶段
    - 步骤：解析PDF → 提取财务数据 → 生成底稿
    - 验证：V0 V1 V2（公式正确）
    - State: {stage: ANALYZING, completed: [..., 解析PDF, 提取财务数据]}
    - 停止检查：继续 → Round 3

  Round 3: VERIFYING 阶段
    - 步骤：交叉验证 → 缺失数据标注 → 生成报告V1
    - 验证：V0 V1 V2 V3 V4
    - State: {stage: VERIFYING, ...}
    - 停止检查：验证通过 → 继续 / 验证失败 → 重做 Round 3

  Round 4: HANDOFF 阶段
    - 步骤：生成最终交付物 → 生成 HANDOFF.md
    - 验证：V0 V4
    - 停止检查：S1 满足 → 停止

问题修复：
  - 解析失败 → 从 .state.json 恢复，从中断步骤继续
  - 每轮有验证 → 质量问题早期发现
  - 人工可随时介入 → 更新 human_decisions → 继续
```

---

## 配套代码库（references/）

本 Skill 提供可复用的 Python 代码库，封装 State / Handoff / Validation 的核心操作。

### 文件结构

```
loop-engineering/references/
├── __init__.py           # 包入口，统一导出
├── state_manager.py      # State 读写、备份、恢复、原子写入
├── handoff_manager.py    # Handoff 包生成（.handoff.json + HANDOFF.md）
├── validator.py          # 每轮六维验证器
└── state-schema.json     # 统一 State Schema 定义
```

### 快速开始

```python
# 初始化新任务
from loop_engineering import quick_init, quick_load, quick_handoff
from loop_engineering import StateManager, HandoffManager, RoundValidator

state = quick_init("./workspace", skill="enterprise-public-disclosure",
                   stage="COLLECTING",
                   stages_pending=["COLLECTING", "EXTRACTING", "DELIVERING"])

# 每轮更新
state.iteration += 1
state.complete_stage("COLLECTING")
state.add_evidence("年报2023", [45, 52])
state.add_data_gap("2023Q3经营现金流", "未披露")
StateManager("./workspace").save(state)

# 验证
validator = RoundValidator()
result = validator.validate(state, round_output="[事实] 营收 5203 亿元")
if not result.passed:
    print(result.errors)

# 生成 Handoff
handoff = quick_handoff("./workspace", state, stop_reason="S1",
                        deliverables=[{"name": "报告", "path": "report.docx", "status": "done"}])

# 断点恢复
state = quick_load("./workspace")
if state:
    print(f"恢复任务 {state.task_id}，从第 {state.iteration} 轮继续")
```

### 关键类说明

| 类/函数 | 文件 | 用途 |
|---------|------|------|
| `State` | state_manager.py | State 数据对象，提供属性访问、证据/缺口/警告管理 |
| `StateManager` | state_manager.py | 文件读写、备份、恢复、原子写入、task_id 生成 |
| `quick_init` / `quick_load` | state_manager.py | 一行代码快速初始化和读取 |
| `HandoffManager` | handoff_manager.py | 生成 .handoff.json + HANDOFF.md |
| `quick_handoff` | handoff_manager.py | 一行代码快速生成 Handoff |
| `RoundValidator` | validator.py | 六维验证（V1-V6），含连续失败计数器 |
| `ValidationResult` | validator.py | 验证结果对象（passed/errors/warnings/checks） |

### 设计约束

- **Python 3.10+**（使用 dataclass、type hints）
- **零外部依赖**：仅使用标准库（json, os, shutil, datetime, re, dataclasses）
- **原子写入**：`os.replace()` 保证 State 文件写入不损坏
- **容错恢复**：State 文件损坏时抛出 `StateCorruptedError`，由调用方处理

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.1.0 | 2026-06-28 | **配套代码库**：新增 references/ 目录，含 state_manager.py（State 读写/备份/恢复/原子写入）、handoff_manager.py（Handoff 包生成）、validator.py（六维验证器）、state-schema.json（统一 Schema）；SKILL.md 新增「配套代码库」章节 |
| 1.0.0 | 2026-06-28 | 初始版本。六元改造框架（Trigger/State/Iteration/Verification/StopConditions/Handoff），含改造工作流、验证方法、前后对比示例 |

---

**使用本 Skill**：当用户要求优化某个 Skill 的执行流程、增加迭代能力、或将一次性 Skill 改造为可循环工作流时，加载本 Skill 并按六元框架执行改造。
