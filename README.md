# WorkBuddy Skills

本仓库用于 WorkBuddy AI 助手技能的跨设备同步与版本管理。

## 使用方法

在新电脑上克隆到 `~/.workbuddy/skills/` 目录：

```bash
git clone https://github.com/yuanliugit/workbuddy-skills.git ~/.workbuddy/skills/
```

日常同步：修改后 `git push`，另一台电脑 `git pull`。

## 技能列表（34 个）

### 银行授信审批体系
| 技能 | 用途 |
|------|------|
| `credit-review-workbench` | 授信审查总调度入口，七型任务路由（A-G），四阶段交付 |
| `work-analysis-loop` | 通用分析循环护栏，六层数据分级，防无限循环 |
| `企业公开信息抓取` | A股/港股企业公开披露资料抓取，年报PDF数据提取 |
| `现金流测算` | 项目偿债现金流测算（DSCR/CFADS），DebtFacility模型 |
| `企业估值分析` | DCF+相对估值+SOTP三法交叉验证，WACC敏感性矩阵 |
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
| `excel-xlsx` | Excel电子表格处理 |
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
| `humanizer` | AI文本人性化处理 |
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

_最后更新：2026-06-28_
