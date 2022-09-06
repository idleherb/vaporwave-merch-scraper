import asyncio
import json
import logging
from typing import Iterable

from scraper.filesystem_helper import resources_dir
from scraper.futures_helper import gather_scraping_results
from scraper.scraper import scrape

LABELS_FILE = resources_dir / "labels.txt"

Url = str


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )


async def main() -> None:
    urls = _read_label_urls()
    future_results = (scrape(url) for url in _read_label_urls())
    results = await gather_scraping_results(future_results, urls)

    print(json.dumps([json.loads(res.to_json()) for res in results]))  # type: ignore

    logging.debug(f"done, found {len(results)} merch items")


def _read_label_urls() -> Iterable[Url]:
    with open(LABELS_FILE) as f:
        for line in f:
            yield line.strip()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
