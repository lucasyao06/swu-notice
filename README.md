# 西南大学通知聚合平台

多人开发的分支、PR、检查与版本发布约定见 [协作开发指南](CONTRIBUTING.md)。

前后端分离的校园通知聚合系统。React 前端通过 HTTP API 访问 Python 后端，支持通知检索、来源筛选、订阅、收藏、阅读状态、定时采集和随系统时间变化的昼夜主题。

## 目录

- `swu-glass-prototype/`：目前使用的 React 前端，包含源码、校园资源、npm 依赖锁文件和测试。
- `swu-notice-monitor/backend/`：Python API、采集器和 SQLite 数据层（仅使用 Python 标准库）。
- `swu-notice-monitor/data/sites.json`：89 个网站的初始化目录，不是采集缓存。
- `deploy/`、`compose.yaml`：新版前端和后端的 Docker 部署配置。

## 本地启动

需要 Python 3.10+、Node.js 22+ 和 npm。

先在仓库根目录启动后端：

```sh
python3 swu-notice-monitor/start.py
```

另开终端，启动新版前端：

```sh
cd swu-glass-prototype
npm ci
npm run dev -- --host 127.0.0.1 --port 5180 --strictPort
```

- 新版前端：http://127.0.0.1:5180
- 后端 API：http://127.0.0.1:8765/api
- 无后端体验：http://127.0.0.1:5180/?mode=demo

首次运行会自动创建新的数据库。真实通知初始为空，代码内的示例数据与真实数据隔离。原电脑的通知、收藏、订阅、已读记录、采集进度和浏览器偏好均未包含在此仓库。

### 独立赛事通知

打开 [赛事模块](http://127.0.0.1:5180/?view=competitions)，或使用主导航“赛事”。模块提供44项具名赛事与赛道的目录、官网通知、关注、收藏、独立消息中心和采集设置。分值来自截图，仅作参考，适用学院及学年尚未确认；空白、零分、MCM/ICM奖项和特殊限制分别保留，不计算个人综测。

赛事使用现有SQLite内的独立表及 `/api/competition/` API，不影响校园订阅、消息数量或采集状态。关注和阅读状态沿用共享单用户模式。赛事演示数据仅存在浏览器内存中，可通过 `?view=competitions&mode=demo` 体验。

后端首次启动自动增量建表并开启赛事每300分钟采集，最多两个请求任务，同一官网串行，遵守robots.txt。首次365天回填建立基线后才为关注赛事生成新公告消息；取消关注保留旧消息，重新关注不补推。手动采集、停止保存进度和定时开关位于赛事“采集设置”。无可靠日期显示“发布时间待核验”，受限来源显示原因。

完整来源和本机实际接入结果见 [赛事官方来源清单](swu-notice-monitor/docs/competition-sources.md)，接口和验收细节见 [赛事开发说明](swu-notice-monitor/docs/competition-module.md)。待核验和访问失败的赛事保留目录，后续可逐项补充官网适配。

### 自动采集

干净安装不会继承原数据库的定时设置。可通过 API 启用网站，并启用 **300 分钟（5 小时）** 的定时采集。后端需持续运行。

在本地 API 启动后执行以下命令。第一条启用目录内全部网站，第二条开启定时采集：

```sh
curl -X PATCH http://127.0.0.1:8765/api/sites \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true}'

curl -X PUT http://127.0.0.1:8765/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"interval_minutes":300,"scheduler_enabled":true}'
```

## 构建与测试

```sh
cd swu-glass-prototype
npm run test:data
npm run build
```

前端输出到 `dist/client`，生产环境需要同源 `/api` 反向代理。Python 测试位于 `swu-notice-monitor/tests`，前端浏览器测试位于 `swu-glass-prototype/tests`。浏览器测试需自行安装 Playwright，并按测试要求提供浏览器或 `CHROME_PATH`。联调测试使用临时数据库。

## Docker

在仓库根目录执行：

```sh
docker compose up -d --build
```

打开 http://127.0.0.1:8080 。数据库存储在命名卷中，容器重建不会删除数据库。根目录 Compose 提供新版前端；采集配置可通过后端 API 设置。若使用自己的域名，设置 `SWU_ALLOWED_ORIGINS` 为该域名完整 Origin。

当前后端为单用户模型，尚无账号隔离。默认端口仅绑定本机，公网部署需自行配置认证和 HTTPS。Docker 配置随源码提供，导出时未执行容器构建。

## GitHub 上传范围

此文件夹不包含采集数据库及备份、运行缓存、日志、`node_modules`、构建输出、测试截图或历史运行报告。`.gitignore` 已排除它们；只需把本文件夹作为仓库根目录上传，无需复制原项目其他目录。

依赖版本由 `package-lock.json` 锁定，首次安装需要联网。前端运行资源由本地服务提供，不依赖 CDN。

校园图片、校徽和第三方代码的说明位于各 `assets` 目录。未替这些素材或整个项目擅自指定开源许可证；发布时请保留已有版权说明。

## 赛事的学院选择

“赛事”页面现在支持计算机与信息科学学院与法学院，默认计信并记住浏览器选择。目录与普通官网公告按学院筛选，可选择全部59项；关注、收藏和消息跨学院保留。各学院分值独立，未列名赛事明确提示分值待确认，创新创业25／20分的截图冲突保留待确认。

配置文件为 `swu-notice-monitor/data/college_competition_rules.json`；后续增加学院只需新增配置及赛事关联。完整说明与本机官方入口、分级规则、采集状态清单见 [赛事模块说明](swu-notice-monitor/docs/competition-module.md) 和 [两学院核验清单](swu-notice-monitor/docs/competition-sources.md)。手动采集可按学院，定时仍覆盖全平台，不受页面学院选择影响。
