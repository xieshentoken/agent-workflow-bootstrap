# 06 · 源码阅读、来源与设计差异

核对日期：2026-11-02。仓库：deepseek-ai/dsh-superagent-prototype。
阅读基线 commit：`6337fc823ce20251c8de8085948165c81aaa701e`；提交时间：2026-10-31T12:05:39Z。
本轮静态阅读 README、SETUP、000–003 文档、007 架构前部，及 policy.ts / environment.ts 的相关实现；没有运行 DSH 或其测试全套。

## 已确认的仓库事实

| 资料 | 事实 | 本 Skill 如何使用 |
|---|---|---|
| [README](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/README.md) | 单 GitHub 仓库编码 Agent；依赖 DSH；研究原型而非正式产品；公开代码不等于内部全部设计 | 不把它直接当作通用生产平台 |
| [SETUP](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/SETUP.md) | 先探测；逐个问；计划确认后执行；不在聊天索要密钥；避免覆盖既有配置 | 转为通用的新手搭建协议，不复制账号和依赖要求 |
| [000 Philosophy](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/docs/000-philosophy.md) | 减少人的注意力成本；窄范围启用；减少噪声；对输出负责 | 减少选项；关键节点通知；不以 Agent 数量为目标 |
| [001 Domain](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/docs/001-domain.md) | Source/Trigger、Mandate、Ticket、Assignment 分离；执行器在领域核心之外 | 事件、授权、任务、执行分开；允许替换工具 |
| [002 Authorization](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/docs/002-authorization.md) | 确定性 gate + assessment；observe 针对 inferred，explicit 仍可执行；运行中策略变化不直接撤销授权 | 借鉴双层准入；增加执行前检查；模拟模式更严格 |
| [003 Execution](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/docs/003-execution.md) | 任务会话与目录；结构化待人工状态；重启先核对外部效果；worker 以宿主 OS 用户无逐命令批准执行 | 借鉴状态与恢复；不沿用其默认执行权限 |
| [007 Architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/docs/007-architecture.md) | Engine 为核心状态唯一写入者；事务内排外部工作，提交后执行；Outbox 记录回执 | 作为可选自动化阶段的实现参考，不强加给手工模式 |
| [policy.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/policy.ts) | `assessmentOutcome` 检查每条启用规则被判断；推断候选非 auto 时记录 would_accept；`settingsPolicy` 执行准入 | 明确规则与模型判断分工，不把提示词当硬约束 |
| [environment.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/6337fc823ce20251c8de8085948165c81aaa701e/src/infra/environment.ts) | 包装命令、清理部分环境与身份配置；代码明确不是 OS 级边界 | 区分防误用与安全隔离 |

## 刻意不同的设计

| DSH 原型 | 本 Skill 的通用方案 | 原因 |
|---|---|---|
| 一个仓库、GitHub/飞书、DSH 执行器 | 任何可定义输入输出的低风险任务；适配器可替换 | 用户要求不绑定工具和过往应用 |
| observe 仅约束推断任务 | 首次 simulate 对全部任务禁止真实外部副作用 | 防止新手误以为“观察”绝不会执行 |
| 结束工单可能在后续人类消息下恢复 | DONE / FAILED / CANCELLED 保持终态，创建关联任务 | 与上一版协议一致，降低隐式重启风险 |
| 策略变化通知运行工单，不立即撤销 | 新受限动作前重查有效许可；撤权阻止新影响 | 更保守的通用边界；中途取消仍须实际工具支持 |
| 无 PR 的 ready 可完成 Ticket | DONE 须验收与交付核实；ready 只是候选状态 | 不把自报完成当通用验收 |
| 包装脚本和目录隔离工作默认值 | 自动化前验证真实权限控制 | 文件分开不等于访问隔离 |

## 与上一版文档的关系

依据本会话 `agent-workflow-v0.1-reading.md` 及 ZIP：保留四层结构、任务合同、审批、证据、运行状态、恢复与工具适配。
本包新增搭建状态、逐步引导、阶段门、脚手架、局部校验器和行为演练。
没有原地改写旧版本；冲突时显式记录并由用户选择，不凭“新文件优先”取得授权。
原 X 文章本轮通过上一版已整理的方法作为背景，未重新审计其实现或核实作者业务成效。

## Skill 格式依据

[Agent Skills specification](https://agentskills.io/specification)：`SKILL.md` 的 name/description；references/assets/scripts 的分层；渐进加载。
[Skill creation best practices](https://agentskills.io/skill-creation/best-practices)：从已有领域材料提炼、计划—验证—执行、给默认方案、用真实执行改进。
本包没有实验性 `allowed-tools` 字段，不暗示所有宿主有相同授权模型。
使用格式不等于已在所有 Agent 产品完成兼容性测试。

所有新增门槛、字段、脚本和示例为本包设计，不应归因于 DeepSeek 已实现。
