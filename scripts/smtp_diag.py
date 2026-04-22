"""SMTP diagnostic — try 163 via multiple transports and print the raw dialogue.

Used one-off during bring-up to distinguish between:
  (a) invalid authorization code → every attempt returns 535
  (b) 163 IP-based blocking of overseas runners → consistent 535 (but EHLO banner often hints at it)
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
import traceback


def test(label: str, fn):
    print(f"\n========== {label} ==========", flush=True)
    try:
        fn()
        print(f">>> {label}: SUCCESS")
    except Exception as exc:  # noqa: BLE001
        print(f">>> {label}: FAIL ({type(exc).__name__}: {exc})")
        traceback.print_exc(file=sys.stdout)


HOST = "smtp.163.com"
USER = os.environ["SMTP_USER"]
PASS = os.environ["SMTP_PASS"]


def try_ssl(port: int) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(HOST, port, context=ctx, timeout=20) as s:
        s.set_debuglevel(1)
        s.ehlo()
        s.login(USER, PASS)
        print("  auth accepted")


def try_starttls(port: int) -> None:
    with smtplib.SMTP(HOST, port, timeout=20) as s:
        s.set_debuglevel(1)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(USER, PASS)
        print("  auth accepted")


test("smtp.163.com:465 SSL", lambda: try_ssl(465))
test("smtp.163.com:994 SSL", lambda: try_ssl(994))
test("smtp.163.com:25 STARTTLS", lambda: try_starttls(25))
test("smtp.163.com:587 STARTTLS", lambda: try_starttls(587))
