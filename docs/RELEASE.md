# Release and Signing

## Release Gates

- Backend unit tests pass.
- Frontend typecheck and static export pass.
- Electron package builds on native macOS, Windows, and Linux runners.
- Deterministic eval fixtures pass.
- SBOM and SHA-256 checksums are generated.
- Third-party dependency and model licenses are reviewed.

## macOS

- Build on macOS.
- Sign with a Developer ID Application certificate.
- Enable Hardened Runtime.
- Notarize with App Store Connect credentials.
- Staple the notarization ticket.
- Validate with `codesign`, `spctl`, and a clean-machine install.

## Windows

- Build on Windows.
- Sign the NSIS installer.
- Sign shipped executables, including the Python sidecar where practical.
- Timestamp signatures.
- Keep publisher identity stable across releases.

## Linux

- Build AppImage and DEB on the oldest supported Ubuntu baseline.
- Publish SHA-256 checksums.
- Provide update instructions because Electron autoUpdater is not the Linux update mechanism.

## Versioning

Use SemVer for app releases. Public desktop tags should use:

```text
rag-desktop-vMAJOR.MINOR.PATCH
```
