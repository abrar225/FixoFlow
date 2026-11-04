"""Select native integration without importing another OS's frameworks."""
import sys
if sys.platform == 'darwin':
    from .macos import (activate_application, copy_to_clipboard, get_frontmost_app_info, get_stable_app_identity, insert_text_at_cursor, notify, play_sound, permission_snapshot, request_all_permissions, open_permission_settings)
elif sys.platform == 'win32':
    from .windows import (activate_application, copy_to_clipboard, get_frontmost_app_info, get_stable_app_identity, insert_text_at_cursor, notify, play_sound, permission_snapshot, request_all_permissions, open_permission_settings)
elif sys.platform.startswith('linux'):
    from .linux import (activate_application, copy_to_clipboard, get_frontmost_app_info, get_stable_app_identity, insert_text_at_cursor, notify, play_sound, permission_snapshot, request_all_permissions, open_permission_settings)
else:
    raise RuntimeError('Unsupported desktop operating system: '+sys.platform)

if sys.platform == 'darwin':
    from .macos import clipboard_restore_status, restore_previous_clipboard, discard_previous_clipboard, copy_to_clipboard_preserving
elif sys.platform == 'win32':
    from .windows import clipboard_restore_status, restore_previous_clipboard, discard_previous_clipboard, copy_to_clipboard_preserving
else:
    from .linux import clipboard_restore_status, restore_previous_clipboard, discard_previous_clipboard, copy_to_clipboard_preserving

__all__ = ["activate_application", "copy_to_clipboard", "get_frontmost_app_info", "get_stable_app_identity", "insert_text_at_cursor", "notify", "play_sound", "permission_snapshot", "request_all_permissions", "open_permission_settings", "clipboard_restore_status", "restore_previous_clipboard", "discard_previous_clipboard", "copy_to_clipboard_preserving"]
