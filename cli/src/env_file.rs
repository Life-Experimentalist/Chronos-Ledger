// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Reading and editing `.env` without disturbing its comments or order.

/// The value of `key`, from the last line that sets it (compose reads the last one too).
pub fn get(text: &str, key: &str) -> Option<String> {
    text.lines()
        .filter_map(|line| line.strip_prefix(key)?.strip_prefix('='))
        .next_back()
        .map(|v| v.trim().to_string())
}

/// Set `key` in place when a line sets it, otherwise append it.
pub fn set(text: &str, key: &str, value: &str) -> String {
    let mut found = false;
    let mut out: Vec<String> = text
        .lines()
        .map(
            |line| match line.strip_prefix(key).and_then(|r| r.strip_prefix('=')) {
                Some(_) => {
                    found = true;
                    format!("{key}={value}")
                }
                None => line.to_string(),
            },
        )
        .collect();
    if !found {
        out.push(format!("{key}={value}"));
    }
    out.join("\n") + "\n"
}

/// Placeholders `.env.example` ships with, and what leaving each one means.
pub const PLACEHOLDERS: &[(&str, &str)] = &[
    (
        "change_me_password",
        "DB_PASSWORD is still the example value",
    ),
    (
        "replace_with_64_char_hex",
        "JWT_SECRET_SIGNING_KEY is still the example value",
    ),
    (
        "replace_with_the_first_admin_password",
        "INITIAL_ADMIN_PASSWORD is still the example value",
    ),
    (
        "your_vapid",
        "VAPID keys are not set, so push notifications are off",
    ),
];

/// `bytes` random bytes as lowercase hex.
pub fn random_hex(bytes: usize) -> String {
    let mut buf = vec![0u8; bytes];
    getrandom::fill(&mut buf).expect("the operating system has no random source");
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

/// A password of letters and digits only, so it survives a URL, a shell and sed.
pub fn random_password(len: usize) -> String {
    const CHARS: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    let mut out = String::with_capacity(len);
    let mut buf = [0u8; 64];
    while out.len() < len {
        getrandom::fill(&mut buf).expect("the operating system has no random source");
        // Rejection sampling: modulo on the full byte range would favour the first characters.
        let limit = 256 - (256 % CHARS.len());
        for b in buf.iter().map(|&b| b as usize).filter(|&b| b < limit) {
            if out.len() == len {
                break;
            }
            out.push(CHARS[b % CHARS.len()] as char);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn get_reads_the_last_assignment_and_ignores_longer_keys() {
        let text = "VERSION=v1\nVERSION_X=no\n# VERSION=comment\nVERSION=v2\n";
        assert_eq!(get(text, "VERSION").as_deref(), Some("v2"));
        assert_eq!(get(text, "MISSING"), None);
    }

    #[test]
    fn set_replaces_in_place_and_keeps_comments() {
        let text = "# top\nA=1\nAB=2\n";
        assert_eq!(set(text, "A", "9"), "# top\nA=9\nAB=2\n");
        assert_eq!(set(text, "C", "3"), "# top\nA=1\nAB=2\nC=3\n");
    }

    #[test]
    fn passwords_have_the_length_asked_for_and_only_safe_characters() {
        let p = random_password(32);
        assert_eq!(p.len(), 32);
        assert!(p.chars().all(|c| c.is_ascii_alphanumeric()));
        assert_ne!(p, random_password(32));
        assert_eq!(random_hex(32).len(), 64);
    }
}
