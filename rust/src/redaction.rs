use regex::Regex;
use std::sync::LazyLock;

static EMAIL_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"([a-zA-Z0-9._%+-]{1,2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
        .expect("email regex")
});

pub fn redact_value(value: &str) -> String {
    let mut text = value.to_string();
    text = EMAIL_RE
        .replace_all(&text, |caps: &regex::Captures| {
            format!("{}***@{}", &caps[1], &caps[2])
        })
        .to_string();
    let patterns = [
        Regex::new(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+")
            .unwrap(),
        Regex::new(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*").unwrap(),
        Regex::new(r"sk-[A-Za-z0-9]{20,}").unwrap(),
    ];
    for p in patterns {
        text = p.replace_all(&text, "[REDACTED]").to_string();
    }
    if text.len() > 200 {
        text = format!("{}...", text.chars().take(197).collect::<String>());
    }
    text
}
