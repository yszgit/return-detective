# 团队协作 / Team workflow

## 当前代码和运行入口

团队当前使用 `agent` 分支，应用入口是根目录的 `app.py` 和 `run_demo.py`。
目录职责见 [项目结构](REPOSITORY_STRUCTURE.md)。其他分支可能仍是早期版本，
合并前先比较文件内容。

## 第一次加入

仓库 owner 添加协作者，队友接受邀请后运行：

```sh
git clone https://github.com/yszgit/return-detective.git
cd return-detective
git switch --track origin/agent
python -m pip install -r requirements.txt
```

已经有本地 `agent` 分支时使用 `git switch agent`。

## 每次开始

先提交或妥善保存自己的修改，再同步：

```sh
git switch agent
git pull --ff-only origin agent
```

多人修改同一模块时，先明确各自负责的文件或函数。遇到非快进更新或冲突，
先与队友核对改动，再合并；不要强制推送或覆盖其他人的工作。

## 验证和提交

```sh
python -m unittest discover -s tests -v
git status
git add path/to/changed-file.py
git commit -m "Describe the verified change"
git push origin agent
```

只暂存本次确认的文件。`main` 的发布合并单独审阅；提交到 `agent` 不代表
已合并 `main`，也不代表 AWS 资源已部署。

## 分工参考

| 工作 | 主要位置 |
| --- | --- |
| Agent 调查和行动 | `rd/agents/`、`rd/tools.py`、响应 playbook |
| 数据、AWS 和评估 | `scripts/`、`aws/`、`rd/data.py`、`evaluation/` |
| 页面和演示 | `app.py`、`docs/VERIFICATION_DEMO.md` |

这些是文件职责，不是新增分支或自动分配人员。跨模块修改前先和相关队友协调。

## AWS 与数据

每位成员使用自己的有效 Workshop 临时凭证。共享代码、数据契约和资源名称；
不要分享密钥。`.env.example` 只放非秘密配置，`.env` 和运行记录留在本地。
当前明确纳入版本管理的数据范围见 [数据政策](DATA_POLICY.md)。
