---
sidebar_position: 3
title: Optional LLM probes
---

# Optional LLM probes

Sqube Execution Guard **v0.1 does not call an LLM** to make `ALLOW` / `BLOCK` / `REQUIRE_APPROVAL` decisions. Policies are deterministic application code (see the [v0.1 spec](./v0.1-spec)).

The repository may include **optional** scripts under `examples/` for manual or agent experimentation with external APIs. These probes are **not** wired into `ExecutionGuard`, are **not** run in CI, and are **not** part of the guard contract.

## NVIDIA Integrate (Kimi vision)

[`examples/nvidia_kimi_vision_probe.py`](https://github.com/Sqube-Groups/sqube-agent-control/blob/main/examples/nvidia_kimi_vision_probe.py) mirrors NVIDIA’s chat-completions sample (default model `moonshotai/kimi-k3`, optional catalog image URL).

**Credentials:** set `NVIDIA_API_KEY` or `NVAPI_API_KEY` in your environment (see repo root `.env.example`). Never commit API keys.

**Dependencies:**

```bash
pip install requests
# or: pip install -e ".[probes]"
```

**Run:**

```bash
export NVIDIA_API_KEY="your-key"
python examples/nvidia_kimi_vision_probe.py              # streaming (default)
python examples/nvidia_kimi_vision_probe.py --no-stream    # JSON response
python examples/nvidia_kimi_vision_probe.py --no-image-url --prompt "Hello"
```

Use these scripts only when you explicitly want to test an external LLM; they do not affect ledger entries or guard decisions.
