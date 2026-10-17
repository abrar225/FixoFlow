#!/bin/bash
# One-time creation of a local code-signing identity for Fixoflow.
#
# Ad-hoc signing (codesign --sign -) pins every TCC permission grant to the
# exact binary hash, so each rebuild silently invalidates the user's
# Accessibility / Input Monitoring / Microphone grants and can leave stale
# System Settings rows. Signing with a stable self-signed certificate keeps
# the designation anchored to the certificate, so grants survive updates.
set -euo pipefail

IDENTITY_NAME="Fixoflow Local Signing"
KEYCHAIN="${HOME}/Library/Keychains/login.keychain-db"

if /usr/bin/security find-identity -p codesigning 2>/dev/null | /usr/bin/grep -q "$IDENTITY_NAME"; then
    echo "Signing identity already present: $IDENTITY_NAME"
    exit 0
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

/usr/bin/openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
    -keyout "$WORK_DIR/key.pem" -out "$WORK_DIR/cert.pem" \
    -subj "/CN=$IDENTITY_NAME/O=Fixoflow Local" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=critical,codeSigning"

/usr/bin/openssl pkcs12 -export -out "$WORK_DIR/identity.p12" \
    -inkey "$WORK_DIR/key.pem" -in "$WORK_DIR/cert.pem" \
    -passout pass:fixoflow

# -T pre-authorizes codesign (and security) to use the private key without an
# interactive prompt. The certificate is intentionally not marked trusted:
# local builds are not quarantined, so Gatekeeper does not block them, and
# trusting a root would require an administrator prompt.
/usr/bin/security import "$WORK_DIR/identity.p12" -k "$KEYCHAIN" -P fixoflow \
    -T /usr/bin/codesign -T /usr/bin/security

echo "Created signing identity: $IDENTITY_NAME"
echo "Future builds will sign with it automatically (scripts/build_app.sh)."
