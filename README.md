# JFlow
An embedded workflow orchestration framework that's Pythonic, async native, and lightweight.

## Quickstart

```python
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
```

Expected Output:
```text
Creating hi
{'name': 'Joe Mama'} Hi Joe Mama Once
{'name': 'Joe Mama'} Hi Joe Mama Twice
1 2
```

## Key Benefits
1. Dependency injection among the tasks with `Depends` (inspired by FastAPI)
2. Auto type hints for results returned by `Depends`
3. Intuitive, simple to use

## What's Happening Behind the Scene
When you create an instance of `Workflow`:
1. You pass in a few `end_goals` into `WorkFlow`. In the example, the `end_goals` are `say_hi` and `say_hi_twice`
2. JFlow recursively analyzes the dependencies starting from the `end_goals` to come up with an execution plan

You add some `entry points` to `Workflow`, which will be used to kick off the workflow

Finally, when you call `run` on the `Workflow` you just created:
1. JFlow collects the `entry points` and feed them to actually kick off the execution plan
2. For every task executed, JFlow tracks its result to avoid duplicate execution
3. Once all `end_goals` have returned results, stop the workflow and return those end results

> In academic jargon, the _execution plan_ is a Directed Acyclic Graph (DAG) data structure

## Why Did The Author Make JFlow?
Apache Airflow, Prefect, Dagster...
There's many big players already in the field of workflow orchestration.

These existing frameworks offer great visualization tools, state tracking, and deployment ecosytem.
They work well in scenarios such as big data processing where each task takes seconds if not hours to execute, 
which justify the overhead of state tracking and distributed execution in the magnitude of seconds.

However, in scenarios where each task takes a few milliseconds at most, and the workflow execution is a part of some other program instead of a standalone job,
an embedded, lightweight, simple to use workflow orchestration framework wins in performance.

And that's what JFlow is meant to do: embedded, lightweight, and simple to use.

The author explored around the popular framework "Hamilton" and couldn't understand it. So he decided to make his own. 
Thus JFlow as born.

## About the Author
Hi! I'm Jiaming Liu, UCSB Class of 2027 Undergrad CS major.

My other works include UCSBPlat.com, and SearchGit.dev

In building SearchGit.dev, I realized I needed a simple to use workflow orchestrator;
none of the existing frameworks is simple to use, so I decided to make my own.
