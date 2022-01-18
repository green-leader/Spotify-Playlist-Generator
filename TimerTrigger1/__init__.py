import datetime
import logging

import azure.functions as func

from playlistbuilder import PlaylistGenerator


def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    build = PlaylistGenerator(plname="Daily Listen - Staging")
    build.main_build()
