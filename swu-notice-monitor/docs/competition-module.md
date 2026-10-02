# 独立赛事通知模块

入口为主导航“赛事”，本地直达地址为 `http://127.0.0.1:5180/?view=competitions`。目录种子为 `data/competitions.json`，覆盖截图44项具名赛事及拆分赛道，不包含笼统的“其他比赛”。六个中国高校计算机大赛赛道保留所属赛事，三项机器人赛事独立登记。

## 数据与采集

在校园SQLite中增量创建 competitions、competition_sources、competition_notices、competition_subscriptions、competition_messages、competition_settings、competition_crawl_state。仅复用数据库连接与锁，不读取或写入校园通知、订阅、消息及任务状态。

公告唯一键为赛事ID与规范化官网URL。重复采集更新元信息，保留收藏、阅读及已验证日期。已读公告同步标记其赛事消息已读；单独标记消息已读仅改变消息状态。

每来源保存初始基线、访问队列、已访问链接和错误。完整首次回填结束后建立更新基线，后续新增公告仅在该赛事被关注时生成一条独立消息。首次回填、重复采集、重新关注均不会补推历史消息。失败不会建立基线，已获得的数据仍可查看。

默认300分钟定时采集；手动采集与定时采集共用赛事任务锁。最多两个采集工作线程，同一请求主机串行访问。采用固定官方主机白名单、公开DNS校验、robots.txt、TLS验证、15秒超时、有限重试、1.5MB响应限制、分批检查点与最多1000页安全上限。停止保留队列，手动再次采集或未完成任务重启后继续。关闭后端时保留恢复标记。页面每5秒查看运行中进度，空闲时每60秒刷新。

HTML采集公告链接、可靠发布日期和详情附件；公开JSON支持实际官网字段映射、原文URL模板与分页；RSS及JSON-LD也可解析。发布日期不使用比赛年份、比赛日期或采集时间推断。英文time标签必须有出版日期上下文；附件公告保留链接，不虚构文件发布日期。过旧的可靠日期公告不进入最近一年列表；无法验证日期的公告明确标注待核验。

每个来源状态和局限见 [实际来源核验清单](competition-sources.md)。状态“正常”代表识别到官方参赛公告；“解析受限”代表公开页面无法提取有效公告；“失败”保留实际访问错误；无核验来源的条目为“待核验”。

## 接口

所有端点位于 `/api/competition/`，返回JSON。修改沿用后端已有Origin策略。列表支持 `limit=1..100`、`offset>=0`，默认10条；total是完整筛选后的数量。

| 方法 | 路径 | 参数或请求体 | 结果 |
| --- | --- | --- | --- |
| GET | catalog | q、group | items、total、policy、kinds |
| GET | catalog/:id | 赛事ID | 赛事、分值、官网、来源核验依据与状态 |
| GET | notices | q、competition、kind、tab=all/following/favorite/unread、limit、offset | items、total |
| GET | notices/:id | 通知ID | 标题、类型、日期、原文、附件、采集时间、read、favorite |
| PATCH | notices/:id | read及/或favorite布尔值 | 更新后的通知 |
| GET / PUT | subscriptions | PUT传competitions赛事ID数组 | competitions |
| GET | messages | limit、offset | items、total、unread |
| PATCH | messages/:id | read=true | ok |
| PATCH | messages | read=true | 全部赛事消息已读 |
| GET / PUT | settings | interval_minutes=5..1440、scheduler_enabled布尔值 | 保存设置 |
| GET | crawl | 无 | running、completed、total、results、last_finished |
| POST | crawl | 可选competition_id | 启动全部配置来源或单场赛事，任务冲突409 |
| POST | crawl/stop | 空对象 | 停止并保存进度 |

错误使用 `{error:string}`，参数错误400、不存在404、任务冲突409。赛事演示仓库仅在前端内存运行，不调用真实赛事修改接口。

## 本地验证

后端：`python -m unittest discover -s tests -v`。比赛测试包含44项及全部奖项分值、HTML/JSON/RSS/英文/附件解析、日期真实性、首次基线、消息去重、关注变化、持久化、失败与中断恢复、分页及校园隔离。

前端：`npm run test:data`、`npm run test:sites`、`npm run build`。

浏览器：先准备Playwright及本地浏览器，设置 `PYTHON_PATH` 和 `CHROME_PATH` 后运行 `node tests/competitions-browser.cjs`，原校园联调检查为 `node tests/backend-integration.cjs`。两个测试均使用临时数据库及独立端口，测试赛事不写入真实记录。赛事检查覆盖目录与分值、分页搜索、关注收藏阅读持久化、消息隔离、错误恢复、演示切换、1440/390/320像素布局及夜间主题。

本机2026-10-02检查：后端88项中87通过，1项POSIX信号测试因Windows跳过；前端13项数据测试、4项静态服务测试通过；赛事和原校园浏览器联调均通过；生产构建通过。Docker文件已同步种子目录结构，本次未执行容器构建。
