import hashlib
from asyncio import FIRST_COMPLETED, Queue, create_task, gather, wait
from typing import Any, Callable, Iterable
from uuid import UUID


async def queue_processing(
    queue_elements: Iterable, worker_func: Callable[[Queue, Any], Any], worker_count: int, **kwargs
):
    queue = Queue()
    for el in queue_elements:
        queue.put_nowait(el)

    tasks = []
    for _ in range(worker_count):
        tasks.append(create_task(worker_func(queue, **kwargs)))

    # convert queue.join() to a full-fledged task, so we can test
    # whether it's done
    queue_complete = create_task(queue.join())

    # wait for the queue to complete or one of the workers to exit
    await wait([queue_complete, *tasks], return_when=FIRST_COMPLETED)

    exception = None
    if not queue_complete.done():
        # If the queue hasn't completed, it means one of the workers has
        # raised - find it and propagate the exception.  You can also
        # use t.exception() to get the exception object. Canceling other
        # tasks is another possibility.
        for task in tasks:
            try:
                if task.done():
                    task.result()  # this will raise
                else:
                    task.cancel()
            except Exception as e:
                exception = e
        queue_complete.cancel()
    else:
        for task in tasks:
            task.cancel()

    await gather(queue_complete, *tasks, return_exceptions=True)

    if exception:
        raise exception


def create_uuid_from_string(val: str):
    hex_string = hashlib.md5(val.encode("UTF-8")).hexdigest()
    return str(UUID(hex=hex_string))
