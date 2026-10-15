# Return Detective：队友 Git / GitHub 使用指南

适用对象：第一次使用 Git 的队友，以及负责数据、Agent、AWS、前端和评估的成员。
仓库：[yszgit/return-detective](https://github.com/yszgit/return-detective)（私有仓库，需要先接受邀请）。
核对日期：2026-10-15。分支内容会继续变化，以 GitHub 上的最新提交为准。

> 核心流程：下载项目 → 切到自己的工作分支 → 修改并验证 → commit → push → 发 PR 到 develop → 队友审核并合并 → 集成负责人将可演示版本合入 main。

> 结构更新：当前整合版使用根目录 rd/；旧演示在 examples/legacy_demo/。分支快照章节是整合前状态，请以当前 README 和整合说明为准。

## 阅读顺序

- 第一次加入：第 1–6 节。
- 每天开发：第 7–9 节。
- 准备交付：第 10–11 节。
- 有冲突或报错：第 12–15 节。
- 只想快速查命令：第 17 节。

---

## 1. 先认识这几个东西

| 名称 | 可以怎样理解 | 在本项目中的作用 |
| --- | --- | --- |
| Git | 本地版本记录工具 | 记录谁改了什么，切换分支，合并代码 |
| GitHub | 团队共享代码的网站 | 保存远程仓库、审核修改、集中合并 |
| Repository / Repo | 一个项目的文件与历史 | 我们的 `return-detective` 仓库 |
| Clone | 第一次把仓库下载到自己电脑 | 同时获得文件和 Git 历史 |
| Branch | 一条独立的开发线 | 先开发一个模块，再交给团队集成 |
| Commit | 在自己电脑里记录一次修改 | 一个可以查阅、比较的版本节点 |
| Push | 把本地提交上传到 GitHub | 让队友看到你提交的内容 |
| Fetch | 读取远程最新提交和分支信息 | 更新 `origin/...`，不直接改当前工作文件 |
| Pull | 获取并整合远程分支的更新 | 更新自己当前的本地分支 |
| Pull Request / PR | 请求把一个分支的改动合入另一个分支 | 供队友检查代码、讨论和批准合并 |
| Merge | 把两条开发线整合起来 | 例如把前端分支合入 `develop` |
| Kiro | 写代码、运行项目的编辑器 | 打开本地仓库；可在内置终端运行 Git |
| Conda 环境 | 本机的 Python 和依赖集合 | 隔离本项目需要的 Python 包 |
| AWS | 云端模型与服务 | Bedrock、S3、DynamoDB、Lambda 等 |

### 四件经常被混淆的事

1. **Save / 保存文件**：文件改在自己电脑上。
2. **Commit**：Git 在自己电脑上记录这个版本。
3. **Push**：这个版本才会出现在 GitHub。
4. **Merge PR**：这个版本才会进入团队的目标分支。

所以，`commit` 完以后，队友还不一定拿得到代码；`push` 完以后，`develop` 也不会自动变化。GitHub 的 PR 提供合并前的讨论与检查入口。参见 [GitHub PR 概念](https://docs.github.com/en/pull-requests/reference/pull-requests)。

---

## 2. 我们的分支怎么用

### 2.1 已有分支

| 分支 | 用途 | 谁主要在这里工作 |
| --- | --- | --- |
| `main` | 已验证、可演示的版本 | 集成负责人 |
| `develop` | 集成各模块并一起验证 | 集成负责人协调 |
| `feature/data` | 数据处理、DuckDB 查询、检测逻辑 | 数据负责人 |
| `feature/agent` | Agent、工具调用、提示词、调查流程 | Agent 负责人 |
| `feature/aws` | AWS 资源、权限、持久化和服务连接 | AWS 负责人 |
| `feature/frontend` | Streamlit 界面、证据展示、审批交互 | 前端负责人 |
| `feature/evaluation` | 测试、评估场景、业务假设验证 | 评估负责人 |

正常合并方向：

```text
feature/data ────────┐
feature/agent ───────┤
feature/aws ─────────┼── PR → develop ── 集成验证 ── PR → main
feature/frontend ───┤
feature/evaluation ─┘
```

这些是团队约定。本文没有替仓库设置分支保护，也不代表 GitHub 已强制要求审批。

### 2.2 一个工作分支尽量只有一位主要提交者

一个人负责前端时，可以使用已有的 `feature/frontend`。

两个人同时做前端时，先约定文件分工，或者各自从 `develop` 建一个任务分支，例如：

```text
feature/frontend-evidence-panel
feature/frontend-approval-form
```

任务分支各自发 PR 到 `develop`。分支名中的人名、模块名和任务名由本人选择；上面是示例，不是已经创建的分支。

### 2.3 当前 starter 在哪里：加入前先看这里

2026-10-15 核对远程分支时：

- 清洗后的 starter 在 **`feature/data`**，导入提交为 `f9ce4e7`。
- `develop` 仍是初始脚手架，尚未包含这次 starter 导入。
- `main` 也尚未包含这次导入；它额外有一处 README 标题修改。
- `feature/agent`、`feature/aws`、`feature/frontend`、`feature/evaluation` 仍是初始脚手架。

**切到其他分支后看不到 `rd/` 或清洗数据，并不表示文件被删掉了。不同分支当前拥有的提交不同。**

需要查看 starter 时，可在 GitHub 选择 `feature/data`，或在本地切换到它。导入内容与待处理问题见 [STARTER_IMPORT.md](STARTER_IMPORT.md)，相关讨论入口见 [PR #1](https://github.com/yszgit/return-detective/pull/1)。本文不把导入视为已经审核通过。

如果你现在就必须基于 starter 开发，而它还没合入 `develop`，请看第 6.3 节。不要为了拿到文件直接覆盖自己的项目文件夹。

---

## 3. 第一次加入：账号、Git 和权限

### 3.1 接受仓库邀请

1. 把自己的 GitHub 用户名告诉仓库 owner。
2. 用被邀请的那个 GitHub 账号登录。
3. 在 GitHub 通知或邀请邮件里接受邀请。
4. 打开 [项目仓库](https://github.com/yszgit/return-detective)，确认能看到文件。

私有仓库显示 `404` 或 `Repository not found` 时，先检查是否登录了正确账号、是否接受邀请。网页上能看仓库，也还需要本机 Git 使用有权限的账号完成身份验证。

我们采用同一个仓库内协作。队友有写入权限后，可以直接 clone 这个仓库并提交自己的分支，无需先 fork 到个人账号。

### 3.2 安装 Git

Windows：从 [Git 官方安装页](https://git-scm.com/install/windows) 下载并安装 Git for Windows。安装后重新打开 Kiro 和终端。

macOS / Linux：参考 [Git 官方安装入口](https://git-scm.com/install) 选择自己的系统。

打开 PowerShell、Git Bash、Anaconda Prompt，或 Kiro 的终端，输入：

```sh
git --version
```

看到类似 `git version ...` 就说明终端能找到 Git。如果出现“无法识别 git”，先重开终端；仍不行再检查安装和 PATH。

### 3.3 配置提交者姓名和邮箱：每台电脑通常做一次

把引号里的示例改成自己的信息：

```sh
git config --global user.name "你的姓名"
git config --global user.email "你的 GitHub 提交邮箱"
```

查看设置：

```sh
git config --global --get user.name
git config --global --get user.email
```

- 姓名是提交记录显示的作者名，可以与 GitHub 用户名不同。
- 邮箱建议使用 GitHub 已验证邮箱，或者 GitHub **Settings → Emails** 提供的 noreply 邮箱；不要自己猜 noreply 地址。
- 这些设置只决定提交署名，不会让 Git 登录 GitHub，也不会赋予仓库权限。
- `--global` 会作为当前电脑用户的默认设置。如果只想给本项目设置，在仓库根目录运行相同命令并去掉 `--global`。

Git 初始设置及身份验证说明见 [GitHub：Set up Git](https://docs.github.com/en/get-started/git-basics/set-up-git)，配置作用范围见 [Git：git-config](https://git-scm.com/docs/git-config)。

### 3.4 GitHub 登录

本指南使用 HTTPS 仓库地址。第一次 clone / pull / push 时，如果 Git Credential Manager 弹出浏览器登录，请用自己的 GitHub 账号完成登录。

如果终端直接要求 GitHub 密码，普通账号密码不能用于 HTTPS Git 操作。优先使用 Git Credential Manager；需要 token 时，按 GitHub 官方说明配置，不要把 token 写进仓库地址或发给队友。参见 [GitHub：Repeated credential prompts](https://docs.github.com/en/get-started/git-basics/why-is-git-always-asking-for-my-credentials)。

---

## 4. 第一次把项目下载到电脑

### 4.1 选择存放项目的位置

先在终端进入你想放项目的**父文件夹**。路径由你自己选择；如果路径有空格，请加引号。例如，Windows 可以先在文件管理器创建 `C:\Projects`，再输入：

```powershell
cd "C:\Projects"
```

然后执行一次：

```sh
git clone https://github.com/yszgit/return-detective.git
cd return-detective
```

`git clone` 会创建项目文件夹。以后更新项目用 fetch / pull，不需要每天重新 clone。

**已经有这个仓库的人，直接进入现有文件夹，跳过 clone。** 不要在项目里面再 clone 同一个项目，否则容易出现 `return-detective/return-detective`，之后会在错误的文件夹里运行命令。

### 4.2 确认自己进入了正确的仓库

```sh
git rev-parse --show-toplevel
git remote -v
git status
```

正常情况：

- 第一条输出本机仓库根目录。
- 第二条的 `origin` 指向 `https://github.com/yszgit/return-detective.git`。
- 第三条显示当前分支和文件修改情况。

`origin` 是 Git 给这个远程仓库起的名字；`origin/develop` 是本机最近一次 fetch 后看到的远程 develop 状态。

### 4.3 用 Kiro 打开整个项目文件夹

在 Kiro 中使用 **Open Folder**，选择 clone 后的 `return-detective` 文件夹。

正确的项目根目录中应有 `README.md`、`requirements.txt`、`app.py`、`.gitignore` 等文件。不要只打开 `rd/`、`docs/` 或单独某个 Python 文件作为项目。

在 Kiro 打开终端后，可以再次运行 `git rev-parse --show-toplevel` 确认位置。

**不要使用 Download ZIP 代替 clone 来参与 Git 协作。** ZIP 适合查看文件，但不带本地 Git 历史和远程跟踪配置。也不用在 clone 的仓库里再执行 `git init`。

---

## 5. 配好 Python / Conda 环境

Git 下载的是项目文件。Python 环境和安装好的依赖需要每个人在自己电脑上准备。

### 5.1 已经有 `aldo-hackthon` 环境

请先切到自己要使用的分支，再安装该分支的依赖。激活已有环境：

```sh
conda activate aldo-hackthon
```

没有此环境的人，可以创建后再激活。下面两行仅适用于**还没有该环境**的人：

```sh
conda create -n aldo-hackthon python=3.12
conda activate aldo-hackthon
```

项目现有 CI 使用 Python 3.12，新建环境建议对齐这个版本。已有 Python 3.11 环境可以先安装依赖并验证；本文没有宣称所有组件已经在 3.11 上通过验证。

如果终端无法识别 `conda`，Windows 可先在 Anaconda / Miniconda Prompt 中运行这些命令。让 Kiro 使用正确解释器也很重要，不要只看终端提示里的环境名。Conda 环境创建与激活见 [Conda 官方环境指南](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)。

### 5.2 确认 Python 来自目标环境

```sh
python -c "import sys; print(sys.executable)"
python --version
```

输出路径应指向自己的 `aldo-hackthon` 环境。

在 Kiro 按 **Ctrl + Shift + P → Python: Select Interpreter**，选择同一个环境。如果没有该命令，先确认已启用 Python 相关扩展。

每个人的解释器绝对路径不同，不要复制其他队友电脑上的 `C:\Users\...` 路径。

### 5.3 安装并更新项目依赖

在仓库根目录、目标环境已激活的情况下运行：

```sh
python -m pip install -r requirements.txt
```

用 `python -m pip` 可以确保把包装进当前 Python。切到一个依赖不同的分支，或者拉取后 `requirements.txt` 有变化，都需要重新执行。

新增项目依赖时，应把必要依赖写进 `requirements.txt` 并随代码一起提交。不要把 Conda 环境文件夹、整个电脑的包列表或缓存上传到 GitHub。

---

## 6. 选择或创建自己的工作分支

本节有三种情况，**选一种符合你情况的做法**。

### 6.1 你独立负责一个模块：使用已有模块分支

以下以前端负责人为例。其他成员把 `feature/frontend` 替换成自己的分支名。

先读取远程分支：

```sh
git fetch origin
git branch -r
```

第一次在这台电脑建立这个分支的本地跟踪关系：

```sh
git switch --track origin/feature/frontend
```

如果提示本地分支已存在，就使用：

```sh
git switch feature/frontend
```

检查结果：

```sh
git branch --show-current
git status
```

应该看到自己的工作分支。`git switch` 会切换当前文件内容；分支创建与切换规则见 [git-switch 官方文档](https://git-scm.com/docs/git-switch)。

### 6.2 同一模块多人开发：建自己的任务分支

先确认 `git status` 没有未提交修改，然后：

```sh
git fetch origin
git switch -c feature/frontend-evidence-panel origin/develop
git push -u origin feature/frontend-evidence-panel
```

这表示：以远程最新 `develop` 为起点，建立新任务分支并上传。把示例分支名改成自己的任务名。

这里使用 `origin/develop`，避免从自己过期的本地 `develop` 开始。后续发 PR 时仍以 `develop` 为目标。

### 6.3 现在必须基于尚未合入 develop 的 starter 开发

建议数据负责人先处理导入说明中的问题，再由团队审核导入 PR 并合入 `develop`。完成后，其他成员按第 7 节同步即可。

如果时间紧，确实需要立即并行开发，可以在干净工作区中**从 `feature/data` 建自己的任务分支**：

```sh
git fetch origin
git switch -c feature/agent-investigation origin/feature/data
git push -u origin feature/agent-investigation
```

这个分支已经包含 starter，之后不要再向 `feature/data` 直接推送自己的 Agent 改动。

该任务的 PR 暂时选择 **base = `feature/data`，compare = 自己的任务分支**，并说明依赖数据导入。数据导入合入 `develop` 后，将任务 PR 的 base 改成 `develop`，重新检查 Files changed 和冲突，再审核合并。

这是存在未合并依赖时的特殊做法。一般任务仍从 `develop` 创建，PR 也合入 `develop`。不要把缺陷尚未处理的 starter 当作已验证的演示版本。

---

## 7. 每次开始开发：先同步

以下继续以已有的 `feature/frontend` 为例。如果你使用自己的任务分支，把分支名换掉。

### 7.1 先检查有没有没保存到 Git 的修改

```sh
git status
```

如果有修改：已经完成的工作先 commit；尚未完成但需要保留的工作可以暂存到 stash，见第 13 节。不要带着不清楚归属的修改随意切换分支。

### 7.2 同步远程自己的分支，再同步 develop

工作区干净时：

```sh
git switch feature/frontend
git fetch origin
git pull --ff-only
git merge --no-edit origin/develop
```

逐行理解：

| 命令 | 做什么 |
| --- | --- |
| `git switch feature/frontend` | 确认正在自己的分支工作 |
| `git fetch origin` | 更新本机记录的远程分支信息 |
| `git pull --ff-only` | 在无需产生分叉合并的情况下更新自己的跟踪分支 |
| `git merge --no-edit origin/develop` | 把团队集成分支的新改动带进自己的分支 |

`--ff-only` 如果发现本地和远程各有新提交，会停止。停止时按第 15 节处理，不要强制覆盖任何一边。此行为见 [git-pull 官方文档](https://git-scm.com/docs/git-pull)。

**在任何一条命令报错后，先停下来处理错误，不要继续照抄后面的命令。**

对第 6.3 节的特殊依赖分支：starter 尚未合入 `develop` 时，和数据负责人协调后，可把最后一行的同步来源换成 `origin/feature/data`。导入完成后恢复从 `origin/develop` 同步。

### 7.3 再检查依赖和运行情况

如果 `requirements.txt` 有变化：

```sh
python -m pip install -r requirements.txt
```

随后运行与你要改的模块相关的检查。不要把已有的模块问题误认为是这次同步失败。

---

## 8. 修改、检查、提交和上传

### 8.1 修改前先说清任务边界

一个任务尽量对应一个可验收结果，例如：

- 前端：让调查页展示 SKU 和证据表。
- 数据：让历史回放查询过滤掉未来记录。
- AWS：把案件读取接到 DynamoDB。
- 评估：验证拒绝审批后不会显示执行成功。

需要改别人负责的接口或共享文件时，先在群里说明。尤其是 `requirements.txt`、`app.py`、工具参数、数据字段和存储结构。

### 8.2 修改后先看差异

```sh
git status
git diff
git diff --stat
```

常见短状态：

| 标记 | 含义 |
| --- | --- |
| `M` | 文件被修改 |
| `??` | 新文件，还没有被 Git 跟踪 |
| `A` | 新文件已加入暂存区 |
| `D` | 文件被删除 |
| `UU` | 文件有尚未解决的合并冲突 |

如果看到大量完全无关的文件变化，先检查是不是让编辑器自动格式化了整个项目，或者打开了错误的文件夹。

### 8.3 运行相关检查

仓库已有的离线检查：

```sh
python -m unittest discover -s tests -v
python run_demo.py quality --offline
```

需要启动界面时：

```sh
python -m streamlit run app.py
```

整合版测试覆盖共享 rd 模块、回放日期、Agent 结果传递、审批与页面；旧脚手架测试在 examples/legacy_demo/。模型和 AWS 使用离线替身，真实服务需要另行验证。修改哪个模块，就写清对应检查结果。

### 8.4 把确定要提交的文件加入暂存区

例如这次只改了 `app.py`：

```sh
git add app.py
git diff --cached
```

`git add` 选择的是本次要提交的内容。`git diff --cached` 显示已经选中的差异。

新手优先按文件添加。只有在确认所有变更都应进入本次提交时，再使用 `git add .`。尤其留意配置、数据、临时结果和意外删除。

### 8.5 创建本地提交

```sh
git commit -m "Add evidence table to investigation page"
```

提交说明写清具体变化。例如：

- `Fix as-of filtering in return lookup`
- `Add DynamoDB case persistence`
- `Handle rejected approvals in case status`

避免只写 `update`、`final`、`stuff`。一个提交尽量表达一件完整的事情。

### 8.6 上传自己的分支

首次推送、或还没设置上游分支时：

```sh
git push -u origin feature/frontend
```

已经设置过之后：

```sh
git push
```

如果使用的是自己的任务分支，首次推送命令中的分支名也要换成任务分支名。

打开 GitHub，选择这个分支，检查最新提交和文件。**push 成功意味着上传成功；是否进入 `develop` 要看 PR 是否已合并。** 分支推送和 upstream 的含义见 [git-push 官方文档](https://git-scm.com/docs/git-push)。

---

## 9. Pull Request：把成果交给团队

### 9.1 网页操作

1. 打开 [仓库](https://github.com/yszgit/return-detective)。
2. 点击 **Pull requests → New pull request**，或使用推送后出现的 **Compare & pull request**。
3. 正常任务选择：
   - **base：`develop`**，表示要合入哪里。
   - **compare：你的工作分支**，表示改动从哪里来。
4. 在 **Files changed** 检查提交内容，有没有意外文件、配置或删除。
5. 写标题、改动说明、验证方式和已知问题。
6. 尚未完成时创建 **Draft PR**；准备好后标记为可审核。
7. 请一名队友检查。团队约定至少一名队友看过后再合并。

特殊依赖 PR 的 base 见第 6.3 节。GitHub 的分支选择与 PR 创建步骤见 [官方 PR 创建指南](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request)。

### 9.2 可直接填写的 PR 说明

```markdown
## 做了什么
-

## 为什么需要
-

## 如何验证
- 运行了什么命令 / 操作了什么页面：
- 实际看到的结果：

## 对其他人的影响
- 是否改了数据字段、函数参数、依赖或 AWS 配置：
- 队友更新后需要做什么：

## 已知问题 / 依赖
-
```

不要把尚未执行的检查写成已通过。页面修改可以附截图，但截图里不要带 AWS 临时凭证。

### 9.3 队友让你修改怎么办

继续在**同一个分支**修改，再 add、commit、push。GitHub 会把新提交更新进原来的 PR，不需要每次重开。参见 [GitHub：更新已有 PR](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request#making-changes-to-files-in-your-pull-request)。

---

## 10. 谁来合并、怎么合并

### 10.1 审核者看什么

- 目标分支是不是 `develop`。
- 改动是否实现了 PR 描述的任务。
- 接口、字段和依赖是否与团队约定一致。
- 作者是否提供了相关验证结果。
- 是否引入临时文件、密钥、无关大文件或意外删除。
- 有无法解决的讨论或冲突时，先解决再合并。

### 10.2 合并步骤

由约定的审核者 / 集成负责人在 GitHub PR 页面检查，再使用可用的合并按钮。

我们已有的 `feature/data`、`feature/agent` 等分支会持续使用，建议采用 **Create a merge commit**，保留它们的提交关系。合并方式是否可用取决于仓库设置；不要假设所有按钮都已启用。参见 [GitHub：Merging a pull request](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request)。

如果团队使用 squash 来合并短任务分支，完成后下一项任务从最新 `develop` 建新分支。不要把旧任务分支一直当作新任务的起点。

**不要删除仍在使用的长期模块分支。** 单次任务分支可以在确认已合并、没有其他人依赖后删除。

### 10.3 合并完以后，其他队友怎样拿到成果

在自己的工作分支上，先确认工作区干净，再按第 7 节运行同步流程。关键是把最新 `origin/develop` 合入自己分支。

只运行自己分支上的 `git pull`，并不会自动把其他分支的改动带过来。

### 10.4 develop 什么时候进入 main

当数据、Agent、AWS 和界面在一起能跑通演示场景后，集成负责人发：

```text
base = main
compare = develop
```

检查演示、配置说明和评估结果，再合并。比赛演示使用确认过的 `main` 版本。

如果 `main` 上有单独的修复，负责人也要把这些提交通过 PR 同步回 `develop`，再协调工作分支更新，避免两条共享分支长期分叉。

---

## 11. GitHub Actions 绿色勾代表什么

当前仓库有 **Integrated offline checks** 工作流，会运行 Python 语法检查、现有单元测试和离线演示。

- 红叉：点进去看失败的步骤和错误输出，再修复并 push。
- 绿色勾：这些已配置的检查通过。
- 没有检查记录：先看 Actions 是否启用、工作流是否被触发。

整合后的 CI 会安装依赖，并验证共享 rd 包、Agent 结果传递、日期、审批与页面。AWS 和模型使用离线替身，线上连接仍需单独验证。

**当前工作流没有自动部署到 AWS。** push 到 GitHub 后，已运行的 AWS 服务也不会因此自动更新。

---

## 12. 合并冲突：怎么处理

### 12.1 为什么会冲突

例如你和队友都改了同一个配置值，Git 无法判断应该保留哪一版。发生冲突后，Git 会暂停合并，等人确定最终内容。

先查看：

```sh
git status
```

冲突文件中可能出现：

```text
  <<<<<<< HEAD
你当前分支的内容
  =======
这次合入分支的内容
  >>>>>>> origin/develop
```

在“把 develop 合入自己分支”这个操作里，Current / HEAD 通常指自己的分支，Incoming 指本次合入的 develop。其他操作的标签含义要结合当前操作判断。

### 12.2 正确处理顺序

1. 找出 `git status` 中有冲突的文件。
2. 与负责同一逻辑的队友确认最终应该是什么。
3. 手工改成正确结果；可能保留一边，也可能组合两边。
4. 删除 `<<<<<<<`、`=======`、`>>>>>>>` 冲突标记。
5. 验证代码还能运行。
6. 对每个已解决文件执行 `git add`。
7. 完成合并提交，再 push。

例如冲突文件是 `app.py`，解决并验证后：

```sh
git add app.py
git status
git commit -m "Resolve merge conflict with develop"
git push
```

文件名按实际冲突文件替换。不要为了让标记消失就对所有文件一律选择 Accept Current 或 Accept Incoming。

### 12.3 发现自己暂时无法正确解决

如果本次合并前工作区是干净的，而且当前还处于这次 merge 冲突中，可以取消这次合并：

```sh
git merge --abort
```

随后检查 `git status`，与队友确认后重新同步。开始 merge 前先提交或保存原有修改，可以减少取消合并时恢复工作区的困难。参见 [git-merge 官方文档](https://git-scm.com/docs/git-merge)。

---

## 13. 工作没做完，但现在需要同步或切分支

### 13.1 用 stash 临时收好修改

```sh
git stash push -u -m "WIP before syncing develop"
git status
```

`-u` 包括尚未跟踪的新文件，但不包括被忽略的 `.env` 等文件。stash 只保存在这台电脑，不会因 push 自动上传到 GitHub。

完成同步并回到原来的工作分支后：

```sh
git stash list
git stash apply 'stash@{0}'
git status
```

这里的 `stash@{0}` 指最新一条 stash；先看列表，确认它就是自己要恢复的那一条。引号能避免 PowerShell 对花括号的误解。

`apply` 恢复修改，但仍保留 stash 备份。确认恢复完整、没有冲突，而且没有另外新增 stash 改变编号后，再删除对应那一条：

```sh
git stash drop 'stash@{0}'
```

如果恢复时也发生冲突，先解决冲突，保留 stash，暂时不要 drop。具体行为见 [git-stash 官方文档](https://git-scm.com/docs/git-stash)。

### 13.2 更适合交给队友看的半成品

如果代码虽然未完成，但需要让队友查看或接手，可以在自己的任务分支提交并 push，开 Draft PR，明确写清什么能用、什么未完成。stash 不适合跨电脑或团队交接。

---

## 14. 常用撤销：先确定要撤销哪一层

### 14.1 只是误加入暂存区，想保留文件修改

```sh
git restore --staged app.py
```

这会取消对 `app.py` 的暂存选择，工作文件中的修改仍在。

### 14.2 想放弃某个文件未暂存的本地修改

先查看差异；确定这些未提交内容不再需要时，才运行第二条：

```sh
git diff -- app.py
git restore -- app.py
```

第二条会用暂存区的版本覆盖工作文件中的对应修改，未保留的编辑会丢失。`restore --staged` 和普通 `restore` 修改的对象不同。参见 [git-restore 官方文档](https://git-scm.com/docs/git-restore)。

### 14.3 已提交并 push 的错误

团队共享历史中，通常用一个新的修复提交，或由负责人用 `git revert` 撤销指定提交。不要为了撤销而覆盖队友已经拉取的历史。

新手不要把 `git reset --hard`、`git clean -fd`、`git push --force` 当作通用报错修复方法。这些操作可能丢弃本地文件或改写共享历史。

---

## 15. 常见报错：看到什么，先做什么

| 提示 / 现象 | 常见原因 | 先怎么做 |
| --- | --- | --- |
| `git` 无法识别 | Git 未安装或终端还没更新 PATH | 安装 Git，重新打开终端 / Kiro，再看 `git --version` |
| `Repository not found` / 404 | URL 不对、账号不对或尚无私有仓库权限 | 打开仓库网页确认账号、邀请和 URL |
| `Permission denied` / 403 | 本机认证账号无写权限 | 确认本人权限和 Git 登录账号，不要借用队友 token |
| `not a git repository` | 当前目录不在 clone 的仓库里 | 进入正确项目；用 `git rev-parse --show-toplevel` 检查 |
| `destination path ... already exists` | 已存在同名文件夹 | 检查是否已有 clone，进入它；需要另一份时改用明确的新目录名 |
| `branch ... already exists` | 本地分支已经创建 | 用 `git switch 分支名`，不要再 `switch -c` |
| `invalid reference` / 找不到远程分支 | 没 fetch、拼错名字或该分支不存在 | `git fetch origin`，再 `git branch -r` |
| `Your local changes ... would be overwritten` | 未提交修改与切换 / 同步重叠 | 先 commit 或 stash，再重试 |
| `nothing to commit` | 没有待提交差异，或文件还没 add | 查看 `git status`；确认改在当前仓库而非另一个文件夹 |
| `no upstream branch` | 新分支没有远程跟踪关系 | 当前就是前端分支时，运行 `git push -u origin feature/frontend`；其他分支换成自己的名字 |
| `non-fast-forward` / push rejected | 远程分支有本地没有的提交 | 看下面的处理步骤，不要 force push |
| `Not possible to fast-forward` | 本地和远程分支都有独立提交 | 看下面的处理步骤，合并远程自己的分支 |
| `ModuleNotFoundError` | 环境不对、依赖没安装或不在正确分支 | 查看 `sys.executable`、分支和 `requirements.txt` |
| `rd/` 文件夹不见了 | 当前分支还没包含 starter | 看第 2.3 和 6.3 节，检查分支内容 |
| `ExpiredToken` | 比赛临时 AWS 凭证过期 | 从比赛环境刷新本人凭证，再验证；不是重新 clone 仓库 |
| `AccessDenied` | AWS 账号、区域、资源或权限配置有问题 | 给 AWS 负责人看不含密钥的错误码和操作名称 |

### push 被拒绝 / 分支发生分叉时

先确认自己在正确分支、没有未提交修改。以前端分支为例：

```sh
git status
git branch --show-current
git fetch origin
git merge --no-edit origin/feature/frontend
```

这把远程**同一个工作分支**的新提交整合到本地。出现冲突就按第 12 节处理；验证后再 `git push`。

不要直接复制 `feature/frontend` 去修复别的分支；同步来源必须与你当前使用的工作分支一致。远程自己的分支与团队的 `develop` 是两个不同的同步来源。

---

## 16. 我们项目的额外约定：数据、AWS、Kiro

### 16.1 哪些东西进入 GitHub

| 内容 | 是否提交 | 说明 |
| --- | --- | --- |
| Python 代码、界面、测试 | 是 | 与任务一起提交 |
| `requirements.txt`、非秘密配置模板 | 是 | 让队友能复现环境 |
| 数据字段说明、查询口径、演示脚本 | 是 | 放在文档中并同步更新 |
| 已导入并被跟踪的清洗数据 | 按团队决定维护 | 当前 starter 数据已在 `feature/data`；修改数据时说明来源、生成步骤和变化 |
| 原始私有数据、新的数据导出 | 先确认共享范围 | 使用获准的存储位置，不随手加入 Git |
| `.env`、AWS 临时密钥、session token、GitHub token | 否 | 每人本机配置 |
| Conda 环境、`.venv`、缓存 | 否 | 每个人本机安装 |
| 本地 `runtime/` 案件状态、临时日志 | 否 | 本地运行产物 |

当前 `.gitignore` 已包含 `.env`、`.aws/`、`.venv/`、`runtime/`、`data/raw/` 等规则。**`.gitignore` 不会自动把已经跟踪的文件从历史中移除。** 如果凭证已经提交，先停止分享并让凭证持有人撤销 / 轮换，再由负责人按 [GitHub 敏感数据处理指南](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) 处理。

大数据集更新不要反复通过 Git 上传完整副本；团队可使用获准的 S3 存储，并在仓库保留数据路径、版本与生成说明。当前已跟踪的 starter 数据在没有团队迁移决定前保持现有使用方式。

### 16.2 GitHub 和 AWS 怎样一起工作

```text
GitHub：保存代码、分支和 PR
    ↓ clone / pull
每个人的电脑：Kiro + Conda + 项目代码
    ↓ 使用自己的有效 AWS 凭证调用
AWS：Bedrock / S3 / DynamoDB / Lambda 等资源
```

- clone / pull 不会给你复制队友的 Conda 环境或 AWS 登录状态。
- Kiro 的账号登录、本机 GitHub 认证和项目调用 AWS 的凭证需要分别确认。
- 比赛临时凭证一般包括 Access Key、Secret Key、Session Token，并会过期；按主办方方式在本机配置，不填进代码、PR、截图或群消息。
- 共享的是代码、资源名称、区域约定和数据契约；每个人使用本人获准的凭证。
- 凭证与权限准备好后，可运行项目的 AWS 检查入口：

```sh
python scripts/check_aws.py
```

此检查会验证 AWS 身份并发起一次小的 Bedrock 调用；要有有效凭证、可用区域及 `RD_MODEL_ID`。本文没有替任何队友验证实时 AWS 连通性。临时凭证环境变量说明见 [AWS 官方文档](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html)。

### 16.3 使用 Kiro AI 修改代码时

给 Kiro 的任务至少包含：

```text
当前任务：让调查页展示证据表。
当前分支：feature/frontend。
主要修改范围：app.py。
如果需要改变共享工具接口，先说明原因。
完成后给出改动清单、验证方式和实际结果。
```

这些是给队友使用的示例提示词，不会因为出现在文档中就自动执行。

AI 修改完成后，仍要自己看 `git diff`、运行相关检查、确认没有改错文件，再 commit / push。不要把“编辑器说完成”直接等同于“团队项目已验证可运行”。

---

## 17. 每天可以照着看的速查卡

> 以下假设你已经建立了本地分支与 upstream，并且使用的是 `feature/frontend`。其他成员把分支名换成自己的；任何一步报错先处理再继续。

### 开工前：工作区先保持干净

```sh
git status
git switch feature/frontend
git fetch origin
git pull --ff-only
git merge --no-edit origin/develop
```

### 做完一项改动后：以前端文件为例

```sh
git diff
python -m unittest discover -s tests -v
git add app.py
git diff --cached
git commit -m "Describe the specific change"
git push
```

提交说明改成实际内容；文件名和验证命令也要与实际任务匹配。

### 交付给团队

```text
GitHub → Pull requests → New pull request
base：develop
compare：自己的工作分支
写改动与验证结果 → 请队友检查 → 合并
```

### 最常用的查看命令

| 想知道什么 | 命令 |
| --- | --- |
| 当前在哪个项目目录 | `git rev-parse --show-toplevel` |
| 当前分支 | `git branch --show-current` |
| 哪些文件改了 | `git status` |
| 尚未暂存的具体差异 | `git diff` |
| 已暂存、下次 commit 会包含什么 | `git diff --cached` |
| 分支和跟踪关系 | `git branch -vv` |
| 远程分支列表 | `git branch -r` |
| 最近五次提交 | `git log --oneline -5` |
| 连接哪个 GitHub 仓库 | `git remote -v` |

如果 `git diff` 或 `git log` 进入分页界面，按 `q` 返回终端。

---

## 18. 团队开工前统一这五件事

1. 每个工作分支当前由谁主要维护。
2. 今天每个人要交付的具体功能和验收方式。
3. 统一 rd 包与前端之间的接口和数据字段。
4. 哪位队友负责审核 PR，哪位负责最终集成。
5. 演示使用哪一个经过验证的 main 提交，以及 AWS 区域和资源配置。

**记住一句话：在自己的分支做改动，commit 记录，push 分享，PR 审核后合入 develop，验证后再进入 main。**

---

## 官方参考

本指南中的团队分工、分支命名和审核约定来自本项目；Git / GitHub / Conda / AWS 的通用操作参考：

- [GitHub：安装和设置 Git](https://docs.github.com/en/get-started/git-basics/set-up-git)
- [Git：Windows 安装](https://git-scm.com/install/windows)
- [GitHub：HTTPS 身份验证与重复凭证提示](https://docs.github.com/en/get-started/git-basics/why-is-git-always-asking-for-my-credentials)
- [GitHub：创建 PR](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request)
- [GitHub：合并 PR](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request)
- [Git：配置](https://git-scm.com/docs/git-config)、[切换分支](https://git-scm.com/docs/git-switch)、[拉取](https://git-scm.com/docs/git-pull)、[推送](https://git-scm.com/docs/git-push)、[合并](https://git-scm.com/docs/git-merge)、[临时保存](https://git-scm.com/docs/git-stash)、[恢复文件](https://git-scm.com/docs/git-restore)
- [Conda：管理环境](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
- [AWS：凭证和环境变量](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html)
- [GitHub：处理已经提交的敏感数据](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
