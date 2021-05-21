"""Twitter bot."""

import logging
import os
import sys

import tweepy

CONSUMER_KEY = os.getenv("TWITTER_API_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

LOGGER = logging.getLogger()


def create_api():
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


class FavListener(tweepy.StreamListener):
    def __init__(self, api):
        self.api = api
        self.me = api.me()

    def on_status(self, tweet):
        LOGGER.info("Processing tweet id %d", tweet.id)

        if tweet.in_reply_to_status_id is not None or tweet.user.id == self.me.id:
            # This tweet is a reply or I'm its author so, ignore it
            return

        if not tweet.favorited:
            # Mark it as Liked, since we have not done it yet
            try:
                tweet.favorite()
            except Exception:
                LOGGER.error("Error on fav", exc_info=True)

        # if not tweet.retweeted:
        #     # Retweet, since we have not retweeted it yet
        #     try:
        #         tweet.retweet()
        #     except Exception:
        #         LOGGER.error("Error on fav and retweet", exc_info=True)

    def on_error(self, status):
        LOGGER.error(status)


def _main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    api = create_api()
    tweets_listener = FavListener(api)
    stream = tweepy.Stream(api.auth, tweets_listener)
    stream.filter(track=["recommend_games"])


if __name__ == "__main__":
    _main()
