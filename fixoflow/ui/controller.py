"""Shared local hub actions; native hosts own rendering and dispatch."""
import json
from fixoflow.config import FixoflowConfig
from fixoflow.platform import permission_snapshot, request_all_permissions, copy_to_clipboard, open_permission_settings

class HubController:
    def _publish_permissions(self):
        self._eval_js(f"onPermissionData({json.dumps(permission_snapshot())});")

    def handle_action(self, action: str, payload):
        """Processes IPC messages coming from hub.html UI."""
        if action == "startShortcutCapture":
            field = payload.get('field')
            if field not in {'hold_shortcut','hands_free_shortcut'}:
                return
            try:
                if self.on_shortcut_capture is None:
                    raise RuntimeError('Open the full Fixo Flow app to record a shortcut.')
                self.on_shortcut_capture(field)
            except Exception as error:
                self._eval_js(f"onShortcutCaptured({json.dumps({'field':field,'binding':None,'message':str(error)})});")
        elif action == "cancelShortcutCapture":
            if self.on_cancel_capture:
                self.on_cancel_capture()
        elif action == "capturePrimaryMouse":
            if self.on_primary_mouse_capture:
                self.on_primary_mouse_capture(payload.get('button'))
        elif action == "checkUpdates":
            if self.on_update_check:
                self.on_update_check()
        elif action == "getUpdateStatus":
            if self.on_update_status:
                self._eval_js(f"onUpdateData({json.dumps(self.on_update_status())});")
        elif action == "openRelease":
            if self.on_open_release:
                self.on_open_release()
        elif action == "getPermissions":
            self._publish_permissions()
        elif action == "requestPermissions":
            self._eval_js(f"onPermissionData({json.dumps(request_all_permissions())});")
            self.handle_action("getControlStatus", {})
        elif action == "getControlStatus":
            if self.on_control_status:
                self._eval_js(f"onControlStatus({json.dumps(self.on_control_status())});")
        elif action == "showOverlay":
            if self.on_show_overlay:
                self.on_show_overlay()
        elif action == "enableShortcut":
            try:
                if self.on_enable_shortcut is None:
                    raise RuntimeError("Open the full Fixoflow application to enable dictation.")
                message = self.on_enable_shortcut()
                if message:
                    self._eval_js(f"onSettingsResult(false, {json.dumps(message)});")
                else:
                    self._eval_js("onSettingsResult(true, 'Shortcut enabled.');")
            except Exception as e:
                self._eval_js(f"onSettingsResult(false, {json.dumps(str(e))});")
            self._publish_permissions()
            self.handle_action("getControlStatus", {})
        elif action == "restartApp":
            if self.on_restart is None:
                self._eval_js("onSettingsResult(false, 'Open the full Fixoflow application to restart it.');")
            else:
                self._eval_js("onSettingsResult(true, 'Restarting Fixoflow…');")
                self.on_restart()
        elif action == "openPermissionSettings":
            section = payload.get("section", "")
            allowed = {"microphone": "Privacy_Microphone", "accessibility": "Privacy_Accessibility", "input": "Privacy_ListenEvent"}
            if section in allowed:
                open_permission_settings(section)
        elif action == "copyText":
            if isinstance(payload.get("text"), str):
                copy_to_clipboard(payload["text"])
        elif action == "getDashboard":
            stats = self.db.get_total_stats()
            top_apps = self.db.get_app_breakdown()
            recent = self.db.get_history(limit=5)
            js = f"onDashboardData({json.dumps(stats)}, {json.dumps(top_apps)}, {json.dumps(recent)});"
            self._eval_js(js)

        elif action == "getInsights":
            import getpass
            user = getpass.getuser()
            insights = {
                "user": user,
                "total": self.db.get_total_stats(),
                "today": self.db.get_today_stats(),
                "streak": self.db.get_streak(),
                "week": self.db.get_week_activity(7),
                "fixes": self.db.get_fix_stats(),
                "apps": self.db.get_app_breakdown(),
            }
            self._eval_js(f"onInsightsData({json.dumps(insights)});")

        elif action == "getHistory":
            search = payload.get("search", "") if hasattr(payload, "get") else ""
            items = self.db.get_history(limit=50, search=str(search or ""))
            js = f"onHistoryData({json.dumps(items)});"
            self._eval_js(js)

        elif action == "deleteHistory":
            sess_id = payload.get("id") if hasattr(payload, "get") else None
            if sess_id:
                self.db.delete_history_item(str(sess_id))
                self.handle_action("getHistory", {})
                self.handle_action("getDashboard", {})

        elif action == "clearHistory":
            self.db.clear_all_history()
            self.handle_action("getHistory", {})
            self.handle_action("getDashboard", {})

        elif action == "getDictionary":
            words = self.db.get_dictionary(limit=100)
            js = f"onDictionaryData({json.dumps(words)});"
            self._eval_js(js)

        elif action == "addWord":
            phrase = str(payload.get("phrase", "") if hasattr(payload, "get") else "")
            replacement = str(payload.get("replacement", "") if hasattr(payload, "get") else "")
            category = str(payload.get("category", "general") if hasattr(payload, "get") else "general")
            if phrase and replacement:
                self.db.upsert_word(phrase, replacement, category=category, auto_learned=0)
                self.handle_action("getDictionary", {})

        elif action == "deleteWord":
            phrase = str(payload.get("phrase", "") if hasattr(payload, "get") else "")
            if phrase:
                self.db.delete_word(phrase)
                self.handle_action("getDictionary", {})

        elif action == "getConfig":
            from dataclasses import asdict
            from fixoflow.brain.polisher import clean_with_rules_counted
            sample = "um basically I can't wait to share the idea period"
            previews = {style: clean_with_rules_counted(sample, style=style)[0]
                        for style in ("natural", "concise", "professional", "verbatim")}
            self._eval_js(f"onStylePreviewData({json.dumps({'input': sample, 'outputs': previews})});")
            js = f"onConfigData({json.dumps(asdict(self.config))});"
            self._eval_js(js)
            self._publish_permissions()

        elif action == "saveConfig":
            cfg_dict = payload.get("config") if hasattr(payload, "get") else {}
            if cfg_dict:
                try:
                    from dataclasses import asdict
                    allowed = {"mode", "hold_shortcut", "hands_free_shortcut", "model_name", "always_show_overlay", "sound_enabled", "overlay_position", "output_style", "check_updates_on_launch", "auto_install_updates"}
                    data = asdict(self.config)
                    data.update({k: v for k, v in cfg_dict.items() if k in allowed})
                    candidate = FixoflowConfig(**data)
                    candidate.validate()
                    if self.on_config_change is None:
                        raise RuntimeError("Open the full Fixoflow application to change dictation settings.")
                    self.on_config_change(candidate)
                    self._eval_js("onSettingsResult(true, 'Preferences applied.');")
                    self.handle_action("getConfig", {})
                except Exception as e:
                    self._eval_js(f"onSettingsResult(false, {json.dumps(str(e))});")
