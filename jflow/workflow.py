import asyncio
import inspect
from collections import defaultdict
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Sequence,
    Tuple,
)

class Workflow:
    def __init__(
        self,
        end_goals: Sequence[Callable[..., Awaitable[Any]]],
    ) -> None:
        self.end_goals = list(end_goals)

        # build dependency map: fn -> [its dependency functions]
        self._deps: Dict[Callable[..., Awaitable[Any]], Sequence[Callable[..., Awaitable[Any]]]] = {}
        for fn in self.end_goals:
            self._build_deps(fn)

        # build reverse map: fn -> [functions that depend on fn]
        self._dependents: Dict[Callable[..., Awaitable[Any]], Sequence[Callable[..., Awaitable[Any]]]] = defaultdict(list)
        for fn, deps in self._deps.items():
            for d in deps:
                self._dependents[d].append(fn)

    def _build_deps(self, fn: Callable[..., Awaitable[Any]]) -> None:
        if fn in self._deps:
            return
        sig = inspect.signature(fn)
        deps = []
        for param in sig.parameters.values():
            default = param.default
            if hasattr(default, "dependency") and asyncio.iscoroutinefunction(default.dependency):
                dep_fn = default.dependency
                deps.append(dep_fn)
                self._build_deps(dep_fn)
        self._deps[fn] = deps

    async def run(
        self,
        initial_inputs: Sequence[Awaitable[Any]],
    ) -> Tuple[Any, ...]:
        # 1) Seed any initial inputs
        cache: Dict[Callable[..., Awaitable[Any]], Any] = {}
        if initial_inputs:
            results = await asyncio.gather(*initial_inputs)
            for coro, res in zip(initial_inputs, results):
                fn_name = coro.cr_code.co_name
                # find the matching function object by name
                for fn in self._deps:
                    if fn.__name__ == fn_name:
                        cache[fn] = res
                        break

        # 2) Compute how many unsatisfied deps each fn has
        rem_deps: Dict[Callable[..., Awaitable[Any]], int] = {
            fn: sum(1 for d in deps if d not in cache)
            for fn, deps in self._deps.items()
        }

        # 3) Kick off all initially-ready (dep‐free) tasks
        task_to_fn: Dict[asyncio.Task, Callable[..., Awaitable[Any]]] = {}
        running: Dict[Callable[..., Awaitable[Any]], asyncio.Task] = {}
        for fn, count in rem_deps.items():
            if count == 0 and fn not in cache:
                task = asyncio.create_task(self._exec(fn, cache))
                running[fn] = task
                task_to_fn[task] = fn

        # 4) As tasks complete, schedule their dependents
        while running:
            done, _ = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                fn = task_to_fn.pop(task)
                result = task.result()
                cache[fn] = result
                running.pop(fn)

                # decrement remaining deps for each dependent
                for dep_fn in self._dependents.get(fn, []):
                    rem_deps[dep_fn] -= 1
                    if rem_deps[dep_fn] == 0:
                        # now ready to run
                        t2 = asyncio.create_task(self._exec(dep_fn, cache))
                        running[dep_fn] = t2
                        task_to_fn[t2] = dep_fn

        # 5) Return results of the end_goals in order
        return tuple(cache[fn] for fn in self.end_goals)

    async def _exec(
        self,
        fn: Callable[..., Awaitable[Any]],
        cache: Dict[Callable[..., Awaitable[Any]], Any],
    ) -> Any:
        """Gather args from cache and await fn(...)"""
        sig = inspect.signature(fn)
        kwargs: Dict[str, Any] = {}
        for param in sig.parameters.values():
            default = param.default
            if hasattr(default, "dependency") and asyncio.iscoroutinefunction(default.dependency):
                dep_fn = default.dependency
                kwargs[param.name] = cache[dep_fn]
            elif default is not inspect._empty:
                kwargs[param.name] = default
            else:
                raise RuntimeError(f"Missing required param {param.name} for {fn.__name__!r}")
        return await fn(**kwargs)
