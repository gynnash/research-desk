# Bounded linked Insight recovery

The citation-scope fix does not rewrite or reset an old failed run. A single,
explicitly authorized recovery can reuse its accepted Research and frozen
historical evidence while obtaining a new generation and independent review.

## Eligibility and boundaries

- The original cycle must be terminal `insight_blocked`, with accepted Research,
  a verifiable failed Insight review, no accepted outputs, and no unknown calls.
- `config/recoveries/<original-cycle-id>.yaml` is a reviewed opt-in request. It
  binds the original configuration, failure receipt and every original checkpoint
  hash. `researchdesk_recovery.make_request` constructs the request; saving it
  requires authorization for the exact new attempt and its allowance.
- Only `<original-cycle-id>-recovery-1` is supported. A second recovery or a
  recovery of a recovery is refused. Ordinary duplicate-input checks stay active;
  only the exact verified original failed Insight batch is exempted.
- All original checkpoint files remain byte-identical. Sources are freshly
  fetched and must reproduce the original input fingerprint and request chain.
  Changed source material, changed history, changed account or altered proofs
  stop before inference.
- The recovery uses `insight-v2`, the original actual model pair, and the same
  membership account. It permits at most four new generation/review calls and
  one revision, with no extra format-review call. Original reservations continue
  to count against both the original cycle cap and shared monthly cap. Every new
  reservation checks all three caps. An unknown request is counted and never
  automatically resent.
- An independent fresh pass is required before test outputs; formal admission
  separately verifies the fresh pass, original Research and recovery lineage.
  Writing and publication gates remain unchanged.

## Authorized morning recovery

The checked-in request for `agent-memory-20261020-0300` binds 102 original files
and nine completed calls. The original cycle ceiling is 16. Recovery permits
at most four additional calls, so the linked cumulative ceiling is 13. At request
preparation the shared monthly ledger was 40/100; the runtime must recheck it.
The old Insight stage keeps its exhausted revision allowance and its old
four-call budget unchanged; the new allowance belongs only to the linked attempt.

The trusted job entry point routes `operation=run` for this exact original slot
to the registered recovery. That allows rerunning the failed analysis job with
its existing plan outputs and a checkout of current `main`. Scheduler catchup
continues to skip the original terminal slot. The job also supports explicit
`operation=recover`; an absent or mismatched request fails closed.

No workflow or command should be launched until the code and request have been
reviewed and the bounded recovery authorized. The existing trusted runner uses
its configured membership profile; no credentials are created or copied.

## Records and retry behavior

New records are under:

- `reports/test/<topic>/cycles/<original>-recovery-1/`
- `reports/test/<topic>/insight-runs/<original>-recovery-1/`
- `reports/<topic>/admissions/<original>-recovery-1/` after admission

The recovery manifest records original failure, candidate, reviewer, request and
checkpoint hashes. Worker export contains only new recovery paths. Publisher
apply validates the unchanged original files and lineage again before admitting
or committing, including interrupted/blocked transfers without an admission plan.
Completed retries reuse the immutable records with zero new inference calls.
An interrupted attempt can resume known completed requests, but never resends an
unknown reservation. A terminal rejected recovery remains blocked and cached.

## Offline checks

```sh
python -m unittest discover -s tests -p 'test_recovery*.py' -v
python -m unittest discover -s tests -p 'test_insight*.py' -v
python -m unittest discover -s tests -v
python workflows/validate.py --include-test
```

Tests use fake transports and fixed sources. They cover immutable originals,
two-call acceptance, four-call revision, rejection, budget and account bounds,
source changes, unknown requests, replay, admission and worker/publisher routing.
