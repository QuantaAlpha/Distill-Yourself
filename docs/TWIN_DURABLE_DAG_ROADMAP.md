# Twin Durable DAG Roadmap

This note captures the long-term design direction for making Distill runs durable at sub-stage granularity. It is intentionally a roadmap, not an implementation in the current PR.

## Current Boundary

The current implementation persists compact `twin_runs` checkpoints:

- Run scope and input snapshot.
- Current stage and stage status.
- Stage counts, truncation state, and lightweight cursor metadata.
- Last error and finish timestamps.

This is sufficient for interactive recovery at the Stage 1-4 boundary. It does not yet model individual shards, retries, artifacts, or leases inside a stage.

## Proposed Tables

`twin_tasks` would represent durable work units:

- `task_id`: stable id.
- `run_id`: parent run.
- `stage`: integer stage number.
- `kind`: `extract_events`, `distill_cards`, `infer_traits`, `compile_runtime`.
- `input_hash`: hash of scoped input ids or prompt payload.
- `status`: `pending`, `running`, `done`, `error`, `cancelled`, `stale`.
- `attempt`: retry counter.
- `lease_owner`, `lease_until`: safe recovery after process death.
- `created_at`, `updated_at`, `finished_at`.

`twin_artifacts` would store stage outputs and validator results:

- `artifact_id`: stable id.
- `task_id`: parent task.
- `artifact_type`: `candidate_json`, `validation_report`, `batch_result`, `runtime_pack`.
- `content_json` or `content_path`: inline small artifacts, file path for large outputs.
- `content_hash`: deduplication and replay safety.
- `created_at`.

## Execution Model

The supervisor owns all writes. Reader agents create candidate artifacts only. The supervisor validates artifacts, deduplicates them, and commits one transactional `twin-batch` per task or stage.

Resume should query unfinished tasks first. If no task DAG exists for an older run, it should fall back to the existing stage-level resume path.

## Why Not In This PR

The task DAG changes schema, prompt orchestration, retry semantics, and UI history views. Combining it with UX polish, documentation, and stage-level recovery would make review too large and increase migration risk.

## Suggested Future PR

Create a dedicated PR after the stage-level recovery flow proves stable:

- Add `twin_tasks` and `twin_artifacts` schema with migration-safe `CREATE TABLE IF NOT EXISTS`.
- Add CLI commands for task creation, leasing, artifact validation, and replay.
- Convert Stage 1 to task-based shards first.
- Keep Stage 2-4 on the existing path until Stage 1 task recovery is validated.
- Add tests for stale leases, duplicate artifacts, failed validation, and idempotent replay.
