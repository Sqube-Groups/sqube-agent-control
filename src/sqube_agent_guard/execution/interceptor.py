from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from sqube_agent_guard.execution.context import ExecutionContext

T = TypeVar("T")


class ExecutionInterceptor(Protocol):
    def intercept(self, ctx: ExecutionContext, next_fn: Callable[[], T]) -> T: ...
