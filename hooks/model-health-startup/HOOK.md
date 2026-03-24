---
name: model-health-startup
description: "Run workforce model health checks on gateway startup"
homepage: https://github.com/eriksjaastad/tools
metadata:
  {
    "openclaw":
      {
        "emoji": "🩺",
        "events": ["gateway:startup"],
        "requires": { "bins": ["bash", "doppler"] },
      },
  }
---

# Model Health Startup

Runs `tools/check_models.sh` when the gateway starts so workforce availability is known before the first patrol cycle.
