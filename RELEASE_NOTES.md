# Hermes 2.0.0-beta.1 — Host and User preview

This preview introduces the split Hermes architecture.

## Included

- **Hermes Host** installs the backend, Open WebUI, local tools, Tailscale and
  automatic services.
- **Hermes User** is a separate lightweight remote interface. It stores only a
  Host Tailscale address and opens the normal Open WebUI sign-in page.
- The Host package embeds the matching Hermes User installer and starts it
  after Host verification.
- No provider API keys, computer-control token, chat database, or Open WebUI
  password is copied to a User device.

## Beta limits

- The split Host/User Debian installers are the supported preview path.
- Windows and macOS continue to ship the complete Host edition in this beta;
  their dedicated User installers are the next compatibility milestone.
- The Host must be online, signed into Tailscale, and configured with
  Tailscale Serve before a User device can connect.
