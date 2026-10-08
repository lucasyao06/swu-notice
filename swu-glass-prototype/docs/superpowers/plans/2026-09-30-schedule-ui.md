# 日程 UI 实施计划

**Goal:** 根据用户原型重做日程界面，补齐轻柔交互动效。
**Architecture:** CalendarPage 管理布局与筛选，ScheduleWeek 管理时间格，ScheduleEditor 管理浮层；Dock 独立管理指针反馈。保留仓库和业务 Hook。
**Tech Stack:** React、CSS、lucide-react、Web Animations API。

- [x] 调整侧栏、日期工具栏、星期/全天/小时格、图标和彩色日程块。
- [x] 重排编辑器为完成状态、标题、日期/时间、提醒/地点/分类、时间安排、备注和子任务；保留原字段与提交验证。
- [x] 新增 Dock 距离放大，测试中央最大值、相邻对称、范围外归零；尊重 quiet 与触摸设备。
- [x] 新增日程悬停与浮层进出，降低背景光强度和频率。
- [x] 验证构建、数据测试、日程浏览器回归及桌面/手机/夜间截图；同步对应 Git 仓库文件。

验收：正式仓库构建通过；19 项数据单测、4 项打包测试通过；schedule-redesign、schedule-selection、schedule-basics、calendar-integration 四组浏览器回归通过。截图保存在 docs/schedule-redesign-{desktop,night,mobile}.png。浏览器测试只使用演示会话或临时数据库。
