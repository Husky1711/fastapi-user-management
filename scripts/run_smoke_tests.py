#!/usr/bin/env python3
"""Local/dev entrypoint — CI uses scripts/smoke_auth_probe.py directly."""

from scripts.smoke_auth_probe import main

if __name__ == "__main__":
    raise SystemExit(main())
