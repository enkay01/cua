# Design

## Context

See [proposal.md](proposal.md) for the reason for this change and [the visual grid spec](specs/visual-grid-localization/spec.md) for its behavior. The `clef-use/reference/` prototype has Python grid math, three-level localization, live Workers AI calls, and replay fixtures. The existing `jev-use` Python and TypeScript candidate sources perform synchronous lookup over an observation that the runner has already prepared. Its visual source creates a `click` candidate with `pid`, `window_id`, screenshot pixel coordinates, `capture_id`, and `delivery_mode`. Driver maps the point once and can refuse a stale capture. The Clef reference localizer checks only the overall runner-up for ambiguity.

## Goals / Non-Goals

**Goals:**
- Preserve synchronous candidate lookup and the existing example runner's action path.
- Use one captured image and capture ID throughout all zoom levels and candidate construction.
- Keep the grid math and refusal behavior equivalent in Python and TypeScript.
- Retain offline fixture replay and remove `clef-use/reference/` after the formal package passes verification.

**Non-Goals:**
- Change Driver's click schema, capture lifetime, or platform input adapters.
- Add automatic foreground fallback after a background refusal.
- Claim a fixed cloud inference time without measurements.

## Decisions

### Keep localization in the Clef example package

`clef-use/python` and `clef-use/typescript` own the grid math, overlays, Clef request and response adapters, and three-level localization. The package includes Python and Node metadata, shared JSON response fixtures, a sample screenshot, and per-language tests. Offline replay is the default test path; live Workers AI calls require an explicit integration run. The alternative, keeping the reference tree as a second runnable implementation, would leave two sets of grid math to maintain.

### Localize before constructing the source

The runner obtains one `get_window_state` observation and checks for advertised capture-bound `click` support. When visual lookup is needed, it awaits a localization operation for the task's target description before constructing `VisualGridSource`. The source holds the completed result, original screenshot dimensions, target identity, capture ID, and delivery mode. `find` only matches that prepared description and returns a control when localization succeeded; it never contacts Cloudflare. `click` converts that control into a candidate. This keeps the existing synchronous `CandidateSource` contract. The alternative, making `find` asynchronous, would require changing every source and task caller in `jev-use`.

The Clef localizer belongs in `clef-use`; the candidate adapter should use the existing `Candidate`, `Control`, and runner types owned by `jev-use` where multi-source arbitration actually happens. The implementation must not create a second incompatible copy of those types in `clef-use`. Python and TypeScript adapters use their language's existing method names, including `type_text` in Python and `typeText` in TypeScript. A separate standalone Clef demo may call the localizer directly, but the shared runner remains the owner of candidate construction and dispatch.

### Keep coordinates in screenshot pixels

All crop boxes refer to the original screenshot image, and the final cell center is translated into that image's pixel coordinates. The adapter checks that the point lies within the captured PNG dimensions. Its candidate contains `pid`, `window_id`, `x`, `y`, `capture_id`, and the runner-authorized `delivery_mode`. It retains the capture ID on the candidate so existing choice validation can reject a mismatch. It never applies `screenshot_to_action`; Driver does that when the capture-bound click is dispatched. The alternative, computing desktop coordinates in the example, would apply the mapping twice.

### Treat capture identity as part of the result

The localization result is bound to one capture ID and `(pid, window_id)` pair. The runner does not reuse it after a new observation, target change, timeout, or attempted action. If the capture changes before candidate construction, the adapter returns no click. If Driver refuses a click with a capture refusal such as `capture_expired`, the runner records the refusal, discards the result, and requires a fresh `get_window_state` plus new Clef localization before another pixel candidate. It never retries without `capture_id`. Capture and action stay on one persistent Driver connection, as required by [the Driver capture-bound action contract](../../../libs/cua-driver/docs/perception-extension.md#capture-bound-parse-and-action).

Cloud calls have a bounded total deadline. A deadline expiry returns an abstention, and the runner starts a new observation if it still needs visual localization. The implementation must measure latency before claiming a duration; the current plan's under-four-second estimate is not a release criterion. Even a result returned before the deadline can be refused by Driver, so refusal handling remains necessary.

### Compare against the best non-adjacent cell

At each level, validate that provider scores refer to known cells and are finite numbers in the expected probability range. Select the highest-scoring cell, then find the highest-scoring cell outside its adjacent eight-cell neighborhood. Abstain when the winner is below the confidence floor or its lead over that non-adjacent cell is less than the ambiguity margin. This fixes the reference loop's blind spot when an adjacent runner-up hides a close third-place cell. Both languages use the same cell order and rounding cases in shared fixture scenarios.

## Risks / Trade-offs

- [Risk] Cloud inference may outlast the capture's lifetime. → Mitigation: Bound the localization call, handle Driver capture refusals, and require fresh localization before another click.
- [Risk] A screenshot can change while inference runs, even if its capture ID remains registered. → Mitigation: Keep Driver's capture-frame check authoritative and treat its refusal as a fresh-observation request.
- [Risk] Cross-language rounding can move a final point by one pixel. → Mitigation: Use the same integer boundary and cell-center fixtures in Python and TypeScript.

## Migration Plan

1. Implement the Python and TypeScript Clef package with replay fixtures and focused tests.
2. Add prepared result adapters to the existing candidate and runner flow, then test capture-bound dispatch and refusal handling.
3. Remove the reference prototype after the formal package and documented mock commands pass. Run an opted-in live click check when an appropriate desktop target is available.
4. If the example integration fails, restore the previous example runner path and keep the Clef localizer disabled; Driver protocol and platform code require no rollback.
