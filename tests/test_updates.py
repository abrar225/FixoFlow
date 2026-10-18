import io
import json
import threading
from urllib.error import HTTPError
import pytest
from fixoflow.updates import API_URL, MAX_METADATA_BYTES, UpdateService, Release, fetch_latest, parse_release, version_tuple


def release(tag='v0.1.1',**changes):
    data={'tag_name':tag,'draft':False,'prerelease':False,'html_url':'https://github.com/abrar225/FixoFlow/releases/tag/'+tag,'body':'A patch.'}
    data.update(changes)
    return data

@pytest.mark.parametrize('value',['1.2','1.0.0-beta','01.2.3','other','1.2.3.4',None])
def test_invalid_release_version_is_rejected(value):
    with pytest.raises(ValueError):version_tuple(value)

def test_version_comparison_is_numeric():
    assert version_tuple('v0.1.10')>version_tuple('0.1.9')

@pytest.mark.parametrize('changes',[{'draft':True},{'prerelease':True},{'html_url':'https://example.com/download'},{'tag_name':'../../malicious'},{'body':[]}])
def test_untrusted_release_metadata_cannot_supply_an_update_link(changes):
    with pytest.raises(ValueError):parse_release(release(**changes))

class Response(io.BytesIO):
    def __init__(self,content,url=API_URL):super().__init__(content);self.url=url
    def geturl(self):return self.url

def test_request_contains_only_public_version_and_no_user_content():
    requests=[]
    def open_(request,timeout):
        requests.append((request,timeout))
        return Response(json.dumps(release()).encode())
    assert fetch_latest(open_).version=='0.1.1'
    req,timeout=requests[0]
    assert req.full_url==API_URL and req.data is None and timeout==10
    assert set(key.lower() for key in req.headers)=={'accept','user-agent'}

def test_empty_repository_is_distinguished_from_network_failure():
    def open_(*args,**kwargs):raise HTTPError(API_URL,404,'Not found',{},None)
    assert fetch_latest(open_) is None

@pytest.mark.parametrize('response',[lambda:Response(b'{}',url='https://example.com'),lambda:Response(b'x'*(MAX_METADATA_BYTES+1)),lambda:Response(b'not json')])
def test_bad_network_boundaries_fail_closed(response):
    with pytest.raises(ValueError):fetch_latest(lambda *a,**k:response())

def test_duplicate_check_is_coalesced_and_close_suppresses_late_ui():
    entered=threading.Event();finish=threading.Event();publications=[];calls=[]
    def fetch():
        calls.append(True);entered.set();assert finish.wait(3);return Release('0.1.1','https://github.com/abrar225/FixoFlow/releases/tag/v0.1.1','')
    service=UpdateService(publications.append,fetcher=fetch)
    try:
        service.check();assert entered.wait(3);service.check();service.close();finish.set();service.executor.shutdown(wait=True)
        assert len(calls)==1
        assert [value['state'] for value in publications]==['checking']
    finally:finish.set();service.close()

def test_unsigned_service_cannot_enable_automatic_installation():
    service=UpdateService(lambda _:None)
    try:
        with pytest.raises(ValueError,match='signed'):service.set_automatic(True)
        service.set_automatic(False)
        assert service.snapshot()['auto_install_available'] is False
    finally:service.close()
