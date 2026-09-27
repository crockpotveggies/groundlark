# Shared hardware resources

- `elec/`: shared atomic part definitions, their footprints and symbols.
- `libraries/`: KiCad footprint libraries used by the native projects.
- `models/`: component and assembly models, including vendor attribution.
- `reference/`: component reference material.
- `vendor/`: preserved upstream hardware and licenses.
- `simulation/`: common and legacy cross-board supporting-circuit simulations.

Product circuits, placement and routed CAD live in their respective product
directories. Keep reusable resources here rather than copying them into each
product. The `elec/` and `libraries/` footprint copies serve different existing
atopile/KiCad consumers; maintain their agreement.

Shared authoring and validation tools remain in [../tools/](../tools/), and
their existing regression suite remains in [../tests/](../tests/). Product paths
are resolved through [project_paths.py](../tools/project_paths.py).
