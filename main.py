"""Entrypoint for the automated pipeline — drains the unprocessed proposal queue
once. Intended to be invoked by the user's API trigger (or run manually / on a
schedule). Safe to re-run: processed rows drop out of the queue.
"""

from pipeline import run_once

if __name__ == "__main__":
    run_once()
