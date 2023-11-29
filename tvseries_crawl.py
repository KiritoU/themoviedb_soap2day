import asyncio
import time

from _db import Database
from base import Crawler
from settings import CONFIG

if __name__ == "__main__":
    test_db = Database()
    page = 1

    while True:
        try:
            print(f"[+] Crawling page: {page}")
            total_pages = asyncio.run(
                Crawler(database=test_db).crawl_movies_or_shows_by_page(
                    page=page, type=CONFIG.TYPE_TV_SHOWS
                )
            )

            page += 1
            if page > total_pages:
                page = 1

        except Exception as e:
            print(e)
        time.sleep(CONFIG.WAIT_BETWEEN_CRAWL_ALL)
