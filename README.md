# 西南大学通知聚合平台

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
