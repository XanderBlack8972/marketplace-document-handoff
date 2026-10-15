from __future__ import annotations

import base64
import io
import os
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from pypdf import PdfReader, PdfWriter

from .infrai_pdf import InfraiError, InfraiPdfClient


class OrderHandoffRequest(BaseModel):
    order_id: str = Field(min_length=1)
    seller_assets: list[str] = Field(min_length=1)
    buyer_updates: list[str] = Field(default_factory=list)


class OrderHandoffResponse(BaseModel):
    order_id: str
    document_count: int
    bundle: dict[str, Any]


class PageGroup(BaseModel):
    name: str = Field(min_length=1)
    pages: list[int] = Field(min_length=1)


class BundleSplitRequest(BaseModel):
    pdf_base64: str = Field(min_length=1)
    groups: list[PageGroup] = Field(min_length=1)


class SplitDocument(BaseModel):
    name: str
    pdf_base64: str


class BundleSplitResponse(BaseModel):
    documents: list[SplitDocument]


def ordered_handoff_inputs(request: OrderHandoffRequest) -> list[str]:
    return [*request.seller_assets, *request.buyer_updates]


def get_pdf_client() -> InfraiPdfClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
    client = InfraiPdfClient(api_key)
    try:
        yield client
    finally:
        client.close()


app = FastAPI(title="Marketplace document handoff")


@app.post("/orders/handoff", response_model=OrderHandoffResponse)
def create_order_handoff(
    request: OrderHandoffRequest,
    client: Annotated[InfraiPdfClient, Depends(get_pdf_client)],
) -> OrderHandoffResponse:
    inputs = ordered_handoff_inputs(request)
    try:
        bundle = client.merge(inputs, idempotency_key=f"order-handoff:{request.order_id}")
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    return OrderHandoffResponse(
        order_id=request.order_id,
        document_count=len(inputs),
        bundle=bundle,
    )


@app.post("/bundles/split", response_model=BundleSplitResponse)
def split_bundle(request: BundleSplitRequest) -> BundleSplitResponse:
    try:
        source = base64.b64decode(request.pdf_base64, validate=True)
        reader = PdfReader(io.BytesIO(source))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="pdf_base64 must contain a PDF") from exc

    documents: list[SplitDocument] = []
    for group in request.groups:
        writer = PdfWriter()
        for page_number in group.pages:
            if page_number < 1 or page_number > len(reader.pages):
                raise HTTPException(status_code=422, detail=f"Page {page_number} is outside the bundle")
            writer.add_page(reader.pages[page_number - 1])
        output = io.BytesIO()
        writer.write(output)
        documents.append(
            SplitDocument(
                name=group.name,
                pdf_base64=base64.b64encode(output.getvalue()).decode("ascii"),
            )
        )
    return BundleSplitResponse(documents=documents)

