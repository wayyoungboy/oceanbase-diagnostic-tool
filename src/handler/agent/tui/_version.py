#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# MIT License - Copyright (c) LangChain, Inc.
# Vendored from deepagents-cli into OceanBase Diagnostic Tool.
# See src/handler/agent/tui/LICENSE for full license text.

"""Version information and lightweight constants for `deepagents-cli`."""

__version__ = "0.0.35"  # x-release-please-version

DOCS_URL = "https://docs.langchain.com/oss/python/deepagents/cli"
"""URL for `deepagents-cli` documentation."""

PYPI_URL = "https://pypi.org/pypi/deepagents-cli/json"
"""PyPI JSON API endpoint for version checks."""

CHANGELOG_URL = "https://github.com/langchain-ai/deepagents/blob/main/libs/cli/CHANGELOG.md"
"""URL for the full changelog."""

USER_AGENT = f"deepagents-cli/{__version__} update-check"
"""User-Agent header sent with PyPI requests."""
