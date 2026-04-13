# FinModPro Evaluation Enhancement Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve model evaluation from simple smoke records into comparison-oriented assessment that can show baseline, RAG-enhanced, and fine-tuned model behavior across QA and risk extraction tasks.

**Architecture:** Extend the existing `EvalRecord` model and `evaluation_service` rather than replacing them. Add the minimum extra fields needed for comparison workflows and update the evaluation UI so it becomes the central evidence surface for later model adaptation work.

**Tech Stack:** Django, existing llm app, Vue 3, current evaluation page, Django test runner, frontend build/test flow

---

## Scope

### In Scope

- Evaluation mode (`baseline`, `rag`, `fine_tuned`)
- Additional extraction metrics
- Dataset metadata
- Comparison-oriented list views
- Frontend grouped comparison display

### Out of Scope

- Large-scale automated benchmark orchestration
- Continuous online drift monitoring
- Separate experiment-tracking subsystem

## Locked Decisions

- Extend `EvalRecord` instead of introducing a second evaluation table.
- Keep old fields valid for backward compatibility.
- Comparison logic is server-assisted but UI-friendly.

## File Structure

- `backend/llm/models.py`
- `backend/llm/services/evaluation_service.py`
- `backend/llm/controllers/evaluation_controller.py`
- `backend/llm/tests.py`
- `frontend/src/api/llm.js`
- `frontend/src/components/EvaluationResult.vue`

## Data Model Extension

Add fields such as:

- `evaluation_mode`
- `precision`
- `recall`
- `f1_score`
- `dataset_name`
- `dataset_version`
- `run_notes`

## Task 1: Add failing backend tests

**Files:**
- Modify: `backend/llm/tests.py`

- [ ] **Step 1: Add tests for new metrics and comparison grouping**
- [ ] **Step 2: Run failing tests**

```bash
cd backend && python manage.py test llm -v 2
```

Expected: FAIL on missing fields or comparison behavior

## Task 2: Extend backend evaluation model and API

**Files:**
- Modify: `backend/llm/models.py`
- Modify: `backend/llm/services/evaluation_service.py`
- Modify: `backend/llm/controllers/evaluation_controller.py`

- [ ] **Step 1: Add model fields and migration**
- [ ] **Step 2: Extend service logic for grouped comparison payloads**
- [ ] **Step 3: Extend list/create API**
- [ ] **Step 4: Verify backend**

```bash
cd backend && python manage.py test llm -v 2
```

Expected: PASS

## Task 3: Extend frontend evaluation page

**Files:**
- Modify: `frontend/src/api/llm.js`
- Modify: `frontend/src/components/EvaluationResult.vue`

- [ ] **Step 1: Add API normalization for new fields**
- [ ] **Step 2: Render grouped baseline/RAG/fine-tuned comparisons**
- [ ] **Step 3: Verify frontend**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS

## Task 4: Final verification and commit

- [ ] **Step 1: Run combined verification**

```bash
cd backend && python manage.py test llm -v 2
cd frontend && npm test
cd frontend && npm run build
```

- [ ] **Step 2: Commit**

```bash
git add backend/llm frontend/src/api/llm.js frontend/src/components/EvaluationResult.vue docs/superpowers/plans/2026-04-13-finmodpro-evaluation-enhancement-phase5.md
git commit -m "feat(platform): enhance model evaluation comparisons"
```

## Acceptance Checklist

- [ ] Evaluation records support comparison-oriented metadata
- [ ] QA and extraction metrics can be displayed together
- [ ] UI clearly shows baseline vs RAG vs fine-tuned runs
