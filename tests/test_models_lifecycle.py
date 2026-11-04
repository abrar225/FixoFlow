import hashlib
import io
import threading
from types import SimpleNamespace

import pytest

from fixoflow.models.catalog import Asset, CATALOG, ModelSpec
from fixoflow.models.manager import ModelManager, verify_model


@pytest.fixture
def fixture_spec():
    data = {'config.json':b'{"n_vocab":51864}', 'weights.npz':b'fixture weights', 'README.md':b'Fixture notice'}
    spec = ModelSpec('fixture-model','Fixture model','mlx','test/model','a'*40,
        tuple(Asset(name,len(body),hashlib.sha256(body).hexdigest()) for name,body in data.items()),'Test fixture')
    return spec,data


def manager(tmp_path,fixture_spec,transform=lambda data:data):
    spec,data=fixture_spec
    calls=[]
    def open_asset(request,timeout):
        calls.append(request.full_url)
        assert '/resolve/'+spec.revision+'/' in request.full_url
        return io.BytesIO(transform(data[request.full_url.rsplit('/',1)[1]]))
    return ModelManager(root=tmp_path,catalog={spec.id:spec},backend='mlx',opener=open_asset),calls


def test_verified_install_has_immutable_assets_and_no_implicit_download(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,calls=manager(tmp_path,fixture_spec)
    assert store.snapshot()[0]['state']=='absent' and not calls
    path=store.install(spec.id)
    assert len(calls)==3 and verify_model(path,spec)==path
    assert store.snapshot()[0]['state']=='installed'
    store.install(spec.id)
    assert len(calls)==3


@pytest.mark.parametrize('transform',[lambda b:b+b'extra',lambda b:b[:-1],lambda b:b'X'*len(b)])
def test_bad_download_never_promotes_or_leaves_partial_model(tmp_path,fixture_spec,transform):
    spec,_=fixture_spec
    store,_=manager(tmp_path,fixture_spec,transform)
    with pytest.raises(ValueError):store.install(spec.id)
    assert not (tmp_path/spec.id).exists()
    assert not list(tmp_path.iterdir())
    assert store.snapshot()[0]['state']=='failed'


def test_existing_damaged_model_is_preserved_without_network(tmp_path,fixture_spec):
    spec,_=fixture_spec
    path=tmp_path/spec.id;path.mkdir();(path/'keep').write_text('existing installation')
    store,calls=manager(tmp_path,fixture_spec)
    with pytest.raises(ValueError):store.install(spec.id)
    assert not calls and (path/'keep').read_text()=='existing installation'


def test_integrity_cache_invalidates_for_replaced_or_modified_files(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,_=manager(tmp_path,fixture_spec)
    path=store.install(spec.id)
    verify_model(path,spec)
    file=path/'weights.npz';file.write_bytes(b'X'*file.stat().st_size)
    with pytest.raises(ValueError,match='SHA-256'):verify_model(path,spec)


def test_cancellation_cleanup_and_other_models_unchanged(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,calls=manager(tmp_path,fixture_spec)
    other=tmp_path/'other';other.mkdir();(other/'keep').write_text('preserved')
    store.cancel()
    with pytest.raises(InterruptedError):store.install(spec.id)
    assert not calls and not (tmp_path/spec.id).exists()
    assert (other/'keep').read_text()=='preserved'
    assert store.snapshot()[0]['state']=='cancelled'


def test_warmup_only_for_matching_verified_installed_model(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,calls=manager(tmp_path,fixture_spec)
    path=store.install(spec.id)
    warmed=[]
    engine=SimpleNamespace(resolve_model_path=lambda:str(path),warm_up=lambda:warmed.append(True))
    store.warm_up(spec.id,engine)
    assert warmed==[True] and store.snapshot()[0]['state']=='ready' and len(calls)==3
    engine.resolve_model_path=lambda:'/different/model'
    with pytest.raises(ValueError,match='does not match'):store.warm_up(spec.id,engine)
    assert warmed==[True]


def test_busy_operation_deduplicates_and_close_retains_worker_ownership(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,_=manager(tmp_path,fixture_spec)
    path=store.install(spec.id)
    started,release=threading.Event(),threading.Event()
    def warm():started.set();assert release.wait(5)
    engine=SimpleNamespace(resolve_model_path=lambda:str(path),warm_up=warm)
    store.start_warm_up(spec.id,engine)
    assert started.wait(2)
    assert store.busy
    with pytest.raises(RuntimeError,match='already running'):store.start_install(spec.id)
    assert not store.close(timeout=.01)
    release.set()
    assert store.close(timeout=2)
    assert not store.busy
    assert store.snapshot()[0]['state']=='cancelled'


def test_catalog_entries_have_hashes_and_both_runtime_variants():
    assert len(CATALOG)>=16
    assert {spec.backend for spec in CATALOG.values()}=={'mlx','cpu','onnx'}
    assert all(spec.license in {'MIT','CC-BY-4.0'} for spec in CATALOG.values())
    assert all(asset.sha256 and asset.bytes>0 for spec in CATALOG.values() for asset in spec.assets)


def test_incompatible_models_never_start_download(tmp_path,fixture_spec):
    spec,_=fixture_spec
    store,calls=manager(tmp_path,fixture_spec)
    store.backend='cpu'
    with pytest.raises(ValueError,match='incompatible'):store.start_install(spec.id)
    assert not calls


def test_multilingual_and_parakeet_capabilities_are_model_specific(monkeypatch):
    from fixoflow.models import catalog
    monkeypatch.setattr(catalog.platform, 'machine', lambda: 'arm64')
    from fixoflow.languages import available_languages, options, validate_language_selection
    assert available_languages('catalog:base-en-mlx',backend='mlx')==('en',)
    assert 'hi' in available_languages('catalog:base-multi-mlx',backend='mlx')
    assert len(options('catalog:base-multi-mlx',backend='mlx'))==100
    assert available_languages('catalog:parakeet-v3-onnx')==(None,)
    assert len(CATALOG['parakeet-v3-onnx'].supported_languages)==25
    assert 'hi' not in CATALOG['parakeet-v3-onnx'].supported_languages
    for language,model in [('hi','catalog:base-en-mlx'),('en','catalog:parakeet-v3-onnx')]:
        with pytest.raises(ValueError):validate_language_selection(language,model,backend='mlx')
    validate_language_selection('hi','catalog:base-multi-mlx',backend='mlx')
    validate_language_selection(None,'catalog:parakeet-v3-onnx')


def test_catalog_language_selection_survives_config_save_and_restart(tmp_path,monkeypatch):
    from fixoflow.config import FixoflowConfig
    from fixoflow.models.catalog import runtime_backend
    config_path=tmp_path/'config.json'
    monkeypatch.setattr(FixoflowConfig,'get_config_path',classmethod(lambda cls:config_path))
    cfg=FixoflowConfig(model_name='catalog:base-multi-'+runtime_backend(),language='es',cache_dir=str(tmp_path/'audio'))
    cfg.save()
    loaded=FixoflowConfig.load()
    assert loaded.language=='es' and loaded.model_name==cfg.model_name and loaded.deferred_language==''
    from fixoflow.models import catalog
    monkeypatch.setattr(catalog.platform, 'machine', lambda: 'arm64')
    cfg=FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language=None,cache_dir=str(tmp_path/'audio'))
    cfg.save()
    assert FixoflowConfig.load().language is None
