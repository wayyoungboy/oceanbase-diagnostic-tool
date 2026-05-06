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

"""Machine-readable JSON output helpers for CLI subcommands.

This module deliberately stays stdlib-only so it can be imported from CLI
startup paths without pulling in unnecessary dependency trees.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Literal

OutputFormat = Literal["text", "json"]
"""Accepted internal output modes for CLI subcommands."""


def add_json_output_arg(parser: argparse.ArgumentParser, *, default: OutputFormat | None = None) -> None:
    """Add a `--json` flag to an argparse parser.

    Args:
        parser: Parser to update.
        default: Default output format for this parser.

            Pass `None` for subparsers so parent parser values are preserved.
    """
    if default is None:
        parser.add_argument(
            "--json",
            dest="output_format",
            action="store_const",
            const="json",
            default=argparse.SUPPRESS,
            help="Emit machine-readable JSON for this command",
        )
    else:
        parser.add_argument(
            "--json",
            dest="output_format",
            action="store_const",
            const="json",
            default=default,
            help="Emit machine-readable JSON for this command",
        )


def write_json(command: str, data: list | dict) -> None:
    """Write a JSON envelope to stdout and flush.

    The envelope is a single-line JSON object with a stable schema:

    ```json
    {"schema_version": 1, "command": "...", "data": ...}
    ```

    Args:
        command: Self-documenting command name (e.g. `'list'`,
            `'threads list'`).
        data: Payload — typically a list for listing commands or a dict
            for action/info commands.

            `default=str` is used so that `Path` and `datetime` objects
            serialize without error.
    """
    envelope = {"schema_version": 1, "command": command, "data": data}
    sys.stdout.write(json.dumps(envelope, default=str) + "\n")
    sys.stdout.flush()
