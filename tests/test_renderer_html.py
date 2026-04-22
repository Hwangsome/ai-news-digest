from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem
from ai_news.renderers.html_email import render_email

UTC = timezone.utc


def _d(title: str, cat: Category, score: float) -> DigestItem:
    raw = RawItem(id=title, source="OpenAI", title="en-" + title,
                  url="https://x/" + title,
                  published_at=datetime(2026, 4, 22, tzinfo=UTC),
                  raw_text=None, metadata={})
    return DigestItem(raw=raw, cn_title=title, cn_summary="摘要 " + title,
                      category=cat, score=score)


def test_render_groups_by_category():
    html = render_email(
        subject="[AI Daily] 2026-04-22",
        heading="每日 AI 要闻 · 2026-04-22",
        banner=None,
        items=[_d("发布 A", Category.MODEL_RELEASE, 9.1),
               _d("产品 B", Category.PRODUCT, 7.0)],
        template="daily.html.j2",
        generated_at="2026-04-22 08:00 CST",
    )
    assert html.index("模型发布") < html.index("产品与工具")
    assert "发布 A" in html
    assert "产品 B" in html
    assert "https://x/" in html
    assert "OpenAI" in html
    assert "9.1" in html


def test_banner_rendered_when_present():
    html = render_email(
        subject="s", heading="h", banner="⚠ 3 源失败",
        items=[_d("x", Category.OPINION, 5.0)],
        template="daily.html.j2", generated_at="t",
    )
    assert "⚠ 3 源失败" in html
    assert 'class="banner"' in html


def test_no_banner_hidden():
    html = render_email(
        subject="s", heading="h", banner=None,
        items=[_d("x", Category.OPINION, 5.0)],
        template="daily.html.j2", generated_at="t",
    )
    assert 'class="banner"' not in html


def test_categories_without_items_not_rendered():
    html = render_email(
        subject="s", heading="h", banner=None,
        items=[_d("only", Category.PRODUCT, 5.0)],
        template="daily.html.j2", generated_at="t",
    )
    assert "产品与工具" in html
    assert "研究与论文" not in html


def test_autoescape_prevents_html_injection():
    html = render_email(
        subject="s", heading="h", banner=None,
        items=[_d("<script>alert(1)</script>", Category.OPINION, 5.0)],
        template="daily.html.j2", generated_at="t",
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_items_still_renders():
    html = render_email(
        subject="s", heading="h", banner=None,
        items=[], template="daily.html.j2", generated_at="t",
    )
    assert "<h1>h</h1>" in html


def test_weekly_template_works():
    html = render_email(
        subject="s", heading="本周 AI 要闻", banner=None,
        items=[_d("x", Category.MODEL_RELEASE, 9.0)],
        template="weekly.html.j2", generated_at="t",
    )
    assert "模型发布" in html
    assert "x" in html
