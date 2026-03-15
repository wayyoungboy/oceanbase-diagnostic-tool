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
@file: paths.py
@desc: Unified path management for obdiag resources.
       Handles both development and packaged (PyInstaller) environments.
"""

import os
import sys
import shutil


def get_base_path():
    """
    Get the base path of obdiag installation.

    In development: returns the project root directory.
    In packaged environment: returns the directory containing the executable.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller packaged environment
        return os.path.dirname(sys.executable)
    else:
        # Development environment - project root (3 levels up from this file)
        return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def get_bundled_path(relative_path):
    """
    Get the path to a bundled resource (plugins, conf, dependencies, etc.).

    In development: returns path relative to project root.
    In packaged environment: returns path from PyInstaller's temporary extraction directory.

    Args:
        relative_path: Relative path like 'plugins', 'conf', 'dependencies/bin'

    Returns:
        Absolute path to the bundled resource.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller packages resources in sys._MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        # Development environment
        return os.path.join(get_base_path(), relative_path)


def get_user_obdiag_path():
    """
    Get the user's ~/.obdiag directory path.

    This is where runtime data, config, and extracted resources are stored.
    """
    obdiag_home = os.environ.get('OBDIAG_HOME')
    if obdiag_home:
        return os.path.expanduser(obdiag_home)
    return os.path.expanduser('~/.obdiag')


def get_user_config_path():
    """Get the user's config.yml path."""
    return os.path.join(get_user_obdiag_path(), 'config.yml')


def get_user_version_path():
    """Get the user's version.yaml path."""
    return os.path.join(get_user_obdiag_path(), 'version.yaml')


def is_initialized():
    """
    Check if obdiag has been initialized (obdiag init executed).

    Returns:
        True if version.yaml exists in user directory.
    """
    return os.path.exists(get_user_version_path())


def get_current_version():
    """
    Get the current obdiag version from the binary.

    Returns:
        Version string or None if not found.
    """
    try:
        from src.common.version import VERSION
        return VERSION
    except ImportError:
        return None


def get_installed_version():
    """
    Get the installed version from ~/.obdiag/version.yaml.

    Returns:
        Version string or None if not initialized.
    """
    version_path = get_user_version_path()
    if not os.path.exists(version_path):
        return None

    try:
        import yaml
        with open(version_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('obdiag_version')
    except Exception:
        return None


def needs_init():
    """
    Check if obdiag needs to be initialized.

    Returns:
        True if not initialized or version mismatch.
    """
    if not is_initialized():
        return True

    current = get_current_version()
    installed = get_installed_version()

    if current and installed and current != installed:
        return True

    return False


def copy_bundled_resources(stdio=None):
    """
    Copy bundled resources (plugins, conf, etc.) to user directory.

    This is called by 'obdiag init' command.

    Args:
        stdio: Optional IO object for logging

    Returns:
        True on success, False on failure.
    """
    user_path = get_user_obdiag_path()

    def log(msg, level='info'):
        if stdio:
            if level == 'verbose':
                stdio.verbose(msg)
            elif level == 'warn':
                stdio.warn(msg)
            elif level == 'error':
                stdio.error(msg)
            else:
                stdio.print(msg)

    # Create user directory structure
    dirs_to_create = [
        user_path,
        os.path.join(user_path, 'check'),
        os.path.join(user_path, 'log'),
        os.path.join(user_path, 'display'),
        os.path.join(user_path, 'gather'),
        os.path.join(user_path, 'rca'),
        os.path.join(user_path, 'backup'),
        os.path.join(user_path, 'backup_conf'),
    ]

    for dir_path in dirs_to_create:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            log(f"Created directory: {dir_path}", 'verbose')

    # Resources to copy from bundled to user directory
    resources = [
        ('plugins', 'plugins'),
        ('conf', 'conf'),
        ('example', 'example'),
    ]

    for src_name, dst_name in resources:
        src_path = get_bundled_path(src_name)
        dst_path = os.path.join(user_path, dst_name)

        if not os.path.exists(src_path):
            log(f"Source resource not found: {src_path}", 'warn')
            continue

        try:
            # Remove existing destination if it exists
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
                log(f"Removed existing: {dst_path}", 'verbose')

            # Copy the resource
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)

            log(f"Copied: {src_name} -> {dst_path}", 'verbose')
        except Exception as e:
            log(f"Failed to copy {src_name}: {e}", 'error')
            return False

    # Copy specific config example files
    ai_yml_src = get_bundled_path('conf/ai.yml.example')
    ai_yml_dst = os.path.join(user_path, 'ai.yml.example')
    if os.path.exists(ai_yml_src):
        try:
            shutil.copy2(ai_yml_src, ai_yml_dst)
            log(f"Copied: ai.yml.example", 'verbose')
        except Exception as e:
            log(f"Failed to copy ai.yml.example: {e}", 'warn')

    # Write version information
    version = get_current_version()
    version_path = get_user_version_path()
    try:
        with open(version_path, 'w') as f:
            f.write(f'obdiag_version: "{version or "unknown"}"\n')
        log(f"Written version info: {version}", 'verbose')
    except Exception as e:
        log(f"Failed to write version: {e}", 'error')
        return False

    return True


def get_resource_path(resource_type, relative_path=''):
    """
    Get the path to a resource, checking user directory first, then bundled.

    This allows users to override bundled resources with their own versions.

    Args:
        resource_type: Type of resource ('plugins', 'conf', 'dependencies', etc.)
        relative_path: Optional path relative to the resource type directory

    Returns:
        Path to the resource (user override or bundled).
    """
    # Check user directory first
    user_resource = os.path.join(get_user_obdiag_path(), resource_type, relative_path)
    if os.path.exists(user_resource):
        return user_resource

    # Fall back to bundled resource
    bundled_resource = get_bundled_path(os.path.join(resource_type, relative_path))
    if os.path.exists(bundled_resource):
        return bundled_resource

    # Return bundled path even if it doesn't exist (for error messages)
    return bundled_resource


def get_plugin_path(plugin_name):
    """
    Get the path to a specific plugin.

    Args:
        plugin_name: Name of the plugin directory (e.g., 'gather', 'check')

    Returns:
        Path to the plugin directory.
    """
    return get_resource_path('plugins', plugin_name)


def get_dependency_path(dependency_name):
    """
    Get the path to a dependency binary (obstack, flamegraph scripts, etc.).

    Args:
        dependency_name: Name of the dependency file

    Returns:
        Path to the dependency.
    """
    # Check user directory first
    user_dep = os.path.join(get_user_obdiag_path(), 'dependencies', 'bin', dependency_name)
    if os.path.exists(user_dep):
        return user_dep

    # Check bundled
    bundled_dep = get_bundled_path(os.path.join('dependencies', 'bin', dependency_name))
    if os.path.exists(bundled_dep):
        return bundled_dep

    # Return bundled path even if it doesn't exist
    return bundled_dep


def get_obstack_path(arch='x86_64'):
    """
    Get the path to the obstack binary for a specific architecture.

    Args:
        arch: Architecture ('x86_64' or 'aarch64')

    Returns:
        Path to the obstack binary.
    """
    if arch == 'aarch64':
        return get_dependency_path('obstack_aarch64')
    else:
        return get_dependency_path('obstack_x86_64')


def get_flamegraph_scripts():
    """
    Get paths to FlameGraph scripts.

    Returns:
        Tuple of (stackcollapse_path, flamegraph_path) or (None, None) if not found.
    """
    stackcollapse = get_dependency_path('stackcollapse-perf.pl')
    flamegraph = get_dependency_path('flamegraph.pl')

    if os.path.exists(stackcollapse) and os.path.exists(flamegraph):
        return stackcollapse, flamegraph

    return None, None