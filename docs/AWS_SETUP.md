# AWS setup / 比赛环境设置

Kiro、GitHub 和应用调用 AWS 的凭证分别配置。Kiro profile 由主办方组织管理员授权。

## 本地先验证

~~~powershell
conda activate aldo-hackthon
python -m pip install -r requirements.txt
python scripts/check_aws.py --data-only
python run_demo.py quality --offline
python -m streamlit run app.py
~~~

默认使用 DuckDB，读取根目录 `data/`；可用 `RD_DATA_DIR` 指定获准的数据目录。

## 连接比赛 AWS

复制 `.env.example` 为本机 `.env`。填入实际区域 `AWS_REGION` 和可用模型 / inference profile 的 `RD_MODEL_ID`。

使用 Athena 时设置 `RD_BACKEND=athena`、`RD_ATHENA_DB`、`RD_ATHENA_WORKGROUP`，以及工作组未提供结果位置时的 `RD_ATHENA_OUTPUT`。资源名称和权限由 AWS 负责人按比赛账号确认；仓库不会自动创建资源。

按 Workshop Studio 说明在本机配置本人临时 Access Key、Secret Key 和 Session Token。凭证会过期，不要进入代码、PR、聊天或截图。

~~~sh
python scripts/check_aws.py
~~~

这个命令会实际验证 AWS 身份、读取配置的数据源，并发起一次小的 Bedrock 调用。成功显示数据量和 Bedrock 回复。

- ExpiredToken：更新临时凭证。
- AccessDenied：核对账号、区域和对应资源权限。
- 模型不可用：核对模型 / inference profile 的账号与区域可用性。
- Athena 失败：核对 Glue 表结构、工作组、结果桶与数据位置。

GitHub CI 仅离线检查，没有自动部署。DynamoDB、真实业务动作、审批认证、通知与云端定时复查属于后续工作。

参考：[Boto3 credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)
