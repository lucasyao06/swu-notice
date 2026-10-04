# 协作开发指南

## 仓库边界

仓库根目录应包含 `README.md`、`compose.yaml`、`swu-glass-prototype/` 和 `swu-notice-monitor/`。
开发前执行 `git rev-parse --show-toplevel`，确认结果为本项目的源码目录。如果显示 `E:/` 等上层目录，先修正仓库边界，不要在上层仓库执行 add、commit 或 push。

已有共享仓库时，优先把它 clone 到独立目录，保留原有历史，再迁移尚未提交的源码修改。没有共享仓库时，在上述源码目录初始化独立仓库，并以 `main` 为默认分支。

数据库、爬取缓存、日志、依赖、构建输出和 `.env` 不提交。`data/sites.json` 与 `package-lock.json` 必须提交。真实数据通过各自本地采集获得，不把正在使用的 SQLite 文件作为协作文件。

## 日常开发

本项目共享仓库：https://github.com/lucasyao06/swu-notice 。没有直接写入权限时，可以请仓库所有者邀请你的 GitHub 账号成为协作者，或者在 GitHub 上 Fork 后提交 PR。是否出现在 Contributors 列表不等于是否有写入权限。

采用 Fork 时，先创建自己的 Fork，再配置远端（将 `<你的账号>` 替换为实际账号）：

```sh
git remote rename origin upstream
git remote add origin https://github.com/<你的账号>/swu-notice.git
git fetch upstream
git push -u origin <你的功能分支>
```

随后创建从自己 Fork 的功能分支到 `lucasyao06/swu-notice:main` 的 PR。后续同步主分支时，从 `upstream/main` 拉取或合并；本指南下面使用 `origin` 的同步示例适用于拥有共享仓库写入权限的情况。

采用 `main` + 短期功能分支。每个功能或修复使用独立分支，避免两人在同一分支直接推送。

```sh
git switch main
git pull --ff-only origin main
git switch -c feature/notice-filter
# 完成功能后，只暂存本次相关文件
git add <相关文件>
git diff --cached
git commit -m "feat: 添加通知筛选"
git push -u origin feature/notice-filter
```

人工分支可使用 `feature/`、`fix/`、`docs/`；Codex 创建的分支使用 `codex/`。提交信息推荐 `feat:`、`fix:`、`docs:`、`test:`、`chore:` 前缀，一次提交围绕一个目的。

推送后创建 Pull Request，由另一位开发者审查后合并。推荐 squash 合并，让 main 上的每个提交对应一个完整变更。不要强制推送 main；需要整理个人分支历史时，先确认没有其他人在使用该分支，再使用 `--force-with-lease`。

同步主分支时，可在功能分支执行 `git fetch origin` 和 `git merge origin/main`。解决冲突后重新运行相关检查，不直接覆盖对方文件。开始开发前沟通主要修改模块，接口变更同时更新 `swu-notice-monitor/docs/api-contract.md`。

## 合并前检查

后端检查从 `swu-notice-monitor/` 执行：

```sh
python -m unittest discover -s tests -v
```

前端检查从 `swu-glass-prototype/` 执行：

```sh
npm ci
npm run test:data
npm run build
npm run test:sites
```

Python 测试使用临时数据库；不要用个人采集数据库作为测试夹具。进程恢复测试涉及 POSIX 信号语义，统一以 Linux CI 结果为准。浏览器交互变更还需按相关 `tests/*.cjs` 的要求运行 Playwright 检查；基础 CI 不包含浏览器测试和 Docker 构建。

## 共享仓库设置

以下设置需要在托管平台启用，文件本身不会自动开启分支保护：

- main 必须通过 PR 合并，至少一位其他开发者批准。
- 必须通过 CI 的 `frontend`、`backend` 检查后才可合并（GitHub 仓库首次运行 CI 后选择对应检查）。
- 禁止 main 强制推送和删除；新提交后重新审查。

Gitee/GitLab 也可采用同样流程；本项目提供的是 GitHub Actions 配置，其他平台需要使用各自 CI 配置。

## 发布与回退

稳定版本使用 `v0.1.0` 这样的语义版本标签，记录本次功能与部署要求。标签在版本确认后创建并推送，避免移动已发布标签。

回退已共享的变更使用 `git revert <提交号>` 并通过 PR 合并，保留历史。数据库结构变更需保持旧数据可迁移，并单独说明备份与回退办法；回退源码不会回退数据库。
