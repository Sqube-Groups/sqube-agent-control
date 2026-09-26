import type { ExecutionEvent } from "./events.js";

export interface EventSink {
  emit(event: ExecutionEvent): void;
}
