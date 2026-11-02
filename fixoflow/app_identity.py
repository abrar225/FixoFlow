"""Persistent personalization scope is separate from a short-lived paste target.

Legacy native Mac bundle identifiers can be migrated without guessing. Legacy
Windows/X11 window/PID arrays cannot: keep them as provenance, not active scope.
"""
import ntpath
import re


def app_scope(value):
    if not isinstance(value, str):
        return ''
    if value.startswith(('macos:bundle:', 'windows:exe:', 'linux:exe:')):
        return value
    if re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', value):
        return 'macos:bundle:' + value
    return ''


def executable_scope(path, system):
    if system == 'windows' and isinstance(path, str) and ntpath.isabs(path):
        return 'windows:exe:' + ntpath.normcase(ntpath.normpath(path))
    if system == 'linux' and isinstance(path, str) and path.startswith('/') and not path.endswith(' (deleted)'):
        return 'linux:exe:' + path
    return ''
