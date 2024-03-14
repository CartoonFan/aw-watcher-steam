from datetime import datetime, timezone
import logging
from time import sleep

from aw_client import ActivityWatchClient
from aw_core.config import load_config_toml
import requests

CONFIG = """
[aw-watcher-steam]
steam_id = ""
api_key = ""
poll_time = 5.0"""

CONFIG_DICT = load_config_toml("aw-watcher-steam", CONFIG)["aw-watcher-steam"]


class ConfigurationError(Exception):
    pass


def get_currently_played_games(api_key, steam_id) -> dict:
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={steam_id}"
    response = requests.get(url=url)
    response.raise_for_status()
    response_data = response.json()["response"]["players"][0]
    if "gameextrainfo" not in response_data:
        return {}
    return {
        "currently-playing-game": response_data["gameextrainfo"],
        "game-id": response_data["gameid"],
    }


def validate_configuration(config):
    if not {"api_key", "steam_id"}.issubset(config):
        missing_keys = {"api_key", "steam_id"} - config.keys()
        raise ConfigurationError(
            f"{', '.join(missing_keys)} not specified in config file, get your api here: https://steamcommunity.com/dev/apikey"
        )


def initialize_client():
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    bucket_name = f"aw-watcher-steam_{client.client_hostname}"
    client.create_bucket(bucket_name, event_type="currently-playing-game")
    client.connect()
    return client, bucket_name


def run_main_loop(client, bucket_name, config):
    logger = logging.getLogger("aw-watcher-steam")
    try:
        while True:
            game_data = get_currently_played_games(
                config["api_key"], config["steam_id"]
            )
            client.heartbeat(
                bucket_name,
                event=game_data,
                pulsetime=config["poll_time"] + 1,
                queued=True,
            )
            if game_data:
                logger.info(f"Currently playing {game_data['currently-playing-game']}")
            sleep(config["poll_time"])
    except Exception:
        logger.exception("Error occurred")


def setup_logging():
    logging.basicConfig(level=logging.INFO)


def main():
    setup_logging()
    try:
        validate_configuration(CONFIG_DICT)
    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
    else:
        client, bucket_name = initialize_client()
        run_main_loop(client, bucket_name, CONFIG_DICT)


if __name__ == "__main__":
    main()
