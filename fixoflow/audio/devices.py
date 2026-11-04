"""Explicit microphone selection without persisting unstable PortAudio indices."""
import json


def input_devices(backend=None):
    if backend is None:
        import sounddevice as backend
    apis = backend.query_hostapis()
    result = []
    for index, device in enumerate(backend.query_devices()):
        if device['max_input_channels'] < 1:
            continue
        host = apis[device['hostapi']]['name']
        key = json.dumps([host, device['name']], ensure_ascii=False)
        result.append({'id': key, 'name': device['name'] + ' · ' + host, 'index': index})
    return result


def resolve_input_device(selection, backend=None):
    if not selection:
        return None  # Explicit system-default policy; resolved at stream creation.
    matches = [item for item in input_devices(backend) if item['id'] == selection]
    if len(matches) != 1:
        raise ValueError('Selected microphone is unavailable or ambiguous. Choose it again in Settings; no other microphone was selected.')
    return matches[0]['index']
