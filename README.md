# Vaporwave Merch Scraper

Live app: http://merch.iwanttorelease.com

## Setup

    poetry shell
    poetry install

## Run Tests

    flake8 .
    mypy .
    pytest --cov=scraper

## Run Scraper

    python -m scraper.main > bandcamp_merch.json
    cat bandcamp_merch.json

## Add or Remove a Music Label

Change file `resources/labels.txt` accordingly.
