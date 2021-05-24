"""Twitter bot."""

import logging
import os
import re
import sys

from urllib.parse import urlencode

import tweepy

from bg_utils import recommend_games
from pytility import truncate

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

    base_url = "https://recommend.games"
    track = ("Recommend.Games", "Recommend_Games", "RecommendGames")
    regex = re.compile(
        pattern=r"Recommend.?Games\s+(for|to)\s+(.+)$",
        flags=re.IGNORECASE | re.MULTILINE,
    )

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user = api.me()

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

        match = self.regex.search(text)

        if not match or not match.group(2):
            return

        username = match.group(2).lower()

        if username == "me":
            return

        LOGGER.info("Recommending games for <%s>…", username)

        results = recommend_games(
            max_results=5,
            user=username,
            exclude_known=True,
            exclude_owned=True,
            exclude_clusters=True,
        )
        games = (truncate(game["name"], 40, respect_word=True) for game in results)
        result_str = "\n".join(f"- {game}" for game in games)

        if not result_str:  # empty response – no recommendations
            LOGGER.info("Unable to create recommendations for <%s>", username)
            return

        query = urlencode({"for": username})
        url = f"{self.base_url}/#/?{query}"

        response = "\n\n".join(
            (
                f"🤖 #RecommendGames for {username.upper()}:",
                result_str,
                f"Full results: {url}",
            )
        )

        self.api.update_status(
            status=response,
            in_reply_to_status_id=status.id,
            auto_populate_reply_metadata=True,
        )


def _main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    api = create_api()
    tweets_listener = RecommendListener(api)
    stream = tweepy.Stream(api.auth, tweets_listener)
    stream.filter(track=RecommendListener.track)


if __name__ == "__main__":
    _main()
