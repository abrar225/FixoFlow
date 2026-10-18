import json
from pathlib import Path
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.languages import LANGUAGES, language_prompt
from fixoflow.model_packs import ModelPackManager, validate_pack
from fixoflow.storage.db import FixoflowDB
from fixoflow.brain.learner import AdaptiveLearner


def test_language_options_require_compatible_model_and_keep_regions_separate():
    assert len(LANGUAGES)==99
    for language in ['en','hi','zh','ja','es','fr','ar','bn','gu']:
        FixoflowConfig(language=language,model_name='multilingual-base').validate()
    for region in ['en-US','en-GB','en-IN']:
        cfg=FixoflowConfig(english_variant=region);cfg.validate();assert cfg.language=='en'
    for language in ['hi',None,'not-a-language']:
        with pytest.raises(ValueError):FixoflowConfig(language=language).validate()
    assert '简体' in language_prompt('zh')
    assert 'हिंदी' in language_prompt('hi')
    assert language_prompt(None)==''


def test_pack_constructor_never_downloads_and_rejects_incomplete(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:pytest.fail('implicit download'))
    manager=ModelPackManager('mlx',tmp_path/'base')
    assert manager.snapshot()['state']=='not_installed'
    assert not (tmp_path/'base').exists()
    with pytest.raises(ValueError):validate_pack(tmp_path/'base','mlx')


def test_language_sensitive_formatting_preserves_unicode_and_english_literals(tmp_path):
    db=FixoflowDB(tmp_path/'test.sqlite');learner=AdaptiveLearner(db)
    db.upsert_word('C++','CPP');db.upsert_word('नाम','पहचान');db.upsert_word('i','I')
    assert learner.format_for_mode('C++ नाम खाना','writing','')=='CPP पहचान खाना'
    assert learner.format_for_mode('İ','writing','')=='I'
    from fixoflow.brain.polisher import TextPolisher
    for language,text in [('zh','这是中文。'),('ja','これは日本語です。'),('hi','यह हिंदी है।')]:
        assert TextPolisher(FixoflowConfig(language=language,model_name='multilingual-base')).polish(text)==text


def test_pack_failure_does_not_replace_existing_directory(tmp_path, monkeypatch):
    import urllib.error
    import fixoflow.model_packs as packs
    path=tmp_path/'base';path.mkdir();(path/'user.txt').write_text('preserve')
    monkeypatch.setattr(packs.urllib.request,'urlopen',lambda *a,**k:(_ for _ in ()).throw(OSError('offline')))
    manager=ModelPackManager('mlx',path);manager._download()
    assert manager.snapshot()['state']=='error'
    assert (path/'user.txt').read_text()=='preserve'
    assert not list(tmp_path.glob('.base-download-*'))


def pinned_fixture(monkeypatch):
    import hashlib
    import fixoflow.model_packs as packs
    contents={'config.json':b'{"n_vocab":51865}', 'weights.npz':b'test-only-model', 'README.md':b'test'}
    monkeypatch.setitem(packs.PACKS,'mlx',{'repo':'test/model','revision':'fixture',
        'files':{name:(len(data),'sha256',hashlib.sha256(data).hexdigest()) for name,data in contents.items()}})
    return contents


def test_corrupt_download_is_never_promoted(tmp_path,monkeypatch):
    import io
    import fixoflow.model_packs as packs
    contents=pinned_fixture(monkeypatch)
    contents['weights.npz']=b'x'*len(contents['weights.npz'])
    monkeypatch.setattr(packs.urllib.request,'urlopen',lambda request,**k:io.BytesIO(contents[request.full_url.rsplit('/',1)[-1]]))
    manager=ModelPackManager('mlx',tmp_path/'pack');manager._download()
    assert manager.snapshot()['state']=='error'
    assert 'integrity' in manager.snapshot()['message']
    assert not manager.path.exists() and manager._stage is None


def test_verified_ready_pack_is_reused_until_files_change(tmp_path,monkeypatch):
    import io
    import fixoflow.model_packs as packs
    contents=pinned_fixture(monkeypatch);calls=[]
    def fetch(request,**kwargs):
        calls.append(request.full_url)
        return io.BytesIO(contents[request.full_url.rsplit('/',1)[-1]])
    monkeypatch.setattr(packs.urllib.request,'urlopen',fetch)
    manager=ModelPackManager('mlx',tmp_path/'pack');manager._download()
    assert manager.snapshot()['state']=='ready'
    manager.start();assert len(calls)==3
    (manager.path/'weights.npz').write_bytes(b'x'*len(contents['weights.npz']))
    with pytest.raises(ValueError,match='integrity'):validate_pack(manager.path,'mlx')


def test_malformed_config_is_expected_failure(tmp_path,monkeypatch):
    import fixoflow.model_packs as packs
    for value in [[],None,{'n_vocab':'many'},{'n_vocab':True}]:
        with pytest.raises(ValueError):packs.validate_model_language(value,'mlx')
    path=tmp_path/'pack';path.mkdir()
    for name in packs.PACKS['mlx']['files']:(path/name).write_text('[]')
    assert ModelPackManager('mlx',path).snapshot()['state']=='not_installed'


def test_shutdown_retains_blocked_worker_then_cleans_after_cancel(tmp_path,monkeypatch):
    import io,threading
    import fixoflow.model_packs as packs
    contents=pinned_fixture(monkeypatch);entered=threading.Event();release=threading.Event()
    class Response(io.BytesIO):
        def read(self,size):
            entered.set();assert release.wait(3)
            return super().read(size)
    monkeypatch.setattr(packs.urllib.request,'urlopen',lambda request,**k:Response(contents[request.full_url.rsplit('/',1)[-1]]))
    manager=ModelPackManager('mlx',tmp_path/'pack');manager.start()
    try:
        assert entered.wait(3)
        assert manager.close(timeout=.01) is False
        assert manager._worker.is_alive() and manager._stage is not None
    finally:release.set()
    assert manager.close(timeout=3)
    assert manager._stage is None and not manager.path.exists()
    assert manager.snapshot()['state']=='cancelled'


def test_cleanup_failure_retains_stage_until_retry(tmp_path,monkeypatch):
    import fixoflow.model_packs as packs
    stage=tmp_path/'.base-download-owned';stage.mkdir();(stage/'part').write_text('partial')
    manager=ModelPackManager('mlx',tmp_path/'pack');manager._stage=stage
    real=packs.shutil.rmtree
    monkeypatch.setattr(packs.shutil,'rmtree',lambda path:(_ for _ in ()).throw(PermissionError('busy')))
    assert manager.close() is False and manager._stage==stage
    monkeypatch.setattr(packs.shutil,'rmtree',real)
    assert manager.close() and manager._stage is None and not stage.exists()


def test_successful_close_is_terminal_even_for_queued_start(tmp_path,monkeypatch):
    import fixoflow.model_packs as packs
    monkeypatch.setattr(packs.urllib.request,'urlopen',lambda *a,**k:pytest.fail('download after accepted close'))
    manager=ModelPackManager('mlx',tmp_path/'pack')
    assert manager.close()
    manager.start()
    assert manager._worker is None and not manager.path.exists()
