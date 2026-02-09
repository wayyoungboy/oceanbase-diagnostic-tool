#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: output_formatter.py
@desc: Unified output formatter for all handlers
"""

import json
import sys
from typing import Any, Optional, Dict, List
import oyaml as yaml
import csv
import io
from tabulate import tabulate


class OutputFormatter:
    """
    Unified output formatter supporting multiple formats.

    Supports: table, json, yaml, csv
    """

    def __init__(self, format: str = 'table', quiet: bool = False, no_color: bool = False, stream=None):
        """
        Initialize output formatter.

        Args:
            format: Output format ('table', 'json', 'yaml', 'csv')
            quiet: Quiet mode (suppress table output)
            no_color: Disable color output
            stream: Output stream (default: sys.stdout)
        """
        self.format = format.lower()
        self.quiet = quiet
        self.no_color = no_color
        self.stream = stream or sys.stdout

        if self.format not in ['table', 'json', 'yaml', 'csv']:
            raise ValueError(f"Unsupported output format: {format}")

    def output(self, data: Any, title: Optional[str] = None):
        """
        Output data in the specified format.

        Args:
            data: Data to output (dict, list, or table data)
            title: Optional title for table format
        """
        if self.quiet and self.format == 'table':
            return

        formatters = {
            'table': self._format_table,
            'json': self._format_json,
            'yaml': self._format_yaml,
            'csv': self._format_csv,
        }

        result = formatters[self.format](data, title)
        print(result, file=self.stream, end='')

    def _format_json(self, data: Any, title: Optional[str] = None) -> str:
        """Format data as JSON."""
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _format_yaml(self, data: Any, title: Optional[str] = None) -> str:
        """Format data as YAML."""
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

    def _format_csv(self, data: Any, title: Optional[str] = None) -> str:
        """Format data as CSV."""
        output = io.StringIO()

        if isinstance(data, dict):
            # Convert dict to list of rows
            if title:
                writer = csv.writer(output)
                writer.writerow([title])
                writer.writerow([])

            # Try to convert to table format
            if all(isinstance(v, (dict, list)) for v in data.values()):
                # Nested structure - flatten
                rows = []
                for key, value in data.items():
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                row = [key] + list(item.values())
                                rows.append(row)
                            else:
                                rows.append([key, value])
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            rows.append([key, k, v])
                    else:
                        rows.append([key, value])

                writer = csv.writer(output)
                for row in rows:
                    writer.writerow(row)
            else:
                # Simple key-value pairs
                writer = csv.DictWriter(output, fieldnames=data.keys())
                writer.writeheader()
                writer.writerow(data)

        elif isinstance(data, list):
            writer = csv.writer(output)
            if data and isinstance(data[0], dict):
                # List of dicts
                fieldnames = data[0].keys()
                writer.writerow(fieldnames)
                for row in data:
                    writer.writerow([row.get(k, '') for k in fieldnames])
            else:
                # Simple list
                for row in data:
                    writer.writerow([row] if not isinstance(row, list) else row)

        else:
            # Simple value
            output.write(str(data))

        return output.getvalue()

    def _format_table(self, data: Any, title: Optional[str] = None) -> str:
        """Format data as table."""
        result = []

        if title:
            result.append(title)
            result.append("")

        if isinstance(data, dict):
            # Try to convert dict to table
            if all(isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) for v in data.values() if isinstance(v, list)):
                # Dict of lists of dicts - format each section
                for section_name, rows in data.items():
                    if rows and isinstance(rows[0], dict):
                        result.append(f"\n{section_name.upper()}:")
                        headers = list(rows[0].keys())
                        table_rows = [[row.get(h, '') for h in headers] for row in rows]
                        result.append(tabulate(table_rows, headers=headers, tablefmt="grid"))
                    else:
                        result.append(f"\n{section_name}: {rows}")
            elif all(isinstance(v, (str, int, float, bool)) for v in data.values()):
                # Simple key-value pairs
                result.append(tabulate([(k, v) for k, v in data.items()], headers=["Key", "Value"], tablefmt="grid"))
            else:
                # Complex nested structure - use JSON
                result.append(json.dumps(data, ensure_ascii=False, indent=2))

        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                # List of dicts - convert to table
                headers = list(data[0].keys())
                table_rows = [[row.get(h, '') for h in headers] for row in data]
                result.append(tabulate(table_rows, headers=headers, tablefmt="grid"))
            else:
                # Simple list
                result.append(tabulate([[item] for item in data], tablefmt="grid"))

        else:
            # Simple value
            result.append(str(data))

        return "\n".join(result) + "\n"
