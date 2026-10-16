# 团队协作 / Team workflow

## 最终项目入口

**main 是最终整合版。** 应用入口是根目录的 `app.py`，命令行入口是 `run_demo.py`。
`new-ui-code` 保留本次整合历史；旧的 `agent`、`feature/data` 等分支不是最终运行入口。
不需要把早期目录或旧 UI 再复制回 main。

## 第一次加入

接受仓库邀请后：

```sh
git clone https://github.com/yszgit/return-detective.git
cd return-detective
git switch main
python -m pip install -r requirements.txt
```

建议使用 Python 3.12；已支持 Python 3.11。创建自己的环境和本地 `.env`，
不要覆盖队友的配置。无需 AWS 的快速启动见 [README](../README.md)。

## 获取最终版本

先提交或妥善保存自己的修改，再同步：

```sh
git fetch origin
git switch main
git pull --ff-only origin main
```

如果提示有本地修改或不能快进，先比较内容，不要使用强制推送或硬重置覆盖工作。
各自的本地 `.env` 和忽略的运行文件不会从 Git 下载。

## 三人协作

一人协调最终整合；其他人按文件或函数分工。即使三人做同一模块，也先约定函数边界。
后续修改在工作分支提交，通过测试和评审后合入 main。不要把共享的 AWS 案件工作区
当成 Git 分支：同一命名空间里的案件会被不同客户端共享。

| 工作 | 主要位置 |
| --- | --- |
| Agent 与权限 | `rd/agents/`、`rd/tools.py`、`rd/policy/` |
| 数据、AWS 和评估 | `scripts/`、`aws/`、`rd/data.py`、`evaluation/` |
| UI 与业务流程 | `app.py`、`rd/ui.py`、`rd/workflow.py`、`rd/verification.py` |

`rd/tools.py` 的公开函数签名和 JSON 契约由团队共享，修改前要协调。

## 提交前检查

```sh
python -m unittest discover -s tests -v
python -m compileall -q rd app.py run_demo.py scripts tests evaluation
git status
git add path/to/changed-file.py
git commit -m "Describe the verified change"
git push origin YOUR_WORK_BRANCH
```

只暂存本次确认的文件。main 的发布需要通过完整离线检查。代码合入不代表
已在任何新 AWS 账号部署，也不代表模型和邮件权限已获批准。

## 演示数据与 AWS

每人使用自己的 Workshop 临时凭证。共享代码、非秘密资源名称和数据契约。
临时凭证、本地 `.env`、HMAC 密钥、原始 CSV、备份和运行轨迹都不上传 Git。

- UI 和 CLI 默认保留案件。
- `Delete / restore cases` 和 CLI `--reset-cases` 会先备份再清空当前工作区。
- 已推进到较晚日期的工作区不能回到过去调查；使用独立运行目录/命名空间或显式重置。
- 多个应用进程使用不同的 DynamoDB 命名空间，避免并发读写互相覆盖。
- SNS 是可选的即时内部案件提醒；未来人工复查计划不会自动发邮件。
