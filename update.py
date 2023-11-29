import asyncio
import time

from _db import Database
from base import Crawler
from settings import CONFIG

if __name__ == "__main__":
    test_db = Database()
    while True:
        try:
            asyncio.run(Crawler(database=test_db).crawl_airing_today_shows())
        except Exception as e:
            print(e)
        time.sleep(CONFIG.WAIT_BETWEEN_UPDATE)

        try:
            asyncio.run(
                Crawler(database=test_db).crawl_changes_shows(
                    movie_type=CONFIG.TYPE_TV_SHOWS
                )
            )
        except Exception as e:
            print(e)

        try:
            asyncio.run(
                Crawler(database=test_db).crawl_changes_shows(
                    movie_type=CONFIG.TYPE_MOVIE
                )
            )
        except Exception as e:
            print(e)

        time.sleep(CONFIG.WAIT_BETWEEN_UPDATE)
