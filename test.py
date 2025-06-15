import asyncio

from jflow import Depends


async def test(a: str, b: str) -> list[int]:
    ...


async def bob(arr=Depends(test)) -> bool:
    print(arr)
    return False


async def main():
    await bob([1, 2, 3])

asyncio.run(main())
