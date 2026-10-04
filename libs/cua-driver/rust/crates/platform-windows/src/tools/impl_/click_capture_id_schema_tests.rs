use super::ClickTool;
use cua_driver_core::tool::Tool;

/// The portable click contract pins `button` and the other accepted
/// fields. A live schema may broaden `capture_id`, which the subset gate
/// allows, so the non-empty bound is pinned here.
#[test]
fn schema_requires_non_empty_capture_id() {
    let tool = ClickTool {
        state: super::ToolState::new(None),
    };
    let d = tool.def();
    let props = d.input_schema.get("properties").expect("properties");
    let capture_id = props.get("capture_id").expect("capture_id field present");
    assert_eq!(capture_id["type"], "string");
    assert_eq!(capture_id["minLength"], 1);
}

#[test]
fn schema_includes_debug_image_out() {
    let tool = ClickTool {
        state: super::ToolState::new(None),
    };
    let d = tool.def();
    let props = d.input_schema.get("properties").expect("properties");
    let dbg = props
        .get("debug_image_out")
        .expect("debug_image_out field present");
    assert_eq!(dbg["type"], "string");
}

#[tokio::test]
async fn debug_image_out_rejected_with_capture_id() {
    let tool = ClickTool {
        state: super::ToolState::new(None),
    };
    let res = tool
        .invoke(serde_json::json!({
            "scope": "desktop",
            "x": 100.0,
            "y": 100.0,
            "capture_id": "cap-123",
            "debug_image_out": "C:\\temp\\dbg.png"
        }))
        .await;
    assert_eq!(res.is_error, Some(true));
    assert_eq!(
        res.structured_content
            .as_ref()
            .and_then(|v| v.get("code"))
            .and_then(|v| v.as_str()),
        Some("invalid_arguments")
    );
}

#[tokio::test]
async fn debug_image_out_rejected_with_from_zoom() {
    let tool = ClickTool {
        state: super::ToolState::new(None),
    };
    let res = tool
        .invoke(serde_json::json!({
            "scope": "desktop",
            "x": 100.0,
            "y": 100.0,
            "from_zoom": true,
            "debug_image_out": "C:\\temp\\dbg.png"
        }))
        .await;
    assert_eq!(res.is_error, Some(true));
    let txt = match res.content.first() {
        Some(cua_driver_core::protocol::Content::Text { text, .. }) => text.as_str(),
        _ => "",
    };
    assert!(txt.contains("debug_image_out is incompatible with from_zoom"));
}
