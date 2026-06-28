# ANTI_REWARD_HACKING.md — Integrity guardrails

The score is on **withheld October actuals**. It is trivially easy to *look* good dishonestly and
fail on the real holdout. Any agent working here MUST obey these. Violations invalidate results.

## Hard rules
1. **No holdout peeking.** Never infer, scrape, reverse-engineer, or hardcode the October actuals.
   `present_*`/`volumes_*` files exist only for training weeks; do not fabricate holdout ones.
2. **Walk-forward only.** For decision date D, the engine may use ONLY data with timestamp < D's
   information horizon. No future actuals, no full-dataset fit then "evaluate" on a slice.
   A decision-log note may inform a decision only on/after its `captured_on` date.
3. **No hardcoded answers.** Don't bake the "right" trim %, the L09-beats-L08 verdict, or the
   pick-by-light date into the engine as constants. The system must *derive* them from data so the
   same logic would work on unseen weeks. Findings in our docs are priors to verify, not to encode.
4. **No fitting to the test scorer.** Don't tune hyperparameters against any holdout proxy. Tune on
   walk-forward training cost only.
5. **Report honestly.** If a belief doesn't pay off, say so and retire it. If cost goes up, report
   it. Negative/null results are findings, not failures to hide. No cherry-picked windows.
6. **Respect irreducible noise.** Day-to-day staffing has noise you cannot remove (README §8).
   Driving training error toward zero is a red flag for overfitting, not a win.

## Self-check before claiming a result
- [ ] Could this number be computed at the real decision time? (no future leak)
- [ ] Is every adjustment derived by code from past data, not a literal constant I chose?
- [ ] Did I report the comparison vs B2 (EW trailing ratio), not just vs B0 baseline?
- [ ] Does it generalise — would the same rule fire correctly on a week I haven't seen?
- [ ] Tests green, including the cost-function boundary at the 2.0 SLA tolerance?

## LLM boundary (see LLM_INTEGRATION.md)
The optional Claude layer may only **propose** candidate beliefs (which still pass curation) and
**narrate** already-verified numbers. It must never generate/adjust a staffing number, decide a
belief's truth, or see holdout actuals. The engine must produce identical numbers with the LLM off —
pinned by `tests/test_llm.py::TestNumbersUnaffectedByLlm`.

## Tests are the contract
Write tests that pin the cost function, the walk-forward boundary (assert no future row is ever
visible to a decision), and belief-expiry behaviour. Tests guard against accidental leakage as the
code grows.
