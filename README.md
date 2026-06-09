# WorkBuddy Skills

本仓库用于 WorkBuddy 技能的跨设备同步。

## 使用方法

在新电脑上克隆到 `~/.workbuddy/skills/` 目录：

```bash
git clone https://github.com/yuanliugit/workbuddy-skills.git ~/.workbuddy/skills/
```

之后每次修改技能后推送：`git push`，另一台电脑拉取：`git pull`。

## 技能列表

| 技能 | 版本 | 用途 |
|------|:---:|------|
| 企业公开信息抓取 | v3.3.0 | A股/港股上市公司公开披露资料抓取与授信报告生成 |
| 现金流测算 | — | 项目偿债现金流测算（DSCR/CFADS），银行信贷审批 |
| **企业估值分析** | v1.0.0 | DCF + 相对估值 + SOTP 三法交叉验证，WACC敏感性矩阵，授信审批专用 |
| **盈利质量分析** | v1.0.0 | 季报回顾 + 分析师预期修正追踪，盈利稳定性与趋势判断 |
