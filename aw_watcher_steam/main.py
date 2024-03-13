import requests
from aw_core.models import Event
import logging
from aw_client import ActivityWatchClient
from aw_core import dirs
from aw_core.config import load_config_toml
from time import sleep

DEFAULT_CONFIG = {"aw-watcher-steam": {"steam_id": "", "api_key": "", "poll_time": 5.0}}


def load_config():
    return load_config_toml("aw-watcher-steam", DEFAULT_CONFIG)


def fetch_player_summaries(api_key, steam_id):
    url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params = {"key": api_key, "steamids": steam_id}
    return requests.get(url=url, params=params)


def process_player_summaries(response):
    if response.status_code != 200:
        raise requests.HTTPError(
            f"Steam API request error, status code: {response.status_code}, response: {response.text}"
        )
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


def send_event(client, bucket_name, event, pulsetime):
    client.heartbeat(bucket_name, event=event, pulsetime=pulsetime, queued=True)


def is_valid_config(config):
    try:
        return all(config[key] for key in ["api_key", "steam_id"])
    except KeyError:
        return False


def watch_games(client, bucket_name, api_key, steam_id, pulsetime, logger):
    response = fetch_player_summaries(api_key=api_key, steam_id=steam_id)
    game_data = process_player_summaries(response)
    if game_data:
        event = Event(data=game_data)
        send_event(client, bucket_name, event, pulsetime)
        logger.info(f"Currently playing {game_data['currently-playing-game']}")


def main():
    logger = logging.getLogger("aw-watcher-steam")
    config_dir = dirs.get_config_dir("aw-watcher-steam")
    config = load_config()
    poll_time = float(config["aw-watcher-steam"].get("poll_time", 5.0)) + 1
    if not is_valid_config(config["aw-watcher-steam"]):
        logger.error(
            f"steam_id or api_key not specified in config file (in folder {config_dir}), get your api here: https://steamcommunity.com/dev/apikey"
        )
        return
    api_key = config["aw-watcher-steam"]["api_key"]
    steam_id = config["aw-watcher-steam"]["steam_id"]
    client, bucket_name = setup_client()

    while True:
        try:
            watch_games(client, bucket_name, api_key, steam_id, poll_time, logger)
        except (requests.HTTPError, requests.RequestException, ValueError) as e:
            logger.error(f"Error: {e}")
        sleep(poll_time - 1)


if __name__ == "__main__":
    main()
