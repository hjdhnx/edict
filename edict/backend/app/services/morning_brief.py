from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import logging
import re
import socket
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

log = logging.getLogger("edict.morning_brief")

DEFAULT_CATEGORIES = ["政治", "军事", "经济", "AI大模型"]

DEFAULT_FEEDS: dict[str, list[tuple[str, str]]] = {
    "政治": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("AP Top News", "https://rsshub.app/apnews/topics/ap-top-news"),
    ],
    "军事": [
        ("Defense News", "https://www.defensenews.com/rss/"),
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ],
    "经济": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ],
    "AI大模型": [
        ("Hacker News", "https://hnrss.org/newest?q=AI+LLM+model&points=50"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ],
}

CATEGORY_KEYWORDS = {
    "军事": [
        "war", "military", "troops", "attack", "missile", "army", "navy", "weapons",
        "战", "军", "导弹", "士兵", "ukraine", "russia", "china sea", "nato",
    ],
    "AI大模型": [
        "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic", "deepseek",
        "machine learning", "neural", "model", "大模型", "人工智能", "chatgpt",
    ],
}

MAX_XML_BYTES = 5 * 1024 * 1024
MAX_ITEMS_PER_CATEGORY = 5
MAX_ITEMS_PER_FEED = 10


def normalize_morning_config(config: dict[str, Any] | None) -> dict[str, Any]:
    config = config if isinstance(config, dict) else {}
    raw_categories = config.get("categories")
    categories: list[dict[str, Any]] = []
    if isinstance(raw_categories, list) and raw_categories:
        for item in raw_categories:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()[:40]
            if name:
                categories.append({"name": name, "enabled": bool(item.get("enabled", True))})
    else:
        categories = [{"name": name, "enabled": True} for name in DEFAULT_CATEGORIES]

    keywords = []
    for keyword in config.get("keywords") or []:
        value = str(keyword).strip()
        if value and value not in keywords:
            keywords.append(value[:60])

    custom_feeds = []
    for feed in config.get("custom_feeds") or []:
        if not isinstance(feed, dict):
            continue
        name = str(feed.get("name") or "自定义").strip()[:60]
        url = str(feed.get("url") or "").strip()
        category = str(feed.get("category") or "").strip()[:40]
        if url and category:
            custom_feeds.append({"name": name or "自定义", "url": url, "category": category})

    return {
        "categories": categories,
        "keywords": keywords,
        "custom_feeds": custom_feeds,
        "wecom_webhook": str(config.get("wecom_webhook") or "").strip(),
        "feishu_webhook": str(config.get("feishu_webhook") or "").strip(),
        "enabled": True,
        "message": config.get("message") or "天下要闻采集后端已启用。",
        "updated_at": config.get("updated_at") or "",
    }


def _is_blocked_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ])


def is_safe_feed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return False
    if _is_blocked_ip(host):
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    return all(not _is_blocked_ip(info[4][0]) for info in infos)


def _clean_xml(xml_text: str) -> str:
    cleaned = re.sub(r"<!DOCTYPE[^>]*(\[[\s\S]*?\])?>", "", xml_text, flags=re.IGNORECASE)
    return re.sub(r"<!ENTITY[^>]*>", "", cleaned, flags=re.IGNORECASE)


def _text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", child.text)).strip()


def _find_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        value = _text(node, name)
        if value:
            return value
    for child in node:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text:
            return html.unescape(re.sub(r"<[^>]+>", "", child.text)).strip()
    return ""


def _find_link(node: ET.Element) -> str:
    link = _find_text(node, ("link",))
    if link:
        return link
    for child in node:
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "link":
            href = child.attrib.get("href", "")
            if href:
                return href.strip()
    return ""


def _find_image(node: ET.Element) -> str:
    for child in node.iter():
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in {"thumbnail", "content"}:
            url = child.attrib.get("url", "")
            if url:
                return url.strip()
        if local == "enclosure" and "image" in child.attrib.get("type", ""):
            url = child.attrib.get("url", "")
            if url:
                return url.strip()
    return ""


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    if len(xml_text.encode("utf-8", errors="ignore")) > MAX_XML_BYTES:
        return []
    try:
        root = ET.fromstring(_clean_xml(xml_text))
    except ET.ParseError:
        return []

    nodes = root.findall(".//item")
    if not nodes:
        nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "entry"]

    items: list[dict[str, str]] = []
    for node in nodes[:MAX_ITEMS_PER_FEED]:
        title = _find_text(node, ("title",))
        summary = _find_text(node, ("description", "summary", "content"))
        link = _find_link(node)
        if not title or not link:
            continue
        items.append({
            "title": title,
            "summary": summary[:240] if summary else title,
            "desc": summary[:240] if summary else title,
            "link": link,
            "pub_date": _find_text(node, ("pubDate", "published", "updated")),
            "image": _find_image(node),
        })
    return items


def _match_category(item: dict[str, str], category: str) -> bool:
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if not keywords:
        return True
    text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('desc', '')}".lower()
    return any(keyword in text for keyword in keywords)


async def _fetch_feed(client: httpx.AsyncClient, source: str, url: str) -> tuple[str, list[dict[str, str]]]:
    try:
        response = await client.get(url, follow_redirects=False)
        response.raise_for_status()
        content = response.content[:MAX_XML_BYTES + 1]
        if len(content) > MAX_XML_BYTES:
            log.warning("RSS feed too large, skipped: %s", url)
            return source, []
        return source, parse_feed(content.decode(response.encoding or "utf-8", errors="ignore"))
    except Exception as exc:
        log.warning("RSS feed failed: %s (%s)", url, exc)
        return source, []


def _enabled_categories(config: dict[str, Any]) -> set[str]:
    enabled = {
        str(item.get("name") or "").strip()
        for item in config.get("categories", [])
        if isinstance(item, dict) and item.get("enabled", True)
    }
    return {name for name in enabled if name} or set(DEFAULT_CATEGORIES)


def _build_feeds(config: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    enabled = _enabled_categories(config)
    feeds = {category: list(values) for category, values in DEFAULT_FEEDS.items() if category in enabled}
    for custom in config.get("custom_feeds", []):
        category = str(custom.get("category") or "").strip()
        url = str(custom.get("url") or "").strip()
        if category not in enabled or not url:
            continue
        if not is_safe_feed_url(url):
            log.warning("Unsafe custom feed skipped: %s", url)
            continue
        feeds.setdefault(category, []).append((str(custom.get("name") or "自定义")[:60], url))
    return feeds


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


async def collect_morning_brief(config: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    normalized = normalize_morning_config(config)
    feeds_by_category = _build_feeds(normalized)
    user_keywords = [str(value).lower() for value in normalized.get("keywords", [])]
    result = {
        "date": date.today().strftime("%Y%m%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": {},
        "enabled": True,
        "message": "天下要闻已采集。",
    }

    headers = {"User-Agent": "Mozilla/5.0 (compatible; EdictMorningBrief/1.0)"}
    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        for category, feeds in feeds_by_category.items():
            tasks = [_fetch_feed(client, source, url) for source, url in feeds]
            feed_results = await asyncio.gather(*tasks) if tasks else []
            seen: set[str] = set()
            items: list[dict[str, str]] = []
            for source, source_items in feed_results:
                for item in source_items:
                    link = item.get("link", "")
                    if not link or link in seen or not _match_category(item, category):
                        continue
                    seen.add(link)
                    item["source"] = source
                    items.append(item)
                    if len(items) >= MAX_ITEMS_PER_CATEGORY:
                        break
                if len(items) >= MAX_ITEMS_PER_CATEGORY:
                    break
            if user_keywords:
                items.sort(
                    key=lambda item: sum(
                        1 for keyword in user_keywords
                        if keyword in f"{item.get('title', '')} {item.get('summary', '')}".lower()
                    ),
                    reverse=True,
                )
            result["categories"][category] = items

    today_path = data_dir / f"morning_brief_{result['date']}.json"
    latest_path = data_dir / "morning_brief.json"
    _atomic_write_json(today_path, result)
    _atomic_write_json(latest_path, result)
    return result
