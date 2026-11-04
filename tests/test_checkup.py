import numpy as np
import pytest

from fixoflow.audio.checkup import MicrophoneCheckup


class Backend:
    def __init__(self,samples=None,status=None,error=None):
        self.samples=samples
        self.status=status
        self.error=error
        self.opened=0
        self.stopped=0
        self.closed=0

    def query_devices(self,device=None,kind=None):
        if kind=='input':return {'default_samplerate':48000}
        return [{'name':'USB Mic','hostapi':0,'max_input_channels':1}]

    def query_hostapis(self):return [{'name':'Test API'}]

    def InputStream(self,**kwargs):
        self.opened+=1
        if self.error:raise RuntimeError(self.error)
        backend=self
        assert kwargs['samplerate']==48000 and kwargs['channels']==1
        assert kwargs['dtype']=='float32' and kwargs['blocksize']==0
        class Stream:
            active=True
            def start(self):
                if backend.samples is not None:
                    kwargs['callback'](backend.samples,len(backend.samples),None,backend.status)
            def stop(self):backend.stopped+=1;self.active=False
            def close(self):backend.closed+=1
        return Stream()


def finish(checkup):
    assert checkup._worker is not None
    checkup._worker.join(3)
    assert not checkup.active
    return checkup.snapshot()


def fast_clock():
    value=[0]
    def clock():value[0]+=.2;return value[0]
    return clock


def test_construction_never_opens_a_microphone():
    backend=Backend()
    checkup=MicrophoneCheckup(backend)
    assert checkup.snapshot()['state']=='idle'
    assert backend.opened==0 and checkup.close()


@pytest.mark.parametrize('amplitude,no_signal,clipping',[(0,True,False),(.1,False,False),(1,False,True)])
def test_checkup_publishes_only_metrics_and_closes_stream(amplitude,no_signal,clipping):
    backend=Backend(np.full((480,1),amplitude,dtype=np.float32))
    checkup=MicrophoneCheckup(backend,clock=fast_clock())
    checkup.start(duration=1)
    state=finish(checkup)
    assert state['state']=='complete'
    assert state['no_signal']==no_signal and state['clipping']==clipping
    assert backend.stopped==backend.closed==1
    assert not any(isinstance(value,np.ndarray) for value in state.values())
    assert not hasattr(checkup,'samples') and not hasattr(checkup,'audio')


def test_stream_error_and_invalid_samples_are_not_reported_as_success():
    for samples,status in [(np.ones((10,1),np.float32),'overflow'),(np.array([[np.nan]],np.float32),None)]:
        backend=Backend(samples,status=status)
        checkup=MicrophoneCheckup(backend,clock=fast_clock())
        checkup.start(duration=1)
        state=finish(checkup)
        assert state['state']=='error' and state['no_signal'] is None
        assert backend.closed==1


def test_cancel_stops_hardware_and_second_start_is_rejected():
    backend=Backend()
    checkup=MicrophoneCheckup(backend)
    checkup.start(duration=10)
    with pytest.raises(ValueError,match='already running'):checkup.start()
    assert checkup.close()
    assert checkup.snapshot()['state']=='cancelled'
    assert backend.closed==backend.stopped==1


def test_open_error_is_visible_without_persisting_audio():
    checkup=MicrophoneCheckup(Backend(error='permission denied'))
    checkup.start(duration=1)
    assert finish(checkup)['message']=='permission denied'


def test_failed_close_keeps_stream_ownership_for_retry():
    backend=Backend()
    original=backend.InputStream
    calls=[]
    def stream(**kwargs):
        value=original(**kwargs)
        def close():
            calls.append('close')
            if len(calls)==1:raise OSError('busy')
        value.close=close
        return value
    backend.InputStream=stream
    checkup=MicrophoneCheckup(backend,clock=fast_clock())
    checkup.start(duration=1)
    assert finish(checkup)['state']=='error'
    with pytest.raises(ValueError,match='cleanup'):checkup.start()
    assert checkup.close()
    assert calls==['close','close']


@pytest.mark.parametrize('duration',[0,11,True,float('nan'),'5',None])
def test_invalid_duration_never_opens_hardware(duration):
    backend=Backend()
    checkup=MicrophoneCheckup(backend)
    with pytest.raises(ValueError):checkup.start(duration=duration)
    assert not backend.opened
