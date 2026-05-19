# AD Delivery Sync Batch Create and Apple Status Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse the Apple monitor lookup result exactly once, then batch-create new delivery-table rows for approved five-image apps while skipping any existing AppleId without updating it.

**Architecture:** `monitor_apple.py` remains the only place that calls Apple lookup and decides whether a package is online. After a version is confirmed online, it hands off a compact approved-item payload to `ad_delivery_sync`, which performs only delivery eligibility checks, AppleId dedupe, target-table existence checks, and Feishu write orchestration. Feishu batch-create request construction, `user_id_type="open_id"`, chunking, and created-id counting stay inside `feishu_service`.

**Tech Stack:** Python, `lark_oapi` Bitable SDK, `unittest`

---

### File Responsibilities

- `monitor_apple.py`
  Owns Apple lookup, online decision, and construction of approved delivery items.
- `models/delivery.py`
  Owns the compact post-lookup payload model and the typed `app_status` contract that delivery sync consumes.
- `services/ad_delivery_sync.py`
  Owns delivery eligibility filtering, duplicate skipping, field mapping, and deciding which rows should be created.
- `services/feishu_service.py`
  Owns Feishu SDK request construction for single-row utilities plus new batch-create primitives, including chunk size handling.
- `tests/test_batch_apple_lookup.py`
  Owns monitor-flow assertions, including proof that the Apple lookup result is handed off once and only online items reach delivery sync.
- `tests/test_delivery_sync.py`
  Owns delivery-sync behavior assertions, including skip-existing, same-run dedupe, batch-create payload shape, and chunking.

---

### Task 1: Replace delivery re-resolution with a post-lookup approved-item handoff

**Files:**
- Modify: `models/delivery.py`
- Modify: `monitor_apple.py`
- Modify: `services/ad_delivery_sync.py`
- Test: `tests/test_batch_apple_lookup.py`
- Test: `tests/test_delivery_sync.py`

- [ ] **Step 1: Write the failing tests**

Add or extend tests to cover:

```python
def test_run_passes_only_online_items_with_app_status_to_delivery_sync():
    ...
```

and

```python
def test_sync_delivery_records_does_not_require_apple_service_lookup():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m unittest \
  tests.test_batch_apple_lookup.AppleMonitorBatchLookupTests.test_run_passes_only_online_items_with_app_status_to_delivery_sync \
  tests.test_delivery_sync.DeliverySyncTests.test_sync_delivery_records_does_not_require_apple_service_lookup -v
```

Expected:
- monitor test fails because the handoff still passes raw records only
- delivery-sync test fails because the service still depends on `AppleStoreService` or performs a second lookup

- [ ] **Step 3: Write minimal implementation**

Refactor to a compact post-lookup payload model in `models/delivery.py`. Do not keep three overlapping wrappers. Remove `AdDeliveryCandidate` and make `sync_delivery_records` accept only the post-lookup payload. The payload should contain:
- `parent_record`
- `current_record`
- `apple_id`
- `app_status`

Define `app_status` as an explicit typed dict or dataclass with the fields currently used downstream:
- `track_view_url`
- `track_name`
- `version`
- `release_date`
- `current_version_release_date`
- `is_online`

Then:
- have `monitor_apple.py` append this payload only after `is_version_online` is true
- pass the payload list into `sync_delivery_records`
- remove Apple lookup responsibility from `AdDeliverySyncService`
- remove the `AppleStoreService` dependency from `AdDeliverySyncService`
- remove the old `collect_delivery_candidates(records: List[ApplePackageRecord])` path rather than keeping two sync entrypoints

- [ ] **Step 4: Run tests to verify they pass**

Run the same command from Step 2.

Expected:
- PASS
- `delivery_sync_service.sync_delivery_records(...)` receives payload items that already contain `app_status`
- no delivery-layer Apple lookup path remains

- [ ] **Step 5: Commit**

```bash
git add models/delivery.py monitor_apple.py services/ad_delivery_sync.py tests/test_batch_apple_lookup.py tests/test_delivery_sync.py
git commit -m "refactor: hand off approved delivery items from monitor"
```

### Task 2: Batch-create new delivery rows with table-wide existence checks and same-run dedupe

**Files:**
- Modify: `services/feishu_service.py`
- Modify: `services/ad_delivery_sync.py`
- Test: `tests/test_delivery_sync.py`

- [ ] **Step 1: Write the failing tests**

Add or extend tests to cover:

```python
def test_sync_delivery_records_batch_creates_multiple_new_rows_once():
    ...
```

```python
def test_sync_delivery_records_skips_existing_and_same_run_duplicate_apple_ids():
    ...
```

```python
def test_sync_delivery_records_reads_target_table_once_and_normalizes_apple_id():
    ...
```

```python
def test_batch_create_records_uses_open_id_and_chunks_payload():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m unittest tests.test_delivery_sync -v
```

Expected:
- FAIL because the sync still creates rows one-by-one
- FAIL because same-run duplicate AppleIds are not explicitly deduped pre-batch
- FAIL because no batch-create primitive exists

- [ ] **Step 3: Write minimal implementation**

In `feishu_service.py` add a batch-create primitive that:
- accepts a list of `fields` payloads
- uses `BatchCreateAppTableRecordRequest`
- always passes `user_id_type="open_id"`
- splits requests by an explicit local `batch_size` constant
- returns created record ids per chunk so `synced_count` can be derived from successful creates only
- treats partial success as “count successful rows, do not retry per-record in v1”

In `ad_delivery_sync.py`:
- read the entire destination table once, not a filtered view
- preserve normalized AppleId comparison
- build `existing_by_apple_id` from destination rows
- add a local `seen_apple_ids` set so duplicates within the same sync run are skipped before payload assembly
- split business logic into small helpers such as `filter_new_items(...)` and `build_batch_fields(...)`
- keep the rule: existing AppleId means skip completely, no update
- build one batch payload per chunk for the remaining new rows
- keep `lookup接口url` generation local from a fixed `https://itunes.apple.com/lookup?id=<AppleId>&country=us` template instead of depending on `AppleStoreService`

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m unittest tests.test_delivery_sync -v
```

Expected:
- PASS
- `create_record` is no longer used by delivery sync for normal multi-row inserts
- `batch_create_records` is called once when within chunk size
- mixed inputs produce a batch payload that contains only new AppleIds
- existing AppleIds and same-run duplicates are skipped

- [ ] **Step 5: Commit**

```bash
git add services/feishu_service.py services/ad_delivery_sync.py tests/test_delivery_sync.py
git commit -m "feat: batch create ad delivery records"
```

### Task 3: Lock down eligibility and no-second-lookup regressions

**Files:**
- Modify: `tests/test_batch_apple_lookup.py`
- Modify: `tests/test_delivery_sync.py`

- [ ] **Step 1: Write the failing tests**

Add or extend tests to cover:

```python
def test_offline_or_not_approved_items_do_not_reach_delivery_sync():
    ...
```

```python
def test_only_five_image_items_are_selected_for_delivery_sync():
    ...
```

```python
def test_monitor_flow_uses_one_lookup_call_for_online_and_delivery_handoff():
    ...
```

The last test must assert Apple lookup call count exactly, not just rely on logs or manual inspection.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m unittest tests.test_batch_apple_lookup tests.test_delivery_sync -v
```

Expected: FAIL until the regression coverage exists.

- [ ] **Step 3: Write minimal implementation**

Only add or tighten code if the tests reveal remaining ambiguity. Prefer to keep this task test-heavy and implementation-light.

- [ ] **Step 4: Run tests to verify they pass**

Run the same command from Step 2.

Expected:
- PASS
- no manual spot-check remains as the main proof

- [ ] **Step 5: Commit**

```bash
git add tests/test_batch_apple_lookup.py tests/test_delivery_sync.py
git commit -m "test: lock down delivery sync regressions"
```

### Task 4: Focused verification

**Files:**
- None

- [ ] **Step 1: Run the focused suite**

Run:

```bash
python -m unittest tests.test_delivery_sync tests.test_batch_apple_lookup -v
```

Expected: PASS

- [ ] **Step 2: Verify request-shape expectations**

Confirm in tests or mocks:
- Apple lookup happens once in the monitor path
- delivery sync does not call Apple lookup at all
- target table rows are read once per sync call
- `batch_create_records` receives only new rows
- `user_id_type="open_id"` is preserved for people fields

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: verify ad delivery batch sync flow"
```

---

### Notes

- Delivery syncing remains gated by both `ENABLE_RECORD_REVIEW=true` and a configured `AD_DELIVERY_WIKI_URL`.
- Existing AppleId rows in the target table must be skipped completely, with no update.
- Same-run duplicate AppleIds must also be skipped before batch payload assembly.
- The first version optimizes request count only; image upload stays out of scope.
