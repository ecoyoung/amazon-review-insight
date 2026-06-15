from __future__ import annotations

from redis import Redis
from rq import Connection, Worker

from app.queueing import QUEUE_NAME, REDIS_URL


def main() -> None:
    connection = Redis.from_url(REDIS_URL)
    with Connection(connection):
        worker = Worker([QUEUE_NAME])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
