import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import urlencode

from bg_utils.recommend import BASE_URL as RECOMMEND_GAMES_BASE_URL
from bg_utils.recommend import recommend_games
from pytility import arg_to_iter, truncate

LOGGER = logging.getLogger()


class StatusProcessor:
    """TODO."""

    base_url: str
    add_link: bool
    regex: re.Pattern
    image_base_path: Optional[Path]

    def __init__(
        self: "StatusProcessor",
        *,
        regex: re.Pattern,
        base_url: str = RECOMMEND_GAMES_BASE_URL,
        add_link: bool = True,
        image_base_path: Union[Path, str, None] = None,
    ):
        self.regex = regex

        self.base_url = base_url
        self.add_link = add_link

        image_base_path = Path(image_base_path).resolve() if image_base_path else None
        self.image_base_path = (
            image_base_path if image_base_path and image_base_path.is_dir() else None
        )

        if self.image_base_path:
            LOGGER.info("Image base path: <%s>", self.image_base_path)

    def find_image_file(
        self: "StatusProcessor",
        url: Optional[str],
        suffix: Optional[str] = ".jpg",
    ) -> Optional[Path]:
        """For a given URL find the locally downloaded file."""

        if not url or not self.image_base_path:
            return None

        url_hash = hashlib.sha1(url.encode("utf-8"))
        hex_digest = url_hash.hexdigest()
        LOGGER.info("Trying to find hash <%s> for URL <%s>…", hex_digest, url)

        if suffix:
            image = self.image_base_path / f"{hex_digest}{suffix}"
            image = image if image.is_file() else None
        else:
            images = self.image_base_path.glob(f"{hex_digest}.*")
            image = next(images, None)

        if image:
            LOGGER.info("URL <%s> found locally at <%s>", url, image)
            return image

        return None

    def process_text(
        self,
        text: str,
    ) -> Tuple[Optional[str], Tuple[dict, ...], Optional[Path]]:
        """Process a tweet."""

        match = self.regex.search(text)

        if not match or not match.group(2):
            return None, (), None

        username = match.group(2).lower()

        if username == "me":
            return None, (), None

        LOGGER.info("Recommending games for <%s> from <%s>…", username, self.base_url)

        results = tuple(
            recommend_games(
                base_url=self.base_url,
                max_results=5,
                user=username,
                exclude_known=True,
                exclude_owned=True,
                exclude_clusters=True,
            )
        )

        if not results:  # empty response – no recommendations
            LOGGER.info("Unable to create recommendations for <%s>", username)
            return None, (), None

        games = (truncate(game["name"], 40, respect_word=True) for game in results)
        result_str = "\n".join(f"- {game}" for game in games)

        lines = [
            f"🤖 #RecommendGames for {username.upper()}:",
            result_str,
        ]

        if self.add_link:
            query = urlencode({"for": username})
            url = f"{self.base_url}/#/?{query}"
            lines.append(f"Full results: {url}")

        response = "\n\n".join(lines)

        image_urls = arg_to_iter(results[0].get("image_url"))
        image_url = next(iter(image_urls), None)
        image_file = self.find_image_file(image_url)

        return response, results, image_file
