# Proposal

## Why

During visual computer use, agents frequently fail to locate small interface elements when accessibility trees are absent, falling back to manual coordinate estimation from raw screenshots and thrashing. Although hierarchical visual grid localization with Cloudflare Clef was implemented in [libs/cua-driver/examples/clef-use](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use), agents executing Cua Driver workflows have no direct MCP tool to invoke it and receive no guidance from the driver skill to avoid manual guessing.

GitHub issue: [enkay01/cua#3](https://github.com/enkay01/cua/issues/3)

## What Changes

- Add a companion FastMCP server in [libs/cua-driver/examples/clef-use/python/server.py](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/python/server.py) exposing `locate_visual_target`.
- Provide environment and `.env` credential resolution for `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- Return structured localization results with coordinates, confidence, and abstention reasons matching [LocalizationResult](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/python/grid_localizer.py#L54).
- Update [Skills/cua-driver/WORKFLOW.md](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver/WORKFLOW.md) and [VISUAL.md](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver/VISUAL.md) to instruct agents to use `locate_visual_target` on saved screenshots rather than estimating pixel coordinates manually.
- Add test coverage for the MCP server tool invocation, parameter validation, and abstention reporting.

## Capabilities

### Modified Capabilities

- `visual-grid-localization`: Add requirements for companion MCP tool exposure (`locate_visual_target`), structured result delivery, and agent workflow instructions that prohibit manual coordinate estimation when visual targets are needed.

## Impact

- Affected code: [libs/cua-driver/examples/clef-use/python](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/python), [Skills/cua-driver/WORKFLOW.md](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver/WORKFLOW.md), [Skills/cua-driver/VISUAL.md](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver/VISUAL.md), and [Skills/cua-driver/SKILL.md](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver/SKILL.md).
- Dependencies: Uses existing `mcp>=1.0.0` dependency in [pyproject.toml](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/examples/clef-use/pyproject.toml).
- Core Driver daemon: No changes to Rust crates or the core Cua Driver binary.
