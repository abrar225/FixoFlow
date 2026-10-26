"""Select native integration without importing another OS's frameworks."""
import sys
if sys.platform == 'darwin':
    from .macos import (activate_application, copy_to_clipboard, get_frontmost_app_info, insert_text_at_cursor,
                        notify, play_sound, permission_snapshot, request_all_permissions, open_permission_settings)
elif sys.platform == 'win32':
    from .windows import (activate_application, copy_to_clipboard, get_frontmost_app_info, insert_text_at_cursor,
                          notify, play_sound, permission_snapshot, request_all_permissions, open_permission_settings)
elif sys.platform.startswith('linux'):
    from .linux import (
        activate_application, copy_to_clipboard, get_frontmost_app_info,
        insert_text_at_cursor, notify, play_sound, permission_snapshot,
        request_all_permissions, open_permission_settings
    )
else:
    raise RuntimeError('Unsupported desktop operating system: ' + sys.platform)

__all__ = [
    "activate_application", "copy_to_clipboard", "get_frontmost_app_info",
    "insert_text_at_cursor", "notify", "play_sound", "permission_snapshot",
    "request_all_permissions", "open_permission_settings"
]
