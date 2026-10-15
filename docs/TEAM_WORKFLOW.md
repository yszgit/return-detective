# 团队协作 / Team workflow

## 整理后的 Agent 分支

`agent` 从 `feature/agent` 的 `f8008f0` 建立，完整 Agent 应用已移到仓库根目录。拉取后按根目录 README 安装依赖；不用再进入 `agent_app/`。原始 starter 保存在 `legacy/starter/`。其他团队分支的文件布局可能仍然不同，合并前参考 `docs/REPOSITORY_STRUCTURE.md` 的路径映射。

```sh
git fetch origin
git switch --track origin/agent
```

已有本地 `agent` 分支时直接 `git switch agent`。数据目录、运行记录和凭证不要提交；当前数据说明在 `docs/DATA_POLICY.md`。

## 第一次加入

仓库 owner 在 Settings → Collaborators 添加队友，队友接受邀请后：

```sh
git clone https://github.com/yszgit/return-detective.git
cd return-detective
git fetch origin
git switch --track origin/feature/data
```

最后一行换成自己的工作分支，例如 `feature/agent`、`feature/aws`、`feature/frontend` 或 `feature/evaluation`。已经有本地分支时直接 `git switch feature/data`。

## 每次开始

先提交或保存自己当前的修改，再同步。以数据分支为例：

```sh
git switch feature/data
git fetch origin
git pull --ff-only
git merge origin/develop
```

出现冲突时，和负责同一文件的人确认内容，解决后再提交。不要强制推送，不要覆盖队友提交。

## 提交与合并

```sh
git add path/to/changed-file.py
git commit -m "Add cohort evidence query"
git push
```

在 GitHub 发起 Pull Request：**base = develop，compare = 自己的工作分支**。写清做了什么、如何验证、是否改动数据字段或配置。至少请一位队友看过后合并。

`main` 放能演示的版本；集成人员把通过验证的 `develop` 合入 `main`。共享的工作分支会长期保留，不自动删除。

## 分工边界

| 方向 | 分支 | 第一件可交付工作 |
| --- | --- | --- |
| 数据 | `feature/data` | 校验订单明细关联、数量、时间和库存定位 |
| Agent | `feature/agent` | 在真实 Bedrock 模型上验证工具调用与假设修正 |
| AWS | `feature/aws` | 完成 S3 读取、DynamoDB 持久化及审批后的 Lambda 操作 |
| 界面 | `feature/frontend` | 展示工具证据、审批状态和独立核验结果 |
| 评估 | `feature/evaluation` | 正常、异常、证据不足场景以及同时间回放基线 |

业务和演讲负责人维护 `docs/` 与 `evaluation/` 中的价值假设、演示脚本和证据；不预填个人姓名或自动分配 GitHub 账号。

新增成员需要独立开发同一模块时，从 `develop` 再开 `feature/<module>-<short-task>`，避免多人同时推同一个分支。

## AWS 与数据

每位成员使用自己的比赛临时凭证。共享的是代码、数据契约和资源名称。密钥不得写入代码、issue、PR、截图或聊天。`.env.example` 只提供非秘密配置字段。

不要把整个 OneDrive 文件夹当成团队同步方式。每个人克隆仓库到自己的目录，通过 GitHub 合并代码。
