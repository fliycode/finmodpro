---
name: FinModPro
description: Financial risk-control platform with domain-specific LLMs — dual-mode analyst workspace and admin war room
colors:
  command-blue: "#2457c5"
  command-blue-deep: "#142f70"
  admin-indigo: "#5b6cff"
  navy-ink: "#1e293b"
  warm-white: "#f8f9fb"
  cool-ash: "#e2e6ed"
  muted-steel: "#7d8798"
  near-black: "#0b0f18"
  shell-canvas-light: "#f4f6fa"
  shell-panel-light: "#ffffff"
  shell-line-light: "rgba(22, 32, 51, 0.09)"
  shell-ink-light: "#172033"
  shell-muted-light: "#5f6b7d"
  shell-canvas-dark: "#101827"
  shell-panel-dark: "#182235"
  shell-line-dark: "rgba(157, 173, 196, 0.16)"
  shell-ink-dark: "#eef3fb"
  shell-muted-dark: "#aeb9c9"
  admin-bg: "#0b121a"
  admin-surface: "rgba(12, 17, 24, 0.78)"
  admin-sidebar: "rgba(10, 15, 22, 0.92)"
  signal-teal: "#8dd0d0"
  risk-red: "#c4493d"
  warning-amber: "#b7791f"
  clearance-green: "#21815c"
typography:
  display:
    fontFamily: "DM Sans, Noto Sans SC, sans-serif"
    fontSize: "clamp(2rem, 3.5vw, 2.5rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "DM Sans, Noto Sans SC, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  title:
    fontFamily: "DM Sans, Noto Sans SC, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "PingFang SC, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "PingFang SC, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: "0.02em"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  admin-base: "0.75rem"
  admin-sm: "0.6875rem"
  admin-xs: "0.625rem"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  "2xl": "24px"
  card: "24px"
  card-admin: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  "2xl": "24px"
  "3xl": "28px"
  "4xl": "40px"
components:
  button-primary:
    backgroundColor: "{colors.command-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "10px 24px"
    size: "36px"
  button-primary-hover:
    backgroundColor: "#1d48a8"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "inherit"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  card-default:
    backgroundColor: "var(--surface-2)"
    textColor: "var(--text-secondary)"
    rounded: "{rounded.card}"
    padding: "24px"
  card-admin:
    backgroundColor: "var(--surface-2)"
    textColor: "var(--text-secondary)"
    rounded: "{rounded.card-admin}"
    padding: "12px"
    shadow: "none"
  input-default:
    backgroundColor: "var(--surface-2)"
    textColor: "var(--text-primary)"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    size: "36px"
---

# Design System: FinModPro

## 1. Overview

**Creative North Star: "The War Room & The Study"**

FinModPro speaks with the voice of a composed expert. It is neither playful nor tense — it is deliberate, restrained, and quietly authoritative. The interface serves two postures of the same disciplined mind: the analyst working through evidence on a clean, neutral surface, and the operator scanning live telemetry in a darkened room.

Both shells share a token-driven system. The workspace presents a light, focused surface with Command Blue accents. The admin compresses into a dense, dark navy environment with indigo accents and signal teal highlights. The same grid, the same sidebar anatomy, the same typographic hierarchy carries across both. The transition between them feels intentional, not jarring.

This system explicitly rejects the standard SaaS dashboard template — no blue-white gradient heroes, no icon-card grids, no decorative glass. Every surface, shadow, and tint exists because it serves the user's work. Nothing is decorative.

**Key Characteristics:**
- Dual-mode visual identity: neutral light workspace for analysts, dark navy war room for operators
- Token-driven shell system: `--shell-*` variables adapt surfaces to light/dark themes
- Tinted neutrals throughout — no pure black or white anywhere
- Soft ambient elevation with large-blur, low-opacity shadows
- Restrained color strategy: one blue accent at ≤10% surface coverage
- Typographic hierarchy built on weight contrast and generous scale ratios
- Admin compact mode: 12px base font, 6px card radius, tighter spacing
- DM Sans for headings, PingFang SC for body — bilingual Chinese/English ready

## 2. Colors

A token-driven shell system with two density modes. The workspace uses standard sizing and Command Blue accents. The admin compresses into a dark, dense environment with its own accent color.

### Shell Tokens

The `.app-shell` scope overrides global tokens so feature pages cannot lock the app into a single theme:

**Light theme** (`:root[data-theme='light'] .app-shell`):
- **Canvas:** `#f4f6fa` — page background. Cool blue-gray.
- **Surface-1:** `rgba(255, 255, 255, 0.96)` — sidebar, topbar, utility bar.
- **Surface-2:** `#ffffff` — cards, panels, dialogs.
- **Surface-3:** `#f7f9fc` — table headers, inactive tabs.
- **Surface-hover:** `#edf2f7` — interactive hover states.
- **Text primary:** `#172033` — headings, emphasis.
- **Text secondary:** `#5f6b7d` — body text, descriptions.
- **Text muted:** `#8a95a7` — placeholders, metadata.
- **Line soft:** `rgba(22, 32, 51, 0.09)` — borders, dividers.
- **Line strong:** `rgba(22, 32, 51, 0.14)` — input borders, emphasis.
- **Brand:** `#2457c5` — Command Blue accent.
- **Brand-soft:** `rgba(36, 87, 197, 0.1)` — accent backgrounds.

**Dark theme** (`:root[data-theme='dark'] .app-shell`):
- **Canvas:** `#101827` — deep navy page background.
- **Surface-1:** `rgba(20, 29, 45, 0.94)` — sidebar, topbar.
- **Surface-2:** `#182235` — cards, panels.
- **Surface-3:** `#202b40` — table headers, inactive tabs.
- **Surface-hover:** `#26334a` — interactive hover states.
- **Text primary:** `#eef3fb` — headings.
- **Text secondary:** `#aeb9c9` — body text.
- **Text muted:** `#7f8ca1` — placeholders, metadata.
- **Line soft:** `rgba(157, 173, 196, 0.16)` — borders.
- **Line strong:** `rgba(157, 173, 196, 0.24)` — input borders.
- **Brand:** `#7da0ff` — lighter Command Blue for dark backgrounds.
- **Brand-soft:** `rgba(125, 160, 255, 0.15)` — accent backgrounds.

### Accent Colors

- **Command Blue** (#2457c5): Workspace accent. Used for primary buttons, active nav items, links, focus rings. Applied to ≤10% of any screen. Oklch equivalent: oklch(48% 0.21 270).
- **Admin Indigo** (#5b6cff): Admin accent. Replaces the original brass. Used for admin active states, emphasis, and alert highlights.
- **Signal Teal** (#8dd0d0): Admin sidebar active indicator (inset left border). Cool cyan signal that reads as "live" in the dark admin shell.

### Semantic
- **Risk Red** (#c4493d): Errors, deletions, risk indicators. Used sparingly.
- **Warning Amber** (#b7791f): Warnings, caution states.
- **Clearance Green** (#21815c): Success, confirmation, safe states.

### Named Rules

**The Shell Scoping Rule.** All color tokens are overridden within `.app-shell` so that workspace and admin can diverge without leaking styles. Feature pages must use shell tokens (`--surface-2`, `--text-primary`), not raw palette values.

**The One Accent Rule.** Command Blue (workspace) or Admin Indigo (admin) appears on ≤10% of any given screen. If a screen feels saturated with accent, it has too much. The accent's power comes from restraint.

**The Tinted Neutral Rule.** No pure black (#000) or pure white (#fff). Every neutral carries a slight blue or cool-gray tint. In dark mode, the deepest background is `#101827`, not black.

## 3. Typography

**Display Font:** DM Sans (with Noto Sans SC fallback for Chinese)
**Body Font:** PingFang SC (with Noto Sans SC, Microsoft YaHei fallback)
**Mono Font:** JetBrains Mono (with ui-monospace, Consolas fallback)

**Character:** Geometric sans for headings paired with a humanist body face. The contrast is quiet — DM Sans has open apertures and a friendly geometry that reads as modern without feeling tech-generic. PingFang SC carries the reading load with warmth and clarity. Together they feel precise but not cold.

### Hierarchy (Workspace — standard scale)
- **Display** (600, clamp(2rem, 3.5vw, 2.5rem), 1.15): Page heroes, dashboard titles. Used once per view at most.
- **Headline** (600, 1.75rem, 1.35): Section headers, card titles, major content divisions.
- **Title** (600, 1.25rem, 1.35): Subsection headers, dialog titles, prominent labels.
- **Body** (400, 1rem, 1.6): Running text, descriptions, table content. Line length capped at 68ch.
- **Label** (500, 0.75rem, 1.35, 0.02em letter-spacing): Form labels, metadata, eyebrow text, nav group labels. Uppercase eyebrow variant at 11px with 0.16em tracking.
- **Mono** (400, 0.875rem, 1.6): Code, token values, model IDs, technical data.

### Admin Compact Scale

The admin shell overrides base font sizes for density:
- **Base:** 12px (0.75rem)
- **Small:** 11px (0.6875rem)
- **Extra small:** 10px (0.625rem)
- **Headline:** 16px (1rem)
- **Title:** 14px (0.875rem)
- **Section heading title:** ~17px (1.05rem)

All Element Plus components (tables, inputs, buttons, tags, pagination) scale down proportionally within the admin shell.

### Named Rules
**The Scale Jump Rule.** Adjacent type steps differ by ≥1.25×. No 14px/15px pairs. If two sizes look almost the same, one is wrong.

**The Length Cap Rule.** Body text lines never exceed 68ch. If a line runs longer, the container is too wide or the column needs subdivision.

## 4. Elevation

Surfaces are flat at rest. Shadows appear as ambient whispers — large blur radii at low opacity — never as heavy structural depth. The system conveys hierarchy through background tone (surface-1 through surface-3) and subtle border lines. Shadows reinforce, never define.

Admin cards are flat by default (no shadow, 1px border only). Workspace cards use ambient shadows.

### Shadow Vocabulary
- **Ambient XS** (`0 1px 2px rgba(16, 24, 40, 0.04)`): Subtle lift on hover rows, tooltips.
- **Ambient SM** (`0 2px 8px -2px rgba(16, 24, 40, 0.08)`): Dropdowns, popovers, light card hover.
- **Ambient MD** (`0 8px 24px -8px rgba(16, 24, 40, 0.12)`): Default workspace card elevation. The workhorse.
- **Ambient LG** (`0 18px 44px -30px rgba(16, 24, 40, 0.22)`): Elevated cards, dialogs. Rare.
- **Ambient XL** (`0 28px 64px -40px rgba(16, 24, 40, 0.32)`): Modal overlays only. Reserved.

Dark mode shadows shift to higher opacity (`rgba(0, 0, 0, ...)` bases) to read against dark surfaces.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Shadows appear only as a response to state (hover, elevation, focus). A card sitting on the page with a heavy shadow is an error — it should feel like paper on a desk, not a floating panel.

**The Admin Flat Rule.** Admin section cards and panels use `box-shadow: none` with a 1px border only. The dark background provides sufficient depth separation; shadows would add visual noise in an already-dense environment.

## 5. Components

### Buttons
- **Shape:** Rounded at 12px (md). Admin buttons use 12px radius. Pill shape (999px) is reserved for filter chips and tags — never for primary actions.
- **Primary:** Command Blue background (#2457c5), white text, 10px vertical × 24px horizontal padding. Height: 36px.
- **Hover:** Deepens to #1d48a8. Transition: background-color 0.2s ease.
- **Focus-visible:** 2px Command Blue ring at 2px offset. No default outline.
- **Ghost:** Transparent background, inherits text color, 10px × 16px padding. Hover adds surface-hover background.
- **Disabled:** 40% opacity on the entire element. No hover change.
- **Admin compact:** 28px height, 12px font, 5px × 12px padding.

### Cards
- **Workspace corner style:** 24px radius (2xl). The generous curve signals containment without feeling like a bubble.
- **Admin corner style:** 6px radius. Tighter corners match the compressed density.
- **Background:** Surface-2 (token-driven, adapts to theme).
- **Border:** 1px solid line-soft. Invisible until you look for it.
- **Shadow (workspace):** Ambient MD at rest, lifts to Ambient LG on hover. Transition: 0.25s ease.
- **Shadow (admin):** None. Border-only. Lifts to Ambient SM on hover.
- **Internal Padding:** 24px (workspace), 12px (admin). Headers use the section-heading pattern with title + optional description.

### Inputs
- **Style:** 1px solid border (line-strong), surface-2 background, 12px radius.
- **Height:** 36px default. Admin: 28px.
- **Padding:** 8px horizontal × 12px vertical.
- **Focus:** Border shifts to Command Blue, adds 2px blue ring at 2px offset. No inner glow.
- **Placeholder:** Muted Steel (#7d8798 in light, #697585 in dark).
- **Error:** Border shifts to Risk Red. Error message appears below in 12px Risk Red text.
- **Dark mode:** Background deepens to #111822. Border remains line-strong.

### Navigation
- **Sidebar width:** 188px (workspace), 200px (admin).
- **Sidebar background:** Shell sidebar token (rgba white in light, rgba dark navy in dark). Admin sidebar is `rgba(10, 15, 22, 0.92)` with a subtle inset right shadow.
- **Nav items:** 8px × 10px padding, 12px radius (workspace) or 14px radius (admin). Icon (28px) + label. Default: transparent. Hover: surface-hover background. Active: surface-2 background, Command Blue text (workspace) or light text with teal inset border (admin).
- **Active indicator (workspace):** Inset 2px left border in Command Blue.
- **Active indicator (admin):** Inset 3px left border in Signal Teal (#8dd0d0), with indigo background tint.
- **Group labels:** 10px font, 0.12em letter-spacing, uppercase. Separated by 12px gaps with border-top dividers.
- **Brand area:** 36px mark (12px radius) + eyebrow label + product name. Bottom padding 12px with border.
- **Sub-navigation:** Expandable items with chevron. Indented 18px with left border line. 34px min-height items.
- **Mobile (≤960px):** Workspace sidebar becomes horizontal scroll. Admin sidebar becomes off-canvas drawer (280px) with overlay.

### Chips & Tags
- **Style:** 999px radius (pill). 11px font (10px in admin). 3px × 7px padding. Surface-3 background, text-secondary color.
- **Meta chips:** Same shape, used for metadata displays. Background tied to category (neutral, risk, success).

### Section Cards (Admin)
- **Style:** Element Plus el-card with ui-card class. 6px radius, no shadow, 1px border.
- **Header:** section-heading pattern with title (~17px, 600) and optional description (14px, text-secondary). Max-width 62ch on description.
- **Spacing:** Consecutive admin section cards get 8px top margin (tighter than workspace's 20px).

### Command Palette
- **Overlay:** Fixed, full-viewport, `rgba(0, 0, 0, 0.48)` with 4px blur backdrop.
- **Container:** 520px wide, 8px radius, surface-1 background, shadow XL.
- **Input row:** Search icon + input + keyboard shortcut hint. 12px padding, bottom border.
- **Results:** Max 320px height, scrollable. Items are 8px × 10px padding, 4px radius. Active/hover: brand-soft background, brand text.
- **Empty state:** 24px padding, centered, muted text.

### Flash Messages (Toast Stack)
- **Position:** Fixed, top-right (16px from top, 24px from right). 380px wide.
- **Style:** 12px radius, 14px × 16px padding. Backdrop blur. Slide-in animation from top.
- **Variants:** Success (green), Error (red), Info (blue), Warning (amber). Each with 50-series background, 100-series border, 600-series text.

### Named Rules
**The No Nested Cards Rule.** Cards inside cards are prohibited. A card is a terminal container. If content needs subdivision, use a section heading, a divider, or whitespace.

## 6. Layout

### Shell Grid
- **Workspace:** `grid-template-columns: 188px minmax(0, 1fr)`. Max content width: 1720px.
- **Admin:** `grid-template-columns: 200px minmax(0, 1fr)`. Max content width: 1480px.
- **Responsive (≤960px):** Single column. Admin sidebar becomes off-canvas.

### Content Padding
- **Workspace:** 18px top, 20px inline, 28px bottom.
- **Admin:** 16px top, 16px inline, 20px bottom. Tighter throughout.

### Page Stack
- **Workspace:** 24px gap between page sections.
- **Admin:** 12px gap. Compressed for density.

### Topbar
- **Height:** ~58px (workspace), ~44px (admin).
- **Style:** Sticky, surface-1 background, 1px bottom border, subtle shadow.
- **Search:** 220–340px wide, 40px height, 12px radius. Icon left-aligned.
- **Admin:** Transparent background with subtle border, smaller font sizes.

### Named Rules
**The Content Width Rule.** Prose containers cap at 68ch. Data-dense layouts use the full shell max-width. Never let content stretch to the viewport edge without a max-width guard.

## 7. Do's and Don'ts

### Do:
- **Do** use shell tokens (`--surface-2`, `--text-primary`, `--line-soft`) rather than raw palette values in components.
- **Do** cap body text at 68ch line length. Use max-width on prose containers.
- **Do** keep accent color to ≤10% of any screen. It is the punctuation, not the paragraph.
- **Do** use the 24px card radius for workspace cards, 6px for admin cards.
- **Do** prefer transparent/surface-hover backgrounds for interactive items at rest. Reserve shadows for elevated states.
- **Do** use the type scale as defined — never interpolate sizes between steps.
- **Do** scale down all Element Plus components within the admin shell (28px buttons, 12px base font, compact tables).
- **Do** use `prefers-reduced-motion` to disable animations for users who request it.

### Don't:
- **Don't** use the standard SaaS blue-white dashboard template — gradient hero stats, icon-card grids, or decorative glass panels. FinModPro is a precision tool, not a marketing dashboard.
- **Don't** use pure black (#000) or pure white (#fff). Every neutral is tinted toward the brand hue.
- **Don't** use border-left or border-right greater than 1px as a colored accent stripe on cards, list items, or alerts.
- **Don't** apply gradient text (background-clip: text). Use a single solid color. Emphasis comes from weight or size.
- **Don't** nest cards inside cards. A card is a terminal container.
- **Don't** use glassmorphism (backdrop-filter blur on surfaces) except in the flash stack and command palette overlay, where it has a functional purpose.
- **Don't** animate layout properties (width, height, top, left). Use transform and opacity only.
- **Don't** use bounce or elastic easings. Ease-out-quart or expo curves only.
- **Don't** use em dashes. Commas, colons, periods, or parentheses instead.
- **Don't** use identical card grids with icon + heading + text repeated endlessly. Vary layout rhythm.
- **Don't** default to modals. Exhaust inline expansion, drawers, or progressive disclosure first.
- **Don't** hardcode dark backgrounds in feature CSS. The shell token system handles theme — feature pages should be theme-agnostic.
