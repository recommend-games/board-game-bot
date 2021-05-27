"""Twitter bot."""

import argparse
import hashlib
import logging
import os
import re
import sys

from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.parse import urlencode

import tweepy

from bg_utils import recommend_games
from pytility import arg_to_iter, truncate

BASE_PATH = Path(__file__).resolve().parent.parent

CONSUMER_KEY = os.getenv("TWITTER_API_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

LOGGER = logging.getLogger()


def create_api():
    """Initialise Twitter API."""

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        LOGGER.info("Authentication OK")
    except Exception:
        LOGGER.exception("Error during authentication")
        raise

    return api


def get_full_text(status):
    """Full text of a tweet."""

    if hasattr(status, "retweeted_status"):
        try:
            return status.retweeted_status.extended_tweet["full_text"]
        except AttributeError:
            return status.retweeted_status.text

    try:
        return status.extended_tweet["full_text"]
    except AttributeError:
        return status.text

    return None


class FavListener(tweepy.StreamListener):
    """Favorite tweets."""

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user = api.me()

    def on_status(self, status):
        LOGGER.info("Processing tweet id %d", status.id)

        if status.in_reply_to_status_id is not None or status.user.id == self.user.id:
            # This tweet is a reply or I'm its author so, ignore it
            return

        if not status.favorited:
            # Mark it as Liked, since we have not done it yet
            try:
                status.favorite()
            except Exception:
                LOGGER.error("Error on fav", exc_info=True)

        # if not status.retweeted:
        #     # Retweet, since we have not retweeted it yet
        #     try:
        #         status.retweet()
        #     except Exception:
        #         LOGGER.error("Error on fav and retweet", exc_info=True)

    def on_error(self, status_code):
        LOGGER.error(status_code)


class RecommendListener(tweepy.StreamListener):
    """Recommend games for a user."""

    base_url: str = "https://recommend.games"
    track: Tuple[str, ...] = ("Recommend.Games", "Recommend_Games", "RecommendGames")
    regex = re.compile(
        pattern=r"Recommend.?Games\s+(for|to)\s+(.+)$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    image_base_path: Optional[Path]

    def __init__(self, api, image_base_path: Union[Path, str, None] = None):
        super().__init__()
        self.api = api
        self.user = api.me()

        image_base_path = Path(image_base_path).resolve() if image_base_path else None
        self.image_base_path = (
            image_base_path if image_base_path and image_base_path.is_dir() else None
        )

        if self.image_base_path:
            LOGGER.info("Image base path: <%s>", self.image_base_path)

    def find_image_file(self, url: Optional[str]) -> Optional[Path]:
        """For a given URL find the locally downloaded file."""

        if not url or not self.image_base_path:
            return None

        url_hash = hashlib.sha1(url.encode("utf-8"))
        hex_digest = url_hash.hexdigest()
        LOGGER.info("Trying to find hash <%s> for URL <%s>…", hex_digest, url)

        images = self.image_base_path.glob(f"{hex_digest}.*")
        image = next(images, None)

        if image:
            LOGGER.info("URL <%s> found locally at <%s>", url, image)
            return image

        return None

    def process_text(self, text: str) -> Tuple[Optional[str], Optional[Path]]:
        """Process a tweet."""

        match = self.regex.search(text)

        if not match or not match.group(2):
            return None, None

        username = match.group(2).lower()

        if username == "me":
            return None, None

        LOGGER.info("Recommending games for <%s>…", username)

        results = tuple(
            recommend_games(
                max_results=5,
                user=username,
                exclude_known=True,
                exclude_owned=True,
                exclude_clusters=True,
            )
        )

        if not results:  # empty response – no recommendations
            LOGGER.info("Unable to create recommendations for <%s>", username)
            return None, None

        games = (truncate(game["name"], 40, respect_word=True) for game in results)
        result_str = "\n".join(f"- {game}" for game in games)

        image_urls = arg_to_iter(results[0].get("image_url"))
        image_url = next(iter(image_urls), None)
        image_file = self.find_image_file(image_url)

        query = urlencode({"for": username})
        url = f"{self.base_url}/#/?{query}"

        response = "\n\n".join(
            (
                f"🤖 #RecommendGames for {username.upper()}:",
                result_str,
                f"Full results: {url}",
            )
        )

        return response, image_file

    def on_status(self, status):
        text = get_full_text(status)

        LOGGER.info(
            "Processing tweet id %d by <%s>: %s",
            status.id,
            status.user.name,
            text,
        )

        if status.user.id == self.user.id:
            # tweet by API user – ignore it
            return

        response, image_file = self.process_text(text)

        if not response:
            return

        try:
            media = self.api.media_upload(image_file) if image_file else None
        except Exception:
            LOGGER.exception("Unable to upload file <%s>", image_file)
            media = None

        self.api.update_status(
            status=response,
            in_reply_to_status_id=status.id,
            auto_populate_reply_metadata=True,
            media_ids=[media.media_id]
            if media and hasattr(media, "media_id")
            else None,
        )


def _parse_args():
    parser = argparse.ArgumentParser(description="TODO")

    parser.add_argument("--dry-run", "-n", action="store_true", help="")
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="log level (repeat for more verbosity)",
    )

    return parser.parse_args()


def _main():
    args = _parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose > 0 else logging.INFO,
        format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
    )

    LOGGER.info(args)

    api = create_api()
    listener = RecommendListener(
        api=api,
        image_base_path=BASE_PATH.parent / "board-game-scraper" / "images" / "full",
    )

    if args.dry_run:
        response, image_file = listener.process_text(
            "@recommend_games for Markus Shepherd"
        )
        LOGGER.info(response)
        LOGGER.info(image_file)
        return

    stream = tweepy.Stream(api.auth, listener)
    stream.filter(track=RecommendListener.track)


if __name__ == "__main__":
    _main()
