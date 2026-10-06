# Hierarchical visual grid localization (`clef-use`)

Visual UI localization using Cloudflare Clef on Workers AI and Cua Driver.

## Overview

When accessibility trees are missing (in games, custom desktop canvases, or legacy status bars), visual perception models need a reliable way to click small UI elements without coordinate drift.

This package implements coarse-to-fine 5x5 probabilistic grid localization:

1. Divide the screenshot into a 5x5 grid (25 cells named A1 to E5).
2. Query Cloudflare Clef (`@cf/cloudflare/clef` or `@cf/cloudflare/clef-flash`) for cell probabilities.
3. Check acceptance thresholds:
   - Confidence floor: Stops if the top probability is below threshold (default 0.25).
   - Ambiguity margin: Stops if any cell outside the winning cell's adjacent 8-neighborhood scores within 0.05 of the winner.
4. Center the next crop window on the winning cell using boundary clamping so dimensions never shrink at screen edges.
5. Zoom in over 3 iterations (Level 1 full screen, Level 2 region, Level 3 icon).
6. Target the geometric center of the winning cell at Level 3 and map coordinates back to root display space.

## Components

The implementation provides matching Python and TypeScript implementations:

- Python package (`python/`):
  - `python/grid.py`: 5x5 grid subdivision, cell geometry calculation, boundary clamping, and Pillow grid overlay rendering.
  - `python/clef_adapter.py`: Cloudflare Workers AI client with live inference and mock fixture replay.
  - `python/grid_localizer.py`: 3-level zoom loop, non-adjacent competitor ambiguity checks, inference deadline enforcement, and capture-bound result objects.
  - `python/sources.py`: `VisualGridSource` conforming to the `CandidateSource` protocol.
  - `python/localizer.py`: Standalone CLI runner.
  - `python/server.py`: Companion MCP server exposing `locate_visual_target` (see below).
  - `python/tests/test_server.py`: Offline tests for the MCP tool (fixture success, credential refusal, invalid image, abstention).
- TypeScript package (`typescript/`):
  - `typescript/grid_localizer.ts`: Grid geometry, boundary clamping, SVG overlay generation, `ClefGridLocalizer`, and observation match validation.
  - `typescript/clef_adapter.ts`: Cloudflare Workers AI adapter, score schema validation, and fixture replay.
  - `typescript/sources.ts`: `VisualGridSource` conforming to the `CandidateSource` protocol.
  - `typescript/localizer.ts`: Standalone CLI runner.

## Capture acquisition and observation binding

The localizer requires complete capture context:

- `capture_id`: The exact snapshot identifier returned by Cua Driver.
- `pid` and `window_id`: The target process and window identifiers.
- `screenshot_w` and `screenshot_h`: The pixel dimensions of the root capture.

When Cua Driver produces a new observation or returns `capture_expired`, previous localization results are invalid. The runner must discard stale candidates and obtain a fresh capture rather than retrying the action with unbound coordinates.

## Delivery-mode selection

Visual grid actions produce capture-bound click candidates with `delivery_mode`:

- Background delivery (`delivery_mode: "background"`): Default mode. Injects the click without stealing desktop focus.
- Foreground delivery (`delivery_mode: "foreground"`): Activated when Driver returns a structured background refusal (such as `background_unavailable` or recommended foreground escalation).

Text entry is rejected by `VisualGridSource`. Because visual grid cells yield coordinate targets without semantic element references, text input requires semantic accessibility elements.

## Abstention rules

The localizer aborts early and returns an explicit failure reason in the following conditions:

- Low confidence (`abstained_low_confidence`): Top cell probability falls below `min_confidence` (default 0.25).
- Ambiguity (`abstained_ambiguous`): A competitor cell outside the winning cell's adjacent 8-neighborhood scores within `ambiguity_margin` (default 0.05) of the top cell. Adjacent neighbors are permitted to score closely to accommodate targets that straddle cell borders.
- Timeout (`abstained_timeout`): Total elapsed inference time exceeds `deadline_ms` (default 30,000 ms).
- Oversized crop: Crop requests with width or height exceeding the root screenshot are rejected before processing.

## Deterministic mock verification

Checked-in fixtures in `fixtures/` allow running the full localization pipeline offline without Cloudflare credentials:

- `fixtures/clef-localization-level1.json`: Golden response for Level 1 full view.
- `fixtures/clef-localization-level2.json`: Golden response for Level 2 region crop.
- `fixtures/clef-localization-level3.json`: Golden response for Level 3 icon crop.
- `fixtures/primeagen-grid-centering-reference.jpg`: Reference screenshot.

### Python mock demo

Run the Python CLI with local fixtures:

```bash
uv run --project libs/cua-driver/examples/clef-use python libs/cua-driver/examples/clef-use/python/localizer.py \
  --image libs/cua-driver/examples/clef-use/fixtures/primeagen-grid-centering-reference.jpg \
  --prompt "Terminal close button" \
  --crop-desktop
```

### TypeScript mock demo

Run the TypeScript CLI with local fixtures:

```bash
npm --prefix libs/cua-driver/examples/clef-use run demo:mock
```

Or run via tsx directly:

```bash
npx --prefix libs/cua-driver/examples/clef-use tsx typescript/localizer.ts \
  --image fixtures/primeagen-grid-centering-reference.jpg \
  --prompt "Terminal close button" \
  --crop-desktop
```

Both runners output each zoom level's winning cell, confidence score, crop coordinates, and the final display-space click target.

## Live inference

To run against Cloudflare Workers AI, set the credentials in your environment:

```bash
export CLOUDFLARE_API_TOKEN="your-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
```

Pass the optional `--model` flag to select between `@cf/cloudflare/clef` and `@cf/cloudflare/clef-flash`.

## Companion MCP server for agents

`python/server.py` exposes the localizer to agents as the `locate_visual_target` MCP tool, so Cua Driver workflows never estimate pixel coordinates by eye. The tool takes a saved screenshot path (from Driver's `screenshot_out_file`) and returns display-space click coordinates bound to the originating capture.

### Setup

Install the server dependencies and provide Cloudflare credentials via environment or a local `.env` / `.env.local` file (auto-loaded on each tool call):

```bash
uv sync --project libs/cua-driver/examples/clef-use --group dev
export CLOUDFLARE_API_TOKEN="your-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
```

### Agent MCP configuration

Register the companion alongside Cua Driver in the agent's MCP configuration (paths relative to the repository root):

```json
{
  "mcpServers": {
    "clef-visual-localization": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "libs/cua-driver/examples/clef-use",
        "--group",
        "dev",
        "python",
        "libs/cua-driver/examples/clef-use/python/server.py"
      ],
      "env": {
        "CLOUDFLARE_API_TOKEN": "your-token",
        "CLOUDFLARE_ACCOUNT_ID": "your-account-id"
      }
    }
  }
}
```

### Tool usage

1. Capture the exact target window with Driver, saving the screenshot to disk:
   `get_window_state({pid, window_id, screenshot_out_file: "/absolute/run-dir/before.png"})`.
2. Call `locate_visual_target` with the saved path and a short target description:
   ```json
   {
     "image_path": "/absolute/run-dir/before.png",
     "prompt": "Terminal close button",
     "capture_id": "capture-from-current-observation",
     "pid": 844,
     "window_id": 10725
   }
   ```
3. On `success: true`, dispatch one Driver `click` with the returned `click_x`, `click_y`, target, and the same `capture_id`; then reobserve from fresh state.
4. On `success: false`, do not act: `abstained_low_confidence`, `abstained_ambiguous`, and `abstained_timeout` mean the target could not be resolved, `unconfigured_credentials` means the server lacks Cloudflare credentials, and `invalid_image` means the screenshot path was wrong.

For offline verification without credentials, pass `mock_fixture_paths` pointing at the checked-in `fixtures/clef-localization-level*.json` files, or set the `CLEF_MOCK_FIXTURES` environment variable to a path-separated fixture list.

## Running tests

Run the Python test suite:

```bash
uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests -c libs/cua-driver/examples/clef-use/pyproject.toml -v
```

Run the TypeScript test suite and type check:

```bash
npm --prefix libs/cua-driver/examples/clef-use test
npm --prefix libs/cua-driver/examples/clef-use run typecheck
```
