# Cross-SDK contract fixtures (v1.0)

Shared semantic scenarios for Python, Node.js, and Rust:

- ALLOW / BLOCK / REQUIRE_APPROVAL
- Approval deny / expiry
- Redaction and parameter hashing
- Policy precedence (BLOCK > REQUIRE_APPROVAL > ALLOW)

Python implements the reference behavior in v1.0.0; other SDKs must match these fixtures before claiming v1 parity.
