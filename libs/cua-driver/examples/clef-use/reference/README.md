# Hierarchical visual grid localization prototype (`clef-use/reference`)

This directory contains the initial working prototype for visual UI localization using Cloudflare Clef on Workers AI and Cua Driver.

> Note: This prototype is preserved here as a reference implementation while the formal RFC #3 candidate source architecture and TypeScript bindings are being implemented. It is tracked for final consolidation and cleanup under [Issue #3](https://github.com/enkay01/cua/issues/3).

## Directory structure

- [`python/grid.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/grid.py): 5x5 grid math, boundary clamping, and PIL overlay rendering.
- [`python/clef_adapter.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/clef_adapter.py): Cloudflare Workers AI client with live inference and mock fixture replay.
- [`python/localizer.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/localizer.py): Coarse-to-fine zoom loop and CLI runner.
- [`python/tests/`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/tests/): Unit tests for coordinate math, edge clamping, ambiguity gates, and 3-level zoom.
- [`fixtures/`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/fixtures/): Reference image and golden JSON response fixtures for Levels 1, 2, and 3.

## Running tests

Run the test suite with pytest:

```bash
PYTHONPATH=libs/cua-driver/examples/clef-use/reference/python .venv/bin/pytest libs/cua-driver/examples/clef-use/reference/python/tests/
```

## Running the localizer

### With Varlock and live Cloudflare Workers AI

Configure `.env.local` with `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, then run:

```bash
PYTHONPATH=libs/cua-driver/examples/clef-use/reference/python pnpm exec varlock run -- \
  .venv/bin/python libs/cua-driver/examples/clef-use/reference/python/localizer.py \
  --image libs/cua-driver/examples/clef-use/reference/fixtures/primeagen-grid-centering-reference.jpg \
  --prompt "monitor icon in the top right menu bar" \
  --crop-desktop \
  --model clef
```

### Offline / mock mode

When no Cloudflare credentials are configured, the localizer falls back to the golden fixtures:

```bash
PYTHONPATH=libs/cua-driver/examples/clef-use/reference/python .venv/bin/python libs/cua-driver/examples/clef-use/reference/python/localizer.py \
  --image libs/cua-driver/examples/clef-use/reference/fixtures/primeagen-grid-centering-reference.jpg \
  --prompt "monitor icon in the menu bar" \
  --crop-desktop
```
