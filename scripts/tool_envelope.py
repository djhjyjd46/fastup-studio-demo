#!/usr/bin/env python3
"""Standard execution envelope for FastUp Studio CLI tools.

Enforces tool quality by providing a deterministic JSON contract for outputs,
standardized error codes, duration tracking (ms), and an explicit `retryable` flag.
Following Google SRE & Anthropic tool design principles.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Optional

# Standard exit codes
EXIT_SUCCESS = 0
EXIT_NON_RETRYABLE = 1
EXIT_RETRYABLE = 2


@dataclass
class ToolError:
    code: str
    message: str
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


@dataclass
class ToolEnvelope:
    status: str  # "success" or "error"
    tool: str
    duration_ms: int
    data: Optional[Any] = None
    error: Optional[ToolError] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": self.status,
            "tool": self.tool,
            "duration_ms": self.duration_ms,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = asdict(self.error)
        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def envelope_success(tool: str, data: Any, duration_ms: int = 0) -> ToolEnvelope:
    """Create a standardized success envelope."""
    return ToolEnvelope(
        status="success",
        tool=tool,
        duration_ms=max(0, duration_ms),
        data=data,
    )


def envelope_error(
    tool: str,
    code: str,
    message: str,
    retryable: bool = False,
    details: Optional[Dict[str, Any]] = None,
    duration_ms: int = 0,
) -> ToolEnvelope:
    """Create a standardized error envelope."""
    return ToolEnvelope(
        status="error",
        tool=tool,
        duration_ms=max(0, duration_ms),
        error=ToolError(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        ),
    )


def run_enveloped(
    tool_name: str,
    fn: Callable[..., Any],
    *args: Any,
    is_retryable_exception: Optional[Callable[[Exception], bool]] = None,
    **kwargs: Any,
) -> ToolEnvelope:
    """Execute a callable and wrap its result or exception into a ToolEnvelope."""
    start_time = time.perf_counter()
    try:
        data = fn(*args, **kwargs)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return envelope_success(tool_name, data, duration_ms=duration_ms)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        code = getattr(exc, "code", exc.__class__.__name__)
        message = str(exc)
        retryable = False
        if is_retryable_exception:
            retryable = is_retryable_exception(exc)
        elif isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            retryable = True

        details = getattr(exc, "details", None)
        return envelope_error(
            tool=tool_name,
            code=str(code),
            message=message,
            retryable=retryable,
            details=details,
            duration_ms=duration_ms,
        )


def emit_envelope_and_exit(envelope: ToolEnvelope) -> None:
    """Print the envelope to stdout and exit with the appropriate exit code."""
    # Ensure stdout handles UTF-8 on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(envelope.to_json(indent=2))
    if envelope.status == "success":
        sys.exit(EXIT_SUCCESS)
    if envelope.error and envelope.error.retryable:
        sys.exit(EXIT_RETRYABLE)
    sys.exit(EXIT_NON_RETRYABLE)
