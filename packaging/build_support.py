"""Shared, import-free build policy used by the native PyInstaller specs."""
from importlib import metadata
from pathlib import Path
import platform


def mac_architecture(machine=None):
    machine = machine or platform.machine()
    if machine not in ("arm64", "x86_64"):
        raise RuntimeError(f"Unsupported native macOS build architecture: {machine}")
    return machine


def license_datas(distributions):
    """Ship upstream license notices without importing GUI/backend modules."""
    result = []
    for name in distributions:
        distribution = metadata.distribution(name)
        notices = []
        for file in distribution.files or ():
            if any(token in Path(str(file)).name.lower() for token in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    notices.append((str(source), f"licenses/{name}/{Path(str(file)).parent}"))
        if not notices:
            fallback = Path(__file__).parent / 'licenses' / f'{name}-LICENSE.txt'
            if fallback.is_file():
                notices.append((str(fallback), f'licenses/{name}'))
            else:
                raise RuntimeError(f"Missing upstream license notice for {name}")
        result.extend(notices)
    return result
