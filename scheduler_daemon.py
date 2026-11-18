import time
import logging
from threading import Event
from stickers_manager import process_due_stickers
from promotions_manager import process_due_promotions
from shayari_manager import process_due_shayari

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("Waguri.SchedulerDaemon")

def run_scheduler_loop(stop_event: Event | None = None) -> None:
    logger.info("Waguri dedicated scheduler daemon started. Checking due schedules every 5 seconds.")
    while stop_event is None or not stop_event.is_set():
        try:
            res_stickers = process_due_stickers()
            if res_stickers:
                logger.info("Dispatched due stickers: %s", res_stickers)
        except Exception as e:
            logger.warning("Error processing due stickers: %s", e)

        try:
            res_promos = process_due_promotions()
            if res_promos:
                logger.info("Dispatched due promotions: %s", res_promos)
        except Exception as e:
            logger.warning("Error processing due promotions: %s", e)

        try:
            res_shayari = process_due_shayari()
            if res_shayari:
                logger.info("Dispatched due shayari: %s", res_shayari)
        except Exception as e:
            logger.warning("Error processing due shayari: %s", e)

        if stop_event is None:
            time.sleep(5)
        elif stop_event.wait(5):
            break

if __name__ == "__main__":
    run_scheduler_loop()
