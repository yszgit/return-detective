# 仓库整合说明

集成分支 `feature/integration-layout` 保留并合入：
- `feature/data`：`f9ce4e7`，清洗数据与工具。
- `feature/agent`：`d01bdb3`，三段 Agent 与 Athena/DuckDB 后端。
- `main`：`a735bae`，README 修改。

## 目录迁移

| 原位置 | 统一位置 |
| --- | --- |
| `agent_app/rd/` 和数据分支 `rd/` | 根目录 `rd/` |
| `agent_app/run_demo.py` | `run_demo.py` |
| 两套依赖和配置 | 根目录 `requirements.txt`、`.env.example` |
| 原 `return_detective/`、界面、样本、测试 | `examples/legacy_demo/` |
| 两份历史回测 CSV | `evaluation/cases_backtest.csv` |
| 原回测脚本 | `evaluation/archive/backtest_original.py`，历史参考 |
| 原 Agent README | `docs/AGENT_IMPORT_ORIGINAL.md`，历史参考 |

清洗 Parquet 保留原始字节；没有重新生成或独立认证其来源。

## 行为修复

1. Strands `structured_output_model` + Pydantic 保留完整嵌套结果。
2. 已有案件会真正关联新增退货。
3. 拒绝审批后为 `REJECTED`；批准后为 `APPROVED`，不表示真实执行。
4. 单条退货和公司基线均限制在回放日期以内。
5. `replay_context` 在 SDK 工作线程中保持稳定日期，单进程内调查串行。
6. 费用按退货单去重，混合商品订单的费用归属仍需核对。
7. `sku_return_rate` 保留签名，`lines_sold` / `return_rate` 返回 null。
8. `fee_audit` 的 `n` / `charged` 统计退货单而非唯一客户。
9. 动作增加模拟标记，`executed=false`；重复审批点击不重复记录动作。
10. 复查工具返回 `planned=true, scheduled=false`，到期日记录在案件中。

## 配置

统一使用 `AWS_REGION`、`RD_MODEL_ID`、`RD_BACKEND`、`RD_DATA_DIR`、`RD_ATHENA_*`。根目录 `.env` 由 `rd/config.py` 加载。旧 `BEDROCK_MODEL_ID` / `AWS_DEFAULT_REGION` 仅作为兼容别名。

## 团队迁移

本 PR 合入 develop 后，先保存修改，在自己的工作分支同步：

~~~sh
git fetch origin
git pull --ff-only
git merge --no-edit origin/develop
python -m pip install -r requirements.txt
~~~

PR 合并前，可检出集成分支进行评审。数据 PR #1 的原提交已经包含在集成历史中。不要重新建立重复的 `agent_app/rd`；所有人围绕同一套共享接口开发。

离线测试覆盖日期、审批、Agent 传递、案件关联、Athena 适配与 UI；线上 AWS、真实执行器、生产审批认证和调度需另行验证 / 实现。

参考：[Strands structured output](https://strandsagents.com/docs/user-guide/sdk/agents/structured-output/)
