# Product

## Register

product

## Users

Two personas, equal weight:

**Financial analysts** use the workspace to run risk analysis, sentiment assessment, and LLM-powered Q&A against domain knowledge bases. They operate in investigation mode — pulling threads, cross-referencing sources, building a picture of risk exposure. Their context is focused desk work during market or review hours.

**System administrators** manage the LLM gateway: model routing, observability, cost tracking, knowledge bases, fine-tuning pipelines, user permissions, and evaluation results. They operate in oversight mode — monitoring health, optimizing throughput, debugging failures. Their context is operational, often time-sensitive.

## Product Purpose

FinModPro is a financial risk-control platform that leverages domain-specific LLMs to accelerate risk analysis workflows. It exists to give analysts and operators a single surface for running AI-assisted risk investigations and managing the underlying model infrastructure.

## Brand Personality

Precise, composed, authoritative. Confident expert tool with no decorative excess. The interface speaks with restraint — it trusts the user's competence and never shouts when a signal will do.

## Anti-references

- **Generic SaaS dashboards** — the standard blue-white template with icon cards, gradient hero stats, and identical card grids. Avoid the "any-company dashboard" look.
- **Consumer fintech** — neobank and payment-app aesthetics (Robinhood, Revolut). Too casual, too animated, wrong energy for risk work.
- **Legacy enterprise** — Bloomberg-terminal density, SAP-style gray forms, dated table-heavy layouts from the 2000s.

## Design Principles

1. **Expert confidence** — The interface assumes domain competence. No hand-holding tooltips, no decorative explainers. Every element justifies its presence.
2. **Dual-mode clarity** — Analyst workspace and admin war room are visually distinct but structurally coherent. Each mode serves its persona without compromise, and the transition between them feels intentional.
3. **Information density with intent** — High-value data gets generous space. Low-value chrome recedes. Neither Bloomberg-dense nor consumer-sparse. Precision in what's surfaced and what's deferred.
4. **Composed under pressure** — Risk work is serious. The interface stays calm and controlled even when the data is alarming. Risk alerts are measured signals, not panic buttons.
5. **Trust through consistency** — A risk-control platform must feel reliable. Predictable interactions, stable layout, no surprising behavior. Correctness in every detail.

## Accessibility & Inclusion

Target: WCAG AA compliance. Contrast ratios ≥4.5:1 for text, ≥3:1 for large text and UI components. Full keyboard navigation with visible focus indicators. Semantic HTML with proper heading hierarchy and landmark regions. Form inputs with associated labels and clear error states. Respect `prefers-reduced-motion` for animations. Test color-blindness safety for the dual-theme palette (workspace warm tones, admin cool tones).
