import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from slugify import slugify

from _db import Database
from helper import helper
from settings import CONFIG

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)


class Soap2day:
    def __init__(self, database: Database):
        self._database = database

    def get_header(self):
        header = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E150",  # noqa: E501
            "Accept-Encoding": "gzip, deflate",
            # "Cookie": CONFIG.COOKIE,
            "Cache-Control": "max-age=0",
            "Accept-Language": "vi-VN",
            # "Referer": "https://mangabuddy.com/",
        }
        return header

    def download_url(self, url):
        return requests.get(url, headers=self.get_header())

    def save_thumb(
        self,
        imageUrl: str,
        imageName: str = "0.jpg",
    ) -> str:
        Path(CONFIG.COVER_SAVE_PATH).mkdir(parents=True, exist_ok=True)
        saveImage = f"{CONFIG.COVER_SAVE_PATH}/covers/{imageName}"

        isNotSaved = not Path(saveImage).is_file()
        if isNotSaved:
            image = self.download_url(imageUrl)
            with open(saveImage, "wb") as f:
                f.write(image.content)
            isNotSaved = True

        return f"{CONFIG.DOMAIN_NAME}/covers/{imageName}"

    def download_cover(self) -> None:
        cover_url = self.film["cover_src"]
        image_extension = cover_url.split("/")[-1].split(".")[-1]
        if image_extension:
            downloaded_cover_name = f"{self.film['slug']}.{image_extension}"
            downloaded_cover_url = self.save_thumb(cover_url, downloaded_cover_name)
            self.film["cover_src"] = downloaded_cover_url

    def get_season_number(self) -> str:
        season_str = self.film["slug"]
        season_str = season_str.replace("\n", " ").lower()
        regex = re.compile(r"season-(\d+)")
        match = regex.search(season_str)
        if match:
            return match.group(1)
        else:
            return "1"

    def generate_film_data(
        self,
        title,
        slug,
        description,
        post_type,
        trailer_id,
        quality,
        fondo_player,
        poster_url,
        extra_info,
    ):
        post_data = {
            "description": description,
            "title": title,
            "slug": slug,
            "post_type": post_type,
            # "id": "202302",
            "youtube_id": trailer_id,
            "quality": quality,
            # "serie_vote_average": extra_info["IMDb"],
            # "episode_run_time": extra_info["Duration"],
            "fondo_player": fondo_player,
            "poster_url": poster_url,
            # "category": extra_info["Genre"],
            # "stars": extra_info["Actor"],
            # "director": extra_info["Director"],
            # "release-year": [extra_info["Release"]],
            # "country": extra_info["Country"],
        }

        key_mapping = {
            "IMDb": "imdb",
            "Duration": "duration",
            "Genres": "genre",
            "Actors": "cast",
            "Starring": "cast",
            "Directors": "director",
            "Created by": "director",
            "Country": "country",
            "Release": "year",
            "Release Year": "year",
        }

        for info_key in key_mapping.keys():
            if info_key in extra_info.keys():
                post_data[key_mapping[info_key]] = extra_info[info_key]

        return post_data

    def get_timeupdate(self) -> datetime:
        timeupdate = datetime.now() - timedelta(hours=10)

        return timeupdate

    def get_slug_list_from(self, table: str, names: list) -> str:
        names = list(set(names))
        res = []
        for name in names[: CONFIG.MAX_CASTS_LENGTH]:
            try:
                condition = f"slug='{slugify(name)}'"
                data = (name, slugify(name))
                be_data_with_slug = self._database.select_or_insert(
                    table=table, condition=condition, data=data
                )
                res.append(be_data_with_slug[0][-1])
            except:
                pass

        if table == "country":
            if len(names) > 0:
                return res[0]
            else:
                return ""

        return json.dumps(res)

    def get_year_from(self, released: str) -> int:
        try:
            dt = datetime.strptime(released, "%Y-%m-%d")
            return int(dt.year)
        except:
            return CONFIG.DEFAULT_RELEASE_YEAR

    def get_imdb_from(self, imdb_str: str) -> float:
        try:
            return float(imdb_str)
        except:
            return 0

    def get_duration_from_movie(self, movie: dict) -> str:
        if "runtime" in movie.keys():
            return movie["runtime"]

        episode_run_time = movie.get("episode_run_time", [])
        if isinstance(episode_run_time, list) and len(episode_run_time) > 0:
            return str(episode_run_time[0])

        if isinstance(episode_run_time, list) and len(episode_run_time) == 0:
            return str("-")

        return str(episode_run_time)

    def insert_movie(self, movie_data: dict, movie_type: str) -> int:
        try:
            timeupdate = self.get_timeupdate()
            genre_names = [genre.get("name") for genre in movie_data.get("genres", [])]
            country_names = [
                country.get("name")
                for country in movie_data.get("production_countries", [])
            ]
            movie = {
                "name": movie_data.get(
                    "original_title",
                    movie_data.get(
                        "original_name",
                        movie_data.get("title", movie_data.get("title", "")),
                    ),
                ),
                "origin_name": movie_data.get(
                    "original_title", movie_data.get("title", "")
                ),
                "thumb": f"{CONFIG.TMDB_IMAGE_PREFIX}{movie_data.get('poster_path', movie_data.get('backdrop_path', ''))}",
                "coverUrl": f"{CONFIG.TMDB_IMAGE_PREFIX}{movie_data.get('backdrop_path', movie_data.get('poster_path', ''))}",
                "genres": self.get_slug_list_from(table="genres", names=genre_names),
                "year": self.get_year_from(
                    movie_data.get("release_date", movie_data.get("last_air_date", ""))
                ),
                "country": self.get_slug_list_from(
                    table="country", names=country_names
                ),
                "view": 0,
                "view_day": 0,
                "view_week": 0,
                "view_month": 0,
                "quality": CONFIG.DEFAULT_QUALITY,
                "duration": self.get_duration_from_movie(movie=movie_data),
                "trailerEmbed": ""
                if not movie_data.get("trailer_id", "")
                else f'https://www.youtube.com/watch?v={movie_data.get("trailer_id", "")}',
                "Casts": json.dumps(movie_data.get("casts", "")),
                "Director": json.dumps(movie_data.get("directors", "")),
                "hot": 0,
                "votePoint": int(movie_data.get("vote_average", 0) * 10),
                "voteNum": movie_data.get("vote_count", 0),
                "imdb": movie_data.get("vote_average", 0),
                "content": movie_data.get("overview", ""),
                "type": movie_type,
                "status": movie_data.get("status", ""),
                "onSlider": 0,
                "public": 1,
                "slug": slugify(
                    str(movie_data.get("id", ""))
                    + "-"
                    + movie_data.get(
                        "original_title",
                        movie_data.get(
                            "original_name",
                            movie_data.get("title", movie_data.get("title", "")),
                        ),
                    )
                ),
                "count_fav": 0,
                "player_fake": 1,
                "movieOn": movie_data.get("movie_on", "Other"),
                "movieTag": json.dumps(movie_data.get("keywords", [])),
                "time": timeupdate.strftime("%Y-%m-%d %H:%M:%S"),
                "creater": timeupdate.strftime("%Y-%m-%d"),
            }

            condition = f"""slug='{movie.get("slug")}' AND type='{movie_type}'"""
            post_id = self._database.select_or_insert(
                table="movie", condition=condition, data=list(movie.values())
            )[0][0]

            return post_id
        except Exception as e:
            helper.error_log(
                f'Failed to insert film: {movie_data.get("title", "")}\n{e}',
                "hdtoday.insert_movie.log",
            )
            return 0

    def insert_root_film(self) -> list:
        condition = (
            f"""slug = '{self.film["slug"]}' AND type='{self.film["post_type"]}'"""
        )
        be_post = self._database.select_all_from(table=f"movie", condition=condition)
        if not be_post:
            logging.info(f'Inserting root film: {self.film["post_title"]}')
            post_data = self.generate_film_data(
                self.film["post_title"],
                self.film["slug"],
                self.film["description"],
                self.film["post_type"],
                self.film["trailer_id"],
                self.film["quality"],
                self.film["cover_src"],
                self.film["cover_src"],
                self.film["extra_info"],
            )

            return self.insert_movie(post_data)
        else:
            return be_post[0][0]

    def validate_movie_episodes(self) -> None:
        res = []
        for ep_num, episode in self.episodes.items():
            episode_name = episode.get("title")
            episode_links = episode.get("links")
            # episodeName = episodeName.replace("Episoden", "").strip()
            episode_name = (
                episode_name.strip()
                .replace("\n", "")
                .replace("\t", " ")
                .replace("\r", " ")
            )
            if episode_links:
                episode_links = [
                    link if link.startswith("https:") else "https:" + link
                    for link in episode_links
                ]
                res.append([episode_name, ep_num, episode_links])
        res.sort(key=lambda x: float(x[1]))
        self.movie_episodes = res

    def get_server_name_from(self, link: str) -> str:
        # return "VIDCLOUD"
        x = re.search(r"//[^/]*", link)
        if x:
            return x.group().replace("//", "")

        return "Default"

    def get_episode_server_from(self, links: list) -> list:
        removeLinks = []
        for removeLink in removeLinks:
            if removeLink in links:
                links.remove(removeLink)
        res = [
            {
                "server_name": self.get_server_name_from(link),
                "server_type": "embed",
                "server_link": link,
            }
            for link in links
        ]

        return res

    def get_ep_num_from(self, ep_name: str) -> str:
        matches = re.search(r"^(\d+)", ep_name)
        if matches:
            return matches.group(1)

        return "1"

    def get_episode_data(self) -> list:
        res = []
        episodes = {}
        for server_data in self.episodes.values():
            server_episodes = server_data.get("episodes", {})
            for ep_name, ep_link in server_episodes.items():
                if not ep_link.startswith("https"):
                    ep_link = "https:" + ep_link

                episodes.setdefault(ep_name, [])
                episodes[ep_name].append(ep_link)

        for ep_name, ep_links in episodes.items():
            ep_links = sorted(list(set(ep_links)))
            episodes[ep_name] = ep_links

        for ep_name, ep_links in episodes.items():
            if self.film["post_type"] == CONFIG.TYPE_MOVIE:
                episode_name = f""
                episode_number = "1"
            else:
                episode_name = ep_name
                episode_number = self.get_ep_num_from(ep_name)

            res.append(
                {
                    "ep_name": episode_name,
                    "ep_num": episode_number,
                    "ep_time": 0,
                    "episode_server": self.get_episode_server_from(ep_links),
                }
            )

        return res

    def insert_episodes(self, movie_id: int) -> None:
        logging.info(
            f"Updating episodes for movie {self.film['post_title']} with ID: {movie_id}"
        )

        # if self.film["post_type"] == CONFIG.TYPE_MOVIE:
        #     self.episodes["Season 1"] = {
        #         "1": "Episode 1",
        #     }

        self.film["season_number"] = self.get_season_number()

        data = [
            {
                "season_name": self.film["season_number"],
                "episode_list": self.get_episode_data(),
            }
        ]

        # for key, value in self.episodes.items():
        #     if "season" in key.lower():
        #         data.append(
        #             {
        #                 "season_name": key,
        #                 "episode_list": self.get_episode_data(season_episodes=value),
        #             }
        #         )

        data = json.dumps(data)

        be_episode_data = self._database.select_or_insert(
            table="episode", condition=f"movie_id={movie_id}", data=(movie_id, data)
        )

        episode_data = be_episode_data[0][2]
        episode_data = (
            episode_data.decode() if isinstance(episode_data, bytes) else episode_data
        )
        # with open("json/diff.txt", "w") as f:
        #     print(data, file=f)
        #     print(episode_data, file=f)

        if episode_data != data:
            print("Diff")
            escape_data = data.replace("'", "''")
            self._database.update_table(
                table="episode",
                set_cond=f"""data='{escape_data}'""",
                where_cond=f"movie_id={movie_id}",
            )

    def get_or_insert_season(
        self, movie_id: int, season_number: int, season_name: str
    ) -> int:
        try:
            condition = f"""num={season_number} AND movieId={movie_id}"""
            data = (season_number, movie_id, season_name)
            season = self._database.select_or_insert(
                table="season", condition=condition, data=data
            )

            season_id = season[0][0]
            logging.info(
                f"Got or inserted season ID: {season_id} <= Movie ID: {movie_id}\tSeason name: {season_name}"
            )

            return season_id
        except:
            return 0

    def get_or_insert_episode(
        self, movie_id: int, season_id: int, episode: dict, thumb_url: str
    ) -> None:
        if not isinstance(episode, dict):
            return

        episode_number = episode.get("episode_number", 0)
        if not episode_number:
            return

        condition = (
            f"""movieId={movie_id} AND seasonId={season_id} AND num={episode_number}"""
        )

        data = (
            movie_id,
            episode_number,
            season_id,
            thumb_url,
            episode.get("name", ""),
            "[]",
        )

        self._database.select_or_insert(table="episode", condition=condition, data=data)
