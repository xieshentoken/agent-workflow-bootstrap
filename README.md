# agent-workflow-bootstrap · 工作流搭建教练

版本：0.1.0 · 日期：2026-11-02 · 状态：可审阅、可试用的 Skill 草案。

## 用途

让一个有能力读取说明的 Agent，协助新手从一个低风险任务开始，建立人主导、工具可替换的工作流程。
它不是 dsh-superagent 的安装器，也不是自动运行的“多 Agent 公司”。

| 内容 | 位置 |
|---|---|
| 给 Agent 的入口指令 | `SKILL.md` |
| 规划说明与取舍 | `DESIGN.md` |
| 分阶段规程与安全约束 | `references/` |
| 新工作区模板 | `assets/workspace/` |
| 可选本地辅助脚本 | `scripts/` |
| 行为演练用例（未声称已执行） | `evals/` |
| 辅助脚本测试 | `tests/` |
| 本次验证范围 | `VALIDATION.md` |

## 开始使用

将完整文件夹交给 Agent。支持 Agent Skills 的宿主按其当前文档安装到项目范围，不默认全局安装。
不支持自动发现 Skill 的工具，直接要求它读取 `SKILL.md`，并按需读取相对路径引用。
不同宿主的工具名、安装路径和权限不同；该目录格式并不保证所有宿主均已兼容。

建议启动语句：

> 请读取 agent-workflow-bootstrap/SKILL.md，协助我建立一套人主导的 Agent 工作流。
> 先复用已有资料，确认一个低风险任务，并检查你真正具备的能力。
> 每轮只问一个影响下一步的问题，给出建议。先向我提交实施计划，不要默认安装 DSH、连接账号或启动后台服务。
> 每阶段给出产物、证据和下一步；不能做到的能力写明，不要假装已经完成。

仅讨论规划时追加：“本轮只规划，不在我的设备上执行。”

## 可选脚本

需要 Python 3.9+，只用标准库。没有 Python 时由 Agent 或用户手工复制模板即可，不要为文本试点强制安装依赖。
`scaffold.py` 默认仅预览；`--apply` 才写入新目录。`check_workspace.py` 只读指定的少量配置与证据引用。
两个脚本都不是权限系统，不连接网络、不发送信息、不调模型、不收集密钥。

```sh
python3 scripts/scaffold.py /absolute/path/to/new-workspace
# 仅在路径和变更已获授权后执行下一条
python3 scripts/scaffold.py /absolute/path/to/new-workspace --apply
python3 scripts/check_workspace.py /absolute/path/to/new-workspace
python3 -m unittest discover -s tests -v
```

现有工作区应读取、对比并提出迁移计划；脚手架不会覆盖它，也没有 `--force` 参数。

## 交付边界

本包未在用户设备安装，未配置云账户、GitHub、消息入口或定时服务。
本包使用自主编写的通用规程和小工具，不包含 dsh-superagent 源码副本。
源码阅读与设计差异见 `references/06-repo-reading.md`。本轮保留上一版工作流，不原地覆盖。
