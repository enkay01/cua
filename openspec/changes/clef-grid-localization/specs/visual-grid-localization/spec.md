# Spec Delta

## Purpose

Enables visual computer-use agents to locate and target small graphical interface elements without coordinate drift through hierarchical 5x5 probabilistic grid subdivision, boundary clamping, and candidate source integration.

## ADDED Requirements

### Requirement: Hierarchical 5x5 visual grid subdivision and labeling
The system SHALL divide a given screenshot or region crop into a 5x5 grid of 25 cells labeled A1 through E5, round cell boundaries to pixel positions, and overlay visible grid lines and cell labels before visual model submission. It SHALL express the final point in the original screenshot's pixel coordinates.

#### Scenario: Full-screen grid overlay
- **WHEN** a full-resolution screen capture is processed at the initial zoom stage
- **THEN** the localizer divides the image into 25 labeled cells from A1 to E5 and generates an annotated image with visible grid lines and label markers

#### Scenario: Sub-region crop overlay
- **WHEN** an intermediate region crop is processed during progressive zoom
- **THEN** the localizer subdivides the cropped area into 25 newly labeled cells spanning the full dimensions of the crop

### Requirement: Boundary-clamped crop positioning
When calculating subsequent crop bounds centered around a target cell, the system SHALL clamp crop coordinates to keep the window within screen bounds while maintaining constant dimensions when the configured crop fits within the screenshot. It SHALL reject an oversized crop before model submission.

#### Scenario: Crop near top-left screen boundary
- **WHEN** the winning cell is located at the top-left boundary (such as cell A1)
- **THEN** the crop window is clamped to origin (0, 0) and maintains its full target width and height without negative offsets or shrinking

#### Scenario: Crop near bottom-right screen boundary
- **WHEN** the winning cell is located at the bottom-right corner of the display
- **THEN** the crop window right and bottom coordinates clamp to display width and height without exceeding boundaries or shrinking

#### Scenario: Configured crop exceeds screenshot dimensions
- **WHEN** a configured crop dimension exceeds the corresponding screenshot dimension
- **THEN** localization rejects the configuration before sending an image to Clef

### Requirement: Confidence floor and ambiguity gating
The system SHALL evaluate model cell probabilities against configurable confidence floor and ambiguity margin thresholds, returning an explicit abstention when criteria are not met. The ambiguity comparison SHALL use the highest-scoring cell that is non-adjacent to the winner.

#### Scenario: Prediction below confidence floor
- **WHEN** the highest cell probability returned by Clef falls below the required threshold (default 0.25)
- **THEN** the localizer halts and returns an abstention result rather than dispatching an unvalidated action

#### Scenario: Ambiguous non-adjacent cells
- **WHEN** the highest-scoring non-adjacent cell is within the ambiguity margin (default 0.05) of the winner, even if an adjacent cell has the second-highest score
- **THEN** the localizer flags the observation as ambiguous and halts the zoom progression

#### Scenario: Unambiguous confident prediction
- **WHEN** the top cell exceeds the confidence floor and leads non-adjacent cells by more than the ambiguity margin
- **THEN** the localizer selects the winning cell and advances to the next zoom level or resolves the final coordinates

### Requirement: Completed observation before candidate lookup
The visual grid component SHALL finish localization and bind the result to one Driver capture before synchronous candidate lookup can return a control. Candidate lookup SHALL NOT initiate provider inference.

#### Scenario: Control available after localization
- **WHEN** localization succeeds for the requested description on the current capture
- **THEN** lookup returns a control bound to that completed result

#### Scenario: No completed result
- **WHEN** no completed result exists for the requested description and current capture
- **THEN** lookup returns no visual control

### Requirement: CandidateSource protocol compliance
The visual grid component SHALL implement the existing example-local Python and TypeScript `CandidateSource` shapes, dispatching click actions under the [Driver capture-bound action contract](../../../../../libs/cua-driver/docs/perception-extension.md#capture-bound-parse-and-action).

#### Scenario: Resolve visual control and click candidate
- **WHEN** `find(role, name)` locates a visual target matching the target description
- **THEN** `click(control, ...)` returns a candidate containing the exact observed `pid`, `window_id`, root screenshot pixel `x` and `y`, authorized `delivery_mode`, and `capture_id`

#### Scenario: Capture-bound click unavailable
- **WHEN** Driver does not advertise capture-bound click
- **THEN** the source offers no visual click candidate

#### Scenario: Reject text entry for visual controls
- **WHEN** direct text entry is requested on a visual grid control
- **THEN** the source returns no text-entry candidate

### Requirement: Stale capture refusal
The system SHALL discard a resolved point when its capture is no longer current or Driver refuses it. Another pixel action SHALL require a fresh capture and localization, without retrying as an unbound click.

#### Scenario: Capture changes before candidate construction
- **WHEN** the current observation has a different capture ID or target from the localization result
- **THEN** the old point produces no click candidate

#### Scenario: Driver refuses an expired capture
- **WHEN** Driver returns `capture_expired` for a click
- **THEN** the client discards the result and requires a new capture and localization before another pixel action
