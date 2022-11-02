import html2text
from mastodon import Mastodon, StreamListener

h = html2text.HTML2Text()
h.ignore_emphasis = True
h.ignore_links = True
h.body_width = None


class MyStreamListener(StreamListener):
    def on_update(self, status):
        print(type(status))
        print(status)
        print(status["content"])
        print(h.handle(status["content"]))


m = Mastodon(api_base_url="https://botsin.space")
m.verify_minimum_version("1.1.0")
m.stream_hashtag("RecommendGames", MyStreamListener())
