"""Bounded, opt-out release discovery; installation belongs to signed Sparkle.

Only public release metadata is requested. Audio, transcripts, user identity,
configuration, and authentication credentials are never included.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import re
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from fixoflow.version import __version__, RELEASES_URL, WEBSITE_URL

API_URL = WEBSITE_URL + '/releases/latest.json'
MAX_METADATA_BYTES = 1_048_576


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Release version must use major.minor.patch.')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    notes: str


def parse_release(data):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1 or data.get('published') is not True:
        raise ValueError('A published product release was not returned.')
    tag = data.get('version')
    version_tuple(tag)
    expected = RELEASES_URL
    if data.get('url') != expected:
        raise ValueError('Release link is outside the Fixo Flow website.')
    notes = data.get('notes')
    if notes is None:
        notes = ''
    if not isinstance(notes, str):
        raise ValueError('Release notes must be text.')
    return Release(tag.removeprefix('v'), expected, notes[:6000])


def fetch_latest(opener=urlopen):
    request = Request(API_URL, headers={'Accept': 'application/json', 'User-Agent': f'FixoFlow/{__version__}'})
    try:
        with opener(request, timeout=10) as response:
            if response.geturl() != API_URL:
                raise ValueError('Unexpected release metadata redirect.')
            content = response.read(MAX_METADATA_BYTES+1)
        if len(content) > MAX_METADATA_BYTES:
            raise ValueError('Release metadata exceeds the allowed size.')
        return parse_release(json.loads(content))
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


class UpdateService:
    def __init__(self, on_change, dispatch=lambda fn: fn(), fetcher=fetch_latest, signed_updater=None):
        self.on_change, self.dispatch, self.fetcher = on_change, dispatch, fetcher
        self.signed_updater = signed_updater
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='FixoFlow-updates')
        self._lock = threading.Lock()
        self._checking = False
        self._closed = False
        self._release = None
        self.status = {'version': __version__, 'state': 'idle', 'message': 'Check for new releases when you want.',
                       'auto_install_available': signed_updater is not None, 'release_url': None}

    def snapshot(self):
        with self._lock:
            return dict(self.status)

    def _publish(self, **changes):
        with self._lock:
            if self._closed:
                return
            self.status.update(changes)
            value = dict(self.status)
        self.dispatch(lambda: self.on_change(value) if not self._closed else None)

    def check(self, manual=True):
        if self.signed_updater is not None:
            self.signed_updater.check(manual)
            return
        with self._lock:
            if self._checking or self._closed:
                return
            self._checking = True
        self._publish(state='checking', message='Checking fixoflow.tech for a new Fixo Flow release…')
        self.executor.submit(self._check)

    def _check(self):
        try:
            release = self.fetcher()
            with self._lock:
                self._release = release
            if release is None:
                self._publish(
                    state='no_releases', message='Update information is not available yet. Please try again later.', release_url=None)
            elif version_tuple(release.version) > version_tuple(__version__):
                self._publish(
                    state='available', message=f'Fixo Flow {release.version} is available.', latest_version=release.version, release_url=release.url)
            else:
                self._publish(state='current', message=f'Fixo Flow {__version__} is up to date.', release_url=None)
        except Exception:
            self._publish(
                state='error', message='Could not check for updates. Check your connection and try again.', release_url=None)
        finally:
            with self._lock:
                self._checking = False

    def set_automatic(self, enabled):
        if enabled and self.signed_updater is None:
            raise ValueError(
                'Automatic installation needs the signed update feed. Check for updates to download a release manually.')
        if self.signed_updater is not None:
            self.signed_updater.set_automatic(enabled)

    def release_url(self):
        with self._lock:
            return self._release.url if self._release is not None else None

    def close(self):
        with self._lock:
            self._closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
