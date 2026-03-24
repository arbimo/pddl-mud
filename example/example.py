# /// script
# requires-python = ">=3.10"
# dependencies = ["unified-planning==1.3.0", "up-aries==0.5", "pddl-mud"]
#
# [tool.uv.sources]
# pddl-mud = { path = "..", editable = true }
# ///
from unified_planning.engines.results import ValidationResultStatus
from unified_planning.shortcuts import PlanValidator

from pddl_mud import Pb, minimize


def accepts(xpb: Pb) -> bool:
    pb = xpb.pb
    plan = xpb.plan

    # Check that the plan is still valid with the default validator
    with PlanValidator(problem_kind=pb.kind) as validator:
        res = validator.validate(pb, plan)
        print("val:", res)
        if res.status == ValidationResultStatus.INVALID:
            return False

    # check that the plan is still invalid with `aries-val`
    with PlanValidator(name="aries-val") as validator:
        res = validator.validate(pb, plan)
        print("val (aries):", res)
        if res.status == ValidationResultStatus.VALID:
            return False

    return True


if __name__ == "__main__":
    # The woodworking problem requires the PDDL add-after-delete semantics which aries-val does not support
    # the following extract a minimal example to pin point the problem
    init = Pb.parse("woodworking/")
    min = minimize(init, accepts=accepts, max_iter=1000, max_stall=100)

    out_dir = "target/"
    print(f"\nWriting results to {out_dir}")
    min.write(out_dir)
