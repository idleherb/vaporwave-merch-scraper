import asyncio
import json
import logging
from collections.abc import Iterable

from scraper.async_helper import gather_scraping_results
from scraper.filesystem_helper import resources_dir
from scraper.model import Url
from scraper.scraper import scrape_label_merch_url

LABELS_FILE = resources_dir / "labels.txt"


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )


async def main() -> None:
    urls = list(_read_label_urls())
    future_results = (scrape_label_merch_url(url) for url in urls)
    results = await gather_scraping_results(future_results, urls)

    print(json.dumps([json.loads(res.to_json()) for res in results]))  # type: ignore[attr-defined]

    logging.debug("... finished, found %s merch items.", len(results))


def _read_label_urls() -> Iterable[Url]:
    with LABELS_FILE.open() as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line or line.startswith("#"):
                continue
            yield line


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
