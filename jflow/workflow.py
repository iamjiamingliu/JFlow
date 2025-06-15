import asyncio
import inspect
from collections import deque
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
        """
        :param end_goals: one or more async functions you ultimately want to run.
                           Their parameters should be defaulted to Depends(some_fn).
        """
        self.end_goals = list(end_goals)

        # Build the full DAG of functions → their dependencies
        self._deps: Dict[Callable[..., Awaitable[Any]], Sequence[Callable[..., Awaitable[Any]]]] = {}
        for fn in self.end_goals:
            self._build_deps(fn)

        # Pre‐compute a topological ordering
        self._topo = self._topological_sort(self._deps)

    def _build_deps(self, fn: Callable[..., Awaitable[Any]]) -> None:
        # If we've already processed this node, skip.
        if fn in self._deps:
            return

        sig = inspect.signature(fn)
        deps = []
        for param in sig.parameters.values():
            default = param.default
            # detect our Depends‐sentinel by duck-typing
            if hasattr(default, "dependency") and asyncio.iscoroutinefunction(default.dependency):
                dep_fn = default.dependency  # the underlying async function
                deps.append(dep_fn)
                self._build_deps(dep_fn)

        self._deps[fn] = deps

    def _topological_sort(
        self,
        deps: Dict[Callable[..., Awaitable[Any]], Sequence[Callable[..., Awaitable[Any]]]]
    ) -> Sequence[Callable[..., Awaitable[Any]]]:
        # Kahn’s algorithm
        in_degree: Dict[Callable[..., Awaitable[Any]], int] = {
            fn: len(dlist) for fn, dlist in deps.items()
        }
        queue = deque(fn for fn, deg in in_degree.items() if deg == 0)
        order: list[Callable[..., Awaitable[Any]]] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            # “Remove” edges from node → its dependents
            for succ, succ_deps in deps.items():
                if node in succ_deps:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        queue.append(succ)

        if len(order) != len(deps):
            raise RuntimeError("Cyclic dependency detected in workflow!")
        return order

    async def run(
        self,
        initial_inputs: Sequence[Awaitable[Any]],
    ) -> Tuple[Any, ...]:
        """
        :param initial_inputs: coroutines for any root funcs you’ve already called,
                               e.g. [create_person(name="Joe")].
        :returns: a tuple of results in the same order as end_goals.
        """
        # 1) Seed any pre‐computed inputs
        seeded: Dict[str, Any] = {}
        coros = list(initial_inputs)
        if coros:
            results = await asyncio.gather(*coros)
            for coro, res in zip(coros, results):
                # match by the function name of the coroutine object
                fn_name = coro.cr_code.co_name
                seeded[fn_name] = res

        # 2) Execute the DAG in topo order
        cache: Dict[Callable[..., Awaitable[Any]], Any] = {}
        for fn in self._topo:
            name = fn.__name__
            if name in seeded:
                cache[fn] = seeded[name]
                continue

            # collect args from cache based on Depends defaults
            sig = inspect.signature(fn)
            kwargs: Dict[str, Any] = {}
            for param in sig.parameters.values():
                default = param.default
                if hasattr(default, "dependency") and asyncio.iscoroutinefunction(default.dependency):
                    dep_fn = default.dependency
                    kwargs[param.name] = cache[dep_fn]
                elif default is inspect._empty:
                    raise RuntimeError(f"Missing value for required {param.name!r} in {fn.__name__}")
                else:
                    # literal/defaulted param
                    kwargs[param.name] = default

            # await the async function
            cache[fn] = await fn(**kwargs)

        # 3) Gather the end‐goal results in order
        return tuple(cache[fn] for fn in self.end_goals)
