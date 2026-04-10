# Admin Dashboard Density And Sidebar Tightening Design

## Goal

Reduce wasted above-the-fold space in the admin dashboard, remove repeated status messaging, move the key trend chart into the primary decision area, add explicit action entry points, and tighten the shared sidebar so the main workspace has more horizontal room.

## Problem Statement

The current admin dashboard exposes real data, but the first screen still wastes attention in four ways:

1. The top-left posture headline and the top-right "当前判断" card repeat the same message.
2. The most decision-critical chart, the 7-day request and retrieval-hit trend, is below less important summary cards.
3. States with zero pending work feel empty instead of reassuring.
4. The shared sidebar still occupies more width than the current information density requires.

The result is a dashboard that is factually correct but still less actionable than it should be.

## Design Summary

The page will move from a "headline plus duplicated status card" layout to a single operational alert banner with embedded actions. KPI cards remain, but the trend chart moves directly under them to occupy the primary analysis zone. Pending-work cards gain an explicit healthy empty state when all queues are zero. The shared sidebar becomes narrower and more compact without changing navigation structure.

## Approach Options

### Option A: Lightweight Operational Reflow

Keep the existing data contract and card system, replace the top strip with one alert banner, move the trend chart upward, and tighten the sidebar.

Pros:
- Minimal backend change
- Preserves current component structure
- Directly addresses layout waste and actionability

Cons:
- Still uses the existing card-based dashboard language

### Option B: Full Two-Column Operations Console

Rebuild the page into a persistent two-column console with charts on the left and queues plus activity on the right.

Pros:
- Higher density
- Strong operations feel

Cons:
- Larger CSS and structure churn
- Higher regression risk for responsive behavior

### Recommendation

Use Option A. It resolves the reported issues with less layout risk and keeps the page aligned with the repo's shared shell primitives.

## Information Architecture

### 1. Operational Alert Banner

Replace the current `overview-strip` split layout with a single horizontal banner that contains:

- A tone-driven alert label
- A short headline
- A single supporting sentence
- One or two action buttons derived from the current posture
- The global refresh button

Examples:

- Low retrieval hit rate:
  - Headline: `检测到近 7 天检索命中率偏低`
  - Summary: `建议检查知识资产、失败入库和召回配置。`
  - Actions: `查看知识库质量`, `优化召回配置`
- Pending risk review:
  - Headline: `存在待审风险需要人工处理`
  - Summary: `建议先完成审核，避免积压进入报告流程。`
  - Actions: `查看风险审查`
- Healthy state:
  - Headline: `平台运行平稳`
  - Summary: `当前无明显积压，可继续推进知识治理与模型运维。`
  - Actions: `查看运行证据`

The current right-side "当前判断" box will be removed entirely.

### 2. KPI Row

Keep the four KPI cards but tighten copy and make each note more operational:

- `知识文档`
- `待审风险`
- `启用模型`
- `近 24h 问答`

The cards remain summary markers, not the main explanatory surface.

### 3. Primary Trend Region

Move `近 7 天请求与命中趋势` immediately below the KPI row and make it the visual center of the page. It becomes the first chart an admin sees.

This section should stay wide and visually dominant.

### 4. Secondary Action Region

Below the trend chart, use a two-column section:

- `待处理事项`
- `运行摘要`

`待处理事项` remains queue-oriented.
`运行摘要` becomes a compact operational panel with directional hints and action links rather than repeating the same posture text.

### 5. Supporting Evidence Region

Keep:

- `风险等级分布`
- `文档处理状态`
- `最近活动`
- `运行证据`

These remain below the fold as diagnostic support, not first-screen competitors.

## Interaction Design

### Banner Actions

The alert banner will expose explicit action buttons. These buttons should navigate directly to the most relevant admin destinations using existing routes.

Proposed mapping:

- `查看知识库质量` -> admin knowledge or overview-adjacent knowledge route if present
- `优化召回配置` -> model configuration route
- `查看风险审查` -> risk review route
- `查看运行证据` -> remain on page and scroll to evidence section if a direct route is not appropriate

If a perfect route does not yet exist in navigation config, use the closest current admin route and keep the copy honest.

### Zero-State Handling

If all queue items in `待处理事项` are zero, replace the list with a positive empty state:

- icon-style marker or status accent
- text: `暂无待办事项，系统运行健康。`

If only some items are zero, keep the existing list layout and render all items normally.

### Refresh Behavior

Keep one global refresh action in the top banner. Do not add per-card refresh controls in this iteration.

Reason:
- It keeps the interaction model simple
- The current API already returns a full dashboard snapshot
- It avoids unnecessary partial-loading complexity

## Sidebar Tightening

The shared sidebar will be narrowed from the current width to a smaller compact width, targeting roughly `204px`.

Additional sidebar adjustments:

- Reduce brand area vertical padding
- Slightly tighten group spacing
- Keep labels visible; do not collapse to icon-only
- Preserve current navigation grouping and active-state treatment

This is a density improvement, not a navigation redesign.

## Data And Logic Changes

No backend API changes are required.

Frontend logic additions in `admin-dashboard.js`:

- derive banner tone, title, summary, and CTA list from the current posture and queue values
- derive whether the pending-work section should render a healthy empty state

The existing normalized dashboard payload remains the source of truth.

## Components And Files

### Modify

- `frontend/src/components/OpsDashboard.vue`
  - remove duplicated top-right status card
  - render a single alert-style operational banner
  - move trend chart upward
  - add CTA buttons
  - add healthy empty state for zero pending work

- `frontend/src/lib/admin-dashboard.js`
  - add helper(s) for banner state and pending-work empty state
  - keep chart builders intact

- `frontend/src/components/ui/AppSidebar.vue`
  - keep structure, only accept tighter visual treatment via shared CSS

- `frontend/src/style.css`
  - narrow sidebar tokens
  - tighten sidebar spacing
  - restyle the admin banner and revised section layout as needed

### No Change

- backend dashboard API
- ECharts wrapper component
- navigation data shape unless route mapping for CTA labels needs a small adapter

## Error Handling

Existing error handling remains:

- API fetch failure still shows the error alert
- stale or missing values still normalize to numeric/string fallbacks

New UI logic must degrade safely:

- if banner CTA mapping cannot determine a route, omit that CTA rather than rendering a broken button
- if trend data arrays are empty, existing chart rendering should still show an empty chart container instead of crashing

## Responsive Behavior

Desktop:
- sidebar narrower
- banner actions aligned on the right
- trend chart full width near the top

Tablet and mobile:
- banner stacks vertically
- KPI cards continue wrapping
- sidebar follows the existing responsive behavior already defined in shared styles

No new breakpoint model is required; the implementation should adapt within the current shell system.

## Testing Strategy

Use test-first changes for the new presentation logic.

Add or update frontend tests to cover:

- banner state generation for warning/risk/healthy cases
- CTA generation for the same cases
- pending-work healthy empty-state detection

Then run:

- `cd frontend && npm test`
- `cd frontend && npm run build`

## Acceptance Criteria

The redesign is complete when all of the following are true:

1. The admin dashboard no longer shows duplicated posture text in both the top-left and top-right areas.
2. The top area uses one alert-style status banner with direct action buttons.
3. The 7-day request and hit trend chart appears above the lower diagnostic sections.
4. `待处理事项` shows a healthy empty state when all actionable counts are zero.
5. The sidebar is visibly narrower and the main content gains more width.
6. Existing dashboard data, charts, and error handling still work.
