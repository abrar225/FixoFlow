from types import SimpleNamespace
from unittest.mock import Mock
import threading
import pytest
from fixoflow.controls import DictationControls, shortcut_label
from fixoflow.config import FixoflowConfig
from fixoflow.shortcuts import Shortcut, ShortcutRouter, validate_pair

class DeferredExecutor:
    def __init__(self): self.pending=[]
    def submit(self,fn,*args): self.pending.append((fn,args))
    def drain(self):
        while self.pending:
            fn,args=self.pending.pop(0);fn(*args)
    def shutdown(self,wait=True): self.drain()

@pytest.fixture
def interaction():
    coordinator=SimpleNamespace(state='IDLE',recorder=SimpleNamespace(is_recording=False),events=[])
    def start(cancellation=None):
        coordinator.events.append('start');coordinator.state='RECORDING';coordinator.recorder.is_recording=True
    def finish(auto_paste):
        coordinator.events.append('stop');coordinator.state='IDLE';coordinator.recorder.is_recording=False
    def cancel():
        coordinator.events.append('cancel');coordinator.state='IDLE';coordinator.recorder.is_recording=False
    coordinator.start_recording=start;coordinator.stop_and_process=finish;coordinator.cancel_recording=cancel
    executor=DeferredExecutor();clock=[0.0]
    controls=DictationControls(coordinator,FixoflowConfig(),executor=executor)
    return controls,coordinator,executor,clock

def test_short_hold_finishes_even_before_microphone_opens(interaction):
    c,b,e,_=interaction;c.hold_press();c.hold_release();assert c.state=='PROCESSING';e.drain();assert b.events==['start','stop']

def test_toggle_does_not_need_a_held_key(interaction):
    c,b,e,_=interaction;c.toggle();e.drain();assert c.state=='RECORDING';c.toggle();e.drain();assert b.events==['start','stop']

def test_autorepeat_does_not_start_multiple_sessions(interaction):
    c,b,e,_=interaction
    for _ in range(8):c.hold_press()
    c.hold_release();e.drain();assert b.events==['start','stop']

def test_holding_key_during_hands_free_does_not_own_that_session(interaction):
    c,b,e,_=interaction;c.toggle();e.drain();c.hold_press();c.hold_release();e.drain();assert b.events==['start'];c.toggle();e.drain();assert b.events==['start','stop']

def test_processing_ignores_all_inputs(interaction):
    c,b,e,_=interaction;c.toggle();c.toggle();c.toggle();c.hold_press();c.hold_release();e.drain();assert b.events==['start','stop']

def test_cancel_queued_start_keeps_audio_and_never_transcribes(interaction):
    c,b,e,_=interaction;c.hold_press();c.cancel();c.hold_release();e.drain();assert b.events==['start','cancel']

def test_start_failure_recovers_for_next_input(interaction):
    c,b,e,_=interaction;original=b.start_recording;b.start_recording=Mock(side_effect=RuntimeError('unavailable'));c.toggle();e.drain();assert c.state=='IDLE';b.start_recording=original;c.toggle();e.drain();assert c.state=='RECORDING'

def test_old_hold_release_cannot_stop_new_toggle_session(interaction):
    c,b,e,_=interaction;c.hold_press();e.drain();c.toggle();e.drain();c.toggle();e.drain();c.hold_release();e.drain();assert b.events==['start','stop','start']

def test_preferences_do_not_replace_pending_capture(interaction):
    c,_,_,_=interaction;c.toggle();update=Mock()
    with pytest.raises(RuntimeError,match='Finish'):c.configure(update)
    update.assert_not_called()

def test_shutdown_drains_start_keeps_audio_and_rejects_events(interaction):
    c,b,_,_=interaction;c.toggle();c.shutdown();c.toggle();c.hold_press();c.hold_release();c.cancel();assert b.events==['start','cancel']

def router(interaction,hold='<ctrl>+<space>',toggle='<alt>+<space>'):
    c,_,_,clock=interaction
    return ShortcutRouter(Shortcut.from_text(hold).as_dict(),Shortcut.from_text(toggle).as_dict(),c,clock=lambda:clock[0])

def test_modifier_first_release_and_repeat(interaction):
    r=router(interaction);r.input(1,'ctrl_r',True);r.input(2,'space',True);r.input(2,'space',True);r.input(1,'ctrl_r',False);r.input(2,'space',False)
    interaction[2].drain();assert interaction[1].events==['start','stop'];assert not r.pressed

def test_both_control_keys_keep_hold_until_last_released(interaction):
    r=router(interaction);r.input(1,'ctrl_l',True);r.input(2,'ctrl_r',True);r.input(3,'space',True);r.input(1,'ctrl_l',False);assert interaction[0].state=='RECORDING';r.input(2,'ctrl_r',False);interaction[2].drain();assert interaction[1].events==['start','stop']

def test_letter_release_after_modifier_change_uses_physical_identity(interaction):
    r=router(interaction,'<cmd>+<shift>+d');r.input(1,'cmd_l',True);r.input(2,'shift_l',True);r.input(3,'d',True);r.input(2,'shift_l',False);r.input(3,'D',False);r.input(1,'cmd_l',False);interaction[2].drain();assert not r.pressed;assert interaction[1].events==['start','stop']

def test_standalone_letter_and_mouse_bindings(interaction):
    r=router(interaction,'a','<mouse:4>');r.input(1,'a',True);r.input(1,'a',False);interaction[2].drain();r.input(4,'mouse:4',True);r.input(4,'mouse:4',True);r.input(4,'mouse:4',False);interaction[2].drain();assert interaction[0].state=='RECORDING';r.input(4,'mouse:4',True);r.input(4,'mouse:4',False);interaction[2].drain();assert interaction[1].events==['start','stop','start','stop']

def test_fn_and_distinct_modifier_sides(interaction):
    r=router(interaction,'<fn>','<ctrl_r>');r.input(63,'fn',True);r.input(63,'fn',False);interaction[2].drain();r.input(59,'ctrl_l',True);r.input(59,'ctrl_l',False);interaction[2].drain();assert interaction[1].events==['start','stop'];r.input(62,'ctrl_r',True);interaction[2].drain();assert interaction[0].state=='RECORDING'

def test_capture_suppresses_dictation_and_quarantines_release(interaction):
    r=router(interaction);seen=[];r.begin_capture(lambda binding,message:seen.append(binding));r.input(1,'ctrl_r',True);r.input(2,'space',True);r.input(2,'space',False);assert r.input(1,'ctrl_r',False) is True;interaction[2].drain();assert interaction[1].events==[];assert seen[0]['keys']==['ctrl_r','space'];assert r.capture is None and not r.quarantined

def test_capture_mouse_timeout_and_escape(interaction):
    r=router(interaction);seen=[];r.begin_capture(lambda b,m:seen.append(b));r.input(4,'mouse:4',True);r.input(4,'mouse:4',False);assert seen[-1]['keys']==['mouse:4'];r.begin_capture(lambda b,m:seen.append(b));interaction[3][0]=21;r.expire_capture();assert seen[-1] is None;r.begin_capture(lambda b,m:seen.append(b));r.input(53,'esc',True);assert seen[-1] is None

def test_primary_capture_clicks_do_not_assign_cancel_button(interaction):
    r=router(interaction);seen=[];r.begin_capture(lambda b,m:seen.append(b));r.input(0,'mouse:0',True);r.input(0,'mouse:0',False);assert not seen;r.commit_capture(['mouse:0']);assert seen[0]['keys']==['mouse:0']

@pytest.mark.parametrize('hold,toggle',[('<ctrl>','<ctrl>+<space>'),('a','a'),('<ctrl_r>','<ctrl>'),('<caps_lock>','a')])
def test_conflicts_and_unholdable_caps_lock_rejected(hold,toggle):
    with pytest.raises(ValueError):validate_pair(Shortcut.from_text(hold).as_dict(),Shortcut.from_text(toggle).as_dict())

def test_left_and_right_modifiers_can_be_separate_bindings():
    validate_pair(Shortcut.from_text('<ctrl_l>').as_dict(),Shortcut.from_text('<ctrl_r>').as_dict())

def test_shortcut_labels_are_not_matching_identity():
    s=Shortcut(('ctrl_r',),'My preferred key');assert shortcut_label(s.as_dict())=='My preferred key';assert Shortcut.read(s.as_dict()).keys==('ctrl_r',)

@pytest.mark.parametrize('release_order',[(1,2),(2,1)])
def test_consumption_belongs_to_each_physical_pair(interaction, release_order):
    r=router(interaction)
    down={1:r.input(1,'ctrl_l',True),2:r.input(2,'space',True)}
    assert down=={1:False,2:True}
    for physical in release_order:
        assert r.input(physical,'ctrl_l' if physical==1 else 'space',False) is down[physical]
    interaction[2].drain()
    assert interaction[1].events==['start','stop']

def test_idle_escape_is_not_intercepted_and_active_escape_is_paired(interaction):
    r=router(interaction)
    assert not r.input(53,'esc',True)
    assert not r.input(53,'esc',False)
    assert not interaction[1].events
    interaction[0].toggle();interaction[2].drain()
    assert r.input(53,'esc',True)
    assert r.input(53,'esc',False)
    interaction[2].drain()
    assert interaction[1].events==['start','cancel']

def test_unrelated_repeat_and_reset_preserve_down_ownership(interaction):
    r=router(interaction)
    assert not r.input(9,'x',True)
    r.input(1,'ctrl_l',True);r.input(2,'space',True)
    assert not r.input(9,'x',True)
    r.reset()
    assert r.input(2,'space',False)
    assert not r.input(1,'ctrl_l',False)
    assert not r.input(9,'x',False)
