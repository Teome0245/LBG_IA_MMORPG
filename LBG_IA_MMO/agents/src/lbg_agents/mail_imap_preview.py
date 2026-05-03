"""
Aperçu messagerie IMAP (INBOX, lecture seule, borné). Bibliothèque standard uniquement.
À garder aligné avec les workers windows_agent / linux_agent si copié ailleurs.
"""

from __future__ import annotations

import imaplib
import re
import ssl
from email import policy
from email.parser import BytesParser
from typing import Any


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _decode_header_value(raw: str) -> str:
    if not raw:
        return ""
    from email.header import decode_header, make_header

    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _parse_header_block(blob: bytes) -> tuple[str, str, str]:
    """Retourne (from_display, subject, date) depuis un fragment de headers."""
    if not blob:
        return "", "", ""
    try:
        msg = BytesParser(policy=policy.compat32).parsebytes(blob)
        f = _decode_header_value(msg.get("From", "") or "")
        s = _decode_header_value(msg.get("Subject", "") or "")
        d = _decode_header_value(msg.get("Date", "") or "")
        return f, s, d
    except Exception:
        return "", "", ""


def _extract_text_peek(dat: list[Any] | None, max_chars: int) -> str:
    if not dat:
        return ""
    for part in dat:
        if not isinstance(part, tuple) or len(part) < 2:
            continue
        chunk = part[1]
        if isinstance(chunk, bytes):
            try:
                t = chunk.decode("utf-8", errors="replace")
            except Exception:
                t = str(chunk)
            t = re.sub(r"\s+", " ", t).strip()
            return t[:max_chars] if max_chars > 0 else t
    return ""


def run_mail_imap_preview(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_ssl: bool,
    from_contains: str,
    subject_contains: str,
    max_messages: int,
    max_body_chars: int,
    max_scan: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Connecte en IMAP, parcourt les derniers messages de l'INBOX (borné),
    retourne les en-têtes + extrait de corps pour ceux qui matchent les filtres (ET logique si les deux présents).
    """
    fc = _norm(from_contains)
    sc = _norm(subject_contains)
    if not fc and not sc:
        return [], "Au moins un filtre from_contains ou subject_contains requis"

    host = host.strip()
    if not host or not user.strip():
        return [], "Configuration IMAP incomplète (host/user)"
    user = user.strip()

    if max_messages < 1:
        max_messages = 1
    if max_messages > 10:
        max_messages = 10
    if max_body_chars < 0:
        max_body_chars = 0
    if max_body_chars > 4000:
        max_body_chars = 4000
    if max_scan < 10:
        max_scan = 10
    if max_scan > 500:
        max_scan = 500

    ctx = ssl.create_default_context()
    try:
        if use_ssl:
            M = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        else:
            M = imaplib.IMAP4(host, port)
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

    try:
        try:
            M.login(user, password)
        except imaplib.IMAP4.error as e:
            return [], f"IMAP login: {e}"

        typ, _ = M.select("INBOX", readonly=True)
        if typ != "OK":
            return [], "Sélection INBOX impossible"

        typ, data = M.uid("SEARCH", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return [], None

        raw_ids = data[0].split()
        if not raw_ids:
            return [], None

        span = raw_ids[-max_scan:]
        out: list[dict[str, Any]] = []

        for uid_b in reversed(span):
            if len(out) >= max_messages:
                break
            uid = uid_b.decode("ascii", errors="ignore")
            typ_h, dat_h = M.uid("FETCH", uid_b, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ_h != "OK" or not dat_h:
                continue
            blob = b""
            for part in dat_h:
                if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
                    blob = part[1]
                    break
            from_d, subj_d, date_d = _parse_header_block(blob)

            ok_from = True
            ok_sub = True
            if fc:
                ok_from = fc in _norm(from_d)
            if sc:
                ok_sub = sc in _norm(subj_d)
            if not (ok_from and ok_sub):
                continue

            snippet = ""
            if max_body_chars > 0:
                spec = f"(BODY.PEEK[TEXT]<0.{max_body_chars}>)"
                typ_b, dat_b = M.uid("FETCH", uid_b, spec)
                if typ_b != "OK":
                    typ_b, dat_b = M.uid("FETCH", uid_b, f"(BODY.PEEK[1]<0.{max_body_chars}>)")
                snippet = _extract_text_peek(dat_b if typ_b == "OK" else None, max_body_chars)

            out.append(
                {
                    "uid": uid,
                    "from": from_d[:512],
                    "subject": subj_d[:512],
                    "date": date_d[:256],
                    "body_preview": snippet,
                }
            )

        return out, None
    except imaplib.IMAP4.error as e:
        return [], f"IMAP: {e}"
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"
    finally:
        try:
            M.logout()
        except Exception:
            pass
