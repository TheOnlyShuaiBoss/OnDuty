# 002 命名与发布准备

- 日期: 2026-09-16 · 用户拍板: 名称 **onduty** / 许可证 **MIT** / 文档 **中英双语**

## 命名依据(实证)

| 候选 | GitHub | PyPI | 结论 |
|---|---|---|---|
| **onduty** | 撞车低(头部 <20★ 且不相关) | **空闲** | ✅ 采用。语义=核心价值主张"让 agent 替人值班" |
| baton | django-baton/AmEx 跨领域占用 | taken(2016 iRODS) | 备选 |
| nightshift | 老无关项目 | taken(2021 弃用科学包) | 备选 |
| agent-relay/agentrelay | 同领域 mnemox/AgentRelay + 同名活跃 PyPI 包 | taken | ❌ 排除 |
| agentd/agent_daemon | AgentDock 1747★ 及海量通用占用 | — | ❌ 无品牌价值 |

## 命名引发的变更(本次全部完成并回归)

1. 包 `agentd/` → `onduty/`;`agentctl.py` + 旧 `__main__` 合并为单入口 `onduty/cli.py`(子命令: daemon/once/check/list/status/run/logs),旧 `agentd run` = 新 `onduty daemon`
2. 品牌串: toast AUMID/标题、webhook 默认模板、daemon 冲突提示 → onduty
3. 新增 `pyproject.toml`:pip 包名 `onduty`,console script `onduty`,requires-python ≥3.10,依赖 PyYAML+croniter
4. `LICENSE`(MIT)、`README.md`(英文主体)+`README.zh.md`、`docs/MANUAL.md`(中文手册)+`docs/MANUAL.en.md`
5. tests 导入更名;tasks.example.yaml 注释更名
6. **本地目录名保持 `D:\ClaudeData\agent_daemon`**(用户工作路径约束,repo 名与目录名解耦,不影响推送)

## 发布就绪清单(推送侧)

- .gitignore: state/ sandbox/ tasks.yaml(用户配置)/ __pycache__/ egg-info/ dist/ build/
- plans/000、001、002 随仓库发布 = 设计文档资产(001 含竞品与实测证据链,开源读者向)
- 待用户: 建 GitHub 仓库 → 给 SSH 远程 → 推送;建议 topics: `ai-agents, cron, scheduler, coding-agent, automation`
- 装好后 TODO(已在 verlog): codebuddy 本机冒烟转正 continue;若掌握 zcode 无头命令,custom 接入示例提交回仓库
