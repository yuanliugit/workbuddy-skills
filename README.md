# WorkBuddy Skills

本仓库用于 WorkBuddy AI 助手技能的跨设备同步与版本管理。

## 使用方法

在新电脑上克隆到 `~/.workbuddy/skills/` 目录：

```bash
git clone https://github.com/yuanliugit/workbuddy-skills.git ~/.workbuddy/skills/
```

日常同步：修改后 `git push`，另一台电脑 `git pull`。

## 技能列表（35 个）

### 银行授信审批体系
| 技能 | 用途 |
|------|------|
| `credit-review-workbench` | 授信审查总调度入口，七型任务路由（A-G），四阶段交付 |
| `work-analysis-loop` | 通用分析循环护栏，六层数据分级，防无限循环 |
| `企业公开信息抓取` | A股/港股企业公开披露资料抓取，年报PDF数据提取 |
| `现金流测算` | 项目偿债现金流测算（DSCR/CFADS），DebtFacility模型 |
| `企业估值分析` | DCF+相对估值+SOTP+LBO+Merger Model五法交叉验证，WACC敏感性矩阵，IRR/MOIC分析 |
| `盈利质量分析` | 季报beat/miss分析+分析师修正追踪，盈利稳定性预警 |
| `investment-industry-research` | 投资导向行业研究，产业链上中下游全覆盖 |
| `loop-engineering` | 六元改造框架：Trigger→State→Iteration→Verification→StopConditions→Handoff |

### 内容生成
| 技能 | 用途 |
|------|------|
| `baoyu-comic` | 知识漫画创作，多风格多画风 |
| `baoyu-slide-deck` | 专业幻灯片生成 |
| `baoyu-infographic` | 信息图表生成，21种布局 |
| `baoyu-cover-image` | 文章封面图生成，11色板+7渲染风格 |
| `baoyu-diagram` | 技术图表/流程图/架构图生成 |
| `baoyu-image-gen` | AI图像生成，多模型支持 |

### 文档处理
| 技能 | 用途 |
|------|------|
| `pdf-generator` | PDF文档生成 |
| `ppt-generator` | PowerPoint演示文稿生成 |
| `word-docx` | Word文档生成与编辑 |
| `excel-xlsx` | Excel电子表格处理，含投行级金融建模规则（三表联动/DCF/LBO/M&A专属规范） |
| `minimax-pdf` | 高质量PDF生成（注重视觉品质） |

### 发布与转换
| 技能 | 用途 |
|------|------|
| `baoyu-post-to-wechat` | 微信公众号文章发布 |
| `baoyu-url-to-markdown` | URL网页内容转Markdown |
| `baoyu-wechat-summary` | 微信群聊摘要生成 |
| `baoyu-youtube-transcript` | YouTube字幕/转录下载 |

### 内容加工
| 技能 | 用途 |
|------|------|
| `baoyu-translate` | 精翻/翻译（中英互译） |
| `baoyu-format-markdown` | Markdown格式化 |
| `humanizer` | AI文本人性化处理（英文） |
| `humanizer-zh` | 中文AI写作痕迹去除（24种通用模式+6种中文特有模式） |
| `summarize` | 文本摘要提取 |

### 开发与工具
| 技能 | 用途 |
|------|------|
| `agent-browser` | 浏览器自动化操作 |
| `github-skill` | GitHub交互（issue/PR/CI） |
| `find-skills` | 技能发现与搜索 |
| `marketplace-skill-installer` | 技能市场一键安装 |
| `skills-security-check` | 技能安全审查 |

### 设计与专业
| 技能 | 用途 |
|------|------|
| `ui-ux-pro-max` | UI/UX设计系统 |
| `data-analysis` | 数据分析 |
| `market-researcher` | 市场研究 |
| `agent-memory` | Agent记忆管理 |
| `cloudstudio-deploy` | CloudStudio云端部署 |

### 其他
| 技能 | 用途 |
|------|------|
| `deai` | DEAI模块 |
| `多模态内容生成` | 文生视频/3D模型等多模态生成 |

---

## 更新日志

### 2026-06-28 — 金融建模能力扩展与中文文本优化

**新建 Skill（1个）**：
- `humanizer-zh` v1.0.0 — 中文AI写作痕迹去除，24种通用AI模式+6种中文特有模式（高频词/宣传式结论/四字排比/破折号滥用/标题空心化/机械分段），与英文`humanizer`分工协同

**Skill 升级（2个）**：
- `企业估值分析` v1.1.0 → v1.2.0 — 新增LBO杠杆收购模型（Sources&Uses/债务分层/IRR/MOIC/5×5敏感性矩阵）和Merger Model并购增厚/稀释分析（Accretion/Dilution/支付方式敏感性/协同效应），原有DCF/相对估值/SOTP三法完整保留
- `excel-xlsx` v1.0.2 → v1.1.0 — 新增Financial Modeling Domain Rules章节（投行颜色约定/三表联动架构/DCF·LBO·M&A专属规则/公式锚定规范/模型审计清单/中国市场Excel惯例），原有7条核心规则完整保留

**优化原则**：所有变更均为纯追加扩展，现有技能内容零删减、零弱化。

---

### 2026-06-28 — 大规模整合与六元改造

**新建 Skill（4个）**：
- `work-analysis-loop` v1.1.0 — 通用分析循环护栏（六层数据分级 + 防无限循环）
- `credit-review-workbench` v1.1.0 — 授信审查总调度入口（七型任务路由）
- `investment-industry-research` v1.1.0 — 投资导向行业研究（产业链全覆盖）
- `loop-engineering` v1.1.0 — 六元改造框架 + Python 代码库

**授信体系 Skill 升级（4个）**：
- `企业公开信息抓取` v3.3.0 → v3.5.0 — 护栏集成 + State断点恢复 + Handoff
- `现金流测算` v1.1.0 → v1.2.0 — 护栏集成 + Trigger + Handoff
- `企业估值分析` v1.0.0 → v1.1.0 — 护栏集成 + 六元改造
- `盈利质量分析` v1.0.0 → v1.1.0 — 护栏集成 + 六元改造

**loop-engineering 配套代码库**（`loop-engineering/references/`）：
- `state_manager.py` — 统一 State 读写管理器（原子写入 + 损坏恢复）
- `handoff_manager.py` — 停止包生成器（.handoff.json + HANDOFF.md）
- `validator.py` — 六维验证器 V1-V6
- `state-schema.json` — 统一 State Schema 定义

**模板生成**：
- 授信初审报告模板（非项目类授信）.docx
- 项目融资初审报告模板（项目类授信）.docx

---
_最后更新：2026-06-28_
