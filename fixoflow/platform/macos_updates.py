"""Optional Sparkle 2 adapter. Never substitutes an unsigned custom installer."""
from pathlib import Path
from urllib.parse import urlparse
import logging
import objc
import AppKit

logger = logging.getLogger(__name__)


class SparkleUpdater:
    def __init__(self,controller):
        self.controller = controller
        self.updater = controller.updater()

    def check(self,manual=True):
        if manual:
            self.controller.checkForUpdates_(None)
        else:
            self.updater.checkForUpdatesInBackground()

    def set_automatic(self,enabled):
        self.updater.setAutomaticallyDownloadsUpdates_(bool(enabled))

    def set_checks(self,enabled):
        self.updater.setAutomaticallyChecksForUpdates_(bool(enabled))


def load_signed_updater():
    bundle = AppKit.NSBundle.mainBundle()
    feed = bundle.objectForInfoDictionaryKey_('SUFeedURL')
    key = bundle.objectForInfoDictionaryKey_('SUPublicEDKey')
    frameworks = bundle.privateFrameworksPath()
    if not feed or not key or not frameworks:
        return None
    if urlparse(str(feed)).scheme != 'https':
        logger.error('Signed updater requires an HTTPS appcast.')
        return None
    path = Path(str(frameworks))/'Sparkle.framework'
    if not path.is_dir():
        return None
    framework = AppKit.NSBundle.bundleWithPath_(str(path))
    if framework is None or not framework.load():
        logger.error('Could not load the packaged Sparkle framework.')
        return None
    controller = objc.lookUpClass('SPUStandardUpdaterController').alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(True,None,None)
    return SparkleUpdater(controller)
