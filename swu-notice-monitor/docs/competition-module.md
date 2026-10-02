# 独立赛事通知模块

入口为主导航“赛事”，本地直达地址为 `http://127.0.0.1:5180/?view=competitions`。目录种子为 `data/competitions.json`，覆盖计信学院44项、法学院17项；共用创新大赛和课外学术挑战杯后，全平台59项（新增15项）具名赛事及拆分赛道，不包含笼统的“其他比赛”。六个中国高校计算机大赛赛道保留所属赛事，三项机器人赛事独立登记。

## 数据与采集

在校园SQLite中新增 competition_colleges、competition_college_rules 两张关联表，原有赛事及数据ID不变。既有独立表为 competitions、competition_sources、competition_notices、competition_subscriptions、competition_messages、competition_settings、competition_crawl_state。仅复用数据库连接与锁，不读取或写入校园通知、订阅、消息及任务状态。

公告唯一键为赛事ID与规范化官网URL。重复采集更新元信息，保留收藏、阅读及已验证日期。已读公告同步标记其赛事消息已读；单独标记消息已读仅改变消息状态。

每来源保存初始基线、访问队列、已访问链接和错误。完整首次回填结束后建立更新基线，后续新增公告仅在该赛事被关注时生成一条独立消息。首次回填、重复采集、重新关注均不会补推历史消息。失败不会建立基线，已获得的数据仍可查看。

默认300分钟定时采集；手动采集与定时采集共用赛事任务锁。最多两个采集工作线程，同一请求主机串行访问。采用固定官方主机白名单、公开DNS校验、robots.txt、TLS验证、15秒超时、有限重试、1.5MB响应限制、分批检查点与最多1000页安全上限。停止保留队列，手动再次采集或未完成任务重启后继续。关闭后端时保留恢复标记。页面每5秒查看运行中进度，空闲时每60秒刷新。

HTML采集公告链接、可靠发布日期和详情附件；公开JSON支持实际官网字段映射、原文URL模板与分页；RSS及JSON-LD也可解析。发布日期不使用比赛年份、比赛日期或采集时间推断。英文time标签必须有出版日期上下文；附件公告保留链接，不虚构文件发布日期。过旧的可靠日期公告不进入最近一年列表；无法验证日期的公告明确标注待核验。

每个来源状态和局限见 [实际来源核验清单](competition-sources.md)。状态“正常”代表识别到官方参赛公告；“解析受限”代表公开页面无法提取有效公告；“失败”保留实际访问错误；无核验来源的条目为“待核验”。

## 学院选择与参考规则

学院及关联规则种子为 `data/college_competition_rules.json`。赛事身份、官网和公告继续共用 `data/competitions.json`；仅评分规则按学院存储。每项 `reference_rules` 含截图名称、类别、列名级别、逐级奖项分值、附注及冲突。计信原44项分值、MCM/ICM字母奖项、显式0与空白均保留。法学院专业技能六级、学术科技四级独立展示；未列明奖项不造分。页面默认显示截图列名级别，详情显示该类别分级标准，并提示其他层级需学院认定。

默认计算机与信息科学学院，浏览器通过 `swu-glass:competition-college` 记忆选择；刷新或切换真实/演示模式后恢复。普通目录及官网公告默认按学院查看，可切换“查看全部赛事”。类别选项由学院配置提供；切换学院清空筛选与分页、关闭详情、取消旧列表及详情请求，并丢弃过期响应。

我的关注、我的收藏、消息均为全平台记录。跨学院条目返回空规则并提示“当前学院截图未列名，分值认定待确认”，不直接沿用另一学院分值；选择学院不会删除关注或个人状态。取消关注停止新提醒，重新关注不补历史。消息未读数不随学院变化。

法学院“互联网＋”关联既有创新大赛；创业计划挑战杯与课外学术作品挑战杯为两个ID。“含弘杯”仅收学术作品，排除创新创业及创业计划赛。两个创新创业赛事引用学术挑战杯分级标准，正文25分与附注20分的上限冲突原样保留并标注待确认。团队贡献比例、不累计与层级认定、证明材料要求列在详情中。不开发证书、论文、专利、科研项目或个人综测计算。

## 接口

所有端点位于 `/api/competition/`，返回JSON。修改沿用后端已有Origin策略。列表支持 `limit=1..100`、`offset>=0`，默认10条；total是完整筛选后的数量。

| 方法 | 路径 | 参数或请求体 | 结果 |
| --- | --- | --- | --- |
| GET | colleges | 无 | items、default_college；学院名称、类别、政策说明 |
| GET | catalog | q、group、college、scope=college/all、category | items、total、policy、kinds |
| GET | catalog/:id | 赛事ID、college | 赛事、分值、官网、来源核验依据与状态 |
| GET | notices | q、competition、kind、tab=all/following/favorite/unread、limit、offset、college、scope、category | items、total |
| GET | notices/:id | 通知ID、college | 标题、类型、日期、原文、附件、采集时间、read、favorite |
| PATCH | notices/:id | read及/或favorite布尔值；college查询参数 | 更新后的通知 |
| GET / PUT | subscriptions | PUT传competitions赛事ID数组 | competitions |
| GET | messages | limit、offset、college（只影响规则上下文） | items、total、unread |
| PATCH | messages/:id | read=true | ok |
| PATCH | messages | read=true | 全部赛事消息已读 |
| GET / PUT | settings | interval_minutes=5..1440、scheduler_enabled布尔值 | 保存设置 |
| GET | crawl | 无 | running、completed、total、results、last_finished |
| POST | crawl | 可选competition_id、college_id | 空体全平台，学院选择其列名赛事来源，单赛事仍可用，任务冲突409 |
| POST | crawl/stop | 空对象 | 停止并保存进度 |

错误使用 `{error:string}`，参数错误400、不存在404、任务冲突409。赛事演示仓库仅在前端内存运行，不调用真实赛事修改接口。

## 本地验证

后端：`python -m unittest discover -s tests -v`。比赛测试包含两学院44／17项及合并59项、分级分值、规则冲突、完整旧库迁移与改规则不重置基线、共享公告与消息去重、学院手动与全平台定时隔离，以及全部奖项分值、HTML/JSON/RSS/英文/附件解析、日期真实性、首次基线、消息去重、关注变化、持久化、失败与中断恢复、分页及校园隔离。

前端：`npm run test:data`、`npm run test:sites`、`npm run build`。

浏览器：先准备Playwright及本地浏览器，设置 `PYTHON_PATH` 和 `CHROME_PATH` 后运行 `node tests/competitions-browser.cjs`，原校园联调检查为 `node tests/backend-integration.cjs`。两个测试均使用临时数据库及独立端口，测试赛事不写入真实记录。赛事检查覆盖学院切换、刷新记忆、59项范围及类别、延迟响应隔离、跨学院个人记录、目录与分值、分页搜索、关注收藏阅读持久化、消息隔离、错误恢复、演示切换、1440/390/320像素布局及夜间主题。

本机2026-10-02检查：后端100项中99通过，1项POSIX信号测试因Windows跳过；前端15项数据测试、4项静态服务测试通过；赛事和原校园浏览器联调均通过；生产构建通过。Docker文件已同步种子目录结构，本次未执行容器构建。

## 本机交付与后续扩展

更新前备份为本机未跟踪的 `data/before-colleges.sqlite3`。在备份副本上逐表逐字段核验：所有校园数据、旧44项赛事及25个来源、个人状态、消息、基线和断点保持一致；新增仅为15项赛事、7个已核验来源配置以及学院和规则关联。真实服务已更新至 localhost:8765，前端继续 localhost:5180。法学院9项配置了来源（含两项共享赛事），其他8项逐项列明身份或入口待核验原因。

已逐个在本机采集新来源，实采结果见 `competition-sources.md`；正常且0条说明可解析但当前365天范围未获得公告，不等同于赛事从未发布。失败和解析受限保留明确原因。本次未执行容器构建；Docker的两个种子文件已同步。

增加学院时只添加学院配置及已有赛事ID的规则关联；新赛事另登记全平台目录。学院规则修改不会改变来源配置，也不会清空采集基线。只有采集入口或解析配置改变才重建对应来源的更新基线。新学院没有账号隔离，沿用共享单用户模式。

所有阶段提交保留在本地 `codex/competition-notices`；未推送远端、未创建PR。
