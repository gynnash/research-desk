# Insight citation scopes (v2)

## Why this changed

The 2026-10-20 slot `agent-memory-20261020-0300` included yesterday's synthesis
as historical evidence H5. That document defined R2 as the LangChain context
management blog and H1 as Letta. In the new bundle, R2 was the Co2In paper, H1
was LangChain, and H2 was Letta. Passing the old document's unqualified labels
into the same context exposed two incompatible citation maps. The generated
candidate reused the historical meanings, and the independent reviewer
correctly returned `revise`.

The first generation also contained malformed JSON, consuming the single
revision before content review. The saved final state is a completed blocked
attempt, not an interrupted successful review.

## v2 behavior

- A current `evidence_index` binds each evidence ID to its title, origin,
  coverage, stable source IDs, and URLs. Generation and review use the same
  projection and instructions.
- Historical document-local R/H labels are projected as scoped labels, such
  as `historical-H5-R2`. They are not valid output `evidence_ids`; citations to
  that historical document must use its current H5 ID. No automatic assertion
  is made that an old citation supports a new source.
- Only the in-memory model projection changes. Original notes, Research
  results, source identities, source URLs, input hashes, and saved checkpoints
  remain untouched. Link destinations are protected during label rewriting.
- The independent review, cross-source checks, budget limits, test-only
  output boundary, and user confirmation for writing/publication still apply.
  Citation scoping does not prove semantic support; reviewer checks remain
  necessary.

New cycle child configurations and the example configuration use `insight-v2`.
Existing checked child configurations keep their original version. v1 prompts
and projection remain byte-compatible so their existing manifest, checkpoint,
and admission proofs can still be verified. Do not edit a bound configuration
to upgrade an already-started run.

## Existing blocked slot: recovery boundary

No existing CLI command safely resumes this terminal slot. Normal cycle replay
returns its cached `insight_blocked` receipt; scheduled catchup intentionally
skips it. This fix does not change those semantics or manufacture a passing
result.

The slot used 6 Research calls and 3 Insight calls. All nine reservations have
completed. Insight exhausted its one revision and has only one of its four
calls left. A corrected generation and independent review need at least two
new calls, so they cannot be appended under the old Insight allowance. The
overall cycle limit is 16; an additional pair would bring cumulative use to
11. The shared monthly limit must also be checked when execution is authorized.

An explicit recovery implementation would need to:

1. Preserve the original 102 saved files, including the rejection, byte for byte.
2. Create an append-only recovery attempt with lineage to the original cycle,
   failed receipt, candidate/reviewer hashes, and v2 mapping version.
3. Reuse accepted Research only after checking all original proofs, protected
   notes, history hashes, and exact original-material content. Stop on changes.
4. Obtain a separate bounded allowance for the new calls, while retaining the
   old reservations in monthly and cumulative cycle accounting. A two-call
   allowance permits one corrective generation/review pair with no revision;
   a four-call allowance permits one independently reviewed revision if needed.
5. Extend admission and job export/apply to validate the new paths and lineage;
   the current admission format assumes the original cycle paths.
6. Require a fresh independent pass before creating accepted test outputs.
   Writing and publication remain separate user gates.

This recovery mechanism is not implemented here. Do not delete receipts,
increase old budgets, alter hashes, bypass duplicate-input checks, or rerun
discovery as a substitute for explicitly recovering this slot.

## Offline verification

```sh
python -m unittest discover -s tests -v
python workflows/test/agent-memory/test_validate_isolation.py
python workflows/validate.py
python workflows/validate.py --include-test
python -m compileall -q scripts tests
git diff --check
```

Regression coverage includes the real historical collision, two current papers,
reordered history, preserved raw inputs/link destinations, identical generation
and review maps, v2 admission proof verification, v1 replay compatibility,
interrupted pre-upgrade child configuration preservation, and reviewer rejection
preventing outputs. Tests use fake providers or cached proofs; no live model
run is required. A live repaired synthesis remains unverified until separately
authorized.
