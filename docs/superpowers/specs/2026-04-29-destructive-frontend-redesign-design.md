# Destructive Frontend Redesign Design

## Problem

The authenticated FinModPro frontend currently uses a mostly uniform shell and a consistent blue-gray visual system across both `/workspace` and `/admin`. The product logic, permissions, route model, and API integrations are functional, but the visual language, page structure, and component boundaries no longer create enough contrast between user work and platform operations. The redesign must preserve data logic and core interactions while replacing the entire authenticated presentation layer with a visibly different system.

## Scope

### In scope

- All authenticated frontend surfaces under `/workspace/*` and `/admin/*`
- Shared authenticated shells, navigation, section framing, and page-level composition
- Page information order and grouping
- Component decomposition for redesigned pages
- Responsive behavior for authenticated surfaces
- Motion, transitions, and loading treatments for redesigned surfaces
- A destructive audit table proving the redesign crossed multiple design dimensions

### Out of scope

- `/login` and its surrounding authenticated entry design
- Backend APIs, payload contracts, permission rules, and route guards
- Core business behavior such as chat flow, knowledge retrieval, risk generation, sentiment analysis, model operations, and user administration semantics
- A route map rewrite that would require backend or authorization changes

## Design brief

- **Primary reference:** Mastercard, only for warm financial trust, editorial rhythm, and composed information flow
- **Secondary reference:** Sentry, only for deep dark operations surfaces and telemetry-oriented control density
- **Register split:** workspace and admin intentionally diverge into two strong visual personalities rather than sharing one softened compromise
- **Core promise:** keep the product working, but make the user side feel like a live financial dossier and the admin side feel like a model war room

## Experience direction

### Workspace

Workspace becomes a **financial dossier canvas**. It should feel like reading and acting on a living case file rather than using a generic app dashboard. The page rhythm is vertical, editorial, and evidence-led. Users should move from conclusion to supporting material to action with minimal chrome competing for attention.

#### Workspace visual language

- Warm paper-like neutrals instead of the current cold blue-gray product palette
- Editorial display type for headings, paired with a highly legible Chinese sans-serif for body content
- Higher contrast between heading and body rhythm, with tighter heading tracking and looser reading blocks
- Surfaces inspired by folders, tickets, annotations, evidence slips, and pinned excerpts rather than generic product cards
- Motion based on reveal, slide, highlight, and drawer expansion, not decorative hover-heavy activity

### Admin

Admin becomes a **war room operations console**. It should feel like a late-night command center for routing, observability, evaluation, and governance. The interface should prioritize situational awareness, operational state, and inspection depth over friendly dashboard tropes.

#### Admin visual language

- Deep navy-charcoal neutrals, explicitly avoiding pure black
- Accent usage constrained to semantic state, active focus, warnings, and telemetry emphasis
- Denser type rhythm, stronger timestamp and label presence, faster scanning
- Thin-line partitions, status bands, monitor slices, and inspector drawers instead of soft white cards
- Motion based on panel push, alert pulse, wipe refresh, and focused expansion using only transform and opacity

## Information architecture

The route map remains broadly intact to avoid unnecessary logic churn. The redesign changes what each page prioritizes and how information is grouped.

### Workspace page model

#### `/workspace/qa`

This becomes the primary canvas page. The layout shifts from a standard page wrapper around chat to a three-region working surface:

1. **Conversation region** for the active dialog and input orchestration
2. **Answer dossier region** for the current result as a structured narrative artifact
3. **Evidence rail** for source excerpts, knowledge hits, and supporting references

The key change is that the answer is no longer just output below a chat interface. It is promoted into the central artifact of the page.

#### `/workspace/knowledge`

This becomes an archive desk. The page is reorganized into:

1. **Filter spine** across the top for search, state, ingestion, and dataset filtering
2. **Asset ledger** as the primary list of managed knowledge assets
3. **Detail panel** for document metadata and management actions
4. **Chunk preview** for content inspection and provenance

On wide screens, multiple regions can remain visible together instead of forcing serial interaction.

#### `/workspace/risk` and `/workspace/sentiment`

These become dossier pages with the same content rhythm:

1. **Conclusion first**
2. **Evidence and sources second**
3. **Timeline or supporting sequence third**
4. **Export and follow-up actions last**

This intentionally reverses the common tool-first layout. Users should see the synthesized result before being asked how to manipulate it.

#### `/workspace/history` and `/workspace/profile`

These remain important but become quieter support surfaces. Their role is contextual continuity, not visual leadership.

### Admin page model

#### `/admin/overview` and `/admin/llm`

These form the war room entry sequence. The top layer emphasizes:

1. Live operational state
2. Routing health
3. Priority alerts
4. High-signal governance or cost anomalies

Only after this top-layer scan should the operator descend into specific model or routing controls.

#### `/admin/llm/models`, `/admin/llm/observability`, `/admin/llm/costs`, `/admin/llm/fine-tunes`

These become one visual family built around:

1. **Status band** for current system state
2. **Command deck** for the main operational interface
3. **Inspector drawer** for secondary detail, logs, or parameter inspection

This shared structure keeps the admin side cohesive even as each route handles different operational content.

#### `/admin/users` and `/admin/evaluation`

These become governance review surfaces. The design should emphasize lists, comparison, review state, and decision confidence rather than decorative summary metrics.

## Layout system

The redesign intentionally rejects the current single-shell sameness.

### Workspace layout

- Desktop uses a dossier-style reading spine with optional side evidence support
- Wide screens can keep source context visible without interrupting the reading flow
- Sections should feel like chapters and inserts, not dashboard modules
- The page structure can use asymmetry and anchored marginalia where it improves evidence reading

### Admin layout

- Desktop uses a command-center composition with horizontal status framing and sectional slicing
- Dense panels can coexist, but hierarchy must stay explicit
- Monitor-like segmentation is preferred over evenly spaced card grids
- Inspection UI should be able to slide, dock, or overlay without collapsing the main operational view

## Responsive strategy

The redesign does not simply collapse the desktop view into a narrower version of the same shell.

### Workspace responsive behavior

- **Wide desktop:** multi-region dossier with persistent support columns where useful
- **Medium screens:** secondary evidence content collapses into drawers or toggled rails
- **Mobile:** chapter-based canvas model, where answer, evidence, sources, and actions become switchable sections rather than one long stacked scroll

### Admin responsive behavior

- **Wide desktop:** full war room with persistent status framing
- **Tablet:** horizontal monitor slices and full-width drawers replace side inspection panels
- **Mobile:** triaged mode focused on overview, alerts, and high-value actions, with secondary configuration reduced or deferred

## Component architecture

Every redesigned page must be split more aggressively than the current implementation. Large page components should be decomposed into shell, surface, and adapter roles.

### Required split pattern

1. **Shell components** handle page composition and region layout only
2. **Surface components** render one bounded content artifact or control region only
3. **State or adapter components** bridge existing APIs, route params, and derived state into the new visual structure

### Example target splits

#### QA page

- `ConversationCanvas`
- `AnswerDossier`
- `EvidenceRail`

#### Admin overview

- `OpsStatusBand`
- `OpsCommandDeck`
- `OpsInspectorDrawer`

The exact filenames can evolve during implementation, but every major page should follow this decomposition discipline.

## Motion and interaction

Motion must support interpretation, not decorate emptiness.

### Workspace motion

- Section reveals with staggered opacity and translation
- Evidence highlight transitions when context changes
- Drawer and annotation movement that reinforces reading order
- Loading treatments that look like dossier placeholders or structured skeletons, not circular spinners

### Admin motion

- Alert pulse reserved for meaningful state change
- Panel refresh wipes or glow passes for live updates
- Inspector drawer push transitions that preserve user orientation
- Faster cadence than workspace, but still restrained and transform-only

## Anti-slop constraints

The redesign must explicitly avoid the most common AI-generated frontend defaults.

- No Inter, Arial, Roboto, or system-default generic typography as the defining face
- No purple-to-blue AI gradient styling
- No equal-width three-card rows as the primary layout trope
- No pure `#000000`
- No default Lucide-like icon language as the entire icon strategy
- No `h-screen` layout dependency
- No circular spinner as the dominant loading pattern
- No centered SaaS hero pattern for authenticated pages

## Preservation boundaries

The redesign preserves:

- Existing API integrations
- Existing auth/session behavior
- Existing route semantics where feasible
- Existing permission checks and route gating
- Existing core actions and outcomes

The redesign replaces:

- Visual tokens for authenticated surfaces
- Layout primitives and authenticated shell composition
- Page-specific markup and class naming
- Component boundaries for major pages
- Information order within pages
- Interaction styling and motion treatment

## Testing implications

Implementation should update or add frontend tests around:

- Route and navigation continuity
- Critical page states after structural decomposition
- Any extracted adapters or page-model helpers introduced during redesign
- Authenticated shell behavior that must survive the visual rewrite

The redesign should be implemented test-first for changed behavior and structure-sensitive logic.

## Destructive audit table

| Dimension | Before | After |
| --- | --- | --- |
| Layout system | Shared app-shell pattern with similar workspace/admin framing | Workspace dossier canvas and admin war room split into separate structural systems |
| Color system | Blue-gray institutional palette across authenticated pages | Warm editorial neutrals for workspace and deep navy-charcoal telemetry palette for admin |
| Typography | Uniform product-style sans hierarchy | Editorial reading hierarchy for workspace and denser command typography for admin |
| Component shape | Rounded product cards and standard section containers | Ticket, folder, drawer, status-band, and monitor-slice surfaces |
| Information order | Tool-first, page-title-first, dashboard-like grouping | Conclusion-first, evidence-first, operational-state-first grouping |
| Motion | Limited product UI hover and standard transitions | Reading-oriented reveal for workspace and command-center push/pulse motion for admin |
| Responsive strategy | Mostly shell collapse and stacking | Chapter-based mobile workspace and triaged admin war room modes |
| Component boundaries | Many pages wrapped around large existing components | Forced split into shell, surface, and adapter components per major page |

## Success criteria

The redesign is successful when:

1. Logged-in users can still complete the same core tasks without backend changes
2. `/workspace` and `/admin` feel like intentionally different environments
3. The new UI is visibly unlike the prior authenticated design across at least six design dimensions
4. The login page remains unchanged
5. The final implementation includes a destructive audit artifact matching the delivered UI
