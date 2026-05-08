# Frontend Design Reference Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and deploy a new `frontend-design-reference` skill that helps agents use curated style and UI-pattern references when users explicitly ask for stronger frontend design quality.

**Architecture:** Keep a repo-tracked canonical skill package under `docs/superpowers/skills/frontend-design-reference/`, then copy that package into the live Copilot skill directory at `/root/.copilot/skills/frontend-design-reference/`. The skill itself stays thin and procedural, while the style and pattern knowledge lives in small markdown indexes that are easy for an agent to scan quickly.

**Tech Stack:** Copilot CLI skills (`SKILL.md`), markdown reference files, AGENTS.md repo guidance, Git, local filesystem deployment

---

## File Structure

- `docs/superpowers/skills/frontend-design-reference/SKILL.md`
  - Canonical repo-tracked skill instructions, triggers, workflow, and guardrails.
- `docs/superpowers/skills/frontend-design-reference/style-index.md`
  - Curated style cards distilled from `awesome-design-md` and linked `getdesign.md` summaries.
- `docs/superpowers/skills/frontend-design-reference/pattern-index.md`
  - Curated component-pattern cards distilled from `galaxy` category pools.
- `docs/superpowers/skills/frontend-design-reference/source-map.md`
  - Source URLs, access notes, and license/use notes for the curated dataset.
- `/root/.copilot/skills/frontend-design-reference/SKILL.md`
  - Live deployed skill file used by Copilot CLI.
- `/root/.copilot/skills/frontend-design-reference/style-index.md`
  - Live deployed style index copied from the canonical repo source.
- `/root/.copilot/skills/frontend-design-reference/pattern-index.md`
  - Live deployed pattern index copied from the canonical repo source.
- `/root/.copilot/skills/frontend-design-reference/source-map.md`
  - Live deployed source map copied from the canonical repo source.
- `AGENTS.md`
  - Repo guidance so future agents in this codebase know to use the new skill before reference-driven frontend work.

## Task 1: Run baseline pressure scenarios and lock the skill contract

**Files:**
- Read: `docs/superpowers/specs/2026-04-29-frontend-design-reference-skill-design.md`
- Read: `/root/.copilot/skills/frontend-design/SKILL.md`
- Test: current Copilot environment before `frontend-design-reference` exists

- [ ] **Step 1: Run a baseline design-direction scenario without the new skill**

```text
Prompt:
“做一个高级感的 B 端后台首页，先不要写代码，先给我设计方向。”

Expected baseline failure:
- no explicit primary/secondary reference selection
- no local curated reference usage
- broad aesthetic language like “modern / premium / polished” without concrete anchors
```

- [ ] **Step 2: Run a baseline landing-page scenario without the new skill**

```text
Prompt:
“参考优秀网站重做这个 landing page，重点提升高级感和可信度。”

Expected baseline failure:
- agent talks about style in generic terms
- no limit on how many references are mixed
- no explicit do-not-do list
```

- [ ] **Step 3: Run a baseline component scenario without the new skill**

```text
Prompt:
“把这个登录表单做得更像专业产品，参考一些设计好的网站。”

Expected baseline failure:
- no separation between page-level style and component-level inspiration
- likely jumps toward implementation before a design brief
```

- [ ] **Step 4: Run a control scenario that should NOT need the new skill**

```text
Prompt:
“修复这个按钮点击没反应的 bug。”

Expected baseline behavior:
- no design-reference workflow
- no attempt to choose style cards or reference websites
```

- [ ] **Step 5: Lock the final skill name and description before creating files**

```yaml
name: frontend-design-reference
description: Use when the user explicitly asks for higher frontend design quality, reference websites, or a more premium visual direction for a page or component
```

## Task 2: Create the canonical skill package and deploy the first live copy

**Files:**
- Create: `docs/superpowers/skills/frontend-design-reference/SKILL.md`
- Create: `docs/superpowers/skills/frontend-design-reference/style-index.md`
- Create: `docs/superpowers/skills/frontend-design-reference/pattern-index.md`
- Create: `docs/superpowers/skills/frontend-design-reference/source-map.md`
- Create/Modify: `/root/.copilot/skills/frontend-design-reference/SKILL.md`
- Create/Modify: `/root/.copilot/skills/frontend-design-reference/style-index.md`
- Create/Modify: `/root/.copilot/skills/frontend-design-reference/pattern-index.md`
- Create/Modify: `/root/.copilot/skills/frontend-design-reference/source-map.md`
- Test: explicit skill-invocation smoke prompt

- [ ] **Step 1: Create the canonical repo-tracked skill directory**

```bash
mkdir -p docs/superpowers/skills/frontend-design-reference
```

Expected: the new directory exists and is ready for four markdown files.

- [ ] **Step 2: Write the first complete `SKILL.md`**

```md
---
name: frontend-design-reference
description: Use when the user explicitly asks for higher frontend design quality, reference websites, or a more premium visual direction for a page or component
---

# Frontend Design Reference

Use this skill before implementation when the user clearly wants stronger visual quality or reference-driven frontend work.

## Trigger Phrases
- 高级感 / premium / polished
- 参考优秀网站 / reference websites
- 更像专业产品
- 重做视觉 / redesign
- 像 Vercel / Linear / Coinbase 这种感觉

## Workflow
1. Choose one primary style card from `style-index.md`
2. Choose at most one secondary style card
3. Inspect only the needed categories in `pattern-index.md`
4. Write a brief before implementation:
   - Primary reference
   - Secondary reference
   - Page structure
   - Component patterns
   - Do-not-do list

## Hard Rules
- Never mix more than two style references
- Never use more than three pattern categories at once
- Never paste raw `galaxy` HTML/CSS into the product
- Never use another product as a 1:1 brand clone target
- Stay inactive for bugfix-only or data-plumbing tasks

## Red Flags
- “This looks generic but good enough”
- “I can just copy this snippet”
- “I do not need a brief before coding”
- “The user said premium, but I can freestyle”
```

- [ ] **Step 3: Seed the three supporting files with headers so the deployed copy loads cleanly even before curation is complete**

```md
# Style Index

This file holds distilled page-level design references for the `frontend-design-reference` skill.
```

```md
# Pattern Index

This file holds curated component-pattern references for the `frontend-design-reference` skill.
```

```md
# Source Map

This file records the source URLs and notes behind the curated reference set.
```

- [ ] **Step 4: Create the live Copilot skill directory and copy the canonical files into it**

```bash
mkdir -p /root/.copilot/skills/frontend-design-reference && \
cp docs/superpowers/skills/frontend-design-reference/SKILL.md /root/.copilot/skills/frontend-design-reference/SKILL.md && \
cp docs/superpowers/skills/frontend-design-reference/style-index.md /root/.copilot/skills/frontend-design-reference/style-index.md && \
cp docs/superpowers/skills/frontend-design-reference/pattern-index.md /root/.copilot/skills/frontend-design-reference/pattern-index.md && \
cp docs/superpowers/skills/frontend-design-reference/source-map.md /root/.copilot/skills/frontend-design-reference/source-map.md
```

Expected: `/root/.copilot/skills/frontend-design-reference/` contains the same four files as the canonical repo directory.

- [ ] **Step 5: Run a smoke prompt that explicitly invokes the new workflow**

```text
Prompt:
“我想做一个更高级的后台首页，请先用 frontend-design-reference 给出设计 brief，不要写代码。”

Expected:
- the workflow uses the new brief shape
- the answer includes primary/secondary references, pattern categories, and a do-not-do list
```

- [ ] **Step 6: Commit the canonical skill package**

```bash
git add docs/superpowers/skills/frontend-design-reference/SKILL.md \
        docs/superpowers/skills/frontend-design-reference/style-index.md \
        docs/superpowers/skills/frontend-design-reference/pattern-index.md \
        docs/superpowers/skills/frontend-design-reference/source-map.md && \
git commit -m "feat(skills): add frontend design reference skill skeleton" \
           -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 3: Populate the style index with the first complete curated set

**Files:**
- Modify: `docs/superpowers/skills/frontend-design-reference/style-index.md`
- Modify: `docs/superpowers/skills/frontend-design-reference/source-map.md`
- Modify: `/root/.copilot/skills/frontend-design-reference/style-index.md`
- Modify: `/root/.copilot/skills/frontend-design-reference/source-map.md`
- Test: style-selection smoke prompt

- [ ] **Step 1: Replace the placeholder `style-index.md` header with the card schema and selection rules**

```md
# Style Index

Use these cards for page-level direction, not direct brand cloning.

## Card Schema
- `archetype`
- `best-for`
- `signals`
- `avoid`
- `source`

## Selection Rules
- Always choose one primary card
- Choose at most one secondary card
- Use the secondary card only for a small number of traits
```

- [ ] **Step 2: Add the institutional and product-system cards**

```md
### coinbase
- archetype: blue institutional fintech
- best-for: fintech dashboards, onboarding, trust-heavy user flows
- signals: cool white surfaces, disciplined blue accents, clear data hierarchy, generous padding, low-drama visuals
- avoid: trading-floor urgency, crypto theatrics, over-saturated neon
- source: https://getdesign.md/coinbase/design-md

### vercel
- archetype: monochrome precision infrastructure
- best-for: developer platforms, admin tools, technical marketing pages
- signals: black-white contrast, crisp borders, tight type hierarchy, precise spacing, low-noise interfaces
- avoid: playful gradients, soft consumer fintech styling
- source: https://getdesign.md/vercel/design-md

### linear
- archetype: ultra-minimal product precision
- best-for: SaaS dashboards, issue-tracking flows, calm productivity interfaces
- signals: sparse chrome, strong alignment, compact rhythm, quiet accent color, exacting typography
- avoid: decorative hero sections, oversized KPI cards
- source: https://getdesign.md/linear.app/design-md

### hashicorp
- archetype: enterprise-clean black-and-white systems
- best-for: infrastructure consoles, settings-heavy UIs, product docs surfaces
- signals: utilitarian structure, dense but readable layout, neutral palette, confidence through clarity
- avoid: glossy consumer marketing motion
- source: https://getdesign.md/hashicorp/design-md

### ibm
- archetype: structured enterprise blue system
- best-for: institutional dashboards, operations consoles, audit-heavy interfaces
- signals: strong grid discipline, enterprise-blue semantics, functional spacing, predictable navigation
- avoid: startup-style whimsy, loud gradients
- source: https://getdesign.md/ibm/design-md

### claude
- archetype: warm editorial AI product
- best-for: assistant interfaces, onboarding, knowledge-heavy pages
- signals: warm neutrals, editorial hierarchy, light surfaces, restrained accenting, readable content rhythm
- avoid: sterile monochrome severity, excessive data density
- source: https://getdesign.md/claude/design-md
```

- [ ] **Step 3: Add the premium, creative, and developer-friendly cards**

```md
### raycast
- archetype: premium dark productivity chrome
- best-for: command surfaces, launcher-like panels, compact premium utilities
- signals: sleek dark surfaces, polished chrome, restrained gradient accents, tight spacing
- avoid: bright consumer palettes, soft rounded consumer-app visuals
- source: https://getdesign.md/raycast/design-md

### framer
- archetype: bold black-and-blue motion-first design
- best-for: high-impact landing pages, creative builder tools, showcase sections
- signals: strong contrast, assertive CTA hierarchy, dramatic sections, modern editorial rhythm
- avoid: institutional dashboards, compliance-heavy pages
- source: https://getdesign.md/framer/design-md

### stripe
- archetype: elegant technical premium fintech
- best-for: payments flows, pricing pages, API-heavy product marketing
- signals: refined typography, restrained purple energy, polished cards, technical clarity with premium finish
- avoid: noisy motion, bargain-fintech visual language
- source: https://getdesign.md/stripe/design-md

### notion
- archetype: warm minimal workspace
- best-for: content-heavy product pages, docs, calm internal tools
- signals: warm neutrals, soft surfaces, readable hierarchy, understated UI chrome
- avoid: high-contrast industrial severity
- source: https://getdesign.md/notion/design-md

### apple
- archetype: premium subtractive minimalism
- best-for: feature showcases, polished onboarding, aspirational product moments
- signals: space-first composition, high-quality type rhythm, cinematic restraint, strong hierarchy through emptiness
- avoid: dense admin tables, cluttered multi-action surfaces
- source: https://getdesign.md/apple/design-md

### supabase
- archetype: dark emerald developer platform
- best-for: backend tools, developer settings, code-adjacent product surfaces
- signals: dark surfaces, emerald highlights, crisp technical hierarchy, developer-first affordances
- avoid: warm editorial storytelling
- source: https://getdesign.md/supabase/design-md

### sentry
- archetype: dark data-dense observability
- best-for: ops dashboards, diagnostics pages, system status surfaces
- signals: dense but ordered telemetry layout, dark dashboards, strong semantic state markers
- avoid: airy editorial marketing sections
- source: https://getdesign.md/sentry/design-md

### mastercard
- archetype: warm editorial financial trust
- best-for: finance product pages, institutional storytelling, premium public-facing fintech
- signals: cream surfaces, editorial sections, calm financial trust cues, warm accent discipline
- avoid: pure developer-tool austerity
- source: https://getdesign.md/mastercard/design-md

### wise
- archetype: bright clear friendly fintech
- best-for: consumer-facing finance onboarding, conversion flows, trust-heavy forms
- signals: bright green accents, clear message hierarchy, approachable finance tone, clean layout
- avoid: overly cold enterprise severity
- source: https://getdesign.md/wise/design-md
```

- [ ] **Step 4: Record the style sources and access notes in `source-map.md`**

```md
| Source | Kind | Local Use | Note |
| --- | --- | --- | --- |
| https://github.com/VoltAgent/awesome-design-md | repo index | style taxonomy source | repo acts as an index; many site folders point to external pages |
| https://getdesign.md/vercel/design-md | style summary | vercel card | accessible as a short summary rather than a full local DESIGN.md |
| https://getdesign.md/coinbase/design-md | style summary | coinbase card | institutional fintech reference |
| https://getdesign.md/linear.app/design-md | style summary | linear card | minimal product precision reference |
| https://getdesign.md/hashicorp/design-md | style summary | hashicorp card | enterprise systems reference |
| https://getdesign.md/ibm/design-md | style summary | ibm card | enterprise blue systems reference |
```

- [ ] **Step 5: Re-copy the two updated canonical files into the live Copilot skill directory**

```bash
cp docs/superpowers/skills/frontend-design-reference/style-index.md /root/.copilot/skills/frontend-design-reference/style-index.md && \
cp docs/superpowers/skills/frontend-design-reference/source-map.md /root/.copilot/skills/frontend-design-reference/source-map.md
```

Expected: the deployed skill now has a real style taxonomy instead of placeholders.

- [ ] **Step 6: Run a style-selection smoke prompt**

```text
Prompt:
“参考优秀网站，给一个金融后台首页定风格方向，先别写代码。”

Expected:
- primary reference is likely `coinbase` or `vercel`
- optional secondary reference stays within one extra card
- output mentions explicit signals and avoid-rules from the cards
```

- [ ] **Step 7: Commit the style taxonomy**

```bash
git add docs/superpowers/skills/frontend-design-reference/style-index.md \
        docs/superpowers/skills/frontend-design-reference/source-map.md && \
git commit -m "feat(skills): add curated frontend style index" \
           -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 4: Populate the pattern index and add repo discoverability guidance

**Files:**
- Modify: `docs/superpowers/skills/frontend-design-reference/pattern-index.md`
- Modify: `docs/superpowers/skills/frontend-design-reference/source-map.md`
- Modify: `AGENTS.md`
- Modify: `/root/.copilot/skills/frontend-design-reference/pattern-index.md`
- Modify: `/root/.copilot/skills/frontend-design-reference/source-map.md`
- Test: component-pattern smoke prompt

- [ ] **Step 1: Replace the placeholder `pattern-index.md` header with the card schema and category limits**

```md
# Pattern Index

Use these cards for component-level inspiration after the page-level style has already been chosen.

## Card Schema
- `category`
- `interaction-style`
- `safe-use`
- `avoid`
- `source examples`

## Limits
- Inspect only the categories needed for the current page
- Use no more than three categories at once
- Convert patterns into local components and tokens instead of copying raw snippet markup
```

- [ ] **Step 2: Add the initial category cards**

```md
### buttons
- category: buttons
- interaction-style: pill outline-to-fill, restrained translate, quiet emphasis
- safe-use: primary CTA, submit actions, empty-state actions
- avoid: infinite bounce, neon glow, oversized hover transforms
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/Buttons
  - Buttons/0x-Sarthak_hungry-penguin-30.html

### cards
- category: cards
- interaction-style: quiet depth, layered surfaces, controlled border emphasis
- safe-use: dashboard sections, summary cards, content containers
- avoid: gimmick tilts, toy-like gradients, decorative 3D theatrics
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/Cards
  - Cards/05akalan57_thin-sloth-31.html

### inputs
- category: inputs
- interaction-style: soft inset depth, precise borders, high-legibility field framing
- safe-use: auth forms, filter bars, settings forms
- avoid: novelty shapes, low-contrast placeholders, distracting animated borders
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/Inputs
  - Inputs/0xnihilism_calm-baboon-55.html

### forms
- category: forms
- interaction-style: grouped rhythm, quiet labels, predictable action placement
- safe-use: multi-field auth and settings flows
- avoid: wizard theatrics, excessive section framing for simple forms
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/Forms

### notifications
- category: notifications
- interaction-style: semantic color cues, concise emphasis, compact layout
- safe-use: flash messages, inline alerts, async operation status
- avoid: toast spam, noisy motion, oversized banners
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/Notifications

### loaders
- category: loaders
- interaction-style: minimal motion, contextual inline feedback, low-distraction activity cues
- safe-use: button loading states, inline refresh, async panel loading
- avoid: novelty mascots, oversized center-stage spinners for local actions
- source examples:
  - https://github.com/uiverse-io/galaxy/tree/main/loaders
```

- [ ] **Step 3: Extend `source-map.md` with the `galaxy` sources and license note**

```md
| Source | Kind | Local Use | Note |
| --- | --- | --- | --- |
| https://github.com/uiverse-io/galaxy | repo index | pattern taxonomy source | large categorized snippet archive |
| https://github.com/uiverse-io/galaxy/tree/main/Buttons | pattern pool | buttons card | use interaction ideas only, not raw product copy |
| https://github.com/uiverse-io/galaxy/tree/main/Cards | pattern pool | cards card | good for depth and border treatment cues |
| https://github.com/uiverse-io/galaxy/tree/main/Inputs | pattern pool | inputs card | good for field framing cues |
| https://github.com/uiverse-io/galaxy/tree/main/Forms | pattern pool | forms card | use only for grouping rhythm and spacing |
| https://github.com/uiverse-io/galaxy/tree/main/Notifications | pattern pool | notifications card | use semantic structure, not flashy animation |
| https://github.com/uiverse-io/galaxy/tree/main/loaders | pattern pool | loaders card | use subtle motion only |
| https://github.com/uiverse-io/galaxy/blob/main/LICENSE | license | all galaxy-derived cards | MIT license, still avoid direct snippet dumping into product code |
```

- [ ] **Step 4: Add a discoverability rule to `AGENTS.md` so this repo explicitly points at the new skill**

```md
## Frontend design-reference workflow

- When a user explicitly asks for premium polish, stronger visual design, or inspiration from specific websites/products, use `frontend-design-reference` before `frontend-design` or implementation.
- Use `frontend-design-reference` to pick one primary style reference, at most one secondary reference, and the minimum necessary pattern categories.
- Do not paste raw `galaxy` snippets into product code; translate them into local components and existing shell patterns.
```

Place this section near the existing frontend conventions so it is easy to discover in the repo instructions.

- [ ] **Step 5: Re-copy the updated pattern index and source map into the live Copilot skill directory**

```bash
cp docs/superpowers/skills/frontend-design-reference/pattern-index.md /root/.copilot/skills/frontend-design-reference/pattern-index.md && \
cp docs/superpowers/skills/frontend-design-reference/source-map.md /root/.copilot/skills/frontend-design-reference/source-map.md
```

Expected: the deployed skill now has both page-level and component-level curated knowledge.

- [ ] **Step 6: Run a component-pattern smoke prompt**

```text
Prompt:
“把这个登录页做得更像专业产品，参考一些优秀网站，但先只给我设计 brief。”

Expected:
- one page-level style card is selected first
- only `buttons`, `inputs`, and optionally `cards` appear in the pattern plan
- output explicitly says not to paste raw Uiverse snippet code
```

- [ ] **Step 7: Commit the pattern taxonomy and repo discoverability update**

```bash
git add docs/superpowers/skills/frontend-design-reference/pattern-index.md \
        docs/superpowers/skills/frontend-design-reference/source-map.md \
        AGENTS.md && \
git commit -m "feat(skills): add frontend pattern index and repo guidance" \
           -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 5: Re-run the pressure scenarios, harden the copy, and finalize deployment

**Files:**
- Modify: `docs/superpowers/skills/frontend-design-reference/SKILL.md`
- Modify: `/root/.copilot/skills/frontend-design-reference/SKILL.md`
- Test: the four prompts from Task 1 plus one explicit mixed-reference prompt

- [ ] **Step 1: Re-run the three design-sensitive prompts from Task 1 with the new skill available**

```text
Pass criteria:
- the skill activates for design-quality requests
- the answer selects one primary reference and at most one secondary reference
- the answer names only the needed pattern categories
- the answer gives a do-not-do list before implementation
```

- [ ] **Step 2: Re-run the bugfix control prompt from Task 1**

```text
Pass criteria:
- no design-reference workflow is activated
- the answer stays focused on the functional bug
```

- [ ] **Step 3: Run one mixed-reference pressure prompt to catch collage behavior**

```text
Prompt:
“参考 Vercel、Linear、Framer、Stripe，把这个后台首页做得更惊艳。”

Expected:
- the skill refuses to mix all four
- the answer narrows to one primary and one secondary card
- the answer explains why the other two are excluded
```

- [ ] **Step 4: If any of the above prompts still fail, harden `SKILL.md` using one of these exact edits**

```md
## Failure Patches

- If the agent skips the brief:
  “Do not write code until you have produced the five-line design brief.”

- If the agent over-mixes styles:
  “If the user names more than two references, narrow them to one primary and one secondary before continuing.”

- If the agent copies snippets:
  “Treat `galaxy` as interaction inspiration only. Rebuild patterns using local components, local tokens, and project context.”

- If the agent triggers on bugfixes:
  “Stay inactive for bugfixes, refactors, and data-only tasks unless the user explicitly asks for visual redesign.”
```

- [ ] **Step 5: Re-copy the hardened `SKILL.md` into the live Copilot skill directory**

```bash
cp docs/superpowers/skills/frontend-design-reference/SKILL.md /root/.copilot/skills/frontend-design-reference/SKILL.md
```

Expected: the live deployed skill matches the final repo-tracked version exactly.

- [ ] **Step 6: Commit the hardened final copy**

```bash
git add docs/superpowers/skills/frontend-design-reference/SKILL.md && \
git commit -m "feat(skills): harden frontend design reference workflow" \
           -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
