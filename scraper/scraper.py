import asyncio
import html as html_lib
import http
import json
import logging
import random
import re
from datetime import datetime
from typing import Iterable

import aiohttp
from aiohttp import ClientSession
from parsel import Selector  # type: ignore

from scraper.futures_helper import gather_scraping_results
from scraper.model import MerchDetails

MERCH_TYPE_CASSETTE = 'Cassette'
MERCH_TYPE_VINYL = 'Record/Vinyl'
RE_DATA_TRALBUM = re.compile(r'data-tralbum="(?P<DATA>.+?)"', re.MULTILINE)
RE_FLOPPY = re.compile(r'floppy', re.IGNORECASE)
RE_MINIDISC = re.compile(r'mini\s*disc', re.IGNORECASE)
RE_VINYL = re.compile(r'\bvinyl\b', re.IGNORECASE)
RE_URL = re.compile(r"^https?://")

MAX_SCRAPING_RETRIES = 12
SCRAPING_DELAY_MS = 0.25  # 250ms


async def scrape(label_merch_url: str) -> Iterable[MerchDetails]:
    logging.debug(f"Scraping label url {label_merch_url}...")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
        async with session.get(label_merch_url) as label_url_response:
            response_url = str(label_url_response.url)
            base_url = response_url[:response_url.rfind('/')]
            album_paths = _parse_merch_page_html(await label_url_response.text(encoding="utf-8"), response_url)
            if album_paths:
                return await _scrape_album_paths(paths=album_paths, base_url=base_url, session=session)
            else:
                try:
                    return await _scrape_album_url(url=response_url, session=session)
                except Exception as e:
                    logging.error(f"failed to scrape url {response_url}", exc_info=e)
                    return []


def _parse_merch_page_html(html: str, url: str) -> set[str]:
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

    parsed_anchors = set([_parse_anchor_html(anchor) for anchor in anchors])

    if not parsed_anchors:
        logging.error(f"failed to parse merch page {url}")

    return parsed_anchors


def _parse_anchor_html(html) -> str:
    release_path = Selector(text=html).xpath('''
        //a[./div[@class="art"]]/@href
    ''').get()

    return release_path


async def _scrape_album_paths(
        paths: Iterable[str],
        base_url: str,
        session: ClientSession
) -> Iterable[MerchDetails]:
    def album_url(path: str) -> str:
        if RE_URL.match(path):
            return path
        if path.startswith('/merch') and base_url.endswith('/merch'):
            path = path[6:]
        return base_url + path

    urls = [album_url(path) for path in paths]
    future_results = (_scrape_album_url(url, session=session) for url in urls)
    results = await gather_scraping_results(future_results, urls)

    return results


async def _scrape_album_url(url: str, session: ClientSession, num_try: int = 0) -> Iterable[MerchDetails]:
    logging.debug(f"Scraping album url {url}...")
    async with session.get(url) as res:
        if res.status != http.HTTPStatus.OK:
            if res.status == http.HTTPStatus.NOT_FOUND:
                logging.error(f"failed to scrape album url {url} ({res.status})")
                return []
            if res.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                if num_try < MAX_SCRAPING_RETRIES:
                    num_try += 1
                    lower_delay = SCRAPING_DELAY_MS * 0.5
                    upper_delay = SCRAPING_DELAY_MS * 1.5
                    actual_delay = 2 ** num_try * random.uniform(lower_delay, upper_delay)
                    logging.warning(
                        f"failed to scrape album url {url}({res.status}), "
                        f"pending retry {num_try} with {actual_delay:.2f}s delay..."
                    )
                    await asyncio.sleep(actual_delay)
                    return await _scrape_album_url(url, session, num_try + 1)
                else:
                    logging.error(f"failed to scrape album url {url} ({res.status}), skipping...")
                    return []
        result = _parse_album_page_html(await res.text(encoding="utf-8"), str(url))
        logging.debug(f"... completed album url {url}")
        return result


def _parse_album_page_html(html: str, url: str) -> Iterable[MerchDetails]:
    match = RE_DATA_TRALBUM.search(html)
    if not match:
        logging.error(f"failed to parse album page {url}")
        return []

    timestamp = datetime.now().isoformat()
    label = Selector(text=html).xpath('''
        //meta[
            @property="og:site_name"
        ]/@content''').get()
    url = Selector(text=html).xpath('''
        //meta[
            @property="og:url"
        ]/@content''').get()
    results: list[MerchDetails] = []
    data_tralbum_raw = match.group('DATA')
    data_tralbum_raw = data_tralbum_raw.replace('&quot;', '"')
    try:
        releases = json.loads(data_tralbum_raw)['packages'] or []
    except KeyError:
        releases = []
    for release in releases:
        if (release['quantity_available'] or 0) > 0:
            results.append(MerchDetails(
                artist=html_lib.unescape(release['album_artist'] or release['download_artist'] or ""),
                currency=release['currency'],
                edition_of=release['edition_size'],
                id=release['id'],
                image_id=release['arts'][0]['image_id'],
                label=html_lib.unescape(label or ""),
                merch_type=html_lib.unescape(_normalize_merch_type(release['type_name'], release['title'])),
                price=release['price'],
                release_date=release['new_date'],
                remaining=release['quantity_available'],
                timestamp=timestamp,
                title=html_lib.unescape(release['album_title'] or release['title'] or ""),
                url=html_lib.unescape(url),
            ))

    return results


def _normalize_merch_type(raw_merch_type: str, title: str) -> str:
    merch_type = raw_merch_type
    if RE_VINYL.search(raw_merch_type):
        merch_type = 'Vinyl'
    if RE_FLOPPY.search(title):
        merch_type = 'Floppy'
    elif RE_MINIDISC.search(title):
        merch_type = 'Minidisc'

    return merch_type
