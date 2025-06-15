import asyncio
from jflow import Depends, Workflow

async def create_person(person_name: str) -> dict:
    return {'name': person_name}

async def create_congratulation(p=Depends(create_person)) -> str:
    print('Creating congratulations')
    return 'Congratulations ' + p['name']

async def say_congratulation(p=Depends(create_person), blessing=Depends(create_congratulation)) -> int:
    print(p, blessing, 'Once')
    return 1

async def say_congratulation_twice(p=Depends(create_person), blessing=Depends(create_congratulation)) -> int:
    print(p, blessing, 'Twice')
    print(p, blessing, 'Twice')
    return 2

async def main():
    congratulation_workflow = Workflow(end_goals=[say_congratulation, say_congratulation_twice])
    say_congratulation_result, say_congratulation_twice_result = await congratulation_workflow.run(
        initial_inputs=[create_person(person_name='Joe Mama')]
    )
    print(say_congratulation_result, say_congratulation_twice_result)

asyncio.run(main())
