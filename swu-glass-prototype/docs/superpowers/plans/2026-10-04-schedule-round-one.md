# 日程第一轮调整

用户已确认上一轮提出的方案并要求实施。

**Goal:** 改善查看当天、连续录入、调整任务属性与完成反馈。
**Architecture:** CalendarPage 管理范围、日期和反馈；ScheduleWeek 复用单日/七日时间格；ScheduleQuickAdd 管理录入草稿；ScheduleEditor 展示属性；数据仍经 calendarRepository/useCalendarData 写入。
**Tech Stack:** React、CSS、lucide-react、现有 Python API/SQLite。

## 约束

- 手机 <=600px 首次进入日视图，桌面保持周视图；手动切换和浏览位置不被定时刷新覆盖。
- 快速录入：今天范围默认今天；收集箱、未安排、全部及自定义清单默认无日期；保留当前清单及分类。
- 日期、清单、优先级、提醒和重复直接可见。时间折叠区仅含全天、开始和结束时间。
- 月视图仅保留全局搜索；无任务提供添加，无匹配提供清除筛选。
- 支持时间块直接完成和重复后继日期反馈；不改变既有重复生成规则。
- 提醒明确实际提醒时间和网页打开时提醒的行为，不增加后台推送。
- 保留固定工具栏、日夜主题、减少动态效果、Dock、范围返回和拖拽/缩放。
- 所有测试写入隔离数据库；不迁移或修改用户的真实数据。

## 实施及验收

- [x] 新增 tests/unit/schedule-round-one.test.mjs、tests/schedule-round-one.cjs；运行并确认缺失功能导致失败。
- [x] src/data/schedule.js 增加 quickTaskDefaults、shiftDate、reminderDateTime、formatReminderTime；实现上下文与时间计算。
- [x] src/pages/ScheduleQuickAdd.jsx 新增连续录入、快捷日期、失败保留和焦点恢复。
- [x] CalendarPage.jsx 和 ScheduleWeek.jsx 实现日视图、手机当天横向定位和直接完成；保留时间格拖拽/缩放。
- [x] ScheduleEditor.jsx 展开常用属性，独立提醒及重复；ScheduleList.jsx/CalendarPage.jsx 完善空状态并移除重复搜索。
- [x] ScheduleReminder.jsx 和 App.jsx 展示提醒时间、打开任务、确认失败反馈及重复完成提示。
- [x] calendar.css 统一分类颜色、优先级标记、可读文字和响应式布局；更新 AGENTS.md。
- [x] npm run test:data 与 npm run build；新浏览器回归、schedule-navigation、schedule-selection、schedule-basics、calendar-integration、schedule-toolbar。
- [x] 检查桌面/手机、日间/夜间截图、页面无溢出、工具栏稳定，git diff --check。

浏览器命令使用 PLAYWRIGHT_PATH 和 CHROME_PATH 指向已安装运行库与 Chrome。日程行为测试使用 tests/fixture_backend.py 的临时数据库与 5181/8876 测试端口，正常预览保持 5180。

## 验证记录

- 新增单元测试先确认缺失导出导致失败；日期上下文及触屏边界均通过浏览器回归复现后修复。
- 前端 22 项单元测试通过，生产构建成功。
- 浏览器 6 组通过：schedule-round-one、schedule-navigation、schedule-selection、schedule-basics、calendar-integration、schedule-toolbar。
- 第一轮回归覆盖 5 个宽度 × 2 种主题 × 4 个视图、真实触摸滚动/选择/轻点、周日及选择工具可达性、连续录入/失败重试、日期上下文、完成回退与实际提醒时间。
- 独立代码审查发现并修复今天新建日期、范围切换快捷日期、平板滚动及手机周视图工具可见性问题。
- 手机时间格默认滑动浏览与轻点新增，通过“选择时段”明确进入拖选，完成选择后恢复浏览。
- 截图存于 docs/superpowers/screenshots/2026-10-04-schedule-round-one，使用隔离测试数据；未写入用户真实数据库。
- git diff --check 通过。
