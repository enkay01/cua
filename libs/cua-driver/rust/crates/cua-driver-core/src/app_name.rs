//! Normalization and matching for application and process names.

/// Normalize an application name by stripping any trailing `.exe` (case-insensitive)
/// and trimming leading/trailing whitespace.
pub fn normalize_app_name(name: &str) -> &str {
    let trimmed = name.trim();
    if trimmed.len() >= 4 && trimmed[trimmed.len() - 4..].eq_ignore_ascii_case(".exe") {
        &trimmed[..trimmed.len() - 4]
    } else {
        trimmed
    }
}

/// Case-insensitive comparison of process / app names, ignoring a trailing `.exe`.
pub fn app_name_matches(app_name: &str, filter: &str) -> bool {
    normalize_app_name(app_name).eq_ignore_ascii_case(normalize_app_name(filter))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_exact_and_case_insensitive() {
        assert!(app_name_matches("notepad", "notepad"));
        assert!(app_name_matches("Notepad", "notepad"));
        assert!(app_name_matches("notepad", "Notepad"));
        assert!(app_name_matches("NOTEPAD", "notepad"));
    }

    #[test]
    fn matches_with_and_without_exe_suffix() {
        assert!(app_name_matches("Notepad.exe", "notepad"));
        assert!(app_name_matches("notepad", "Notepad.exe"));
        assert!(app_name_matches("Notepad.EXE", "notepad"));
        assert!(app_name_matches("Notepad.exe", "NOTEPAD.EXE"));
    }

    #[test]
    fn rejects_substring_collisions() {
        assert!(!app_name_matches("Code - Insiders", "Code"));
        assert!(!app_name_matches("Code", "Code - Insiders"));
        assert!(!app_name_matches("Slack Helper", "Slack"));
        assert!(!app_name_matches("terminal", "term"));
    }
}
