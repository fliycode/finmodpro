# FinModPro LLaMA-Factory Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing `FineTuneRun` registry into a first-phase training control plane that can export LLaMA-Factory-compatible datasets, track external jobs, accept authenticated runner callbacks, and register successful artifacts back into the existing LiteLLM model-management flow.

**Architecture:** Keep training execution external. Django owns the control plane: `FineTuneRun` metadata, export manifests, callback tokens, and candidate model registration. A future LLaMA-Factory runner will pull an export bundle, execute training outside the app, and push status/artifact updates back through a scoped callback endpoint. Successful artifacts will be surfaced as `provider=litellm` candidate model configs instead of introducing a second runtime model path.

**Tech Stack:** Django models/services/controllers, existing `llm` admin APIs, JSON export bundles, filesystem-backed artifacts for phase one, LiteLLM-backed `ModelConfig`, Django test runner

---

## File Structure

- Modify: `backend/llm/models.py`
  Purpose: expand `FineTuneRun` from simple registry row into control-plane record with job metadata, export provenance, callback token hash, and deployment linkage
- Add: `backend/llm/migrations/0005_fine_tune_run_control_plane_fields.py`
  Purpose: persist new task/control-plane fields
- Modify: `backend/llm/serializers.py`
  Purpose: expose richer fine-tune data safely and validate creation/update payloads
- Modify: `backend/llm/services/fine_tune_service.py`
  Purpose: handle run creation, export bundle metadata, callback token generation/validation, and candidate model registration
- Add: `backend/llm/services/fine_tune_export_service.py`
  Purpose: build LLaMA-Factory-compatible export bundles and manifests
- Add: `backend/llm/services/fine_tune_callback_service.py`
  Purpose: verify callback tokens and apply scoped state/artifact updates
- Modify: `backend/llm/controllers/fine_tune_controller.py`
  Purpose: add export-detail and callback endpoints without changing existing admin registry entry points
- Modify: `backend/llm/tests.py`
  Purpose: lock control-plane behavior with model, API, and service regression coverage
- Modify: `frontend/src/api/llm.js`
  Purpose: normalize new run fields for the admin UI
- Modify: `frontend/src/components/ModelConfig.vue`
  Purpose: surface job state, export status, callback readiness, and artifact registration linkage without implying in-app GPU execution
- Modify: `backend/.env.example`
  Purpose: document export root and callback-secret configuration
- Modify: `backend/docs/dependency-services.md`
  Purpose: document the external LLaMA-Factory runner boundary and LiteLLM re-registration path

## Task 1: Lock the control-plane contract with failing tests

**Files:**
- Modify: `backend/llm/tests.py`

- [ ] **Step 1: Add failing model and service tests for richer FineTuneRun metadata**

Add tests that expect:

- `create_fine_tune_run()` generates a stable `run_key`
- a callback token is created once and only a hash is stored server-side
- export metadata is initialized in a structured JSON field
- a new run starts in explicit `pending` status with `queued_at` populated

- [ ] **Step 2: Add failing API tests for callback and candidate registration flow**

Add tests that expect:

- admin GET for fine-tune runs returns `run_key`, `runner_name`, `export_path`, `deployment_endpoint`, and `registered_model_config_id`
- runner callback endpoint rejects missing/invalid token
- successful callback can move `pending -> running -> succeeded`
- successful callback can write metrics and artifact manifest without requiring an admin session

- [ ] **Step 3: Run focused tests and confirm failure before implementation**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.FineTuneRunControlPlaneTests llm.tests.FineTuneRunCallbackApiTests -v 2
```

Expected: FAIL because the richer metadata fields, token flow, and callback endpoint do not exist yet.

- [ ] **Step 4: Commit**

```bash
cd /root/finmodpro
git add backend/llm/tests.py
git commit -m "Lock the fine-tune control-plane contract before wiring external training" -m "These tests move the existing registry toward a real control plane by pinning export metadata, callback-token behavior, and external runner state updates before implementation starts." -m "Constraint: Training execution must remain external and should not depend on an authenticated admin session\nRejected: Add fields and callbacks without contract tests | too easy to drift API semantics across admin and runner lanes\nConfidence: high\nScope-risk: narrow\nReversibility: clean\nDirective: Keep runner callbacks scoped to a single run and token; do not widen them into generic admin writes\nTested: Focused Django llm control-plane tests (expected fail before implementation)\nNot-tested: Full frontend/admin integration"
```

## Task 2: Expand FineTuneRun into a control-plane record

**Files:**
- Modify: `backend/llm/models.py`
- Add: `backend/llm/migrations/0005_fine_tune_run_control_plane_fields.py`
- Modify: `backend/llm/serializers.py`

- [ ] **Step 1: Add model fields for run identity, export metadata, and deployment linkage**

Introduce a minimal first-phase field set:

- indexed identifiers:
  - `run_key`
  - `external_job_id`
  - `runner_name`
- timing:
  - `queued_at`
  - `started_at`
  - `finished_at`
  - `last_heartbeat_at`
- JSON payloads:
  - `dataset_manifest`
  - `training_config`
  - `artifact_manifest`
- linkage:
  - `export_path`
  - `deployment_endpoint`
  - `deployment_model_name`
  - `registered_model_config` (nullable FK)
- security:
  - `callback_token_hash`

- [ ] **Step 2: Create migration and keep existing rows backward-compatible**

Requirements:

- existing rows remain readable
- nullable/new JSON fields default sanely
- existing `FineTuneRunSummarySerializer` callers do not break

- [ ] **Step 3: Expand serializers carefully**

Creation serializer should accept only control-plane-safe inputs:

- `base_model_id`
- dataset identity
- strategy
- optional training config summary
- optional runner hint

Update serializer should stay admin-only and avoid exposing raw token material.

- [ ] **Step 4: Run focused llm tests and migrate checks**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py makemigrations --check
backend/.venv/bin/python backend/manage.py test llm.tests.ModelConfigApiTests llm.tests.FineTuneRunControlPlaneTests -v 2
```

- [ ] **Step 5: Commit**

```bash
cd /root/finmodpro
git add backend/llm/models.py backend/llm/migrations/0005_fine_tune_run_control_plane_fields.py backend/llm/serializers.py
git commit -m "Give fine-tune runs enough structure to act as a training control plane" -m "The old registry fields were enough for manual bookkeeping but not enough for export provenance, callback verification, or deployment linkage. This change adds the minimum stable structure needed before any external runner is wired in." -m "Constraint: Existing admin registry views must remain readable during the transition\nRejected: Split into many new training domain tables in phase one | too much schema churn before the flow is proven\nConfidence: medium\nScope-risk: moderate\nReversibility: clean\nDirective: Prefer extending JSON payloads over multiplying relational tables until real runner traffic proves the shape\nTested: Migration check and focused llm tests\nNot-tested: Production data migration with large historical run volume"
```

## Task 3: Implement dataset export bundles and callback verification

**Files:**
- Add: `backend/llm/services/fine_tune_export_service.py`
- Add: `backend/llm/services/fine_tune_callback_service.py`
- Modify: `backend/llm/services/fine_tune_service.py`
- Modify: `backend/llm/controllers/fine_tune_controller.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add export settings**

Document and load:

- `FINE_TUNE_EXPORT_ROOT`
- `FINE_TUNE_CALLBACK_SECRET`
- optional `FINE_TUNE_EXPORT_BASE_URL`

- [ ] **Step 2: Build the export service**

Responsibilities:

- generate stable `run_key`
- create filesystem export directory
- write:
  - `manifest.json`
  - `dataset_info.json`
  - `train.jsonl`
  - optional `eval.jsonl`
  - `README.md`
- persist `export_path` and `dataset_manifest`

Phase-one simplification:

- allow synthetic/registry-backed placeholder sample export if no full supervised dataset builder exists yet
- mark placeholder exports explicitly in the manifest so they cannot be mistaken for production-quality datasets

- [ ] **Step 3: Build callback token and verification flow**

Requirements:

- generate opaque token on run creation
- store only a hash on the model
- expose the raw token only at create time to admins
- runner callback endpoint validates token against one run only

- [ ] **Step 4: Add callback and export-detail endpoints**

Add endpoints for:

- admin export detail / manifest download metadata
- runner callback update

Callback payload should support:

- `status`
- `external_job_id`
- `metrics`
- `artifact_manifest`
- `deployment_endpoint`
- `deployment_model_name`
- `failure_reason`

- [ ] **Step 5: Run focused control-plane tests**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm.tests.FineTuneRunControlPlaneTests llm.tests.FineTuneRunCallbackApiTests llm.tests.FineTuneRunExportServiceTests -v 2
```

- [ ] **Step 6: Commit**

```bash
cd /root/finmodpro
git add backend/llm/services/fine_tune_export_service.py backend/llm/services/fine_tune_callback_service.py backend/llm/services/fine_tune_service.py backend/llm/controllers/fine_tune_controller.py backend/.env.example backend/llm/tests.py
git commit -m "Make fine-tune runs exportable and externally updatable without admin-session coupling" -m "This introduces the actual control-plane mechanics: export bundles for LLaMA-Factory-compatible training input and a scoped callback path for external runners to report job progress and artifacts safely." -m "Constraint: External runners must not reuse interactive admin authentication\nRejected: Store raw callback tokens for later retrieval | avoid reversible secret storage in application data\nConfidence: medium\nScope-risk: moderate\nReversibility: clean\nDirective: Treat callback payloads as untrusted input and keep the accepted field set narrow\nTested: Focused llm export/callback tests\nNot-tested: Real LLaMA-Factory runner integration against live GPU infrastructure"
```

## Task 4: Register successful artifacts back into the LiteLLM model flow

**Files:**
- Modify: `backend/llm/services/fine_tune_service.py`
- Modify: `backend/llm/tests.py`
- Modify: `frontend/src/api/llm.js`
- Modify: `frontend/src/components/ModelConfig.vue`
- Modify: `backend/docs/dependency-services.md`

- [ ] **Step 1: Add candidate model registration logic**

Behavior:

- on successful callback with deployment info, optionally create a new inactive `ModelConfig(provider=\"litellm\")`
- set `model_name` to the reported LiteLLM alias or deployment model name
- set endpoint to the LiteLLM proxy
- link the created config back to `FineTuneRun.registered_model_config`

- [ ] **Step 2: Surface linkage in admin UI**

The admin page should show:

- whether export bundle exists
- whether callback token was issued
- whether an external job id exists
- whether an artifact was registered into a candidate model config

Keep wording explicit:

- training execution is external
- registration does not auto-activate the candidate model

- [ ] **Step 3: Add regression tests for candidate model registration**

Cover:

- successful callback creates inactive `litellm` candidate config
- duplicate success callbacks do not create duplicate model configs
- failed runs never auto-register a model

- [ ] **Step 4: Run backend + frontend verification**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test llm -v 2
cd frontend && npm test
```

- [ ] **Step 5: Commit**

```bash
cd /root/finmodpro
git add backend/llm/services/fine_tune_service.py backend/llm/tests.py frontend/src/api/llm.js frontend/src/components/ModelConfig.vue backend/docs/dependency-services.md
git commit -m "Route successful training artifacts back through the existing LiteLLM model boundary" -m "The control plane is only useful if successful runs can become candidate runtime models without opening a second serving path. This change keeps all trained-model activation decisions inside the existing ModelConfig and LiteLLM workflow." -m "Constraint: Application runtime must not learn a special-case path for self-trained models\nRejected: Point chat services directly at runner-reported endpoints | would fork runtime behavior away from LiteLLM governance\nConfidence: high\nScope-risk: moderate\nReversibility: clean\nDirective: Keep trained models inactive by default; activation must remain an explicit admin action\nTested: llm backend tests and frontend tests\nNot-tested: Live LiteLLM alias provisioning automation"
```

## Task 5: Final verification and delivery

**Files:**
- Modify as needed based on fixes from verification

- [ ] **Step 1: Run Django checks and focused regression suite**

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py check
backend/.venv/bin/python backend/manage.py test llm chat risk -v 1
```

- [ ] **Step 2: Run frontend and config verification**

```bash
cd /root/finmodpro/frontend && npm test
cd /root/finmodpro && docker compose -f docker-compose.prod.yml config
```

- [ ] **Step 3: Manual inspection checklist**

Confirm:

- fine-tune run creation returns raw callback token once
- admin list view never leaks stored token hash
- export path and manifest are visible
- successful callback can produce a candidate `litellm` model config
- no change implies in-app GPU training

- [ ] **Step 4: Final commit**

```bash
cd /root/finmodpro
git add backend/llm frontend/src/api/llm.js frontend/src/components/ModelConfig.vue backend/.env.example backend/docs/dependency-services.md docker-compose.prod.yml
git commit -m "Turn the fine-tune registry into a LLaMA-Factory-ready training control plane" -m "FinModPro now owns the orchestration metadata it was already hinting at: export bundles, callback-scoped status updates, and runtime-safe candidate model registration through LiteLLM. Training stays outside the app, but the platform can finally track and operationalize the result." -m "Constraint: Training execution remains external and repo-local verification cannot cover live GPU jobs\nRejected: Continue treating fine-tune runs as manual notes only | blocks reproducibility and artifact operationalization\nConfidence: medium\nScope-risk: broad\nReversibility: clean\nDirective: Keep future runner integrations behind the callback/export boundary; do not let direct GPU execution leak into the web app\nTested: Django checks, llm/chat/risk tests, frontend tests, docker compose config\nNot-tested: End-to-end training on a live LLaMA-Factory cluster"
```

## Verification Mapping

- FineTuneRun metadata/control-plane boundary: covered by Tasks 1-3
- Export bundle generation and callback security: covered by Task 3
- LiteLLM candidate registration: covered by Task 4
- Admin/UI compatibility and final regression: covered by Tasks 4-5
