import asyncio as aio
import time


async def main(id, time):
  print(f"func {id} start")
  await aio.sleep(time)
  print(f"func {id} end")

async def functio():
  async with aio.TaskGroup() as tg:
    task1 = tg.create_task(main(1, 3))
    task2 = tg.create_task(main(2, 6))

  print(task1.result())
  print(task2.result())

if __name__ == "__main__":
    start = time.perf_counter()
    aio.run(functio())
    print(f"Total time elapsed: {time.perf_counter() - start:.2f} seconds")