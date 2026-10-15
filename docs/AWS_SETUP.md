# AWS setup / Workshop Studio

1. 登录主办方提供的 Workshop Studio，进入比赛账号，记下指定的区域代码。
2. 在实验室的临时凭证入口复制适用于自己系统的配置命令。临时凭证包含 `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY` 和 `AWS_SESSION_TOKEN` 三项。
3. 把命令运行在自己的终端，之后从同一终端启动项目。凭证过期时重新获取三项，不要提交到 Git。
4. 设置实际可用的区域和模型 ID / inference profile ID。不要使用模型显示名称。

PowerShell（交互输入两个非秘密配置项）：

```powershell
$env:AWS_DEFAULT_REGION = Read-Host "Competition region code"
$env:BEDROCK_MODEL_ID = Read-Host "Enabled model or inference profile ID"
.\.venv\Scripts\python.exe -m return_detective.check_aws
.\.venv\Scripts\python.exe -m streamlit run app.py
```

也可以把 `.env.example` 复制成 `.env` 后填写非秘密配置项；凭证仍使用实验室终端配置。`.env` 已被 Git 忽略。

检查器先验证 STS 身份，再执行一次很小的 Bedrock 请求。返回模型回答才证明该配置已连通；本仓库不预设账号、区域、模型、真实资源或访问成功。

## Resources for the AWS owner

| Resource | Suggested setting |
| --- | --- |
| S3 data bucket | Choose a globally unique private name; store synthetic CSVs and policies |
| Cases table | `return-detective-cases`; String partition key `case_id`; on-demand billing |
| Inventory table | `return-detective-inventory`; String partition key `stock_id`; on-demand billing |
| Actions Lambda | `return-detective-actions`; Python runtime; logs; approval validation and idempotency |

开发身份需要调用所选 Bedrock 模型、读取指定 S3 对象、访问案件表和调用指定 Lambda 的权限。Lambda 执行角色另外需要日志和指定表的读写权限。资源创建还需要主办方允许的部署权限；出现拒绝时请 mentor 调整比赛角色。

后端必须独立校验审批、审批人身份、操作范围和重复执行。库存更新使用条件写入或事务。演示用的 `DemoRetail` 不提供身份认证或多人共享持久化。

## Troubleshooting

| Error | Check |
| --- | --- |
| `NoCredentialsError` | Whether all three temporary credential values are set in this terminal |
| `ExpiredToken` | Refresh temporary credentials from the lab |
| `AccessDeniedException` | Role permissions, model account access, and any provider activation requirements |
| `ValidationException` | Region, model ID, supported Converse API, or required inference profile |

Official references: [temporary credentials](https://docs.aws.amazon.com/sdkref/latest/guide/feature-static-credentials.html), [model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html), [Lambda execution roles](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html).
