# Planning upgrade waves

Describe the upgrade jobs you intend to ship. Each package has a stable ID, current version, target version and an optional depends_on list of other upgrade jobs in the inventory. Omit external dependencies that are outside the rollout. Versions are opaque identifiers, so the planner also works with internal release numbers.

The planner finds strongly connected components. A cycle becomes one coordinated unit and cannot be partially approved. It then schedules available units in dependency order, taking at most parallelism units per wave and using stable names to break ties. Dependencies marked ready in a wave become available to dependents in the next wave. A large cycle counts as one unit.

Select units for rollout. The exporter refuses selections with missing prerequisites and produces rollout-waves.json with package versions and group boundaries. rollback-order.json lists original versions in reverse wave order for operator review. Rollback feasibility, version constraints, migrations and compatibility require testing in the actual environment.
