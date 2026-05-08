---
name: FinModPro
description: Financial risk-control platform with domain-specific LLMs — dual-mode analyst workspace and admin war room
colors:
  command-blue: "#2457c5"
  command-blue-deep: "#142f70"
  navy-ink: "#1e293b"
  warm-white: "#f8f9fb"
  cool-ash: "#e2e6ed"
  muted-steel: "#7d8798"
  near-black: "#0b0f18"
  parchment: "#f3ecdf"
  dossier-ink: "#2f2418"
  ochre-amber: "#9a6a2c"
  war-room-navy: "#0f1722"
  admin-slate: "#182231"
  brass: "#d5a441"
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
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  "2xl": "24px"
  card: "24px"
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
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  card-default:
    backgroundColor: "#ffffff"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.card}"
    padding: "24px"
  input-default:
    backgroundColor: "#ffffff"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    size: "36px"
---

# Design System: FinModPro

## 1. Overview

**Creative North Star: "The War Room & The Study"**

FinModPro speaks with the voice of a composed expert. It is neither playful nor tense — it is deliberate, restrained, and quietly authoritative. The interface serves two postures of the same disciplined mind: the analyst bent over a warm-lit desk, pulling threads through evidence, and the operator scanning live telemetry in a darkened room.

The workspace shell wraps the analyst in paper tones — parchment, ink, ochre. It is a study: warm, focused, unhurried. The admin shell surrounds the operator in deep navy, brass, and signal teal. It is a war room: technical, alert, precise. These two modes are visually distinct but structurally coherent. The same grid, the same sidebar anatomy, the same typographic hierarchy carries across both. The transition between them feels intentional, not jarring.

This system explicitly rejects the standard SaaS dashboard template — no blue-white gradient heroes, no icon-card grids, no decorative glass. Every surface, shadow, and tint exists because it serves the user's work. Nothing is decorative.

**Key Characteristics:**
- Dual-mode visual identity: warm parchment study for analysts, dark navy war room for operators
- Tinted neutrals throughout — no pure black or white anywhere
- Soft ambient elevation with large-blur, low-opacity shadows
- Restrained color strategy: one blue accent at ≤10% surface coverage; workspace and admin each have one distinctive accent
- Typographic hierarchy built on weight contrast and generous scale ratios
- DM Sans for headings, PingFang SC for body — bilingual Chinese/English ready

## 2. Colors

Two calibrated palettes sharing one structural skeleton. The workspace palette is warm and paper-derived (parchment, ink, ochre). The admin palette is cool and instrument-derived (navy, brass, teal). A single command blue accent bridges both modes.

### Primary
- **Command Blue** (#2457c5): The sole cross-mode accent. Used for primary buttons, active nav items, links, and focus rings. Applied to ≤10% of any screen — its scarcity is the point. Oklch equivalent: oklch(48% 0.21 270).

### Neutral
- **Navy Ink** (#1e293b): Primary text on light surfaces. Deep but never black — carries a hint of blue.
- **Warm White** (#f8f9fb): Page background, surface-adjacent areas. Tinted 0.005 chroma toward blue — never pure white.
- **Cool Ash** (#e2e6ed): Borders, dividers, disabled states. Visible but recessive.
- **Muted Steel** (#7d8798): Tertiary text, placeholders, metadata. Low contrast but still legible.
- **Near Black** (#0b0f18): Dark mode page background. Tinted toward blue, never #000.

### Workspace (warm register)
- **Parchment** (#f3ecdf): Workspace page background. Warm paper tone — oklch(94% 0.015 85).
- **Dossier Ink** (#2f2418): Primary text on workspace surfaces. Warm brown-black — oklch(22% 0.02 75).
- **Ochre Amber** (#9a6a2c): Workspace accent. Earthy and warm — oklch(52% 0.12 70).

### Admin (cool register)
- **War Room Navy** (#0f1722): Admin page background. Deep blue-black — oklch(12% 0.02 260).
- **Admin Slate** (#182231): Admin surface panels. Slightly lifted from the background — oklch(18% 0.015 258).
- **Brass** (#d5a441): Admin accent. Muted gold — oklch(72% 0.13 85).
- **Signal Teal** (#8dd0d0): Admin alert/highlight. Cool cyan signal — oklch(78% 0.08 200).

### Semantic
- **Risk Red** (#c4493d): Errors, deletions, risk indicators. Used sparingly.
- **Warning Amber** (#b7791f): Warnings, caution states.
- **Clearance Green** (#21815c): Success, confirmation, safe states.

### Named Rules
**The Two-Desk Rule.** Workspace surfaces use warm tones (parchment, ink, ochre). Admin surfaces use cool tones (navy, brass, teal). Never mix warm workspace colors into admin or vice versa — the boundary is absolute. Command Blue is the only color that crosses both modes.

**The One Accent Rule.** Command Blue appears on ≤10% of any given screen. If a screen feels blue, it has too much accent. The accent's power comes from restraint.

## 3. Typography

**Display Font:** DM Sans (with Noto Sans SC fallback for Chinese)
**Body Font:** PingFang SC (with Noto Sans SC, Microsoft YaHei fallback)
**Mono Font:** JetBrains Mono (with ui-monospace, Consolas fallback)

**Character:** Geometric sans for headings paired with a humanist body face. The contrast is quiet — DM Sans has open apertures and a friendly geometry that reads as modern without feeling tech-generic. PingFang SC carries the reading load with warmth and clarity. Together they feel precise but not cold.

### Hierarchy
- **Display** (600, clamp(2rem, 3.5vw, 2.5rem), 1.15): Page heroes, dashboard titles. Used once per view at most.
- **Headline** (600, 1.75rem, 1.35): Section headers, card titles, major content divisions.
- **Title** (600, 1.25rem, 1.35): Subsection headers, dialog titles, prominent labels.
- **Body** (400, 1rem, 1.6): Running text, descriptions, table content. Line length capped at 68ch.
- **Label** (500, 0.75rem, 1.35, 0.02em letter-spacing): Form labels, metadata, eyebrow text, nav group labels. Uppercase eyebrow variant at 11px with 0.16em tracking.
- **Mono** (400, 0.875rem, 1.6): Code, token values, model IDs, technical data.

### Named Rules
**The Scale Jump Rule.** Adjacent type steps differ by ≥1.25×. No 14px/15px pairs. If two sizes look almost the same, one is wrong.

**The Length Cap Rule.** Body text lines never exceed 68ch. If a line runs longer, the container is too wide or the column needs subdivision.

## 4. Elevation

Surfaces are flat at rest. Shadows appear as ambient whispers — large blur radii at low opacity — never as heavy structural depth. The system conveys hierarchy through background tone (surface-1 through surface-3) and subtle border lines. Shadows reinforce, never define.

### Shadow Vocabulary
- **Ambient XS** (`0 1px 2px rgba(16, 24, 40, 0.04)`): Subtle lift on hover rows, tooltips.
- **Ambient SM** (`0 2px 8px -2px rgba(16, 24, 40, 0.08)`): Dropdowns, popovers, light card hover.
- **Ambient MD** (`0 8px 24px -8px rgba(16, 24, 40, 0.12)`): Default card elevation. The workhorse.
- **Ambient LG** (`0 18px 44px -30px rgba(16, 24, 40, 0.22)`): Elevated cards, dialogs. Rare.
- **Ambient XL** (`0 28px 64px -40px rgba(16, 24, 40, 0.32)`): Modal overlays only. Reserved.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Shadows appear only as a response to state (hover, elevation, focus). A card sitting on the page with a heavy shadow is an error — it should feel like paper on a desk, not a floating panel.

## 5. Components

### Buttons
- **Shape:** Rounded at 12px (md). Fully pill shape (999px) is reserved for filter chips and tags — never for primary actions.
- **Primary:** Command Blue background (#2457c5), white text, 10px vertical × 24px horizontal padding. Height: 36px.
- **Hover:** Deepens to #1d48a8. Transition: background-color 0.2s ease.
- **Focus-visible:** 2px Command Blue ring at 2px offset. No default outline.
- **Ghost:** Transparent background, inherits text color, 10px × 16px padding. Hover adds surface-3 background.
- **Disabled:** 40% opacity on the entire element. No hover change.

### Cards
- **Corner Style:** 24px radius (2xl). The generous curve signals containment without feeling like a bubble.
- **Background:** Surface-2 (white in light, #181f2a in dark).
- **Border:** 1px solid line-soft (7% opacity). Invisible until you look for it.
- **Shadow:** Ambient MD at rest, lifts to Ambient LG on hover. Transition: 0.25s ease.
- **Internal Padding:** 24px (header and body). Headers use the section-heading pattern with title + optional description.

### Inputs
- **Style:** 1px solid border (line-strong, 12% opacity), surface-2 background, 12px radius.
- **Height:** 36px default.
- **Padding:** 8px horizontal × 12px vertical.
- **Focus:** Border shifts to Command Blue, adds 2px blue ring at 2px offset. No inner glow.
- **Placeholder:** Muted Steel (#7d8798).
- **Error:** Border shifts to Risk Red. Error message appears below in 12px Risk Red text.
- **Dark mode:** Background deepens to #111822. Border remains line-strong.

### Navigation
- **Sidebar:** 264px (workspace) or 248px (admin) wide, sticky, full viewport height. Padding: 18px × 14px.
- **Nav items:** 11px vertical × 12px horizontal padding, 10px radius. Icon (18px) + label. Default: transparent. Hover: surface-hover background. Active: surface-3 background, Command Blue or Ochre Amber (workspace) / Brass (admin) text color, 600 weight.
- **Group labels:** 10px font, 0.18em letter-spacing, uppercase. Separated by 14px gaps with border-top dividers.
- **Brand area:** 46px mark (14px radius) + eyebrow label + product name. Bottom padding 14px with optional border.

### Chips & Tags
- **Style:** 999px radius (pill). 11px font. 3px × 7px padding. Surface-3 background, text-secondary color.
- **Meta chips:** Same shape, used for metadata displays. Background tied to category (neutral, risk, success).

### Section Cards (Admin)
- **Style:** Element Plus el-card with ui-card class. Card radius (24px), ambient MD shadow.
- **Header:** section-heading pattern with title (16px, 600) and optional description (14px, text-secondary).
- **Spacing:** Consecutive admin section cards get 20px top margin.

### Named Rules
**The No Nested Cards Rule.** Cards inside cards are prohibited. A card is a terminal container. If content needs subdivision, use a section heading, a divider, or whitespace.

## 6. Do's and Don'ts

### Do:
- **Do** use workspace tokens (parchment, dossier ink, ochre) exclusively within workspace shells and admin tokens (war room navy, brass, signal teal) exclusively within admin shells.
- **Do** cap body text at 68ch line length. Use max-width on prose containers.
- **Do** keep Command Blue to ≤10% of any screen. It is the punctuation, not the paragraph.
- **Do** use the 24px card radius consistently for all card-like containers.
- **Do** prefer transparent/surface-hover backgrounds for interactive items at rest. Reserve shadows for elevated states.
- **Do** use the type scale as defined — never interpolate sizes between steps.
- **Do** respect the dual-mode boundary: warm tones in workspace, cool tones in admin. The only cross-mode color is Command Blue.

### Don't:
- **Don't** use the standard SaaS blue-white dashboard template — gradient hero stats, icon-card grids, or decorative glass panels. FinModPro is a precision tool, not a marketing dashboard.
- **Don't** use pure black (#000) or pure white (#fff). Every neutral is tinted toward the brand hue.
- **Don't** use border-left or border-right greater than 1px as a colored accent stripe on cards, list items, or alerts.
- **Don't** apply gradient text (background-clip: text). Use a single solid color. Emphasis comes from weight or size.
- **Don't** nest cards inside cards. A card is a terminal container.
- **Don't** use glassmorphism (backdrop-filter blur on surfaces) except in the workspace utility bar, where it has a functional purpose.
- **Don't** animate layout properties (width, height, top, left). Use transform and opacity only.
- **Don't** use bounce or elastic easings. Ease-out-quart or expo curves only.
- **Don't** use em dashes. Commas, colons, periods, or parentheses instead.
- **Don't** use identical card grids with icon + heading + text repeated endlessly. Vary layout rhythm.
- **Don't** default to modals. Exhaust inline expansion, drawers, or progressive disclosure first.
