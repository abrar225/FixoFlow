"""Portable shortcut identity, conflict rules, capture, and edge routing.

Input adapters supply physical identities separately from printable labels.
No OS imports, audio work, or persistent key log belongs in this module.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import sys
import time

MODIFIERS = {'ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'alt_l', 'alt_r', 'cmd', 'cmd_l', 'cmd_r', 'shift', 'shift_l', 'shift_r', 'fn'}
NAMED = MODIFIERS | {'space','tab','enter','backspace','delete','esc','caps_lock','home','end','page_up','page_down','left','right','up','down',
    'media_play_pause','media_volume_mute','media_volume_down','media_volume_up','media_previous','media_next','media_eject'} | {f'f{i}' for i in range(1,25)}
SYMBOLS = {'ctrl':'⌃','alt':'⌥','cmd':'⌘','shift':'⇧','fn':'Fn','space':'Space','esc':'Escape','caps_lock':'Caps Lock',
           'page_up':'Page Up','page_down':'Page Down','media_play_pause':'Play / Pause','media_volume_up':'Volume Up','media_volume_down':'Volume Down','media_volume_mute':'Mute'}

if sys.platform != 'darwin':
    SYMBOLS.update(ctrl='Ctrl',alt='Alt',cmd='Windows' if sys.platform=='win32' else 'Super',shift='Shift')


def key_label(key):
    if key.startswith('mouse:'):
        number = int(key[6:])
        return {0:'Left Click',1:'Right Click',2:'Middle Click'}.get(number, f'Mouse {number+1}')
    if key.startswith('vk:'):
        return f'Key code {key[3:]}'
    if key.endswith(('_l','_r')) and key[:-2] in SYMBOLS:
        return SYMBOLS[key[:-2]] + (' Left' if key.endswith('_l') else ' Right')
    return SYMBOLS.get(key, key.upper() if len(key) == 1 else key.replace('_',' ').title())


@dataclass(frozen=True)
class Shortcut:
    keys: tuple[str, ...]
    label: str = ''

    def __post_init__(self):
        if not self.keys or any(not isinstance(key,str) for key in self.keys) or len(self.keys) != len(set(self.keys)):
            raise ValueError('Choose a key or button without duplicate keys.')
        for key in self.keys:
            if not isinstance(key, str) or not (len(key) == 1 or key in NAMED or re.fullmatch(r'(?:vk|mouse):\d+', key)):
                raise ValueError(f'Unsupported shortcut key: {key!r}')
            if key.startswith('mouse:') and not 0 <= int(key[6:]) <= 31:
                raise ValueError('This mouse button is not supported.')
        if len([key for key in self.keys if key.startswith('mouse:')]) > 1:
            raise ValueError('Choose one mouse button per shortcut.')
        if not isinstance(self.label, str) or len(self.label) > 200:
            raise ValueError('Invalid shortcut label.')

    @classmethod
    def read(cls, value):
        if not isinstance(value, dict) or not isinstance(value.get('keys'), list):
            raise ValueError('Shortcut must contain a list of keys.')
        return cls(tuple(value['keys']), value.get('label',''))

    @classmethod
    def from_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Choose a shortcut key or button.')
        keys = tuple(part.strip().strip('<>').lower() for part in value.split('+'))
        return cls(keys)

    def display(self):
        return self.label or ' + '.join(key_label(k) for k in self.keys)

    def as_dict(self):
        return {'keys':list(self.keys), 'label':self.display()}


def compatible(a, b):
    if a == b:
        return True
    return (a in {'ctrl','cmd','alt','shift'} and b in {a+'_l',a+'_r'}) or (b in {'ctrl','cmd','alt','shift'} and a in {b+'_l',b+'_r'})


def validate_pair(hold, hands_free):
    a, b = Shortcut.read(hold), Shortcut.read(hands_free)
    if 'caps_lock' in a.keys:
        raise ValueError('Caps Lock emits toggle events on macOS. Use another hold-to-talk key.')
    subset = lambda x,y: all(any(compatible(k,j) for j in y.keys) for k in x.keys)
    if subset(a,b) or subset(b,a):
        raise ValueError('Choose distinct, non-overlapping hold-to-talk and hands-free shortcuts.')
    return a,b


class ShortcutRouter:
    """Only emits edges: repeat, release ordering, and capture cannot toggle twice."""
    def __init__(self, hold, hands_free, controls, clock=time.monotonic):
        self.hold, self.hands_free = validate_pair(hold, hands_free)
        self.controls = controls
        self.clock = clock
        self.pressed = {}
        self.active = {'hold':False,'hands_free':False}
        self.capture = None
        self.quarantined = False

    def _matches(self, binding):
        tokens = [token for token,_ in self.pressed.values()]
        no_extra_modifiers = not any(token in MODIFIERS and not any(compatible(required,token) for required in binding.keys) for token in tokens)
        return no_extra_modifiers and all(any(compatible(required,actual) for actual in tokens) for required in binding.keys)

    def begin_capture(self, callback):
        if self.controls.state != 'IDLE':
            raise RuntimeError('Finish or cancel dictation before changing shortcuts.')
        self.capture = (callback, self.clock()+20)
        self.quarantined = True
        self.pressed.clear()

    def cancel_capture(self, message='Shortcut recording cancelled.'):
        capture,self.capture = self.capture,None
        self.quarantined = bool(self.pressed)
        if capture:
            capture[0](None,message)

    def expire_capture(self):
        if self.capture and self.clock() >= self.capture[1]:
            self.cancel_capture('Shortcut recording timed out. Try again.')

    def commit_capture(self, keys, label=''):
        if not self.capture:
            return
        binding = Shortcut(tuple(dict.fromkeys(keys)),label)
        callback = self.capture[0]
        self.capture = None
        self.quarantined = bool(self.pressed)
        callback(binding.as_dict(),'Shortcut selected. Save preferences to apply it.')

    def input(self, physical, token, down, label=''):
        self.expire_capture()
        if down and physical in self.pressed:
            return self.capture is not None or self.quarantined or any(self.active.values())
        if self.capture:
            if token in {'mouse:0','mouse:1'}:
                return False
            if down:
                if token == 'esc' and not self.pressed:
                    self.cancel_capture()
                    return True
                self.pressed[physical] = (token,label or key_label(token))
                if token.startswith('mouse:'):
                    # Primary clicks remain available for Cancel and navigation.
                    if token not in {'mouse:0','mouse:1'}:
                        self.commit_capture([v[0] for v in self.pressed.values()], ' + '.join(v[1] for v in self.pressed.values()))
            else:
                if physical in self.pressed:
                    values = list(self.pressed.values())
                    self.pressed.pop(physical,None)
                    self.commit_capture([v[0] for v in values], ' + '.join(v[1] for v in values))
            return token not in {'mouse:0','mouse:1'}
        was_pressed = physical in self.pressed
        if down:
            self.pressed[physical] = (token,label)
        else:
            self.pressed.pop(physical,None)
        if self.quarantined:
            self.quarantined = bool(self.pressed)
            return was_pressed
        matched = {'hold':self._matches(self.hold), 'hands_free':self._matches(self.hands_free)}
        consumed = False
        for mode in ('hands_free','hold'):
            if matched[mode] and not self.active[mode]:
                self.controls.toggle() if mode == 'hands_free' else self.controls.hold_press()
                consumed = True
            elif self.active[mode] and not matched[mode]:
                if mode == 'hold':
                    self.controls.hold_release()
                consumed = True
        self.active = matched
        if down and token == 'esc' and not consumed:
            self.controls.cancel()
            return True
        return consumed

    def reset(self):
        self.cancel_capture()
        if self.active['hold']:
            self.controls.hold_release()
        self.pressed.clear()
        self.active = {'hold':False,'hands_free':False}
        self.quarantined = False
