"""Shared Jinja environment, so filters are registered exactly once."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from . import pages

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["nutrient"] = pages.format_nutrient
templates.env.filters["number"] = pages.format_number
