import html as html_lib
import json
import logging
import re
from datetime import datetime
from typing import Iterable, Optional

import aiohttp
from aiohttp import ClientSession
from parsel import Selector

from scraper.async_helper import gather_scraping_results, request_with_retry
from scraper.model import MerchItem, Url

MERCH_TYPE_CASSETTE = "Cassette"
MERCH_TYPE_VINYL = "Record/Vinyl"
RE_DATA_TRALBUM = re.compile(r'data-tralbum="(?P<DATA>[^"]+)"', re.MULTILINE)
RE_FLOPPY = re.compile(r"floppy", re.IGNORECASE)
RE_MINIDISC = re.compile(r"mini\s*disc", re.IGNORECASE)
RE_VINYL = re.compile(r"\bvinyl\b", re.IGNORECASE)
RE_URL = re.compile(r"^https?://")


async def scrape_label_merch_url(url: Url) -> Iterable[MerchItem]:
    logging.debug(f"Scraping label merch url {url}...")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        maybe_res = await request_with_retry(session, url=url)
        if not maybe_res:
            return []
        html, response_url = maybe_res
        base_url = response_url[:response_url.rfind("/")]
        merch_item_paths = _parse_label_merch_html(html)
        if merch_item_paths:
            return await _scrape_merch_item_paths(paths=merch_item_paths, base_url=base_url, session=session)
        else:
            logging.warning(
                f"failed to find merch item entries in label merch html {response_url}, "
                f"attempting to scrape as merch item..."
            )
            try:
                return await _scrape_merch_item_url(url=response_url, session=session)
            except Exception as e:
                logging.error(f"failed to scrape url {response_url}", exc_info=e)
                return []


def _parse_label_merch_html(html: str) -> set[str]:
    anchors = Selector(text=html).xpath('''
        //li[
            (contains(@class,"merch-grid-item")
                or contains(@class,"featured-item"))
                and ./div[
                    contains(@class,"merchtype")
                ]
                and ./p[
                    contains(@class,"price")
                        and not(contains(@class,"sold-out"))
                ]
        ]/a[./div[@class="art"]]''').getall()

    return set(filter(None, [_parse_anchor_html(anchor) for anchor in anchors]))


def _parse_anchor_html(html) -> str | None:
    merch_item_path = Selector(text=html).xpath('''
        //a[./div[@class="art"]]/@href
    ''').get()

    return merch_item_path


async def _scrape_merch_item_paths(
        paths: Iterable[str],
        base_url: Url,
        session: ClientSession
) -> Iterable[MerchItem]:
    def album_url(path: str) -> str:
        if RE_URL.match(path):
            return path
        if path.startswith("/merch") and base_url.endswith("/merch"):
            path = path[6:]
        return base_url + path

    urls = [album_url(path) for path in paths]
    future_results = (_scrape_merch_item_url(url, session=session) for url in urls)
    results = await gather_scraping_results(future_results, urls)

    return results


async def _scrape_merch_item_url(url: Url, session: ClientSession) -> Iterable[MerchItem]:
    logging.debug(f"Scraping merch item url {url}...")
    maybe_res = await request_with_retry(session, url=url)
    if not maybe_res:
        return []
    html, _ = maybe_res
    result = _parse_merch_item_html(html, url)
    if result:
        logging.debug(f"... completed merch item url {url}")
    return result


def _parse_merch_item_html(html: str, url: Url) -> Iterable[MerchItem]:
    maybe_match = RE_DATA_TRALBUM.search(html)
    if not maybe_match:
        logging.error(f"failed to parse merch item html {url}")
        return []

    data_tralbum_raw = maybe_match.group("DATA")
    data_tralbum_raw = data_tralbum_raw.replace("&quot;", '"')
    try:
        releases = json.loads(data_tralbum_raw)["packages"] or []
    except KeyError:
        return []

    timestamp = datetime.now().isoformat()
    label = Selector(text=html).xpath('''
        //meta[
            @property="og:site_name"
        ]/@content''').get()
    album_url = Selector(text=html).xpath('''
        //meta[
            @property="og:url"
        ]/@content''').get()
    results: list[MerchItem] = []
    for release in releases:
        maybe_quantity_available: Optional[int] = release["quantity_available"]
        if maybe_quantity_available is None or maybe_quantity_available > 0:
            results.append(MerchItem(
                artist=html_lib.unescape(release["album_artist"] or release["download_artist"] or ""),
                currency=release["currency"],
                edition_of=release["edition_size"],
                id=release["id"],
                image_id=release["arts"][0]["image_id"],
                label=html_lib.unescape(label or ""),
                merch_type=html_lib.unescape(_normalize_merch_type(release["type_name"], release["title"])),
                price=release["price"],
                release_date=release["new_date"],
                remaining=maybe_quantity_available,
                timestamp=timestamp,
                title=html_lib.unescape(release["album_title"] or release["title"] or ""),
                url=html_lib.unescape(album_url or ""),
            ))

    return results


def _normalize_merch_type(raw_merch_type: str, title: str) -> str:
    merch_type = raw_merch_type
    if RE_VINYL.search(raw_merch_type):
        merch_type = "Vinyl"
    if RE_FLOPPY.search(title):
        merch_type = "Floppy"
    elif RE_MINIDISC.search(title):
        merch_type = "Minidisc"

    return merch_type
