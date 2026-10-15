from __future__ import annotations

import json
import os
import sys
import base64
import io

import httpx
from pypdf import PdfWriter


def example_pdf() -> str:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return base64.b64encode(output.getvalue()).decode("ascii")


def main() -> None:
    service_url = os.environ.get("HANDOFF_SERVICE_URL", "http://127.0.0.1:8000")
    payload = {
        "order_id": "order-1048",
        "seller_assets": [example_pdf(), example_pdf()],
        "buyer_updates": [example_pdf()],
    }
    response = httpx.request(
        method="POST",
        url=f"{service_url}/orders/handoff",
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"Handoff request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
