"""Frontend routes serving the Leaflet-based display."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .templates import load_template

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def frontend_index() -> HTMLResponse:
    """Serve the main Leaflet dashboard."""

    markup = load_template("index.html")
    return HTMLResponse(markup)
