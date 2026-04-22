"""Render digest HTML email via Jinja2 templates."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai_news.models import Category, DigestItem

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2", "html.j2"]),
)

_CATEGORY_ORDER = [
    Category.MODEL_RELEASE,
    Category.PRODUCT,
    Category.RESEARCH,
    Category.TOOLING,
    Category.OPINION,
]


def _group_by_category(items: list[DigestItem]) -> list[tuple[Category, list[DigestItem]]]:
    by_cat: dict[Category, list[DigestItem]] = {c: [] for c in _CATEGORY_ORDER}
    for d in items:
        by_cat.setdefault(d.category, []).append(d)
    return [(c, by_cat[c]) for c in _CATEGORY_ORDER if by_cat.get(c)]


def render_email(*, subject: str, heading: str, banner: str | None,
                 items: list[DigestItem], template: str, generated_at: str) -> str:
    tpl = _env.get_template(template)
    return tpl.render(
        subject=subject,
        heading=heading,
        banner=banner,
        items_by_category=_group_by_category(items),
        generated_at=generated_at,
    )
