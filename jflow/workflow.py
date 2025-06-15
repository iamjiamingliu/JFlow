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
    Union
)

Func = Callable[..., Awaitable[Any]]
MaybeAwaitable = Union[Any, Awaitable[Any]]


class Workflow:
    def __init__(self, *end_goals: Func) -> None:
        """
        :param end_goals: async functions whose results you ultimately want.
        """
        self.end_goals = list(end_goals)
        # Build fn -> [its dependency fns]
        self._deps: Dict[Func, Sequence[Func]] = {}
        for fn in self.end_goals:
            self._build_deps(fn)
        # Build reverse map fn -> [functions depending on it]
        self._dependents: Dict[Func, Sequence[Func]] = defaultdict(list)
        for fn, deps in self._deps.items():
            for d in deps:
                self._dependents[d].append(fn)
        # Store user‐provided entry points
        self._entry_points: Dict[Func, MaybeAwaitable] = {}

    def add_entry_point(self, fn: Func, value: MaybeAwaitable) -> None:
        """
        Seed `fn` with either an already‐computed value, or an awaitable that
        returns its value.
        """
        self._entry_points[fn] = value

    def _build_deps(self, fn: Func) -> None:
        if fn in self._deps:
            return
        sig = inspect.signature(fn)
        deps = []
        for param in sig.parameters.values():
            default = param.default
            if hasattr(default, "dependency") and inspect.iscoroutinefunction(default.dependency):
                dep_fn = default.dependency
                deps.append(dep_fn)
                self._build_deps(dep_fn)
        self._deps[fn] = deps

    async def run(self) -> Tuple[Any, ...]:
        # 1) Seed cache with entry points
        cache: Dict[Func, Any] = {}
        for fn, val in self._entry_points.items():
            if inspect.isawaitable(val):
                cache[fn] = await val  # await coroutine
            else:
                cache[fn] = val  # concrete value

        # 2) Count unmet dependencies for every fn
        rem_deps: Dict[Func, int] = {
            fn: sum(1 for d in deps if d not in cache)
            for fn, deps in self._deps.items()
        }

        # 3) Kick off all ready tasks
        running: Dict[Func, asyncio.Task] = {}
        for fn, count in rem_deps.items():
            if count == 0 and fn not in cache:
                running[fn] = asyncio.create_task(self._execute(fn, cache))

        # 4) As tasks complete, schedule dependents
        while running:
            done, _ = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                # find which fn finished
                finished_fn = next(f for f, t in running.items() if t is task)
                running.pop(finished_fn)
                result = task.result()
                cache[finished_fn] = result
                # decrement deps of its dependents
                for child in self._dependents.get(finished_fn, []):
                    rem_deps[child] -= 1
                    if rem_deps[child] == 0:
                        running[child] = asyncio.create_task(self._execute(child, cache))

        # 5) Collect and return end‐goal results in order
        return tuple(cache[fn] for fn in self.end_goals)

    async def _execute(self, fn: Func, cache: Dict[Func, Any]) -> Any:
        """
        Gathers kwargs for `fn` from cache (via Depends) or defaults,
        then awaits it.
        """
        sig = inspect.signature(fn)
        kwargs: Dict[str, Any] = {}
        for param in sig.parameters.values():
            default = param.default
            if hasattr(default, "dependency") and inspect.iscoroutinefunction(default.dependency):
                dep_fn = default.dependency
                kwargs[param.name] = cache[dep_fn]
            elif default is not inspect._empty:
                kwargs[param.name] = default
            else:
                raise RuntimeError(f"Missing required parameter {param.name!r} for {fn.__name__}")
        return await fn(**kwargs)
