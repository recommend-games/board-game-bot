"""Twitter bot."""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Tuple, Union

import tweepy
from bg_utils.recommend import BASE_URL as RECOMMEND_GAMES_BASE_URL
from dotenv import load_dotenv
from urllib3.exceptions import HTTPError

from board_game_bot.utils import StatusProcessor

BASE_PATH = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger()

load_dotenv()


def create_api(
    consumer_key,
    consumer_secret,
    access_token=None,
    access_token_secret=None,
):
    """Initialise Twitter API."""

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    if access_token and access_token_secret:
        auth.set_access_token(access_token, access_token_secret)
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


class RecommendListener(tweepy.StreamListener):
    """Recommend games for a user."""

    track: Tuple[str, ...] = ("Recommend.Games", "Recommend_Games", "RecommendGames")

    def __init__(
        self,
        *,
        api,
        base_url: str = RECOMMEND_GAMES_BASE_URL,
        add_link: bool = True,
        image_base_path: Union[Path, str, None] = None,
    ):
        super().__init__(api=api)
        self.user = self.api.me()
        self.processor = StatusProcessor(
            regex=re.compile(
                pattern=r"Recommend.?Games\s+(for|to)\s+(.+)$",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
            base_url=base_url,
            add_link=add_link,
            image_base_path=image_base_path,
        )

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

        response, _, image_file = self.processor.process_text(text)

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

    parser.add_argument(
        "--twitter-consumer-key",
        default=os.getenv("TWITTER_API_KEY"),
        help="",
    )
    parser.add_argument(
        "--twitter-consumer-secret",
        default=os.getenv("TWITTER_API_SECRET_KEY"),
        help="",
    )
    parser.add_argument(
        "--twitter-access-token",
        default=os.getenv("TWITTER_ACCESS_TOKEN"),
        help="",
    )
    parser.add_argument(
        "--twitter-access-token-secret",
        default=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        help="",
    )
    parser.add_argument(
        "--base-url",
        "-u",
        default=os.getenv("RECOMMEND_GAMES_BASE_URL") or RECOMMEND_GAMES_BASE_URL,
        help="",
    )
    parser.add_argument("--no-link", "-l", action="store_true", help="")
    parser.add_argument(
        "--image-base-path",
        "-i",
        default=BASE_PATH.parent / "board-game-scraper" / "images" / "full",
        help="",
    )
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

    api = create_api(
        consumer_key=args.twitter_consumer_key,
        consumer_secret=args.twitter_consumer_secret,
        access_token=args.twitter_access_token,
        access_token_secret=args.twitter_access_token_secret,
    )
    listener = RecommendListener(
        api=api,
        base_url=args.base_url,
        add_link=not args.no_link,
        image_base_path=args.image_base_path,
    )

    if args.dry_run:
        response, games, image_file = listener.processor.process_text(
            "@recommend_games for Markus Shepherd"
        )
        LOGGER.info(response)
        LOGGER.info(games)
        LOGGER.info(image_file)
        return

    stream = tweepy.Stream(api.auth, listener)

    try:
        stream.filter(track=RecommendListener.track)
    except HTTPError:
        LOGGER.info("Closing Twitter bot 🤖 Bye bye!")
    except Exception:
        LOGGER.exception("Something went wrong 😬 …")


if __name__ == "__main__":
    _main()
