"""Shared local hub actions; native hosts own rendering and dispatch."""
import json
from fixoflow.config import FixoflowConfig
from fixoflow.platform import permission_snapshot, request_all_permissions, copy_to_clipboard, open_permission_settings

class HubController:
    def close_model_packs(self):
        if getattr(self, 'preferences_pending', False):
            self._eval_js("flushPreferences(); onSettingsResult(true,'Preferences are still saving. Please retry Quit after they finish.');")
            return False
        coordinator=getattr(self,'coordinator',None)
        if coordinator is not None and not coordinator.close_services():
            self._eval_js("onSettingsResult(false,'Microphone or model cleanup is still pending. Retry Quit shortly.');")
            return False
        manager=getattr(self,'model_packs',None)
        if manager is None or manager.close(terminal=False):return True
        self._eval_js("onSettingsResult(false,'Model download is stopping or needs cleanup. Please retry Quit in a moment.');")
        return False

    def _publish_permissions(self):
        self._eval_js(f"onPermissionData({json.dumps(permission_snapshot())});")

    def handle_action(self, action: str, payload):
        """Processes IPC messages coming from hub.html UI."""
        if action in {'getOnboarding', 'saveOnboarding', 'practiceDictation', 'cancelPractice'}:
            from fixoflow.onboarding import snapshot, candidate
            try:
                if action == 'saveOnboarding':
                    if getattr(self, 'preferences_pending', False):
                        raise ValueError('Wait for your preference changes to finish saving, then continue.')
                    callback = getattr(self, 'on_config_change', None)
                    if callback is None: raise ValueError('Open the full app to save setup progress.')
                    callback(candidate(self.config, payload.get('step'), payload.get('complete', False)))
                elif action == 'practiceDictation':
                    if getattr(self, 'preferences_pending', False):
                        raise ValueError('Wait for your model and language choices to finish saving.')
                    callback = getattr(self, 'on_practice', None)
                    if callback is None: raise ValueError('Open the full app to test dictation.')
                    callback()
                elif action == 'cancelPractice':
                    callback = getattr(self, 'on_cancel_practice', None)
                    if callback: callback()
                self._eval_js('onOnboardingData('+json.dumps(snapshot(self.config))+');')
            except Exception as error:
                self._eval_js('onOnboardingError('+json.dumps(str(error))+');')
        elif action in {'getClipboardStatus','restorePreviousClipboard'}:
            from fixoflow.platform import clipboard_restore_status, restore_previous_clipboard
            status = (restore_previous_clipboard(insertion_confirmed=True) if action == 'restorePreviousClipboard'
                      and payload.get('confirmed') is True else clipboard_restore_status())
            self._eval_js('onClipboardStatus('+json.dumps(status)+');')
        elif action == 'getTrayStatus':
            callback = getattr(self, 'on_tray_status', None)
            self._eval_js('onTrayStatus('+json.dumps(callback() if callback else {'available':False,'message':'Open the full app to use its native tray.'})+');')
        elif action in {'getRecovery','retryRecovery','deleteRecovery','revealRecovery'}:
            try:
                if action=='retryRecovery':
                    callback=getattr(self,'on_recovery',None)
                    if callback is None:raise ValueError('Open the full application to retry recovery.')
                    callback(str(payload.get('id','')))
                    self._eval_js("onHistoryResult('Recovery queued. Results will be saved in History; nothing will be pasted.');")
                elif action=='deleteRecovery':
                    status=self.on_control_status() if self.on_control_status else {}
                    if status.get('state','IDLE')!='IDLE':raise ValueError('Finish the current operation before deleting recovery audio.')
                    self.db.delete_recovery_item(str(payload.get('id','')))
                    self.handle_action('getHistory',{})
                elif action=='revealRecovery':self.db.reveal_recovery_audio(str(payload.get('id','')))
                self._eval_js('onRecoveryData('+json.dumps(self.db.get_recovery_items())+');')
            except (ValueError,OSError,RuntimeError) as error:
                self._eval_js(f'onHistoryResult({json.dumps(str(error))});')
        elif action in {'startMicCheck','cancelMicCheck','getServices','installCatalogModel','warmSelectedModel','cancelCatalogModel'}:
            coordinator=getattr(self,'coordinator',None)
            configure=getattr(self,'on_maintenance',None)
            if coordinator is None:
                self._eval_js("onSettingsResult(false,'Open the full app to use microphone checks and model management.');")
                return
            try:
                if action=='startMicCheck':
                    if getattr(self,'preferences_pending',False):raise ValueError('Wait for your microphone choice to finish saving before checking it.')
                    if configure is None:raise ValueError('Dictation control is unavailable.')
                    configure(lambda:coordinator.checkup.start(self.config.input_device))
                elif action=='cancelMicCheck':coordinator.checkup.close()
                elif action=='installCatalogModel':
                    if configure is None:raise ValueError('Dictation control is unavailable.')
                    configure(lambda:coordinator.model_manager.start_install(str(payload.get('id',''))))
                elif action=='warmSelectedModel':
                    if getattr(self,'preferences_pending',False):raise ValueError('Wait for your model choice to finish saving before warming it.')
                    if configure is None:raise ValueError('Dictation control is unavailable.')
                    if not self.config.model_name.startswith('catalog:'):raise ValueError('Select an installed catalog model before warming it.')
                    configure(lambda:coordinator.model_manager.start_warm_up(self.config.model_name.removeprefix('catalog:'),coordinator.stt))
                elif action=='cancelCatalogModel':coordinator.model_manager.cancel()
                self._eval_js('onServiceData('+json.dumps({'microphone':coordinator.checkup.snapshot(),'models':coordinator.model_manager.snapshot(),'busy':coordinator.maintenance_busy})+');')
            except Exception as error:
                self._eval_js(f'onSettingsResult(false,{json.dumps(str(error))});')
        elif action == 'getInputDevices':
            try:
                from fixoflow.audio.devices import input_devices
                self._eval_js(f'onInputDeviceData({json.dumps(input_devices())}, "");')
            except Exception:
                self._eval_js('onInputDeviceData([], "Microphone list unavailable. Refresh after connecting your microphone.");')
        elif action == 'getHistoryAudio':
            import base64
            sid = str(payload.get('id',''))
            try:
                data = self.db.read_history_audio(sid)
                uri = 'data:audio/wav;base64,' + base64.b64encode(data).decode('ascii')
                self._eval_js(f'onHistoryAudioData({json.dumps(sid)}, {json.dumps(uri)}, "");')
            except (ValueError, OSError) as error:
                self._eval_js(f'onHistoryAudioData({json.dumps(sid)}, null, {json.dumps(str(error))});')
        elif action == 'getContextualSuggestions':
            self._eval_js(f'onContextualSuggestions({json.dumps(str(payload.get("id","")))}, {json.dumps(self.db.contextual_suggestions(str(payload.get("id",""))))});')
        elif action in {'getCorrections', 'proposeCorrection', 'approveCorrection', 'forgetCorrection', 'undoCorrectionApproval'}:
            try:
                if action == 'proposeCorrection':
                    self.db.propose_correction(str(payload.get('session_id', '')), payload.get('text'))
                elif action == 'approveCorrection':
                    self.db.approve_correction(str(payload.get('id', '')))
                elif action == 'forgetCorrection':
                    self.db.forget_correction(str(payload.get('id', '')))
                elif action == 'undoCorrectionApproval':
                    self.db.undo_correction_approval(str(payload.get('id','')))
                self._eval_js(f'onCorrectionData({json.dumps(self.db.get_corrections())});')
                if action != 'getCorrections':
                    self._eval_js("onHistoryResult('Correction memory updated. Raw transcripts are preserved.');")
            except (ValueError, OSError) as error:
                self._eval_js(f'onHistoryResult({json.dumps(str(error))});')
        elif action == 'getSessionJournal':
            self._eval_js(f'onSessionJournalData({json.dumps(self.db.get_session_journal())});')
        elif action == 'preferencesPending':
            self.preferences_pending = payload.get('pending') is True
        elif action in {'getStartupStatus','openStartupSettings'}:
            if action == 'openStartupSettings':
                callback = getattr(self, 'on_open_startup_settings', None)
                if callback:
                    try:
                        callback()
                    except Exception as error:
                        self._eval_js(f"document.getElementById('startupStatus').textContent={json.dumps(str(error))};")
                        return
            callback = getattr(self, 'on_startup_status', None)
            if callback:
                self._eval_js(f"onStartupData({json.dumps(callback())});")
        elif action in {'getLanguageOptions','installModelPack','cancelModelPack'}:
            from fixoflow.languages import options, ENGLISH_VARIANTS, MULTILINGUAL_MESSAGE
            manager=getattr(self,'model_packs',None)
            if action=='cancelModelPack' and manager:manager.cancel()
            requested = payload.get('model_name', self.config.model_name)
            # A draft-model query is read-only and cannot download or select it.
            try: choices = options(requested)
            except ValueError: choices = options(self.config.model_name)
            data={'languages':choices,'variants':ENGLISH_VARIANTS,'message':MULTILINGUAL_MESSAGE,
                  'model_name':requested,
                  'deferred_language':self.config.deferred_language}
            self._eval_js(f"onLanguageData({json.dumps(data)});")
        elif action == "startShortcutCapture":
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
            offset=max(0,int(payload.get("offset",0)))
            items = self.db.get_history(limit=51, search=str(search or ""), offset=offset)
            js = f"onHistoryData({json.dumps(items[:50])}, {json.dumps({'offset':offset,'has_more':len(items)>50})});"
            self._eval_js(js)

        elif action == "deleteHistory":
            sess_id = payload.get("id") if hasattr(payload, "get") else None
            if sess_id:
                try:self.db.delete_history_item(str(sess_id),cache_root=self.config.cache_dir)
                except (OSError,ValueError) as error:
                    self._eval_js(f"onHistoryResult({json.dumps(str(error))});")
                    return
                self.handle_action("getHistory", {})
                self.handle_action("getDashboard", {})
                self.handle_action('getCorrections', {})
                self.handle_action('getSessionJournal', {})

        elif action == "clearHistory":
            try:self.db.clear_all_history(cache_root=self.config.cache_dir)
            except (OSError,ValueError) as error:self._eval_js(f"onHistoryResult({json.dumps(str(error))});")
            self.handle_action("getHistory", {})
            self.handle_action("getDashboard", {})
            self.handle_action('getCorrections', {})
            self.handle_action('getSessionJournal', {})

        elif action == "getDictionary":
            offset=max(0,int(payload.get('offset',0)))
            words = self.db.get_dictionary(limit=101,offset=offset,search=str(payload.get('search','')))
            js = f"onDictionaryData({json.dumps(words[:100])}, {json.dumps({'offset':offset,'has_more':len(words)>100})});"
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
            sample = "um basically I can't wait to share the idea."
            previews = {style: clean_with_rules_counted(sample, style=style)[0]
                        for style in ("natural", "concise", "professional", "verbatim")}
            self._eval_js(f"onStylePreviewData({json.dumps({'input': sample, 'outputs': previews})});")
            js = f"onConfigData({json.dumps(asdict(self.config))});"
            self._eval_js(js)
            self._publish_permissions()
            startup = getattr(self, 'on_startup_status', None)
            if startup:
                self._eval_js(f"onStartupData({json.dumps(startup())});")

        elif action in {"saveConfig", "autosaveConfig"}:
            from fixoflow.settings import SettingsBusy
            automatic = action == 'autosaveConfig'
            request_id = payload.get('request_id')
            def reply(status, message):
                if automatic:
                    self._eval_js(f"onPreferencesResult({json.dumps({'request_id':request_id,'status':status,'message':message})});")
                else:
                    self._eval_js(f"onSettingsResult({str(status == 'saved').lower()}, {json.dumps(message)});")
            cfg_dict = payload.get("config") if hasattr(payload, "get") else {}
            if isinstance(cfg_dict, dict) and cfg_dict:
                try:
                    from dataclasses import asdict
                    allowed = {"mode", "role_preset", "theme", "input_device", "cpu_threads", "hold_shortcut", "hands_free_shortcut", "model_name", "always_show_overlay", "sound_enabled", "overlay_position", "output_style", "check_updates_on_launch", "auto_install_updates", "spoken_commands", "language", "english_variant", "start_at_login", "restore_clipboard", "close_to_tray"}
                    data = asdict(self.config)
                    data.update({k: v for k, v in cfg_dict.items() if k in allowed})
                    candidate = FixoflowConfig(**data)
                    candidate.validate_product()
                    if self.on_config_change is None:
                        raise RuntimeError("Open the full Fixoflow application to change dictation settings.")
                    status = self.on_control_status() if self.on_control_status else {}
                    if status.get('state', 'IDLE') != 'IDLE':
                        raise SettingsBusy('Waiting until dictation finishes…')
                    if 'start_at_login' in cfg_dict:
                        self.on_config_change(candidate, startup_requested=True)
                    else:
                        self.on_config_change(candidate)
                    reply('saved', 'Saved automatically.' if automatic else 'Preferences applied.')
                    if not automatic:
                        self.handle_action("getConfig", {})
                    startup = getattr(self, 'on_startup_status', None)
                    if startup:
                        self._eval_js(f"onStartupData({json.dumps(startup())});")
                except SettingsBusy as error:
                    reply('waiting', str(error))
                except Exception as e:
                    reply('error', str(e))
            else:
                reply('error', 'No valid preference changes were received.')
