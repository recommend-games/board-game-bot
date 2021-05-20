"""Twitter bot."""

import os

import tweepy

CONSUMER_KEY = os.getenv("TWITTER_API_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")


def _main():
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        print("Authentication OK")
    except Exception:
        print("Error during authentication")
        raise

    timeline = api.home_timeline()
    for tweet in timeline:
        print(f"{tweet.user.name} said {tweet.text}")


if __name__ == "__main__":
    _main()
