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
