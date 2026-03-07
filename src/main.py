"""Entry point: load config, run scheduler, check BMS availability every N minutes."""

import logging
import signal
import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler

from src import bms_crawler, config, slack_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_job() -> None:
    cfg = config.load_config()
    result = bms_crawler.run_check(cfg)
    if result.available:
        logger.info(
            "Tickets available for %s on %s. %s",
            cfg["movie_name"],
            cfg["target_date_str"],
            result.message,
        )
        if result.showtimes:
            logger.info("Showtimes / options: %s", result.showtimes)
        if result.movie_url:
            logger.info("URL: %s", result.movie_url)
        webhook_url = cfg.get("slack_webhook_url")
        if webhook_url:
            if slack_notify.notify_tickets_available(
                webhook_url=webhook_url,
                movie_name=cfg["movie_name"],
                target_date_str=cfg["target_date_str"],
                message=result.message,
                showtimes=result.showtimes or [],
                movie_url=result.movie_url,
            ):
                logger.info("Slack notification sent")
            else:
                logger.warning("Slack notification failed")
    else:
        logger.info(
            "Tickets not yet available for %s on %s. %s",
            cfg["movie_name"],
            cfg["target_date_str"],
            result.message,
        )


def main() -> None:
    try:
        cfg = config.load_config()
    except ValueError as e:
        logger.error("Invalid config: %s", e)
        sys.exit(1)

    interval_minutes = cfg["cron_interval_minutes"]
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_job,
        trigger="interval",
        minutes=interval_minutes,
        id="bms_check",
        next_run_time=None,
    )

    def shutdown(_sig=None, _frame=None) -> None:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Starting BMS crawler: checking every %s minute(s) for '%s' on %s in %s",
        interval_minutes,
        cfg["movie_name"],
        cfg["target_date_str"],
        cfg["bms_city"],
    )
    scheduler.start()
    run_job()

    try:
        while scheduler.running:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
