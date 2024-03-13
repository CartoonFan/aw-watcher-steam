import requests
from aw_core.models import Event
import logging
from aw_client import ActivityWatchClient
from aw_core import dirs
from aw_core.config import load_config_toml
from time import sleep

CONFIG = """
[aw-watcher-steam]
steam_id = ""
api_key = ""
poll_time = 5.0"""


def load_config():
    return load_config_toml("aw-watcher-steam", CONFIG)


def fetch_player_summaries(api_key, steam_id):
    url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params = {"key": api_key, "steamids": steam_id}
    return requests.get(url=url, params=params)


def process_player_summaries(response, logger):
    if response.status_code != 200:
        logger.error(
            f"Steam API request error, status code: {response.status_code}, response: {response.text}"
        )
        return None
    response_data = response.json()["response"]["players"][0]
    if "gameextrainfo" not in response_data:
        return None
    return {
        "currently-playing-game": response_data["gameextrainfo"],
        "game-id": response_data["gameid"],
    }


def setup_client():
    client = ActivityWatchClient("aw-watcher-steam", testing=False)
    bucket_name = f"{client.client_name}_{client.client_hostname}"
    client.create_bucket(bucket_name, event_type="currently-playing-game")
    client.connect()
    return client, bucket_name


def send_heartbeat(client, bucket_name, game_data, pulsetime, logger):
    event = Event(data=game_data)
    client.heartbeat(bucket_name, event=event, pulsetime=pulsetime, queued=True)
    logger.info(f"Currently playing {game_data['currently-playing-game']}")


def watch_games(client, bucket_name, api_key, steam_id, pulsetime, logger):
    response = fetch_player_summaries(api_key, steam_id)
    game_data = process_player_summaries(response, logger)
    if game_data:
        send_heartbeat(client, bucket_name, game_data, pulsetime, logger)


def setup_logging():
    logger = logging.getLogger("aw-watcher-steam")
    return logger


def check_config_and_log_errors(config, config_dir, logger):
    if not (config.get("api_key") and config.get("steam_id")):
        logger.error(
            f"steam_id or api_key not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )
        return False
    return True


def main():
    logger = setup_logging()
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config()["aw-watcher-steam"]
    poll_time = float(config.get("poll_time", 5.0)) + 1
    if not check_config_and_log_errors(config, config_dir, logger):
        return
    api_key = config["api_key"]
    steam_id = config["steam_id"]
    client, bucket_name = setup_client()

    while True:
        try:
            watch_games(client, bucket_name, api_key, steam_id, poll_time, logger)
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Error: {e}")
        sleep(poll_time - 1)


if __name__ == "__main__":
    main()
