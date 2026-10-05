# Hierarchical visual grid localization (`clef-use`)

Visual UI localization using Cloudflare Clef on Workers AI and Cua Driver.

## Overview

When accessibility trees are missing (in games, custom desktop canvases, or legacy status bars), visual perception models need a reliable way to click small UI elements without coordinate drift.

This package implements a coarse-to-fine 5x5 grid search:

1. Divide the screenshot into a 5x5 grid (25 cells named A1 to E5).
2. Query Cloudflare Clef (`@cf/cloudflare/clef` or `@cf/cloudflare/clef-flash`) for cell probabilities.
3. Check acceptance thresholds:
   - Confidence floor: Stops if the top probability is below threshold (default 0.25).
   - Ambiguity margin: Stops if two non-adjacent cells score within 0.05 of each other.
4. Center the next crop window on the winning cell using boundary clamping so dimensions never shrink at screen edges.
5. Zoom in over 3 iterations (Level 1 full screen, Level 2 region, Level 3 icon).
6. Target the geometric center of the winning cell at Level 3 and map coordinates back to root display space.

## Reference prototype

The working reference prototype and test suite are located in [`reference/`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/).

- [`reference/python/grid.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/grid.py): 5x5 grid math, boundary clamping, and PIL overlay rendering.
- [`reference/python/clef_adapter.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/clef_adapter.py): Cloudflare Workers AI client with live inference and mock fixture replay.
- [`reference/python/localizer.py`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/localizer.py): Coarse-to-fine zoom loop and CLI runner.
- [`reference/python/tests/`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/python/tests/): Unit tests for coordinate math, edge clamping, ambiguity gates, and 3-level zoom.
- [`reference/fixtures/`](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/reference/fixtures/): Reference image and golden JSON response fixtures for Levels 1, 2, and 3.

The formal candidate source integration and TypeScript ports will replace this temporary reference directory as tracked under [Issue #3](https://github.com/enkay01/cua/issues/3).
