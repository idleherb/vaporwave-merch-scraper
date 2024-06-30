# Vaporwave Merch Scraper

Live app: http://merch.iwanttorelease.com

## Prerequesites

[Python 3.12](https://www.python.org/downloads/) and [Poetry](https://python-poetry.org/docs/#installation) installed.

## Setup

    poetry shell
    poetry install

## Run Tests

    ruff .
    mypy .
    pytest --cov=scraper

## Run Scraper

    python -m scraper.main > merch_items.json

## Add or Remove a Music Label

Change the URLs in `resources/labels.txt` accordingly.
Use a `#` at the beginning of any line to exclude it from scraping. 
