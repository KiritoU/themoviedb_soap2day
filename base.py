import asyncio
import json
import sys
from time import sleep

from icecream import ic
from tmdb import route

from _db import Database
from settings import CONFIG
from soap2day import Soap2day

base = route.Base()
base.key = CONFIG.TMDB_API_KEY


class Crawler:
    def __init__(self, database: Database) -> None:
        self._soap2day = Soap2day(database=database)

    async def get_trailer_from_movie_or_show(self, movie: dict, movie_type: str) -> str:
        if movie_type == CONFIG.TYPE_MOVIE:
            videos = await route.Movie().videos(movie.get("id"))
        else:
            videos = await route.Show().videos(movie.get("id"))
        if not isinstance(videos, dict):
            return ""

        sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

        videos = videos.get("results", [])
        for video in videos:
            if video.get("type", "").lower() == "trailer":
                return video.get("key", "")

        return ""

    async def get_cast_and_production_from_movie_or_show(
        self, movie: dict, movie_type: str
    ):
        if movie_type == CONFIG.TYPE_MOVIE:
            credits = await route.Movie().credits(movie.get("id"))
        else:
            credits = await route.Show().aggregate_credits(movie.get("id"))
        if not isinstance(credits, dict):
            return "", ""

        sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

        casts = credits.get("cast", [])
        casts_name = [
            cast.get("name", cast.get("original_name", ""))
            for cast in casts
            if isinstance(cast, dict)
        ]

        crews = credits.get("crew", [])
        productions_name = [
            crew.get("name", crew.get("original_name", ""))
            for crew in crews
            if isinstance(crew, dict)
            and crew.get("known_for_department", "") == "Production"
        ]

        return casts_name, productions_name

    async def get_movie_or_show_keywords(self, movie: dict, movie_type: str) -> list:
        if movie_type == CONFIG.TYPE_MOVIE:
            credits = await route.Movie().keywords(movie.get("id"))
        else:
            credits = await route.Show().keywords(movie.get("id"))
        if not isinstance(credits, dict):
            return "", ""

        sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

        results = credits.get("results", [])
        results_name = [
            result.get("name", "") for result in results if isinstance(result, dict)
        ]

        return results_name

    async def crawl_show_season(
        self,
        inserted_movie_id: int,
        show_id: int,
        season_number: int,
        movie_cover_url: str,
    ) -> None:
        if not season_number:
            return

        season = await route.Season().details(
            tv_id=show_id, season_number=season_number
        )

        if not isinstance(season, dict):
            # TODO: Noti
            return

        sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

        inserted_season_id = self._soap2day.get_or_insert_season(
            movie_id=inserted_movie_id,
            season_number=season_number,
            season_name=season.get("name", ""),
        )

        episodes = season.get("episodes", [])
        for episode in episodes:
            self._soap2day.get_or_insert_episode(
                movie_id=inserted_movie_id,
                season_id=inserted_season_id,
                episode=episode,
                thumb_url=movie_cover_url,
            )

    async def crawl_movie_by_id(
        self, movie_id: int, movie_type: str, movie_on: str = "Other"
    ) -> None:
        try:
            if movie_type == CONFIG.TYPE_MOVIE:
                movie = await route.Movie().details(movie_id)
            else:
                movie = await route.Show().details(movie_id)

            if not isinstance(movie, dict):
                # TODO: Noti
                return

            print(f'[+] Crawling {movie_type} name: {movie.get("original_name", "")}')

            sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

            casts, directors = await self.get_cast_and_production_from_movie_or_show(
                movie=movie, movie_type=movie_type
            )
            keywords = await self.get_movie_or_show_keywords(
                movie=movie, movie_type=movie_type
            )
            movie["casts"] = casts
            movie["directors"] = directors
            movie["keywords"] = keywords
            movie["movie_on"] = movie_on
            movie["trailer_id"] = await self.get_trailer_from_movie_or_show(
                movie=movie, movie_type=movie_type
            )
            # with open("test/movie.json", "w") as f:
            #     f.write(json.dumps(movie, indent=4))

            movie_cover_url = f"{CONFIG.TMDB_IMAGE_PREFIX}{movie.get('backdrop_path', movie.get('poster_path', ''))}"

            inserted_movie_id = self._soap2day.insert_movie(
                movie_data=movie, movie_type=movie_type
            )
            if inserted_movie_id and movie_type == CONFIG.TYPE_TV_SHOWS:
                seasons = movie.get("seasons", [])
                for season in seasons:
                    season_number = season.get("season_number", 0)
                    await self.crawl_show_season(
                        inserted_movie_id=inserted_movie_id,
                        show_id=movie_id,
                        season_number=season_number,
                        movie_cover_url=movie_cover_url,
                    )

        except Exception as e:
            print(e)

    async def crawl_movies_or_shows_by_page(
        self, movie_type: str, page: int = 1, movie_on: str = "Other"
    ) -> int:
        if movie_type == CONFIG.TYPE_MOVIE:
            movies = await route.Movie().popular(page=page)
        else:
            movies = await route.Show().popular(page=page)

        if not isinstance(movies, dict):
            # TODO: Noti
            return 0

        sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

        total_pages = movies.get("total_pages", 0)
        results = movies.get("results", [])

        for result in results:
            movie_id = result.get("id", 0)
            if not movie_id:
                continue

            await self.crawl_movie_by_id(
                movie_id, movie_type=movie_type, movie_on=movie_on
            )

        return total_pages

    async def crawl_airing_today_shows(self) -> None:
        page = 1

        while True:
            print(f"[+] Crawling airing today page: {page}")
            movies = await route.Show().airing_today(page=page)

            if not isinstance(movies, dict):
                # TODO: Noti
                return 0

            sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

            total_pages = movies.get("total_pages", 0)
            results = movies.get("results", [])

            for result in results:
                movie_id = result.get("id", 0)
                if not movie_id:
                    continue

                await self.crawl_movie_by_id(
                    movie_id, movie_type=CONFIG.TYPE_TV_SHOWS, movie_on="Airing"
                )

            page += 1
            if page > total_pages:
                break

    async def crawl_changes_shows(self, movie_type: str) -> None:
        page = 1

        while True:
            if movie_type == CONFIG.TYPE_MOVIE:
                movies = await route.Movie().changes(page=page)
            else:
                movies = await route.Show().changes(page=page)

            if not isinstance(movies, dict):
                # TODO: Noti
                return 0

            sleep(CONFIG.WAIT_BETWEEN_TMDB_REQUEST)

            total_pages = movies.get("total_pages", 0)
            results = movies.get("results", [])

            for result in results:
                movie_id = result.get("id", 0)
                if not movie_id:
                    continue

                await self.crawl_movie_by_id(
                    movie_id, movie_type=CONFIG.TYPE_TV_SHOWS, movie_on="Other"
                )

            page += 1
            if page > total_pages:
                break
