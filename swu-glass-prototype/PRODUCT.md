# 西南大学通知与日程工作台

## Register
Product: a task-focused application, not a marketing site.

## Users and purpose
Students and staff browse campus notices, manage subscriptions and arrange their schedules. The schedule is a dedicated full-viewport workspace with weekly, monthly and list views.

## Design principles
- Follow the user's supplied schedule reference and the accepted constraints in AGENTS.md.
- Keep controls compact, aligned and stable as views and filters change.
- Give content the available viewport space; the auto-hidden Dock is an overlay.
- Use readable pale surfaces by day and neutral black/charcoal surfaces at night.
- Preserve data, dates, view preferences and scroll position during navigation.
- Keep motion gentle and respect reduced-motion and the motion-off preference.

## Existing implementation
React/Vite frontend, Python JSON API and SQLite persistence. Data adapters, repositories and hooks form the boundary between presentation and backend. Demo data is isolated from live data.

## Avoid
Blue-tinted dark surfaces, excessive bottom whitespace, shifting toolbars, misaligned panels, and implementation details in product-facing copy.
