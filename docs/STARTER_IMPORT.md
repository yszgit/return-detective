# Cleaned starter import / 清洗数据版本

这次把用户指定的本地 `return_detective_starter/return_detective/` 中 12 个原始文件上传到 `feature/data`。相对目录保持一致：`rd/`、`scripts/prepare_data.py` 和 `data/`。校验清单见 `starter-import-manifest.sha256`，记录导入时的原始字节 SHA-256。

数据来源是团队提供的本地 starter。导入过程没有获得原始 CSV、额外数据字典或独立来源证明，因此不把这批数据标为 synthetic，也不把原型操作手册当作 ALDO 的正式政策。

## 文件与规模

| 文件 | 内容 | 读取结果 |
| --- | --- | --- |
| `data/returns.parquet` | 退货记录 | 649,745 行，日期 2024-02-04 至 2026-01-31 |
| `data/sku_sales.parquet` | SKU 销售汇总 | 64,388 行 |
| `data/exchanges.parquet` | 换货记录 | 61,934 行 |
| `data/baseline.parquet` | 全期退货原因基线 | 12 类 |
| `data/cases_backtest.csv` | 回测候选记录 | 1,201 行，其中 134 行有 report_date |

候选信号不等于已确认根因或已避免退货。`after_flag` 也不代表实际节省金额或被干预避免的退货。

## 本地读取

在仓库根目录安装 `requirements.txt` 后：

```sh
python -c "from rd.data import one; print(one('select count(*) as n from returns'))"
python -c "from rd.detect import screen; print(screen('Aalto', 'Quality', '2024-07-21'))"
```

`rd.data` 默认读取根目录的 `data/`。也可通过 `RD_DATA_DIR` 指定其他数据目录。`rd.store` 默认在本地 `runtime/cases.json` 保存案件；此目录已加入 Git 忽略规则，团队共享持久化需要接 DynamoDB。

原始文件中的算法和动作逻辑保留供团队审核。已验证 DuckDB 读取、一个抽样筛查及 Python 语法；实际 Strands / Bedrock 调用尚待比赛账号验证。当前默认 Streamlit 页面仍使用原始 `return_detective/` 包和 `data/sample/`，尚未接入 `rd/`。

## 合入 develop 前的跟进

1. **回放时间边界**：`baseline_share` 使用全历史基线，`get_return` 没有回放日期过滤，需要避免未来信息进入历史调查。
2. **退货率口径**：筛查是退货原因占比；`sku_return_rate` 的销售分母是全期汇总，需要匹配销售群体、数量和观察窗口。
3. **费用粒度**：按退货单聚合后的费用连接到商品行，后续逐行求和可能重复累计。需要核对原始费用定义。
4. **审批状态**：拒绝最后一项审批时，`decide_approval` 仍会把案件设为 `ACTIONED`。需区分被拒绝、待处理和执行成功。
5. **实际执行与验证**：当前业务动作以 JSON 日志为主；库存、费用状态变更、真实核验和定时重查还需实现。

## 团队接法

- 数据：维护 `rd/data.py`、`rd/detect.py`、清洗脚本与数据定义。
- Agent：基于 `TRIAGE_TOOLS`、`INVESTIGATOR_TOOLS`、`RESPONSE_TOOLS` 补编排入口；验证工具选择和证据引用。
- AWS：把本地案件存储与模拟业务动作接到 DynamoDB / Lambda。
- 界面：将 `rd/` 工具查询、审批和核验结果接入应用。
- 评估：增加日期边界、费用去重、拒绝审批和重复执行检查。
