# PDDL Minimal Unsatisfiable Domain (pddl-mud)


Provides a utility script to minimize a PDDL domain and problem (and witness plan), so that it still satisfies some properties.

The script reads from an input directory with the following files (the name of the directory should be specified).

```
data/
  domain.pddl
  problem.pddl
  plan
```

The main function accepts:
 - an input dir (from which to read the PDDL problem)
 - an output dir (where results will be written)
 - an `accepts` function that given a (domain, problem, plan) returns true if those fulfill the desired properties

The main function will then attempt to remove elements from the input so that the resulting problem/plan still satisfies the properties.

The typical use case for this is to simplify a problem where a planner incorrectly output `unsatisfiable` while we have a valid witness plan.
For this use case, the accept function should be set so that it returns true iff both:
 - the plan is a valid solution for this problem
 - the tested planner return `unsatisfiable`

 The results will be domain/problem/plan with as little elements as possible so that the problem remains satisfiable (the witness plan is valid) but the planner still incorrectly derive UNSAT.

## Example 

The [`example.py`](example/example.py) file contains an example for minimizing the `woodworking` domain that is not supported `aries-val` (due to lack of support for add-after-delete).
It can be run with:

```sh
cd example/ && uv run --no-project --script  example.py
```

## Disclaimer

This is a not a production ready project and has very narrow support in general. It may fail on input more complex than the few that I have actually tested.
It also relies on undocumented aspects of `unified-planning` and may break with updates.
