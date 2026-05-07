#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# MIT License - Copyright (c) LangChain, Inc.
# Vendored from deepagents-cli into OceanBase Diagnostic Tool.
# See src/handler/agent/tui/LICENSE for full license text.

"""Lightweight runtime context type for CLI model overrides.

Extracted from `configurable_model` so hot-path modules (`app`,
`textual_adapter`) can import `CLIContext` without pulling in the langchain
middleware stack.
"""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class CLIContext(TypedDict, total=False):
    """Runtime context passed via `context=` to the LangGraph graph.

    Carries per-invocation overrides that `ConfigurableModelMiddleware`
    reads from `request.runtime.context`.
    """

    model: str | None
    """Model spec to swap at runtime (e.g. `'openai:gpt-4o'`)."""

    model_params: dict[str, Any]
    """Invocation params (e.g. `temperature`, `max_tokens`) to merge
    into `model_settings`."""
