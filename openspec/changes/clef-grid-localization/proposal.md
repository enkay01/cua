# Proposal

## Why

When desktop accessibility trees are absent (such as in games and canvas applications), a visual agent needs a way to locate small controls in a Driver screenshot. Cloudflare Clef returns scores for a 25-cell grid. Three levels of subdivision can narrow a target to a screenshot pixel, but the result must remain bound to the captured image and must abstain when competing cells remain plausible.

GitHub issue: [enkay01/cua#3](https://github.com/enkay01/cua/issues/3)
Decision: Implement hierarchical probabilistic visual grid localization with Cloudflare Clef as an example package in `libs/cua-driver/examples/clef-use`, integrate with the existing example-local `CandidateSource` and runner pattern in both languages, use checked-in golden fixtures and capture-bound Driver clicks, and remove the temporary reference prototype after verification.

## What Changes

- Port grid math, boundary clamping, image overlay rendering, and the Clef client adapter into formal Python and TypeScript modules under `libs/cua-driver/examples/clef-use/`.
- Complete cloud localization before synchronous `CandidateSource.find` lookup; use the existing example candidate and runner types for multi-source arbitration.
- Compare the winner with the highest-scoring non-adjacent cell at each level and abstain when its lead is below the ambiguity margin.
- Build click candidates with root screenshot pixel coordinates, the exact observed target, `capture_id`, and an authorized `delivery_mode`; require new localization after a capture refusal.
- Provide golden JSON response fixtures for all three zoom levels under `libs/cua-driver/examples/clef-use/fixtures/`.
- Remove the temporary reference prototype directory `libs/cua-driver/examples/clef-use/reference/` upon formal completion.

## Capabilities

### New Capabilities
- `visual-grid-localization`: Hierarchical 5x5 grid subdivision, boundary clamping, probabilistic cell selection, prepared candidate lookup, confidence and ambiguity abstention, and capture-bound visual click dispatch.

### Modified Capabilities
<!-- None -->

## Impact

- Target code: `libs/cua-driver/examples/clef-use/` and the example-local candidate and runner integration in `libs/cua-driver/examples/jev-use/`.
- Protocols: Uses the existing Python and TypeScript `CandidateSource` shapes without changing the public Driver protocol.
- External dependencies: Cloudflare Workers AI Clef API (`@cf/cloudflare/clef`), Pillow (Python), and standard fetch/canvas (TypeScript).
