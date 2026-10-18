#!/usr/bin/env python3
"""Embed a caller-provisioned Sparkle framework and public update settings.

No downloads or private keys. Run on an unsigned staging bundle before signing.
An incomplete configuration fails the build rather than advertising auto-update.
"""
from __future__ import annotations
import argparse
import base64
import os
from pathlib import Path
import plistlib
import subprocess
from urllib.parse import urlparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app',type=Path)
    args=parser.parse_args()
    names=('FIXOFLOW_SPARKLE_FRAMEWORK','FIXOFLOW_UPDATE_FEED_URL','FIXOFLOW_UPDATE_PUBLIC_KEY')
    values=[os.environ.get(name,'') for name in names]
    if not any(values):
        print('Update discovery enabled; signed automatic installer is not configured.')
        return
    if not all(values):
        parser.error('Configure all three: '+', '.join(names))
    framework,feed,key=values
    source=Path(framework).expanduser().resolve()
    if source.name!='Sparkle.framework' or not source.is_dir():
        parser.error('Provide an existing official Sparkle.framework directory.')
    url=urlparse(feed)
    if url.scheme!='https' or not url.hostname or url.username or url.password:
        parser.error('The appcast must have a public HTTPS URL without credentials.')
    try:
        public=base64.b64decode(key,validate=True)
    except ValueError:
        parser.error('The Ed25519 public key must be valid base64.')
    if len(public)!=32:
        parser.error('The Ed25519 public key must be 32 bytes.')
    subprocess.run(['codesign','--verify','--deep','--strict',str(source)],check=True)
    target=args.app/'Contents/Frameworks/Sparkle.framework'
    subprocess.run(['ditto',str(source),str(target)],check=True)
    info=args.app/'Contents/Info.plist'
    data=plistlib.loads(info.read_bytes())
    data.update({'SUFeedURL':feed,'SUPublicEDKey':key,'SUEnableAutomaticChecks':False,
                 'SUAutomaticallyUpdate':False,'SUEnableInstallerLauncherService':True})
    info.write_bytes(plistlib.dumps(data))
    print('Embedded Sparkle and public appcast settings. Sign and notarize before publication.')


if __name__=='__main__':main()
