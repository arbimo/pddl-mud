import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, TypeVar

import unified_planning as up
from unified_planning.engines import PlanGenerationResultStatus, ValidationResultStatus
from unified_planning.io import PDDLReader, PDDLWriter
from unified_planning.model import FNode
from unified_planning.model.problem import Problem
from unified_planning.plans import ActionInstance, Plan, SequentialPlan
from unified_planning.shortcuts import And, OneshotPlanner, PlanValidator

T = TypeVar("T")


def select(lst: List[T]) -> T | None:
    """Selects an arbitrary element from a list"""
    if len(lst) == 0:
        return None
    return lst[random.randrange(len(lst))]


def remove(lst: List[T]) -> T | None:
    """Removes an arbitrary element from a list.
    If the elements of the list are `And` expression, it will consider removing a conjunct from the and expression"""
    if len(lst) == 0:
        return None
    elem = lst.pop(random.randrange(len(lst)))
    if isinstance(elem, FNode) and elem.is_and():
        args = [a for a in elem.args]  # copy args
        if len(args) <= 1:
            # conjuncts with 0 or 1 element, consider its removal entirely
            return elem
        rm = remove(args)
        assert rm is not None
        lst.append(elem.environment.expression_manager.And(*args))
        return rm
    return elem


@dataclass
class Pb:
    """Problem to minimize (with a witness plan)"""

    pb: Problem
    plan: Plan

    def clone(self) -> Pb:
        pb = self.pb.clone()
        plan = self.plan.replace_action_instances(
            lambda a: ActionInstance(pb.action(a.action.name), a.actual_parameters)
        )
        return Pb(pb, plan)

    @staticmethod
    def parse(dir: str | Path) -> Pb:
        if isinstance(dir, str):
            dir = Path(dir)
        reader = PDDLReader()
        pb = reader.parse_problem(dir / "domain.pddl", dir / "problem.pddl")
        plan = reader.parse_plan(pb, dir / "plan")
        return Pb(pb, plan)

    def write(self, dir: str | Path):
        if isinstance(dir, str):
            dir = Path(dir)
        dir.mkdir(exist_ok=True)
        writer = PDDLWriter(self.pb)
        writer.write_domain(dir / "domain.pddl")
        writer.write_problem(dir / "problem.pddl")
        writer.write_plan(self.plan, dir / "plan")


def minimize(
    init: Pb,
    accepts: Callable[[Pb], bool],
    max_iter=1000,
    max_stall=30,
) -> Pb:
    pb = init.pb
    plan = init.plan

    print(pb)
    print(plan)

    assert accepts(init), "The initial problem does not pass the requirements..."

    failures_since_last_success = 0

    cur = init.clone()
    for i in range(max_iter):
        print()
        simplifier: Callable[[Pb], Pb|None] | None = select(SIMPLIFICATIONS)
        assert simplifier is not None, "No simpliciations available"
        candidate = simplifier(cur.clone())
        if candidate is None:
            failures_since_last_success += 1
        elif accepts(candidate):
            print("==> accept")
            cur = candidate
            failures_since_last_success = 0
        else:
            print("==> denied")
            failures_since_last_success += 1
        if failures_since_last_success > max_stall:
            break

    print("Finished simplifications (max-iter or max-stalled iters reached)")

    assert accepts(cur), "Simplified model is not accepted..."

    print("\n\n\n===== Simplified model =======\n")
    print(cur.pb)
    print("\n===== Simplified plan =======\n")
    print(cur.plan)

    return cur


def action_removal(pb: Pb) -> Pb | None:
    act = remove(pb.pb.actions)
    if act is None:
        return None
    print("Removing action:", act.name)
    return pb


def precond_removal(pb: Pb) -> Pb | None:
    act: Action = select(pb.pb.actions)
    if act is None:
        return None
    pre = remove(act.preconditions)
    if pre is None:
        return None
    print(f"removed precond {pre} from {act.name}")
    # print(pb)
    return pb


def eff_removal(pb: Pb) -> Pb | None:
    act: Action = select(pb.pb.actions)
    if act is None:
        return None
    eff = remove(act.effects)
    if eff is None:
        return None
    print(f"removed effect from {act.name}")
    return pb


def init_removal(pb: Pb) -> Pb | None:
    initialized_fluents = list(pb.pb.explicit_initial_values.keys())
    f = select(initialized_fluents)
    if f is None:
        return None
    print(f"Removing initial value for: {f}")
    del pb.pb.explicit_initial_values[f]
    return pb


def goal_removal(pb: Pb) -> Pb | None:
    g = remove(pb.pb.goals)
    if g is None:
        return None
    print(f"Removing goal: {g}")
    return pb


def plan_operation_removal(pb: Pb) -> Pb | None:
    op = remove(pb.plan.actions)
    if op is None:
        return None
    print(f"Removing plan operation: {op}")
    return pb


def metric_removal(pb: Pb) -> Pb | None:
    if len(pb.pb.quality_metrics) == 0:
        return None
    pb.pb.clear_quality_metrics()
    return pb


def fluent_removal(pb: Pb) -> Pb | None:
    f = remove(pb.pb.fluents)
    if f is None:
        return None
    print(f"Removfing fluent {f}")
    # in addition, we need to clean its usage in defaults and initial values
    if f in pb.pb.fluents_defaults:
        del pb.pb.fluents_defaults[f]
    to_rm = [x for x in pb.pb.explicit_initial_values.keys() if x.fluent() == f]
    for x in to_rm:
        del pb.pb.explicit_initial_values[x]
    return pb


def object_removal(pb: Pb) -> Pb | None:
    o = remove(pb.pb.all_objects)
    if o is None:
        return None
    # the action parameters may refer to objects
    # we stop if this is the case (otherwise it may crash when parsing the plan from a file)
    for a in pb.plan.actions:
        for param in a.actual_parameters:
            if param.object() == o:
                return None
    return pb


SIMPLIFICATIONS: List[Callable[[Pb], Pb|None]] = [
    action_removal,
    precond_removal,
    eff_removal,
    init_removal,
    goal_removal,
    plan_operation_removal,
    metric_removal,
    fluent_removal,
    object_removal,
]



if __name__ == "__main__":

    def accepts(xpb: Pb) -> bool:
        pb = xpb.pb
        plan = xpb.plan

        with PlanValidator(problem_kind=pb.kind) as validator:
            res = validator.validate(pb, plan)
            if res.status == ValidationResultStatus.INVALID:
                return False

        params = {
            "min-depth": 2,
            "max-depth": 2,
        }
        with OneshotPlanner(name="aries", params=params) as planner:
            res = planner.solve(pb)
            if res.status != PlanGenerationResultStatus.UNSOLVABLE_INCOMPLETELY:
                return False

        return True

    init = Pb.parse("target/")
    min = minimize(init, accepts=accepts, max_iter=200, max_stall=100)

    out_dir = Path("target2/")
    print(f"\nWriting results to {out_dir}")
    min.write(out_dir)
