---
name: frontend-design-reference
description: Use when the user explicitly asks for higher frontend design quality, reference websites, or a more premium visual direction for a page or component
---

# Frontend Design Reference

Use this skill before `frontend-design` or implementation when the user clearly wants stronger visual quality or reference-driven frontend work.

## Trigger Phrases
- 高级感 / premium / polished
- 参考优秀网站 / reference websites
- 更像专业产品
- 重做视觉 / redesign
- 像 Vercel / Linear / Coinbase 这种感觉

## Workflow
1. Choose one primary style card from `style-index.md`.
2. Choose at most one secondary style card.
3. Inspect only the needed categories in `pattern-index.md`.
4. Write a brief before implementation:
   - Primary reference
   - Secondary reference
   - Page structure
   - Component patterns
   - Do-not-do list

If the supporting indexes are still placeholders, stop after the brief structure and say that curated cards are not populated yet.

## Quick Reference
- One primary style reference.
- At most one secondary style reference.
- At most three pattern categories.
- Five-line brief before code.

## Hard Rules
- Never mix more than two style references.
- If the user names more than two references, narrow them to one primary and one secondary before continuing.
- Never use more than three pattern categories at once.
- Do not write code until the brief is complete.
- Treat `galaxy` as interaction inspiration only. Rebuild patterns with local components, local tokens, and project context.
- Never use another product as a 1:1 brand clone target.
- Stay inactive for bugfix-only or data-plumbing tasks.

## Red Flags
- “This looks generic but good enough”
- “I can just copy this snippet”
- “I do not need a brief before coding”
- “The user said premium, but I can freestyle”

## Common Mistakes
- Mixing too many brand directions instead of picking one dominant reference.
- Borrowing a snippet literally instead of translating its interaction idea.
- Jumping into implementation before the brief locks the page structure and constraints.
