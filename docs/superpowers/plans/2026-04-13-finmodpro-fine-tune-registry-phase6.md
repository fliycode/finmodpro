# FinModPro Fine-Tune Registry Phase 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a platform-managed registry for LoRA/fine-tune runs and model lineage so FinModPro can track domain adaptation work even before full online training orchestration exists.

**Architecture:** Keep actual training execution external for now and build a registry/tracking layer inside the existing `llm` app. Tie fine-tune runs to base models and dataset metadata, and let admins inspect and activate resulting model candidates through the current model management surface.

**Tech Stack:** Django, existing llm app, Vue 3, current model config page, Django test runner, frontend build/test flow

---

## Scope

### In Scope

- Fine-tune run registry
- Base model linkage
- Dataset linkage metadata
- Artifact path/status tracking
- Model lineage display in admin UI

### Out of Scope

- Full in-platform training execution
- GPU job scheduler
- Auto-deployment pipeline for trained artifacts

## Locked Decisions

- Keep training external in this phase.
- Do not fake online training if only registration exists.
- Fine-tuned model lineage must be queryable from the existing admin model page.

## File Structure

- `backend/llm/models.py`
- `backend/llm/services/fine_tune_service.py`
- `backend/llm/controllers/fine_tune_controller.py`
- `backend/llm/urls.py`
- `backend/llm/tests.py`
- `frontend/src/api/llm.js`
- `frontend/src/components/ModelConfig.vue`

## Data Model

Suggested shape:

```python
class FineTuneRun(models.Model):
    base_model = models.ForeignKey(ModelConfig, related_name="fine_tune_runs", on_delete=models.CASCADE)
    dataset_name = models.CharField(max_length=255)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    strategy = models.CharField(max_length=64, default="lora")
    status = models.CharField(max_length=32, default="pending")
    artifact_path = models.CharField(max_length=500, blank=True, default="")
    metrics = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## Task 1: Add failing backend tests

**Files:**
- Modify: `backend/llm/tests.py`

- [ ] **Step 1: Add fine-tune run CRUD/list tests**
- [ ] **Step 2: Run failing tests**

```bash
cd backend && python manage.py test llm -v 2
```

Expected: FAIL on missing fine-tune registry components

## Task 2: Implement backend registry

**Files:**
- Modify: `backend/llm/models.py`
- Create: `backend/llm/services/fine_tune_service.py`
- Create: `backend/llm/controllers/fine_tune_controller.py`
- Modify: `backend/llm/urls.py`

- [ ] **Step 1: Add model and migration**
- [ ] **Step 2: Add service helpers for create/list/update**
- [ ] **Step 3: Mount fine-tune endpoints**
- [ ] **Step 4: Verify backend**

```bash
cd backend && python manage.py test llm -v 2
```

Expected: PASS

## Task 3: Extend admin model management UI

**Files:**
- Modify: `frontend/src/api/llm.js`
- Modify: `frontend/src/components/ModelConfig.vue`

- [ ] **Step 1: Add fine-tune API methods**
- [ ] **Step 2: Add lineage/run history presentation to model page**
- [ ] **Step 3: Keep “activation” flow explicit between base and fine-tuned candidates**
- [ ] **Step 4: Verify frontend**

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
git add backend/llm frontend/src/api/llm.js frontend/src/components/ModelConfig.vue docs/superpowers/plans/2026-04-13-finmodpro-fine-tune-registry-phase6.md
git commit -m "feat(platform): add fine-tune registry and lineage"
```

## Acceptance Checklist

- [ ] Fine-tune runs can be registered and listed
- [ ] Base model and dataset metadata are tracked
- [ ] Admin UI shows lineage and candidate activation context
- [ ] Platform is explicit that training execution remains external
