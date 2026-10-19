"""Native public-distribution checks, not a SmartScreen-reputation guarantee.

Run after signing/notarization, before staging. Reports are local CI evidence;
keep them with the native job logs, not as an independently signed attestation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta


def digest(path):
    with path.open("rb") as stream:
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
        return checksum.hexdigest()


def run(command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def verify_windows(path, thumbprint):
    if sys.platform != "win32":
        raise ValueError("Authenticode verification must run on Windows")
    if not thumbprint or len(thumbprint) != 40 or any(c not in "0123456789abcdefABCDEF" for c in thumbprint):
        raise ValueError("Supply the expected publisher certificate SHA-1 thumbprint (not a secret)")
    # Pass the filename through stdin, not interpolated PowerShell code.
    command = r'''$ErrorActionPreference = 'Stop'
$p = [Console]::In.ReadToEnd()
$s = Get-AuthenticodeSignature -LiteralPath $p
if ($s.Status -ne 'Valid') { throw "Invalid Authenticode signature: $($s.Status)" }
if (-not $s.TimeStamperCertificate) { throw 'Missing trusted timestamp' }
@{ thumbprint = $s.SignerCertificate.Thumbprint; subject = $s.SignerCertificate.Subject } | ConvertTo-Json -Compress
'''
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            input=str(path), text=True, capture_output=True, check=True)
    signer = json.loads(result.stdout)
    if signer["thumbprint"].upper() != thumbprint.upper():
        raise ValueError("Publisher certificate does not match the expected identity")
    # SignTool checks the Authenticode policy and every embedded signature.
    run(["signtool.exe", "verify", "/pa", "/all", "/tw", str(path)])
    return {"authenticode": True, "timestamp": True, "publisher": signer["subject"],
            "certificate_thumbprint": signer["thumbprint"]}


def verify_macos(path):
    if sys.platform != "darwin":
        raise ValueError("Gatekeeper verification must run on macOS")
    run(["hdiutil", "verify", str(path)])
    run(["xcrun", "stapler", "validate", str(path)])
    run(["spctl", "--assess", "--type", "open", "--context", "context:primary-signature", "--verbose=2", str(path)])
    import plistlib
    attached = plistlib.loads(subprocess.run(
        ["hdiutil", "attach", "-readonly", "-nobrowse", "-plist", str(path)],
        check=True, capture_output=True).stdout)
    devices = attached["system-entities"]
    device = next(item["dev-entry"] for item in devices if "dev-entry" in item)
    try:
        mount = Path(next(item["mount-point"] for item in devices if "mount-point" in item))
        app = mount / "Fixoflow.app"
        run(["codesign", "--verify", "--deep", "--strict", str(app)])
        run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(app)])
    finally:
        run(["hdiutil", "detach", device])
    return {"gatekeeper": True, "stapled_notarization": True, "nested_app_assessed": True}


def require_report(path, platform, directory):
    record = json.loads((directory / f"{platform}-trust.json").read_text())
    verified_at = datetime.fromisoformat(record["verified_at"])
    age = datetime.now(timezone.utc) - verified_at
    if age < -timedelta(minutes=5) or age > timedelta(hours=24):
        raise ValueError(f"Expired {platform} trust report; rerun native verification")
    expected = ("authenticode", "timestamp") if platform == "windows" else ("gatekeeper", "stapled_notarization", "nested_app_assessed")
    if record.get("platform") != platform or record.get("sha256") != digest(path):
        raise ValueError(f"Stale or mismatched {platform} trust report; verify the exact installer")
    if not all(record.get("checks", {}).get(key) is True for key in expected):
        raise ValueError(f"Missing {platform} public trust checks")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=["windows", "macos"])
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--certificate-thumbprint")
    parser.add_argument("--reports", type=Path, default=Path("dist/trust"))
    args = parser.parse_args()
    report_path = args.reports / f"{args.platform}-trust.json"
    # A failed recheck must not leave an older passing report for staging.
    report_path.unlink(missing_ok=True)
    path = args.artifact.resolve(strict=True)
    before = digest(path)
    checks = verify_windows(path, args.certificate_thumbprint) if args.platform == "windows" else verify_macos(path)
    if digest(path) != before:
        raise ValueError("Artifact changed during verification")
    report = {"platform": args.platform, "sha256": before, "checks": checks,
              "verified_at": datetime.now(timezone.utc).isoformat()}
    args.reports.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("VERDICT: PASS — native public trust checks; reputation and physical-device acceptance remain separate")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout or "", file=sys.stderr)
            print(error.stderr or "", file=sys.stderr)
        print(f"VERDICT: FAIL — {error}", file=sys.stderr)
        sys.exit(1)
