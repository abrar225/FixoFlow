"""One release identity for package metadata, native bundles, and update checks."""
__version__ = '0.3.2'
VERSION_PARTS = tuple(int(part) for part in __version__.split('.'))
BUILD_NUMBER = VERSION_PARTS[0] * 1_000_000 + VERSION_PARTS[1] * 1_000 + VERSION_PARTS[2]
REPOSITORY = 'https://github.com/abrar225/FixoFlow'
RELEASES_URL = REPOSITORY + '/releases'
