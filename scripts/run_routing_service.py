#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    host = os.getenv("INDPROJ04_ROUTING_HOST", "0.0.0.0")
    port = int(os.getenv("INDPROJ04_ROUTING_PORT", "8014"))
    uvicorn.run("agentdns_routing.service_api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
