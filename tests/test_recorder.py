import threading
import wave
import numpy as np
import pytest
from fixoflow.audio import recorder as module
from fixoflow.config import FixoflowConfig

class Stream:
    def __init__(self, **options):
        self.callback = options['callback']
    def start(self): pass
    def stop(self): pass
    def close(self): pass

@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(module.sd, 'InputStream', Stream)
    return module.AudioRecorder(FixoflowConfig(cache_dir=str(tmp_path)))

def feed(recorder, samples=1600, status=None):
    recorder._audio_callback(np.full((samples, 1), 0.25, np.float32), samples, None, status)

def test_capture_persists_before_stop_and_retains_short_tail(recorder, monkeypatch):
    persisted = threading.Event()
    real_sync = module.os.fsync
    def sync(fd):
        real_sync(fd)
        persisted.set()
    path = recorder.start()
    monkeypatch.setattr(module.os, 'fsync', sync)
    feed(recorder, 31)
    assert persisted.wait(3)
    with wave.open(str(path)) as saved:
        assert saved.getnframes() == 31
    audio, returned_path = recorder.stop()
    assert len(audio) == 31
    assert returned_path == path
    assert recorder._stream is None

def test_constructor_writes_no_session(recorder):
    assert not list(module.Path(recorder.config.cache_dir).iterdir())

def test_input_overflow_is_not_success(recorder):
    path = recorder.start()
    feed(recorder, status='input overflow')
    with pytest.raises(module.RecordingError, match='input overflow') as caught:
        recorder.stop()
    assert caught.value.session_path == path
    assert path.exists()

def test_disk_failure_is_not_success(recorder, monkeypatch):
    recorder.start()
    def no_space(fd): raise OSError('disk full')
    monkeypatch.setattr(module.os, 'fsync', no_space)
    feed(recorder)
    with pytest.raises(module.RecordingError, match='disk full'):
        recorder.stop()

def test_queue_backpressure_is_explicit(recorder, monkeypatch):
    recorder.start()
    def full(block): raise module.queue.Full
    monkeypatch.setattr(recorder._pending, 'put_nowait', full)
    feed(recorder)
    with pytest.raises(module.RecordingError, match='pending buffer is full'):
        recorder.stop()

def test_start_failure_closes_stream_and_writer(recorder, monkeypatch):
    class Broken(Stream):
        def start(self): raise RuntimeError('microphone denied')
    monkeypatch.setattr(module.sd, 'InputStream', Broken)
    with pytest.raises(module.RecordingError, match='microphone denied'):
        recorder.start()
    assert not recorder.is_recording
    assert recorder._stream is None
    assert recorder._writer is None

def test_failed_close_retains_ownership_for_retry(recorder, monkeypatch):
    recorder.start()
    stream = recorder._stream
    def failed_close(): raise OSError('close failed')
    monkeypatch.setattr(stream, 'close', failed_close)
    with pytest.raises(module.RecordingError, match='close failed'): recorder.stop()
    assert recorder._stream is stream
    with pytest.raises(module.RecordingError, match='cleanup'): recorder.start()
    monkeypatch.setattr(stream, 'close', lambda: None)
    with pytest.raises(module.RecordingError, match='close failed'): recorder.stop()
    assert recorder._stream is None
    recorder.start()
    recorder.stop()

def test_stalled_writer_retains_resources_until_cleanup_retry(recorder, monkeypatch):
    recorder.start()
    entered = threading.Event()
    release = threading.Event()
    real_sync = module.os.fsync
    def blocked_sync(fd):
        entered.set()
        assert release.wait(3)
        real_sync(fd)
    monkeypatch.setattr(module.os, 'fsync', blocked_sync)
    writer = recorder._writer
    real_join = writer.join
    monkeypatch.setattr(writer, 'join', lambda timeout=None: real_join(timeout=0.01))
    feed(recorder)
    assert entered.wait(2)
    try:
        with pytest.raises(module.RecordingError, match='cleanup needs retry'):
            recorder.stop()
        assert recorder._writer is writer
        assert recorder._output is not None
        with pytest.raises(module.RecordingError, match='cleanup'):
            recorder.start()
    finally:
        release.set()
        real_join(timeout=3)
    with pytest.raises(module.RecordingError, match='cleanup needs retry'):
        recorder.stop()
    assert recorder._writer is None
    assert recorder._output is None
