from datetime import datetime, timezone
import logging
import sys
from time import sleep

from aw_client import ActivityWatchClient
from aw_core import dirs
from aw_core.models import Event
import requests


CONFIG = """
[aw-watcher-steam]
steam_id = ""
api_key = ""
poll_time = 5.0"""


class SteamAPIError(Exception):
    pass


def load_config():
    from aw_core.config import load_config_toml as _load_config

    return _load_config("aw-watcher-steam", CONFIG)


def get_currently_played_games(api_key, steam_id) -> dict:
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={api_key}&steamids={steam_id}"
    response = requests.get(url=url)
    if response.status_code == 200:
        response_data = response.json()["response"]["players"][0]
        if "gameextrainfo" in response_data:
            return {
                "currently-playing-game": response_data["gameextrainfo"],
                "game-id": response_data["gameid"],
            }
    raise SteamAPIError(
        f"Steam API request error, error code: {response.status_code} {response.text}"
    )


def log_and_sleep(logger, error_message, poll_time):
    logger.error(error_message)
    sleep(poll_time)


def create_and_send_event(client, bucket_name, game_data, poll_time):
    now = datetime.now(timezone.utc)
    event = Event(timestamp=now, data=game_data)
    client.heartbeat(bucket_name, event=event, pulsetime=poll_time + 1, queued=True)
    currently_playing_game = game_data["currently-playing-game"]
    print(f"Currently playing {currently_playing_game}")


def main():
    logger = logging.getLogger("aw-watcher-steam")
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config()
    poll_time = float(config["aw-watcher-steam"].get("poll_time"))
    api_key = config["aw-watcher-steam"].get("api_key", "")
    steam_id = config["aw-watcher-steam"].get("steam_id", "")
    if api_key == "" or steam_id == "":
        logger.warning(
            f"steam_id or api_key not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )
        sys.exit(1)
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    bucket_name = f"{client.client_name}_{client.client_hostname}"
    client.create_bucket(bucket_name, event_type="currently-playing-game")
    client.connect()
    running = True
    while running:
        try:
            game_data = get_currently_played_games(api_key=api_key, steam_id=steam_id)
            create_and_send_event(client, bucket_name, game_data, poll_time)
        except SteamAPIError as e:
            log_and_sleep(logger, f"Error fetching data: {e}", poll_time)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            running = False
        sleep(poll_time)


if __name__ == "__main__":
    main()
