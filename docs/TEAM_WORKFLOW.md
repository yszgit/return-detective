# Team workflow / 团队协作

详细入门：[Git / GitHub 指南](GITHUB_TEAM_GUIDE_ZH.md)。迁移说明：[INTEGRATION.md](INTEGRATION.md)。

工作分支 → PR 到 develop → 集成验证 → PR 到 main。同一模块多人开发时，各自创建任务分支。

| 方向 | 主要位置 |
| --- | --- |
| Data | rd/data.py、rd/detect.py、scripts/prepare_data.py |
| Agent | rd/agents.py、rd/tools.py |
| AWS | aws/、存储与执行器接口 |
| Frontend | app.py |
| Evaluation | tests/、evaluation/ |

配置与工具接口共享；不要每人复制一套项目。rd/tools.py 的改动需相关负责人协调。

先提交 / stash 当前修改，在自己的工作分支运行：

~~~sh
git fetch origin
git pull --ff-only
git merge --no-edit origin/develop
python -m pip install -r requirements.txt
~~~

分支没有 upstream 时先建立跟踪关系。任何一步报错先处理再继续。

提交前查看 git diff、运行相关检查。PR 写清改动、验证结果和接口影响，至少一位队友看过再合并。集成负责人核对演示后再进入 main。

本次集成 PR 合入 develop 后，所有工作分支先同步 develop，再继续修改统一 rd 包。每人本机安装环境、使用本人比赛凭证。
