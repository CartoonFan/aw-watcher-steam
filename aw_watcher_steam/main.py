import logging
import time

from aw_client import ActivityWatchClient
from aw_core import dirs
from aw_core.config import load_config_toml
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aw-watcher-steam")

STEAM_API_URL = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
CONFIG_SECTION = "aw-watcher-steam"
DEFAULT_POLL_TIME = 60.0

def get_currently_played_games(api_key, steam_id) -> dict:
    response = requests.get(STEAM_API_URL, params={"key": api_key, "steamids": steam_id})
    response.raise_for_status()
    return response.json().get("response", {}).get("players", [{}])[0].get("gameextrainfo", None)

def initialize_client():
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    client.create_bucket(client.client_name, event_type="currently-playing-game")
    return client

def main():
    config = load_configuration()
    if not validate_configuration(config):
        return

    client = initialize_client()
    poll_time = config.get("poll_time", DEFAULT_POLL_TIME)

    while True:
        game_name = get_currently_played_games(config["api_key"], config["steam_id"])
        log_current_game(game_name)
        send_heartbeat(client, game_name, poll_time)
        time.sleep(poll_time)

def log_current_game(game_name):
    if game_name:
        logger.info(f"Currently playing {game_name}")

def send_heartbeat(client, game_name, poll_time):
    client.heartbeat(data={"gameextrainfo": game_name}, pulsetime=poll_time + 1, queued=True)

def load_configuration():
    config = {"api_key": '', "steam_id": '', "poll_time": DEFAULT_POLL_TIME}
    config.update(load_config_toml(CONFIG_SECTION, "config.toml").get(CONFIG_SECTION, {}))
    return config

def validate_configuration(config):
    required_keys = {"api_key", "steam_id"}
    for key in required_keys:
        if key not in config:
            config_dir = dirs.get_config_dir("aw-watcher-steam")
            logger.warning(f"{key} not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey")
            return False
    return True

if __name__ == "__main__":
    main()