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


def validate_config(config, config_dir):
    api_key = config["aw-watcher-steam"].get("api_key", "")
    steam_id = config["aw-watcher-steam"].get("steam_id", "")
    if not api_key or not steam_id:
        logger = logging.getLogger("aw-watcher-steam")
        logger.warning(
            f"steam_id or api_key not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )
        sys.exit(1)


def main():
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config_toml("aw-watcher-steam", CONFIG)
    validate_config(config, config_dir)
    poll_time = float(config["aw-watcher-steam"].get("poll_time"))
    api_key = config["aw-watcher-steam"]["api_key"]
    steam_id = config["aw-watcher-steam"]["steam_id"]
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    bucket_name = f"{client.client_name}_{client.client_hostname}"
    client.create_bucket(bucket_name, event_type="currently-playing-game")
    client.connect()
    while True:
        try:
            if game_data := get_currently_played_games(
                api_key=api_key, steam_id=steam_id
            ):
                now = datetime.now(timezone.utc)
                event = Event(timestamp=now, data=game_data)
                client.heartbeat(
                    bucket_name, event=event, pulsetime=poll_time + 1, queued=True
                )
                print(f"Currently playing {game_data['currently-playing-game']}")
            else:
                print("Currently not playing any game")
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            logging.error(traceback.format_exc())
        sleep(poll_time)


if __name__ == "__main__":
    main()
