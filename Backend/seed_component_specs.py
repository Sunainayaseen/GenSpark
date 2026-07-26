"""
One-time seeder: populate Component.specs with structured hardware specs.

The compatibility engine validates builds from STRUCTURED specs (socket, DDR,
wattage, clearances, …). The catalog ships those columns empty, so this script
derives them deterministically from each component's name via
`app.services.hardware_specs.derive_specs` and persists the result.

Run from the Dashboard directory:
    .venv\\Scripts\\python.exe seed_component_specs.py            # write specs
    .venv\\Scripts\\python.exe seed_component_specs.py --dry-run  # preview only
    .venv\\Scripts\\python.exe seed_component_specs.py --force    # overwrite existing

Idempotent: re-running re-derives and updates. Without --force it skips parts
that already have a structured `specs.kind`, so manual spec edits are preserved.
"""
import os
import sys
import json

os.environ.setdefault('USE_SQLITE', '0')

from app import create_app, db                      # noqa: E402
from app.models import Component                    # noqa: E402
from app.services.hardware_specs import derive_specs, classify  # noqa: E402

DRY = '--dry-run' in sys.argv
FORCE = '--force' in sys.argv


def main():
    app = create_app()
    with app.app_context():
        comps = Component.query.order_by(Component.id).all()
        written = skipped = low_conf = 0
        by_kind = {}
        for c in comps:
            existing = c.specs if isinstance(c.specs, dict) else None
            if existing and existing.get('kind') and not FORCE:
                skipped += 1
                continue
            specs = derive_specs(c.name or '')
            kind = specs.get('kind', 'other')
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if not specs.get('confident', False):
                low_conf += 1
            if DRY:
                print(f'[{c.id:>4}] {kind:11} {("LOW " if not specs.get("confident") else "    ")}'
                      f'{c.name[:42]:42} {json.dumps({k: v for k, v in specs.items() if k != "kind"})}')
            else:
                c.specs = specs
            written += 1
        if not DRY:
            db.session.commit()
        print('\n--- summary ---')
        print('by kind:', dict(sorted(by_kind.items())))
        print(f'{"would write" if DRY else "wrote"}: {written}   skipped(existing): {skipped}   '
              f'low-confidence: {low_conf}')
        if low_conf:
            print('NOTE: low-confidence parts are OEM/ambiguous names; the validator '
                  'will `skip` (not assert) checks it cannot prove for them.')


if __name__ == '__main__':
    main()
