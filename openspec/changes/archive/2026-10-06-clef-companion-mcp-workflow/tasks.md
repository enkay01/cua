# Tasks

## 1. FastMCP server implementation

- [x] 1.1 Implement the FastMCP server in `libs/cua-driver/examples/clef-use/python/server.py` defining `locate_visual_target`, credential loading from environment and `.env`, and image loading; verify with `uv run --project libs/cua-driver/examples/clef-use python -c "import server"`.
- [x] 1.2 Wire `locate_visual_target` to `ClefGridLocalizer` with input validation, observation metadata propagation (`capture_id`, `pid`, `window_id`), and structured dictionary output; verify offline execution against golden fixtures.

## 2. Server tests and offline verification

- [x] 2.1 Add unit tests in `libs/cua-driver/examples/clef-use/python/tests/test_server.py` covering successful fixture localization, unconfigured credentials refusal, invalid image file path, and abstention reporting; verify with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests/test_server.py`.
- [x] 2.2 Run full `clef-use` test suite to verify no regressions in grid math or client adapters with `uv run --project libs/cua-driver/examples/clef-use pytest libs/cua-driver/examples/clef-use/python/tests`.

## 3. Skill workflow updates and documentation

- [x] 3.1 Update `libs/cua-driver/rust/Skills/cua-driver/WORKFLOW.md` under pixel coordinates to explicitly prohibit manual coordinate estimation from screenshots and direct agents to `locate_visual_target`; verify documentation links.
- [x] 3.2 Update `libs/cua-driver/rust/Skills/cua-driver/VISUAL.md` and `SKILL.md` to document the companion MCP visual localization route, and sync updates to `libs/cua/skills/cua-driver` and active local skills; verify skill synchronization.
- [x] 3.3 Document server setup, agent MCP configuration snippet, and tool usage in `libs/cua-driver/examples/clef-use/README.md`; verify markdown formatting.
