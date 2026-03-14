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
        if result.theatres:
            logger.info("Theatres (%d): %s", len(result.theatres), result.theatres)
        if result.theatre_show_types:
            for venue, types_list in result.theatre_show_types.items():
                logger.info("  %s: %s", venue, types_list)
        elif result.show_types:
            logger.info("Show types: %s", result.show_types)
        if result.movie_url:
            logger.info("URL: %s", result.movie_url)
        webhook_url = cfg.get("slack_webhook_url")
        preferred = cfg.get("preferred_theatre_substrings") or []
        preferred_show_types = cfg.get("preferred_show_types") or []
        theatres_list = result.theatres or []
        theatre_show_types = result.theatre_show_types or {}
        if preferred:
            preferred_lower = [s.lower() for s in preferred]
            matching = [
                t for t in theatres_list
                if any(sub in t.lower() for sub in preferred_lower)
            ]
        else:
            matching = list(theatres_list)

        def has_preferred_show_type(theatre_name: str) -> bool:
            types_at = theatre_show_types.get(theatre_name, [])
            if not preferred_show_types:
                return True
            pref_lower = [p.lower() for p in preferred_show_types]
            for st in types_at:
                st_lower = st.lower()
                for p in pref_lower:
                    if p in st_lower or st_lower in p:
                        return True
            return False

        matching_with_show_type = [t for t in matching if has_preferred_show_type(t)]
        notify = (
            (not preferred or matching)
            and (not preferred_show_types or matching_with_show_type)
        )
        if webhook_url and notify:
            if slack_notify.notify_tickets_available(
                webhook_url=webhook_url,
                movie_name=cfg["movie_name"],
                target_date_str=cfg["target_date_str"],
                message=result.message,
                showtimes=result.showtimes or [],
                movie_url=result.movie_url,
                theatres=theatres_list,
                preferred_matches=(
                    matching_with_show_type
                    if (preferred and preferred_show_types)
                    else (matching if preferred else None)
                ),
                show_types=result.show_types or [],
                theatre_show_types=result.theatre_show_types or {},
            ):
                logger.info("Slack notification sent")
            else:
                logger.warning("Slack notification failed")
        elif webhook_url and not notify:
            if preferred and not matching:
                logger.info(
                    "Tickets available but no preferred theatre (substrings: %s); skipping Slack",
                    preferred,
                )
            elif preferred_show_types and matching and not matching_with_show_type:
                logger.info(
                    "Preferred theatre(s) found but none has preferred show type (%s); skipping Slack",
                    preferred_show_types,
                )
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
