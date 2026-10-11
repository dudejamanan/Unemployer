from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source, first


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _child_text(el, name: str) -> str:
    for c in el:
        if _strip_ns(c.tag) == name and (c.text or "").strip():
            return c.text.strip()
    return ""


def parse_feed(xml_text: str) -> list:
    """RSS 2.0 <item> or Atom <entry> -> list of dicts(title, link, published, summary, id)."""
    root = ET.fromstring(xml_text)
    items = []
    for el in root.iter():
        if _strip_ns(el.tag) not in ("item", "entry"):
            continue
        link = _child_text(el, "link")
        if not link:                      # Atom: <link href="...">
            for c in el:
                if _strip_ns(c.tag) == "link" and c.get("href"):
                    link = c.get("href")
                    break
        items.append({
            "title": _child_text(el, "title"), "link": link,
            "published": first(_child_text(el, "pubDate"), _child_text(el, "published"), _child_text(el, "updated")),
            "summary": first(_child_text(el, "description"), _child_text(el, "summary"), _child_text(el, "content"),
                             _child_text(el, "encoded")),
            "id": first(_child_text(el, "guid"), _child_text(el, "id"), link),
        })
    return items


class RssSource(Source):
    name = "rss"
    closes_missing = False

    def key(self, cfg):
        return f"rss:{cfg['name']}"

    def fetch(self, client, cfg):
        xml_text = client.get_text(cfg["url"], headers={"Accept": "application/rss+xml, application/atom+xml, text/xml, */*"})
        out = []
        for it in parse_feed(xml_text):
            if not it["title"] or not it["link"]:
                continue
            out.append(Opportunity(
                source=self.name, board=self.key(cfg), external_id=it["id"] or it["link"],
                title=it["title"], company=cfg.get("company", cfg["name"]), apply_url=it["link"],
                location=cfg.get("location", ""), opp_type=cfg.get("opp_type", "job"),
                description=html_to_text(it["summary"]), posted_at=parse_any_datetime(it["published"]),
            ))
        return out
