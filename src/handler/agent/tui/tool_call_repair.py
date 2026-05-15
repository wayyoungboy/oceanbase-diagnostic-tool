#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""Middleware that repairs malformed JSON in LLM tool call arguments.

Some LLMs (e.g. Qwen3) occasionally produce invalid JSON in function-call
arguments — stray line-number prefixes, trailing commas, etc.  LangChain's
``default_tool_parser`` moves these calls to ``AIMessage.invalid_tool_calls``
and LangGraph's ``ToolNode`` never executes them, leaving the user with a
confusing error.

This middleware intercepts the model response, attempts lightweight JSON
repair on each ``invalid_tool_call``, and promotes successfully repaired
calls back to ``tool_calls`` so the graph can execute them normally.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import tool_call

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

_LINE_NUMBER_RE = re.compile(r"^(\s*)\d+\s+", re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _try_repair_json(raw: str) -> dict[str, Any] | None:
    """Attempt to repair common LLM JSON errors and parse the result.

    Returns the parsed dict on success, or ``None`` if repair fails.
    """
    # Strategy 1: strip line-number prefixes (e.g. "  9    " at line start)
    cleaned = _LINE_NUMBER_RE.sub(r"\1", raw)
    # Strategy 2: remove trailing commas before } or ]
    cleaned = _TRAILING_COMMA_RE.sub(r"\1", cleaned)

    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def _repair_response(response: ModelResponse) -> ModelResponse:
    """Inspect the response for invalid tool calls and attempt repair."""
    if not response.result:
        return response

    msg = response.result[0]
    if not isinstance(msg, AIMessage):
        return response

    invalid_calls = msg.invalid_tool_calls
    if not invalid_calls:
        return response

    repaired_tool_calls = list(msg.tool_calls)
    still_invalid = []

    for itc in invalid_calls:
        raw_args = itc.get("args")
        if not isinstance(raw_args, str) or not raw_args.strip():
            still_invalid.append(itc)
            continue

        parsed = _try_repair_json(raw_args)
        if parsed is not None:
            logger.info("Repaired invalid tool call '%s' (id=%s)", itc.get("name"), itc.get("id"))
            repaired_tool_calls.append(tool_call(name=itc.get("name") or "", args=parsed, id=itc.get("id")))
        else:
            logger.warning("Could not repair invalid tool call '%s' (id=%s): %s", itc.get("name"), itc.get("id"), raw_args[:200])
            still_invalid.append(itc)

    if len(still_invalid) == len(invalid_calls):
        return response

    repaired_msg = msg.model_copy(update={"tool_calls": repaired_tool_calls, "invalid_tool_calls": still_invalid})
    return ModelResponse(result=[repaired_msg, *response.result[1:]], structured_response=response.structured_response)


class ToolCallRepairMiddleware(AgentMiddleware):
    """Repair malformed JSON in ``invalid_tool_calls`` before the graph sees them."""

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        return _repair_response(handler(request))

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse:
        return _repair_response(await handler(request))
