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

"""
@time: 2025/03/15
@file: init.py
@desc: Init command handler - extracts bundled resources to user directory
"""

import os
import sys
import shutil

from src.common.paths import (
    get_user_obdiag_path,
    get_user_version_path,
    get_bundled_path,
    get_current_version,
    get_installed_version,
    is_initialized,
    copy_bundled_resources,
)


class InitHandler:
    """Handler for 'obdiag init' command."""

    def __init__(self, context, force=False, skip_backup=False):
        self.context = context
        self.stdio = context.stdio
        self.force = force
        self.skip_backup = skip_backup
        self.user_path = get_user_obdiag_path()

    def handle(self):
        """Execute the init command."""
        self.stdio.print("=" * 60)
        self.stdio.print("OceanBase Diagnostic Tool - Initialization")
        self.stdio.print("=" * 60)
        self.stdio.print("")

        # Check if already initialized
        if is_initialized() and not self.force:
            installed_version = get_installed_version()
            current_version = get_current_version()

            if installed_version == current_version:
                self.stdio.print(f"obdiag is already initialized (version: {installed_version})")
                self.stdio.print("")
                self.stdio.print("To re-initialize, use: obdiag init --force")
                return True
            else:
                self.stdio.print(f"Version change detected: {installed_version} -> {current_version}")
                self.stdio.print("Re-initializing...")
                self.stdio.print("")

        # Backup existing configuration if requested
        if is_initialized() and not self.skip_backup:
            self._backup_existing_config()

        # Copy bundled resources
        self.stdio.print("Copying resources to ~/.obdiag...")
        self.stdio.verbose(f"Target directory: {self.user_path}")

        if not copy_bundled_resources(self.stdio):
            self.stdio.error("Failed to copy resources.")
            return False

        # Setup bash completion
        self._setup_bash_completion()

        # Clean up old scene files
        self._cleanup_old_files()

        # Print success message
        self._print_success_message()

        return True

    def _backup_existing_config(self):
        """Backup existing configuration files."""
        backup_dir = os.path.join(self.user_path, 'backup_conf')
        os.makedirs(backup_dir, exist_ok=True)

        # Files to backup
        config_file = os.path.join(self.user_path, 'config.yml')
        if os.path.exists(config_file):
            import time
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'config.yml.{timestamp}')
            try:
                shutil.copy2(config_file, backup_file)
                self.stdio.verbose(f"Backed up config.yml to {backup_file}")
            except Exception as e:
                self.stdio.warn(f"Failed to backup config.yml: {e}")

    def _setup_bash_completion(self):
        """Setup bash command completion."""
        bashrc_file = os.path.expanduser('~/.bashrc')

        # Check if we have bundled init_obdiag_cmd.sh
        init_cmd_src = get_bundled_path('rpm/init_obdiag_cmd.sh')

        # Also check in user directory (from previous installation)
        init_cmd_user = os.path.join(self.user_path, 'init_obdiag_cmd.sh')

        # Check if init_obdiag_cmd.sh exists in bundled resources or user directory
        init_cmd_path = None
        if os.path.exists(init_cmd_src):
            init_cmd_path = init_cmd_src
        elif os.path.exists(init_cmd_user):
            init_cmd_path = init_cmd_user

        if init_cmd_path:
            # Copy to user directory for profile.d
            profile_target = '/etc/profile.d/obdiag.sh'
            try:
                if os.path.exists(profile_target) or os.access('/etc/profile.d', os.W_OK):
                    shutil.copy2(init_cmd_path, profile_target)
                    self.stdio.verbose(f"Installed bash completion to {profile_target}")
            except PermissionError:
                self.stdio.verbose("Skipped bash completion installation (requires root)")
            except Exception as e:
                self.stdio.verbose(f"Could not install bash completion: {e}")

        # Check for old alias in .bashrc
        if os.path.exists(bashrc_file):
            try:
                with open(bashrc_file, 'r') as f:
                    content = f.read()

                # Update old alias if exists
                if "alias obdiag='sh" in content:
                    self.stdio.print("Updating obdiag alias in .bashrc...")
                    with open(bashrc_file, 'a') as f:
                        f.write("\n# Updated by obdiag init\n")
                        f.write("alias obdiag='obdiag'\n")
            except Exception as e:
                self.stdio.verbose(f"Could not update .bashrc: {e}")

    def _cleanup_old_files(self):
        """Clean up old scene files from previous versions."""
        rca_path = os.path.join(self.user_path, 'rca')
        if os.path.exists(rca_path):
            try:
                for f in os.listdir(rca_path):
                    if f.endswith('_scene.py'):
                        file_path = os.path.join(rca_path, f)
                        os.remove(file_path)
                        self.stdio.verbose(f"Removed old scene file: {f}")
            except Exception as e:
                self.stdio.verbose(f"Error cleaning up old files: {e}")

    def _print_success_message(self):
        """Print success message with next steps."""
        current_version = get_current_version()

        self.stdio.print("")
        self.stdio.print("=" * 60)
        self.stdio.print("Initialization completed successfully!")
        self.stdio.print("")
        self.stdio.print(f"Version: {current_version}")
        self.stdio.print(f"Config:  {self.user_path}/config.yml")
        self.stdio.print("")
        self.stdio.print("Next steps:")
        self.stdio.print("  1. Edit the config file if needed:")
        self.stdio.print(f"     vi {self.user_path}/config.yml")
        self.stdio.print("")
        self.stdio.print("  2. Run obdiag commands:")
        self.stdio.print("     obdiag --help")
        self.stdio.print("")
        self.stdio.print("  3. For bash completion, run:")
        self.stdio.print("     source ~/.bashrc")
        self.stdio.print("     # or")
        self.stdio.print("     source /etc/profile.d/obdiag.sh")
        self.stdio.print("=" * 60)


def init_handler(context, force=False, skip_backup=False):
    """
    Entry point for init command.

    Args:
        context: Handler context
        force: Force re-initialization
        skip_backup: Skip backing up existing config

    Returns:
        True on success, False on failure
    """
    handler = InitHandler(context, force=force, skip_backup=skip_backup)
    return handler.handle()