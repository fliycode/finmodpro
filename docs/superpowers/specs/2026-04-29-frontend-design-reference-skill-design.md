# Frontend Design Reference Skill Design

## Goal

Create an independent skill that helps an agent reliably switch into a reference-driven design workflow when a user explicitly asks for higher design quality, stronger visual polish, or inspiration from strong frontend products.

The skill should make two external sources actually usable during design work:

1. `awesome-design-md` as a source of macro visual language and product archetypes.
2. `galaxy` as a source of micro interaction and component pattern inspiration.

## Problem Statement

Agents are usually aware that design inspiration exists, but they often do not operationalize it well. In practice, they fall into one of three failure modes:

1. They do not proactively consult any reference source even when the user clearly asks for a stronger visual outcome.
2. They consult references in an ad hoc way, which leads to shallow borrowing or inconsistent style mixing.
3. They over-apply raw snippets or brand mimicry, producing collage-like UI rather than a coherent product design.

The goal is not to build a full design search engine. The goal is to create a low-noise skill that changes the agent's decision path:

- detect when design quality is the real ask
- pick a style direction before implementation
- use component inspiration selectively
- convert references into implementation constraints instead of direct copying

## Source Constraints And Opportunities

The two source repositories are useful in different ways and should not be treated symmetrically.

### `awesome-design-md`

This source is most valuable as a style taxonomy. It groups many product aesthetics such as Vercel, Coinbase, Linear, Framer, and others into recognizable design archetypes.

However, the repository itself primarily acts as an index of design entries and external links. The per-site folders do not reliably contain full local `DESIGN.md` documents. This makes full local mirroring a poor first move.

Design implication:

- build a local distilled style index rather than trying to mirror the whole source
- preserve source URLs so the index can be expanded later

### `galaxy`

This source is most valuable as a component-pattern pool. It contains a very large number of categorized HTML snippets such as buttons, cards, inputs, forms, notifications, loaders, and patterns.

Its scale is also its risk. Pulling it into the agent workflow without curation encourages snippet-driven design and over-stylized UI.

Design implication:

- use `galaxy` as a curated pattern source, not as a drop-in component library
- index categories and interaction styles, not raw bulk content

## Design Summary

Build a new independent skill with a thin `SKILL.md` and a small set of local markdown indexes. The skill should trigger only when the user explicitly signals that visual quality matters. Once triggered, it should guide the agent through a strict sequence:

1. classify the request as design-sensitive
2. choose one primary style reference and at most one secondary reference
3. choose only the component categories needed for the current page
4. translate the references into project-appropriate design constraints
5. move into implementation only after producing a brief design direction

The skill should bias toward coherence over breadth. It should prefer a small number of well-described local reference cards over large raw mirrors.

## Approach Options

### Option A: Prompt-Only Reference Skill

Create only a `SKILL.md` with instructions to consult the external sources when frontend polish is requested.

Pros:

- smallest implementation footprint
- lowest maintenance cost

Cons:

- the agent still depends on real-time searching
- reference usage remains inconsistent
- likely to be forgotten or applied shallowly

### Option B: Independent Skill With Local Curated Indexes

Create a dedicated skill plus local markdown indexes for style references and pattern references.

Pros:

- stable low-noise retrieval path
- much better odds that the agent actually uses the references
- easier to keep aligned with the intended workflow

Cons:

- requires one-time curation effort
- needs occasional refresh as source ecosystems evolve

### Option C: Large Local Mirror With Retrieval Layer

Mirror as much source material as possible locally and add scripts to search it.

Pros:

- highest reference coverage

Cons:

- highest maintenance cost
- much noisier agent experience
- low leverage because `awesome-design-md` is not a clean full-content mirror source

### Recommendation

Use Option B.

It captures the strongest parts of both sources without importing their worst trade-offs. The agent gets a reliable retrieval surface, but remains focused on making design decisions rather than browsing massive raw archives.

## Trigger Conditions And Role Boundaries

The skill should activate only when the user clearly signals that visual design quality matters.

### Positive Triggers

Examples of likely triggers:

- “make it feel more premium”
- “参考优秀网站”
- “提升设计质量”
- “更像专业产品”
- “重做这个 landing page”
- “让这个后台更高级”
- “参考 Vercel / Linear / Coinbase 这种感觉”

### Non-Triggers

The skill should not activate for:

- pure bug fixes
- data plumbing tasks
- backend changes
- ordinary CRUD UI work without a stated visual-design goal

### Role Boundary

This skill does not directly generate the final page design by itself. Its job is to switch the agent from default implementation mode into a reference-driven design mode.

It is responsible for:

- deciding whether reference-driven design is needed
- selecting a small set of relevant references
- converting those references into constraints and guidance

It is not responsible for:

- directly copying source snippets
- reproducing another product's branding
- forcing design exploration when the task is not design-sensitive

## Skill Package Structure

The skill package should remain markdown-first and easy for an agent to scan.

### Proposed Files

1. `SKILL.md`
2. `style-index.md`
3. `pattern-index.md`
4. `source-map.md`

### `SKILL.md`

This file should contain:

- triggering conditions
- decision flow
- maximum mixing rules
- brief output contract
- anti-patterns and red flags

### `style-index.md`

This file should contain 15 to 25 distilled style cards derived from `awesome-design-md`.

Each style card should include:

- `name`
- `archetype`
- `best-for`
- `signals`
- `avoid`
- `source`

Example direction:

- `vercel` → monochrome precision, infrastructure-grade clarity
- `coinbase` → blue institutional trust, fintech restraint
- `linear` → ultra-minimal product precision with tight hierarchy

### `pattern-index.md`

This file should contain curated component-pattern cards derived from `galaxy`, grouped by category rather than by raw snippet dump.

Each pattern card should include:

- `category`
- `interaction-style`
- `safe-use`
- `avoid`
- `source examples`

Typical categories:

- buttons
- cards
- inputs
- forms
- notifications
- loaders

### `source-map.md`

This file should record:

- original repository or page URL
- any noteworthy access limitation
- a short note about why the source belongs in the curated set

This creates an audit trail and makes later refresh work safer.

## Agent Workflow

The skill should enforce the following sequence.

### 1. Detect Design-Sensitive Intent

If the user clearly asks for stronger design quality or reference-driven redesign, load the skill workflow.

### 2. Select Page-Level Style Direction First

Choose one primary style reference and at most one secondary style reference from `style-index.md`.

Rules:

- the primary reference defines the dominant page character
- the secondary reference can contribute only a small number of traits
- do not mix more than two style references

### 3. Select Only Relevant Component Categories

From `pattern-index.md`, inspect only the categories needed for the current page or component.

Examples:

- auth page → buttons, inputs, cards
- admin dashboard → cards, navigation-adjacent patterns, filters, notifications
- marketing landing page → cards, buttons, forms, layout patterns

Do not preload unrelated categories.

### 4. Convert References Into A Design Brief

Before implementation, the agent should produce a short design brief that includes:

- primary and secondary references
- key page-level constraints
- component-level inspiration areas
- explicit “do not do” rules

### 5. Hand Off To Implementation

Only after the brief is formed should the agent continue into frontend design or implementation work.

## Guardrails And Failure Handling

### Hard Guardrails

1. Do not paste raw `galaxy` snippets into the product as-is.
2. Do not use `awesome-design-md` as a brand cloning system.
3. Do not mix more than two style references.
4. Do not use more than three component categories at once unless the page truly demands it.

### Priority Rules

- page-level coherence outranks local flourish
- the primary style reference outranks the secondary one
- product fit outranks visual novelty

### Failure Handling

If no precise style match exists:

- choose the two closest local style cards
- explain the gap briefly
- fall back to a restrained, coherent default rather than an unconstrained invention

If the pattern candidates are too decorative:

- mark them unsuitable for enterprise or institutional contexts
- retain only the transferable interaction idea

If the source content is partially inaccessible:

- continue using the local distilled cards
- do not block the workflow on source retrieval

## Testing Strategy

This skill should not be written and deployed without explicit scenario testing.

### RED: Baseline Without Skill

Run a set of design-sensitive prompts without the skill and record failures.

Suggested prompts:

- “做一个高级感的 SaaS 登录页”
- “把这个后台首页做得更像专业产品”
- “参考优秀网站重做这个 landing page”

Expected baseline failure patterns:

- no reference usage
- reference usage without selection discipline
- direct snippet-style thinking
- implementation before design brief

### GREEN: Re-Run With Skill

Run the same scenarios with the skill installed.

Expected behaviors:

- the skill is triggered when the prompt clearly asks for stronger design quality
- the agent chooses one primary and one optional secondary style reference
- the agent narrows pattern lookup to relevant component categories
- the agent outputs a brief before implementation

### REFACTOR: Close Loopholes

Common loopholes to watch for:

- the agent mentions references but does not actually use the local indexes
- the agent selects too many references
- the agent copies local inspiration too literally
- the agent skips the design brief and goes straight to implementation

The skill should be refined until those behaviors are explicitly countered.

## Acceptance Criteria

The design is successful when all of the following are true:

1. The skill triggers reliably for explicitly design-quality-driven frontend tasks.
2. The skill stays inactive for ordinary non-design frontend work.
3. The agent uses `style-index.md` for page-level direction and `pattern-index.md` for selective component inspiration.
4. The agent produces a brief design direction before implementation.
5. The workflow reduces collage-like results and improves visual coherence.
6. The curated local index remains small enough for an agent to scan quickly.
7. The design remains useful even when the original source content is only partially accessible.

## Out Of Scope

This design does not include:

- building a full design search product
- mirroring every external source locally
- automatically generating Figma-equivalent design systems
- enforcing visual outcomes for tasks that do not ask for design quality
