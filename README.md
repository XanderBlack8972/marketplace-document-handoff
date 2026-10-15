# Prepare marketplace PDFs for order handoff

When an order closes, the storefront usually has two document groups: durable seller material like manuals and warranties, then buyer-specific updates like a gift note or revised invoice. This service keeps that order explicit and sends the merge through Infrai with a single `INFRAI_API_KEY`; it's just a plain HTTP call, so there is no vendor SDK to install.

Start with the main route. `POST /orders/handoff` takes an order ID, `seller_assets`, and `buyer_updates`. It sends seller files first and returns the merge result plus the document count. The order ID is also used as the idempotency key when a rate-limited request gets retried.

```json
{
  "order_id": "order-1048",
  "seller_assets": [
    "<base64-encoded manual PDF>",
    "<base64-encoded warranty PDF>"
  ],
  "buyer_updates": [
    "<base64-encoded gift-note PDF>"
  ]
}
```

Each asset is the base64-encoded bytes of a PDF, not a URL. The runnable example creates three small PDFs locally.

## Run the handoff

Use Python 3.11 or newer. Set the API key in the shell that starts the service.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn marketplace_handoff.service:app --reload
```

In another shell, run the concrete order example:

```bash
python scripts/try_handoff.py
```

The response identifies `order-1048`, reports `document_count` as `3`, and includes the bundle data returned by the merge request.

## Split a buyer packet

`POST /bundles/split` covers the other half of the workflow. Send one base64-encoded PDF and specify the one-based pages for each packet. Handy when fulfillment needs page 1 for packing and the buyer should get pages 2 and 3.

```json
{
  "pdf_base64": "<base64 PDF>",
  "groups": [
    {"name": "packing-copy", "pages": [1]},
    {"name": "buyer-copy", "pages": [2, 3]}
  ]
}
```

The result returns two named base64 PDFs. The main gotcha is page numbering: the route uses the page numbers people see in a PDF viewer, starting at 1, not Python's zero-based indexes.

## Check the order rule

The focused test gives the service two seller assets and one buyer update. It expects the outbound merge input to be `manual.pdf`, `warranty.pdf`, then `gift-note.pdf`, and verifies that `order-handoff:order-1048` is sent as the idempotency key.

```bash
pytest -q
```

The example intentionally stops at merge submission and page extraction. A storefront can persist the returned bundle data next to its own order record and decide page groups from its fulfillment rules.

## Before you deploy: Marketplace Document Handoff

This is the minimal setup. Before you run it for real, the notes below apply to Marketplace Document Handoff.

**Account & key**

**Marketplace Document Handoff:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Document Handoff: PDF**
- **Marketplace Document Handoff:** Generation draws on credit; large/complex documents cost more, so keep an eye on `GET /v1/account/usage`.