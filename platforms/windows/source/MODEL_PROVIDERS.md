# Hermes model providers and Workspace presets

Hermes separates three choices:

1. The **base model** in Open WebUI handles chat, reasoning, and tool calls.
2. The **vision model** in the Workspace preset analyzes desktop screenshots.
3. Open WebUI's built-in **Web Search** supplies current web results to every model.

## Add a cloud/API text model

1. Open **Admin Settings → Connections → OpenAI API Connections**.
2. Choose **Add Connection**.
3. Enter the provider's OpenAI-compatible base URL and API key. Open WebUI also
   includes compatibility paths for providers such as Anthropic and Gemini.
4. Verify the connection. If model discovery is unsupported, enter the provider's
   exact model ID in the connection's model allowlist, then save.
5. Open **Workspace → Models**, duplicate Hermes Alpha or create a model with the
   cloud model as its base, and attach **Hermes Alpha Smart Operator** under Tools.
6. Enable **Native** function calling, Built-in Tools, and Web Search.

API keys belong in Open WebUI's protected connection settings, never in a system
prompt, chat message, model preset, or source file.

## Create a Hermes preset from the terminal

After the base model appears in Open WebUI, a preset can be created without copying
tool configuration by hand:

```bash
cd ~/hermes-v4
python3 workspace_preset.py \
  --id hermes-cloud-example \
  --name "Hermes Cloud Example" \
  --base-model exact-provider-model-id \
  --vision-provider nvidia \
  --vision-model nvidia/nemotron-3.5-super-vl-120b-a12b
systemctl --user restart open-webui.service
```

The preset appears in Workspace and the normal model picker with Hermes desktop
tools and web search already attached.

## Select a vision model

Each Hermes Workspace preset stores `hermesVision` metadata. The vision tool reads
that selection automatically. All three canonical presets use NVIDIA Super VL:

```json
{"provider": "nvidia", "model": "nvidia/nemotron-3.5-super-vl-120b-a12b"}
```

For an OpenAI-compatible cloud vision endpoint:

1. Create `~/.config/hermes/vision.env` with
   `HERMES_VISION_API_KEY=your-key`, then run `chmod 600` on the file. The
   action-bridge service loads this optional file automatically.
2. Run `systemctl --user daemon-reload` and restart the action bridge.
3. Explicitly enable and select the provider through Hermes's
   `configure_vision_model` tool or the authenticated `/models/vision` endpoint.
4. Create a preset with `--vision-provider openai_compatible` and the exact
   vision-capable model ID.

Cloud vision sends the captured desktop screenshot to the configured API provider.
Hermes never returns the API key in status responses.

The built-in `nvidia` provider is an exception to the separate environment-file
step: it reuses the credential for the matching
`https://integrate.api.nvidia.com/v1` Open WebUI connection. The key is never
copied into a preset, source file, status response, or tool output.

## Installed Hermes profiles

- `Hermes Alpha`: Ultra 550B chat/tools, Super VL vision.
- `Hermes Beta`: Super VL chat/tools/vision.
- `Hermes Gamma`: Lightning 30B chat/tools, Super VL vision.
- Document embedding model: `nvidia/nemotron-3-embed-1b`
- Speech-to-text: Deepgram `nova-3`
- Text-to-speech: ElevenLabs

## Web search

Hermes enables Open WebUI Web Search globally with DDGS/DuckDuckGo, Auto backend,
five results, and native function calling as the model default. Workspace presets
enable it by default. It can still be switched off for an individual chat when the
user does not want search. A model must support structured tool calls to use
agentic search reliably.
