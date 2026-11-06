# Hermes Host and User

Hermes 2 separates the system into two installable roles on every supported platform.

## Hermes Host

Install this on the computer Hermes should control. It owns Open WebUI, cloud
provider connections, chats, memory, local tools, browser control and the
Tailscale connection. It starts automatically after boot.

The Host package embeds the matching Hermes User installer. When Host setup
finishes its health check, it opens that installer for the local computer.

## Hermes User

Install this on another Tailscale-connected computer. It contains no model,
backend service, provider key, bearer token, chat database or desktop-control
capability. It remembers only a validated Host Tailscale address and opens it
inside the Hermes desktop app. The user then signs into Open WebUI normally.

## Connection sequence

1. Install Hermes Host and sign into Tailscale.
2. In Host setup, enable Tailscale Serve for Hermes.
3. Install Hermes User on a remote device and sign into the same tailnet.
4. Enter the Host's `.ts.net` address in Hermes User.
5. Sign in with the existing Open WebUI username and password.

This design intentionally avoids pairing codes and avoids copying secrets to
remote devices.
