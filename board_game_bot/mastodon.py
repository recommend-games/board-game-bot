import logging

import html2text
import mastodon

from board_game_bot.utils import StatusProcessor

LOGGER = logging.getLogger(__name__)


class RecommendListener(mastodon.StreamListener):
    """Recommend games for a user."""

    api: mastodon.Mastodon
    user: mastodon.Mastodon.AttribAccessDict
    status_processor: StatusProcessor
    html_processor: html2text.HTML2Text
    track: str = "RecommendGames"

    def __init__(
        self,
        *,
        api: mastodon.Mastodon,
        base_url: str = RECOMMEND_GAMES_BASE_URL,
        add_link: bool = True,
        image_base_path: Union[Path, str, None] = None,
    ):
        super().__init__()

        self.api = api
        if not self.api.verify_minimum_version("1.1.0"):
            LOGGER.error("Mastodon API needs to be at least v1.1.0")
            raise Something

        self.user = self.api.me()

        self.status_processor = StatusProcessor(
            regex=re.compile(
                pattern=r"#Recommend.?Games\s+(for|to)\s+(.+)$",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
            base_url=base_url,
            add_link=add_link,
            image_base_path=image_base_path,
        )

        self.html_processor = html2text.HTML2Text(
            baseurl=self.api.api_base_url,
            bodywidth=None,
        )
        self.html_processor.ignore_emphasis = True
        self.html_processor.ignore_links = True

    def on_update(self, status):
        """TODO."""

        text = self.html_processor.handle(status["content"])

        LOGGER.info(
            "Processing toot id %d by <%s>: %s",
            status["id"],
            status["account"]["username"],
            text,
        )

        if status["account"]["id"] == self.user["id"]:
            # toot by API user – ignore it
            return

        response, image_file = self.processor.process_text(text)

        if not response:
            return

        # TODO media upload
        # try:
        #     media = self.api.media_upload(image_file) if image_file else None
        # except Exception:
        #     LOGGER.exception("Unable to upload file <%s>", image_file)
        #     media = None
        media = None

        self.api.status_post(
            status=response,
            in_reply_to_id=status,
            media_ids=[media["id"]] if media and media.get("id") else None,
            visibility="unlisted",
            language="en",
            idempotency_key=None,  # TODO use for retries
        )


def _parse_args():
    parser = argparse.ArgumentParser(description="TODO")

    # parser.add_argument(
    #     "--twitter-consumer-key",
    #     default=os.getenv("TWITTER_API_KEY"),
    #     help="",
    # )
    # parser.add_argument(
    #     "--twitter-consumer-secret",
    #     default=os.getenv("TWITTER_API_SECRET_KEY"),
    #     help="",
    # )
    # parser.add_argument(
    #     "--twitter-access-token",
    #     default=os.getenv("TWITTER_ACCESS_TOKEN"),
    #     help="",
    # )
    # parser.add_argument(
    #     "--twitter-access-token-secret",
    #     default=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    #     help="",
    # )
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

    # api = create_api(
    #     consumer_key=args.twitter_consumer_key,
    #     consumer_secret=args.twitter_consumer_secret,
    #     access_token=args.twitter_access_token,
    #     access_token_secret=args.twitter_access_token_secret,
    # )

    api = mastodon.Mastodon(access_token="bot_user.secret")
    listener = RecommendListener(
        api=api,
        base_url=args.base_url,
        add_link=not args.no_link,
        image_base_path=args.image_base_path,
    )

    if args.dry_run:
        response, image_file = listener.processor.process_text(
            "#RecommendGames for Markus Shepherd"
        )
        LOGGER.info(response)
        LOGGER.info(image_file)
        return

    api.stream_hashtag(tag=listener.track, listener=listener)


if __name__ == "__main__":
    _main()
