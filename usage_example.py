import asyncio
from jflow import Depends, Workflow

async def create_person(person_name: str) -> dict:
    return {'name': person_name}

async def create_hi(p=Depends(create_person)) -> str:
    print('Creating hi')
    return 'Hi ' + p['name']

async def say_hi(p=Depends(create_person), blessing=Depends(create_hi)) -> int:
    print(p, blessing, 'Once')
    return 1

async def say_hi_twice(p=Depends(create_person), blessing=Depends(create_hi)) -> int:
    print(p, blessing, 'Twice')
    return 2

async def main():
    workflow = Workflow(say_hi, say_hi_twice)
    result1, result2 = await workflow.run(entry_points={create_person: ['Joe Mama',]})
    print(result1, result2)

asyncio.run(main())
