"""গভর্নড discovery ফলকে সত্যনিষ্ঠ chat response-এ রূপান্তর।"""
from __future__ import annotations

import html
import ipaddress
import re
from typing import Any
from urllib.parse import quote, urlsplit


def _safe_title(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    # বাংলা: HTML/Markdown control escape; উৎসের টেক্সট কোনো নির্দেশ নয়।
    text = html.escape(" ".join(value.split())[:300], quote=True)
    return re.sub(r"([\\`*_{}\[\]#!|])", r"\\\1", text)


def _safe_link(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return ""
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
            return ""
        host = url.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return quote(value, safe=":/?&=%#@+;,-._~")
        return ""
    except ValueError:
        return ""


def render_discovery(payload: dict[str, Any], *, bengali: bool) -> str:
    """কেবল আসা source metadata দেখাই; article পড়া বা fact-check দাবি করি না।"""
    status = payload.get("status")
    if status == "needs_clarification":
        return ("কোন ধরনের তথ্য খুঁজব—খবর, গবেষণাপত্র, সাধারণ জ্ঞান নাকি সফটওয়্যার রিপোজিটরি? লাইভ দাম বা আবহাওয়া এখন যাচাই করতে পারি না।"
                if bengali else "Which kind of information should I look for: news, research papers, reference material, or software repositories? I can't currently check live prices or weather.")
    if status == "consent_required":
        source = _safe_title(payload.get("source")) or "external source"
        return (f"খুঁজতে শুধু আপনার সার্চের কথাটি {source}-এ পাঠাতে হবে; উৎসটি সেটি সংরক্ষণ করতে পারে। ব্যক্তিগত বা গোপন তথ্য না দিয়ে অনুমতি দিন।"
                if bengali else f"To search, only your query will be sent to {source}, which may retain it. Please consent without including private or secret information.")
    if status == "no_results" and payload.get("executed") is True:
        return ("নির্বাচিত উৎসে দেখানোর মতো কোনো ফল পাওয়া যায়নি। অন্য শব্দ বা অন্য ধরনের উৎস দিয়ে চেষ্টা করুন।"
                if bengali else "The selected source returned no usable results. Try different terms or another source type.")
    if status != "ok" or payload.get("executed") is not True or not isinstance(payload.get("results"), list):
        raise ValueError("Invalid source discovery response")
    entries = []
    for entry in payload["results"][:5]:
        if not isinstance(entry, dict):
            continue
        title, link = _safe_title(entry.get("title")), _safe_link(entry.get("url"))
        if title and link:
            date = _safe_title(entry.get("published"))
            excerpt = _safe_title(entry.get("snippet"))
            entries.append(f"- {title}" + (f" ({date})" if date else "")
                           + (f"\n  {excerpt}" if excerpt else "") + f"\n  {link}")
    if not entries:
        raise ValueError("No safe source metadata")
    source = _safe_title(payload.get("source")) or "source"
    if bengali:
        intro = f"{source}-এ পাওয়া কয়েকটি ফল:\n\n"
        notice = "\n\nএগুলো উৎসের শিরোনাম/সংক্ষিপ্ত অংশ; পুরো পৃষ্ঠা পড়ে বা দাবিগুলো স্বাধীনভাবে যাচাই করিনি। সময়ও বদলাতে পারে।"
    else:
        intro = f"Results from {source}:\n\n"
        notice = "\n\nThese are source-provided titles/excerpts; I have not read the full pages or independently verified their claims. Information may change."
    return intro + "\n".join(entries) + notice


def is_bengali_request(text: Any, pref: Any) -> bool:
    if isinstance(pref, str) and pref.lower().startswith(("en", "bn")):
        return pref.lower().startswith("bn")
    if not isinstance(text, str):
        return False
    return bool(re.search(r"[\u0980-\u09ff]", text) or re.search(r"\b(khobor|khabar|ajker|bangladesher|gobeshona|khuj[eo])\b", text.lower()))
