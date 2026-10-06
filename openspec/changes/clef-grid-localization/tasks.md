# Tasks

## 1. Package and fixtures

- [x] 1.1 Set up `clef-use` Python and Node package metadata with offline test commands; verify `uv sync --project libs/cua-driver/examples/clef-use` and `npm --prefix libs/cua-driver/examples/clef-use install` succeed.
- [x] 1.2 Move the three golden Clef responses and sample screenshot into `clef-use/fixtures/`; verify each JSON file parses with `python -m json.tool` and the sample image opens in the Python test suite.

## 2. Python localization

- [x] 2.1 Move the reference grid math and overlay into the formal `clef-use` Python package, reject crop sizes larger than the screenshot, and add edge and fractional-center fixtures; verify with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests/test_grid_math.py`.
- [x] 2.2 Move the live Clef adapter and fixture replay into the formal package, validate returned cell scores, and test malformed responses without network access; verify with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests/test_clef_adapter.py`.
- [x] 2.3 Implement the highest-scoring non-adjacent competitor rule, including an adjacent runner-up plus close third-place case; verify with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests/test_grid_localizer.py`.
- [x] 2.4 Bind a completed Python localization result to the screenshot dimensions, `(pid, window_id)`, and capture ID, with a bounded total inference deadline; verify timeout and capture-mismatch cases in the `clef-use` Python suite with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests`.

## 3. TypeScript localization

- [x] 3.1 Add the TypeScript grid math, overlays, and crop validation using the same fixture cases and rounding outcomes as Python; verify with `npm --prefix libs/cua-driver/examples/clef-use test`.
- [x] 3.2 Add the TypeScript live Clef adapter and fixture replay, response validation, non-adjacent ambiguity checks, capture-bound result data, and a bounded total deadline; verify malformed response, third-place, and timeout cases with `npm --prefix libs/cua-driver/examples/clef-use test` and `npm --prefix libs/cua-driver/examples/clef-use run typecheck`.

## 4. Candidate and runner integration

- [x] 4.1 Add Python `VisualGridSource` to the existing example candidate types, with synchronous `find`, complete capture-bound click arguments, and no text-entry candidate; verify focused source tests and `uv run --project libs/cua-driver/examples/jev-use python -m unittest discover -s libs/cua-driver/examples/jev-use/python/tests`.
- [x] 4.2 Add the equivalent TypeScript source using `typeText` and the existing `Candidate` type; verify source tests, `npm --prefix libs/cua-driver/examples/jev-use test`, and `npm --prefix libs/cua-driver/examples/jev-use run typecheck`.
- [x] 4.3 Make each runner await localization before candidate lookup, preserve the persistent Driver connection, and discard results after an observation change or capture refusal; verify replay cases for `capture_expired`, target mismatch, and no unbound retry in both example test suites.
- [x] 4.4 Document capture acquisition, delivery-mode selection, abstention, and fresh-localization requirements in the `clef-use` README; verify its mock commands against the installed example packages.

## 5. Integration check

- [x] 5.1 Run both complete example test suites and typechecks after integration, then run one explicitly opted-in live capture-bound click check on an available desktop target; verify the action reaches the target and record the tested commit plus any operating-system limitation. Keep the live check out of default tests.
- [x] 5.2 Remove `clef-use/reference/` only after the formal package passes the focused checks and its README no longer links into `reference/`; verify the directory is absent and the Python and TypeScript mock demos still run.
