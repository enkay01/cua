# Spec Delta

## ADDED Requirements

### Requirement: Companion MCP tool exposure
The system SHALL expose visual grid localization as a Model Context Protocol tool named `locate_visual_target`. The tool SHALL accept an image file path and a target prompt, resolve Cloudflare credentials from environment variables or a local `.env` file, and return display-space coordinates, confidence score, and status.

#### Scenario: Successful element localization over MCP
- **WHEN** an MCP client invokes `locate_visual_target` with a valid image path and prompt
- **THEN** the tool returns a structured response with `success: true`, `status: "success"`, root display-space `click_x` and `click_y`, confidence, and winning cell

#### Scenario: Abstention returned as structured failure
- **WHEN** localization halts due to low confidence, ambiguous competitors, or timeout
- **THEN** the tool returns `success: false` with null click coordinates and reports the specific abstention status and reason

#### Scenario: Missing Cloudflare credentials
- **WHEN** `locate_visual_target` is invoked without `CLOUDFLARE_API_TOKEN` or `CLOUDFLARE_ACCOUNT_ID`
- **THEN** the tool returns an explicit error indicating unconfigured credentials before attempting inference

### Requirement: Visual targeting skill guidance
The Cua Driver skill documentation in [Skills/cua-driver](file:///Users/iannkwocha/Documents/GitHub/cua/libs/cua-driver/rust/Skills/cua-driver) SHALL instruct agents to obtain target coordinates via `locate_visual_target` on saved screenshots when semantic controls are absent, explicitly prohibiting manual coordinate estimation from raw images.

#### Scenario: Semantic element missing from accessibility tree
- **WHEN** an agent operating Cua Driver needs to interact with an element not represented in `get_window_state`
- **THEN** the workflow directs the agent to capture a full-resolution screenshot with `screenshot_out_file` and run `locate_visual_target` to obtain click coordinates

#### Scenario: Dispatching capture-bound click from localization
- **WHEN** `locate_visual_target` provides resolved coordinates associated with a capture ID
- **THEN** the skill directs the agent to dispatch Driver's `click` tool using `pid`, `window_id`, `click_x`, `click_y`, and the matching `capture_id`
