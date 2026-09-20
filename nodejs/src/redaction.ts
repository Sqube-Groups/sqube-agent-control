const EMAIL_RE =
  /([a-zA-Z0-9._%+-]{1,2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
const TOKEN_PATTERNS = [
  /(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+/gi,
  /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi,
  /sk-[A-Za-z0-9]{20,}/g,
];

export function redactValue(value: unknown): string {
  let text = toSummaryString(value);
  text = text.replace(EMAIL_RE, (_m, a: string, b: string) => `${a}***@${b}`);
  for (const pattern of TOKEN_PATTERNS) {
    text = text.replace(pattern, "[REDACTED]");
  }
  if (text.length > 200) {
    text = text.slice(0, 197) + "...";
  }
  return text;
}

function toSummaryString(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "object" && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    return Object.keys(obj)
      .sort()
      .map((k) => `${k}=${redactValue(obj[k])}`)
      .join(" ");
  }
  if (Array.isArray(value)) {
    return value.map((v) => redactValue(v)).join(" ");
  }
  return String(value);
}
