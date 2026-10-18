"""Deletion of explicitly owned session files, never arbitrary DB paths."""
import json
import os
from pathlib import Path
import re
import stat
import wave

SESSION_NAME = re.compile(r'session_\d{8}_\d{6}_\d{6}\.wav\Z')


def session_files(audio_path, root):
    path=Path(audio_path).absolute();root=Path(root).resolve()
    if path.parent.resolve()!=root or not SESSION_NAME.fullmatch(path.name):
        raise ValueError('Linked recording ownership is unknown; files and History were preserved.')
    files=[path,path.with_suffix('.transcript.json')]
    for file in files:
        if file.is_symlink():raise ValueError('Refusing to delete a linked symbolic file; History was preserved.')
        if file.exists() and not stat.S_ISREG(file.stat().st_mode):raise ValueError('Linked recording is not a regular file.')
    return files


def identity(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):raise ValueError('Recording file identity changed; deletion stopped.')
    return [info.st_dev,info.st_ino]


def validate_legacy(audio_path,root,raw_text):
    """Conservative one-time claim for old generated sessions, on explicit delete."""
    files=session_files(audio_path,root)
    try:
        if files[0].exists():
            with wave.open(str(files[0])) as audio:
                if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):
                    raise ValueError('Legacy recording format is unknown; History was preserved.')
        if files[1].exists():
            data=json.loads(files[1].read_text())
            if not isinstance(data,dict) or data.get('raw_text') != raw_text:
                raise ValueError('Legacy transcript does not match History; deletion stopped.')
    except (wave.Error,EOFError,json.JSONDecodeError) as error:
        raise ValueError('Legacy session is malformed; files and History were preserved.') from error
    return files


def unlink_owned(path,expected):
    path=Path(path)
    try:
        if identity(path)!=expected:raise ValueError('Recording was replaced; deletion stopped.')
        # On POSIX bind the parent directory to avoid traversal through a changed
        # ancestor. Compare the final file identity immediately before unlink.
        if os.unlink in os.supports_dir_fd:
            descriptor=os.open(path.parent,os.O_RDONLY)
            try:
                info=os.stat(path.name,dir_fd=descriptor,follow_symlinks=False)
                if [info.st_dev,info.st_ino]!=expected or not stat.S_ISREG(info.st_mode):raise ValueError('Recording identity changed.')
                os.unlink(path.name,dir_fd=descriptor)
            finally:os.close(descriptor)
        else:path.unlink()
    except FileNotFoundError:pass
