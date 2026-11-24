import logging
import time
from .experiments import process_one


def main():
    while True:
        try:
            if not process_one():
                time.sleep(0.4)
        except Exception:
            logging.exception("worker transaction failed")
            time.sleep(2)


if __name__ == "__main__":
    main()
