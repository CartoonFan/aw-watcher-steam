from datetime import datetime, timezone
import logging
import sys
from time import sleep
import traceback

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


def is_valid_config(config, config_dir) -> None:
    steam_config = config["aw-watcher-steam"]
    poll_time = steam_config.get("poll_time")
    api_key = steam_config.get("api_key")
    steam_id = steam_config.get("steam_id")

    if not poll_time or not api_key or not steam_id:
        raise ValueError(
            f"steam_id, api_key not specified or invalid poll_time in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )

    try:
        poll_time = float(poll_time)
        if poll_time <= 0:
            raise ValueError
    except ValueError:
        raise ValueError(
            f"Invalid poll_time value in config file (in folder {config_dir})"
        )


def send_event(client, bucket_name, game_data):
    if game_data:
        client.heartbeat(
            bucket_name,
            event=Event(data=game_data),
            pulsetime=game_data["poll_time"] + 1,
            queued=True,
        )


def run_polling_loop(client, bucket_name, api_key, steam_id, poll_time):
    try:
        while True:
            game_data = get_currently_played_games(api_key=api_key, steam_id=steam_id)
            send_event(client, bucket_name, game_data)
            status_message = (
                f"Currently playing {game_data['currently-playing-game']}"
                if game_data
                else "Currently not playing any game"
            )
            logger.info(status_message)
            sleep(poll_time)
    except Exception as e:
        logger.exception("An error occurred")


def setup_and_run(config):
    poll_time = config["aw-watcher-steam"]["poll_time"]
    api_key = config["aw-watcher-steam"]["api_key"]
    steam_id = config["aw-watcher-steam"]["steam_id"]
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    bucket_name = f"{client.client_name}_{client.client_hostname}"
    client.create_bucket(bucket_name, event_type="currently-playing-game")
    client.connect()
    run_polling_loop(client, bucket_name, api_key, steam_id, poll_time)


def main():
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config_toml("aw-watcher-steam", CONFIG)
    try:
        is_valid_config(config, config_dir)
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    setup_and_run(config)


if __name__ == "__main__":
    main()
