import logging
import sys
from time import sleep

from aw_client import ActivityWatchClient
from aw_core import dirs
from aw_core.config import load_config_toml
from aw_core.models import Event
import requests

logger = logging.getLogger("aw-watcher-steam")

CONFIG = """
[aw-watcher-steam]
steam_id = ""
api_key = ""
poll_time = 5.0"""


class ActivityWatchClientManager:
    def __init__(self, client_name):
        self.client = ActivityWatchClient(client_name, testing=False)

    def __enter__(self):
        self.client.connect()
        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.disconnect()


def get_currently_played_games(api_key, steam_id) -> dict:
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={steam_id}"
    response = requests.get(url=url)
    response.raise_for_status()
    response_data = response.json()["response"]["players"][0]
    return (
        {k: response_data.get(k, "") for k in ["gameextrainfo", "gameid"]}
        if "gameextrainfo" in response_data
        else {}
    )


def validate_poll_time(poll_time_str):
    poll_time = float(poll_time_str)
    if poll_time <= 0:
        raise ValueError("Invalid poll_time value in config file")
    return poll_time


def validate_config(config, config_dir) -> None:
    steam_config = config["aw-watcher-steam"]
    required_keys = ["poll_time", "api_key", "steam_id"]
    if missing_keys := ", ".join(
        key for key in required_keys if not steam_config.get(key)
    ):
        raise ValueError(
            f"{missing_keys} not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )
    steam_config["poll_time"] = validate_poll_time(steam_config["poll_time"])


def run_polling_loop(client, bucket_name, api_key, steam_id, poll_time):
    while True:
        game_data = get_currently_played_games(api_key=api_key, steam_id=steam_id)
        if game_data:
            client.heartbeat(
                bucket_name,
                event=Event(data=game_data),
                pulsetime=poll_time + 1,
                queued=True,
            )
        status_message = f"Currently {'playing ' + game_data['currently-playing-game'] if game_data else 'not playing any'} game"
        logger.info(status_message)
        sleep(poll_time)


def setup_and_run(config):
    steam_config = config["aw-watcher-steam"]
    with ActivityWatchClientManager("aw-watcher-steam") as client:
        bucket_name = f"{client.client_name}_{client.client_hostname}"
        client.create_bucket(bucket_name, event_type="currently-playing-game")
        try:
            run_polling_loop(client, bucket_name, **steam_config)
        except Exception:
            logger.exception("An error occurred")


def main():
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config_toml("aw-watcher-steam", CONFIG)
    try:
        validate_config(config, config_dir)
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    setup_and_run(config)


if __name__ == "__main__":
    main()
