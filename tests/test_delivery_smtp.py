from email import message_from_bytes

from ai_news.delivery.smtp import InMemoryMailer, Mailer, build_message


def test_build_message_is_multipart_utf8():
    raw = build_message(
        sender="a@b.com", to="c@d.com",
        subject="[AI Daily] 中文", html="<p>你好</p>",
    )
    msg = message_from_bytes(raw)
    assert msg["Subject"].startswith("=?")   # encoded non-ASCII
    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    assert len(html_parts) == 1
    assert "你好" in html_parts[0].get_payload(decode=True).decode("utf-8")


def test_in_memory_mailer_captures():
    m = InMemoryMailer()
    assert isinstance(m, Mailer)
    m.send(sender="s@x", to="r@x", subject="s", html="<b>h</b>")
    assert len(m.sent) == 1
    assert m.sent[0].subject == "s"
    assert m.sent[0].html == "<b>h</b>"
    assert m.sent[0].sender == "s@x"
    assert m.sent[0].to == "r@x"


def test_multiple_sends_preserve_order():
    m = InMemoryMailer()
    m.send(sender="a", to="b", subject="1", html="x")
    m.send(sender="a", to="b", subject="2", html="y")
    assert [s.subject for s in m.sent] == ["1", "2"]
