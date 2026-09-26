import { createRequire } from "node:module";
import { EventType, type ExecutionEvent } from "../events.js";
import type { EventSink } from "../eventSink.js";
import { redactValue } from "../redaction.js";

const require = createRequire(import.meta.url);

const TERMINAL = new Set<EventType>([
  EventType.ACTION_SUCCEEDED,
  EventType.ACTION_FAILED,
  EventType.ACTION_CANCELLED,
  EventType.ACTION_BLOCKED,
  EventType.APPROVAL_DENIED,
  EventType.APPROVAL_EXPIRED,
]);

const PAYLOAD_ALLOW: Partial<Record<EventType, Set<string>>> = {
  [EventType.ACTION_REQUESTED]: new Set(["action", "resource"]),
  [EventType.CONTEXT_RESOLVED]: new Set(["correlation_id", "root_execution_id"]),
  [EventType.POLICY_EVALUATED]: new Set(["decision", "policy_id", "policy_version", "reason"]),
  [EventType.ACTION_BLOCKED]: new Set(["reason"]),
  [EventType.APPROVAL_REQUESTED]: new Set(["approval_id", "expires_at"]),
  [EventType.APPROVAL_DENIED]: new Set(["reason"]),
  [EventType.APPROVAL_EXPIRED]: new Set(["reason"]),
  [EventType.ACTION_STARTED]: new Set(["approval_id"]),
  [EventType.ACTION_FAILED]: new Set(["error", "duration_ms"]),
  [EventType.ACTION_SUCCEEDED]: new Set(["duration_ms"]),
  [EventType.ACTION_CANCELLED]: new Set(["reason"]),
};

function safeAttr(key: string, value: unknown): string | number | boolean | undefined {
  const lower = key.toLowerCase();
  if (lower.includes("secret") || lower.includes("token") || lower.includes("password")) {
    return undefined;
  }
  if (value === null || value === undefined) return undefined;
  if (typeof value === "boolean" || typeof value === "number") return value;
  if (typeof value === "string") return value.length > 64 ? redactValue(value) : value;
  return redactValue(value);
}

function payloadAttrs(
  eventType: EventType,
  payload: Record<string, unknown>
): Record<string, string | number | boolean> {
  const allowed = PAYLOAD_ALLOW[eventType] ?? new Set<string>();
  const out: Record<string, string | number | boolean> = {};
  for (const key of allowed) {
    const val = safeAttr(key, payload[key]);
    if (val !== undefined) out[`sqube.${key}`] = val;
  }
  if (payload.approval_id !== undefined) {
    const v = safeAttr("approval_id", payload.approval_id);
    if (v !== undefined) out["sqube.approval_id"] = String(v);
  }
  if (eventType === EventType.POLICY_EVALUATED && payload.decision !== undefined) {
    out["sqube.decision"] = String(payload.decision);
  }
  if (eventType === EventType.POLICY_EVALUATED && payload.policy_id !== undefined) {
    out["sqube.policy_id"] = String(payload.policy_id);
  }
  return out;
}

type SpanLike = {
  addEvent: (name: string, attrs?: Record<string, string | number | boolean>) => void;
  setAttribute: (k: string, v: string | number | boolean) => void;
  end: () => void;
};

type CounterLike = { add: (n: number) => void };
type HistogramLike = { record: (n: number) => void };

export class OtelEventSink implements EventSink {
  private tracer: { startSpan: (name: string, opts?: { attributes?: Record<string, string | number | boolean> }) => SpanLike } | null = null;
  private counters = new Map<string, CounterLike>();
  private durationHist: HistogramLike | null = null;
  private spans = new Map<string, SpanLike>();

  constructor(tracerName = "sqube.agent.control") {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const api = require("@opentelemetry/api") as typeof import("@opentelemetry/api");
      this.tracer = api.trace.getTracer(tracerName) as unknown as typeof this.tracer;
      const meter = api.metrics.getMeter(tracerName);
      const names = [
        "sqube.executions.total",
        "sqube.executions.allowed",
        "sqube.executions.blocked",
        "sqube.executions.approval_required",
        "sqube.executions.succeeded",
        "sqube.executions.failed",
        "sqube.executions.cancelled",
        "sqube.approvals.granted",
        "sqube.approvals.denied",
        "sqube.approvals.expired",
      ];
      for (const name of names) {
        this.counters.set(name, meter.createCounter(name));
      }
      this.durationHist = meter.createHistogram("sqube.execution.duration");
    } catch {
      this.tracer = null;
    }
  }

  emit(event: ExecutionEvent): void {
    try {
      this.emitInner(event);
    } catch {
      /* telemetry must not affect execution */
    }
  }

  private emitInner(event: ExecutionEvent): void {
    if (!this.tracer) return;

    let span = this.spans.get(event.execution_id);
    const attrs = payloadAttrs(event.event_type, event.payload);
    attrs["sqube.execution_id"] = event.execution_id;

    if (event.event_type === EventType.ACTION_REQUESTED) {
      attrs["sqube.agent_id"] = event.actor;
      span = this.tracer.startSpan("sqube.execution", { attributes: attrs });
      this.spans.set(event.execution_id, span);
      this.inc("sqube.executions.total");
      span.addEvent("execution requested", attrs);
      return;
    }

    if (!span) {
      span = this.tracer.startSpan("sqube.execution", {
        attributes: { "sqube.execution_id": event.execution_id },
      });
      this.spans.set(event.execution_id, span);
    }

    const eventName = event.event_type.replace(/_/g, " ").toLowerCase();
    span.addEvent(eventName, attrs);
    this.recordMetrics(event, attrs);

    if (TERMINAL.has(event.event_type)) {
      const status = attrs["sqube.decision"] ?? event.event_type;
      span.setAttribute("sqube.status", String(status));
      span.end();
      this.spans.delete(event.execution_id);
    }
  }

  private inc(name: string, n = 1): void {
    this.counters.get(name)?.add(n);
  }

  private recordMetrics(
    event: ExecutionEvent,
    attrs: Record<string, string | number | boolean>
  ): void {
    switch (event.event_type) {
      case EventType.POLICY_EVALUATED: {
        const d = String(attrs["sqube.decision"] ?? "");
        if (d === "ALLOW") this.inc("sqube.executions.allowed");
        else if (d === "BLOCK") this.inc("sqube.executions.blocked");
        else if (d === "REQUIRE_APPROVAL") this.inc("sqube.executions.approval_required");
        break;
      }
      case EventType.ACTION_BLOCKED:
        this.inc("sqube.executions.blocked");
        break;
      case EventType.ACTION_SUCCEEDED:
        this.inc("sqube.executions.succeeded");
        this.recordDuration(event.payload.duration_ms);
        break;
      case EventType.ACTION_FAILED:
        this.inc("sqube.executions.failed");
        this.recordDuration(event.payload.duration_ms);
        break;
      case EventType.ACTION_CANCELLED:
        this.inc("sqube.executions.cancelled");
        break;
      case EventType.APPROVAL_GRANTED:
        this.inc("sqube.approvals.granted");
        break;
      case EventType.APPROVAL_DENIED:
        this.inc("sqube.approvals.denied");
        break;
      case EventType.APPROVAL_EXPIRED:
        this.inc("sqube.approvals.expired");
        break;
      default:
        break;
    }
  }

  private recordDuration(ms: unknown): void {
    if (typeof ms === "number" && this.durationHist) {
      this.durationHist.record(ms);
    }
  }
}
