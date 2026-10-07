# Design

## Context

See [proposal.md](proposal.md) for motivation and [specs/visual-grid-localization/spec.md](specs/visual-grid-localization/spec.md) for requirements.

The Python package in [libs/cua-driver/examples/clef-use](../../../../libs/cua-driver/examples/clef-use) already contains complete 5x5 subdivision, boundary clamping, and Workers AI integration in [grid_localizer.py](../../../../libs/cua-driver/examples/clef-use/python/grid_localizer.py). In addition, [pyproject.toml](../../../../libs/cua-driver/examples/clef-use/pyproject.toml) lists `mcp>=1.0.0` as a dependency.

The Cua Driver skill documentation lives in [libs/cua-driver/rust/Skills/cua-driver](../../../../libs/cua-driver/rust/Skills/cua-driver) and is synced to client distributions.

## Goals / Non-Goals

**Goals:**
- Expose visual grid localization as an MCP tool named `locate_visual_target` using Python FastMCP.
- Support credential loading from process environment variables and project `.env` files.
- Return structured status, coordinates, confidence, and explicit abstention reasons.
- Update Cua Driver skill files ([WORKFLOW.md](../../../../libs/cua-driver/rust/Skills/cua-driver/WORKFLOW.md), [VISUAL.md](../../../../libs/cua-driver/rust/Skills/cua-driver/VISUAL.md), [SKILL.md](../../../../libs/cua-driver/rust/Skills/cua-driver/SKILL.md)) to guide agents toward `locate_visual_target` and prohibit manual pixel estimation.

**Non-Goals:**
- Modify the Cua Driver Rust core, daemon protocol, or platform input adapters.
- Port Clef grid subdivision and image rendering into Rust.
- Replace open-ended visual parsing provided by `cua-perception`.

## Decisions

### Implement companion MCP server with Python FastMCP

The server will be implemented in `libs/cua-driver/examples/clef-use/python/server.py` using `mcp.server.fastmcp.FastMCP`.

Rationale: FastMCP provides clean decorator-based tool definitions and handles stdio transport without boilerplate. It directly imports [`ClefGridLocalizer`](../../../../libs/cua-driver/examples/clef-use/python/grid_localizer.py#L93) and [`ClefClient`](../../../../libs/cua-driver/examples/clef-use/python/clef_adapter.py#L32), reusing existing tested code without duplicating logic.

Alternatives considered:
- TypeScript MCP server: Feasible via `@modelcontextprotocol/sdk`, but Python already has `mcp` in `pyproject.toml` and existing test infrastructure.
- Native Rust MCP tool in Cua Driver: Rejected because it couples Driver core to Cloudflare Workers AI and requires reimplementing grid math and image rendering in Rust.

### Accept file path for screenshot input

The `locate_visual_target` tool will take an `image_path` string rather than inlined base64 image data.

Rationale: Driver's observation tools (`get_window_state` and `get_desktop_state`) write screenshots to disk when `screenshot_out_file` is provided. Passing the file path avoids large payloads and memory overhead across MCP stdio communication.

Alternatives considered:
- Inlined base64 strings: Adds significant serialization latency and increases prompt context token load unnecessarily.

### Return complete structured localization results

The tool returns a dictionary matching [LocalizationResult](../../../../libs/cua-driver/examples/clef-use/python/grid_localizer.py#L54):
- On success: `success=True`, `status="success"`, `click_x`, `click_y`, `confidence`, `winning_cell`, and any passed `capture_id`, `pid`, `window_id`.
- On abstention: `success=False`, `status` (`abstained_low_confidence`, `abstained_ambiguous`, `abstained_timeout`), `reason`, and null coordinates.

Rationale: Explicit failure contracts prevent agents from guessing coordinates when visual confidence is inadequate.

### Direct agents away from manual pixel estimation in skill documentation

Update [WORKFLOW.md](../../../../libs/cua-driver/rust/Skills/cua-driver/WORKFLOW.md) and [VISUAL.md](../../../../libs/cua-driver/rust/Skills/cua-driver/VISUAL.md) in [libs/cua-driver/rust/Skills/cua-driver](../../../../libs/cua-driver/rust/Skills/cua-driver). Instruct agents that when accessibility controls are absent, they must write `screenshot_out_file` and call `locate_visual_target` rather than eyeballing coordinates.

Rationale: Session f8149b59 demonstrated that without explicit instruction in the skill, agents default to inspecting raw PNG previews and hallucinating coordinates.

## Risks / Trade-offs

- [Risk] Unconfigured Cloudflare credentials in agent environment → Mitigation: Check for token presence on startup or invocation; return an actionable `unconfigured_credentials` error message before network requests.
- [Risk] Missing or invalid screenshot file path → Mitigation: Check file existence and load with Pillow inside a protected try-except block, returning structured file error.
- [Risk] Stale capture after localization → Mitigation: Pass `capture_id` through the tool output, and document that Driver's capture contract remains authoritative.
