use crate::protocol::ToolResult;
use serde_json::json;

/// Geometry of a window screenshot relative to its native window dimensions.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ScreenshotGeometry {
    pub width: u32,
    pub height: u32,
    pub native_width: u32,
    pub native_height: u32,
}

impl ScreenshotGeometry {
    /// Construct a geometry if all dimensions are positive.
    pub fn new(width: u32, height: u32, native_width: u32, native_height: u32) -> Option<Self> {
        if width > 0 && height > 0 && native_width > 0 && native_height > 0 {
            Some(Self {
                width,
                height,
                native_width,
                native_height,
            })
        } else {
            None
        }
    }

    /// Independent horizontal and vertical scaling factors `(native_w / w, native_h / h)`.
    #[inline]
    pub fn scale(&self) -> (f64, f64) {
        (
            f64::from(self.native_width) / f64::from(self.width),
            f64::from(self.native_height) / f64::from(self.height),
        )
    }

    /// Validate that a coordinate falls within inclusive screenshot bounds `(0.0 <= x <= width, 0.0 <= y <= height)`.
    pub fn validate_bounds(&self, x: f64, y: f64) -> Result<(), ToolResult> {
        if !x.is_finite()
            || !y.is_finite()
            || x < 0.0
            || x > f64::from(self.width)
            || y < 0.0
            || y > f64::from(self.height)
        {
            return Err(ToolResult::error(format!(
                "Coordinates ({x}, {y}) are outside the screenshot bounds (0..={}, 0..={}).",
                self.width, self.height
            ))
            .with_structured(json!({
                "code": "screenshot_coordinate_out_of_bounds",
                "x": x,
                "y": y,
                "screenshot_width": self.width,
                "screenshot_height": self.height,
            })));
        }
        Ok(())
    }

    /// Bounds-check coordinate and convert to scaled floating-point native coordinates.
    pub fn to_native_f64(&self, x: f64, y: f64) -> Result<(f64, f64), ToolResult> {
        self.validate_bounds(x, y)?;
        let (scale_x, scale_y) = self.scale();
        Ok((x * scale_x, y * scale_y))
    }

    /// Bounds-check coordinate (inclusive: `0.0 <= x <= width`, `0.0 <= y <= height`),
    /// scale each axis independently, and round to the nearest integer pixel.
    pub fn to_native(&self, x: f64, y: f64) -> Result<(i32, i32), ToolResult> {
        self.validate_bounds(x, y)?;

        let (scale_x, scale_y) = self.scale();
        let nx = (x * scale_x).round();
        let ny = (y * scale_y).round();

        if nx < f64::from(i32::MIN)
            || nx > f64::from(i32::MAX)
            || ny < f64::from(i32::MIN)
            || ny > f64::from(i32::MAX)
        {
            return Err(ToolResult::error(format!(
                "Scaled coordinate ({nx}, {ny}) is outside the i32 pixel range."
            )));
        }

        Ok((nx as i32, ny as i32))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::image_utils::downscaled_dimensions;

    #[test]
    fn dimension_table_exact_corners_and_independent_axis_scaling() {
        // Pure dimension table: (native_w, native_h)
        let test_dimensions = [
            (1080, 1920), // portrait
            (3440, 1440), // ultrawide
            (1366, 767),  // odd dimensions
            (1001, 999),  // near-square odd
            (3840, 2160), // 4K UHD
            (640, 480),   // sub-cap
        ];
        let caps = [1568, 1456, 800];

        let mut observed_differing_scales = false;

        for &(nw, nh) in &test_dimensions {
            for &cap in &caps {
                let (w, h) = downscaled_dimensions(nw, nh, cap);
                let geom = ScreenshotGeometry::new(w, h, nw, nh).expect("valid geometry");

                let (scale_x, scale_y) = geom.scale();
                if (scale_x - scale_y).abs() > 1e-9 {
                    observed_differing_scales = true;
                }

                // Assert exact corner recovery: (0, 0) -> (0, 0)
                let (x0, y0) = geom.to_native(0.0, 0.0).expect("origin in bounds");
                assert_eq!((x0, y0), (0, 0));

                // Assert exact corner recovery: (w, h) -> (nw, nh) within +-0 pixels
                let (x_max, y_max) = geom.to_native(w as f64, h as f64).expect("max in bounds");
                assert_eq!(x_max, nw as i32);
                assert_eq!(y_max, nh as i32);

                // Round-trip center coordinate
                let (cx, cy) = (w as f64 / 2.0, h as f64 / 2.0);
                let (ncx, ncy) = geom.to_native(cx, cy).expect("center in bounds");
                let expected_ncx = ((nw as f64) / 2.0).round() as i32;
                let expected_ncy = ((nh as f64) / 2.0).round() as i32;
                assert_eq!(ncx, expected_ncx);
                assert_eq!(ncy, expected_ncy);
            }
        }

        // Prove that our test matrix contains cases where horizontal and vertical ratios differ!
        assert!(
            observed_differing_scales,
            "dimension table must include instances where scale_x != scale_y"
        );
    }

    #[test]
    fn nearest_pixel_rounding_never_truncates() {
        // scale is 1.0 (native == delivered)
        let geom = ScreenshotGeometry::new(100, 100, 100, 100).unwrap();
        // 10.49 -> 10, 10.50 -> 11
        assert_eq!(geom.to_native(10.49, 10.49).unwrap(), (10, 10));
        assert_eq!(geom.to_native(10.50, 10.50).unwrap(), (11, 11));

        // scale is 2.0
        let geom2 = ScreenshotGeometry::new(50, 50, 100, 100).unwrap();
        // 5.24 * 2 = 10.48 -> 10
        assert_eq!(geom2.to_native(5.24, 5.24).unwrap(), (10, 10));
        // 5.25 * 2 = 10.50 -> 11
        assert_eq!(geom2.to_native(5.25, 5.25).unwrap(), (11, 11));
    }

    #[test]
    fn rejects_out_of_bounds_coordinates_with_structured_refusal() {
        let geom = ScreenshotGeometry::new(800, 600, 1600, 1200).unwrap();

        let check_oob = |x: f64, y: f64| {
            let res = geom.to_native(x, y);
            assert!(res.is_err());
            let err = res.unwrap_err();
            let structured = err.structured_content.expect("structured refusal");
            assert_eq!(
                structured["code"].as_str().unwrap(),
                "screenshot_coordinate_out_of_bounds"
            );
            assert_eq!(structured["screenshot_width"].as_u64().unwrap(), 800);
            assert_eq!(structured["screenshot_height"].as_u64().unwrap(), 600);
        };

        check_oob(-0.1, 100.0);
        check_oob(100.0, -0.1);
        check_oob(800.1, 300.0);
        check_oob(400.0, 600.1);
        check_oob(f64::NAN, 100.0);
        check_oob(100.0, f64::INFINITY);

        // Inclusive boundaries are accepted
        assert!(geom.to_native(0.0, 0.0).is_ok());
        assert!(geom.to_native(800.0, 600.0).is_ok());
    }
}
