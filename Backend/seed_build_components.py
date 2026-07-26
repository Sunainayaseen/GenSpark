"""
Attach components to the prebuilt PcBuild rows that exist in the DB.

The 3 seeded gaming builds (Performance / Balanced / Budget) had ZERO
build_components, so their detail pages showed no parts. This wires a coherent
7-part list (CPU, GPU, Motherboard, RAM, Storage, PSU, Case) to each build by
matching real catalog components by name, then recomputes total_price from the
attached parts.

Idempotent: re-running won't duplicate links (skips parts already attached).

Run from the Dashboard/ folder:
    python seed_build_components.py
"""
import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from app import create_app, db  # noqa: E402
from app.models import PcBuild, Component, BuildComponent  # noqa: E402

# build_type -> ordered list of exact component names (must exist in `components`).
BUILD_PARTS = {
    'Performance': [
        'AMD Ryzen 7 7700X 8-Core Processor',
        'NVIDIA GeForce RTX 4070 12GB',
        'MSI PRO B650-P WiFi (ATX)',
        'Corsair Vengeance 32GB DDR5 6000MHz',
        'Samsung 980 1TB NVMe SSD',
        'Corsair RM750e 750W 80+ Gold',
        'NZXT H5 Flow Mid-Tower Airflow Case',
    ],
    'Balanced': [
        'AMD Ryzen 5 7600 6-Core Processor',
        'NVIDIA GeForce RTX 4060 Ti 16GB',
        'MSI PRO B650M-A WiFi (mATX)',
        'Corsair Vengeance 16GB DDR5 5600MHz',
        'Samsung 980 1TB NVMe SSD',
        'Cooler Master MWE 650W 80+ Gold',
        'Montech AIR 903 Mid-Tower Case',
    ],
    'Budget': [
        'AMD Ryzen 5 5600G 6-Core Processor',
        'NVIDIA GeForce RTX 4060 8GB',
        'Gigabyte A520M DS3H (mATX)',
        'Corsair Vengeance LPX 16GB DDR4 3200MHz',
        'Kingston NV2 512GB NVMe SSD',
        'Cooler Master MWE 450W 80+ Bronze',
        'Cooler Master MasterBox Q300L Compact mATX Case',
    ],
}


def find_component(name):
    comp = Component.query.filter_by(name=name).first()
    if not comp:
        # Fall back to a loose match so a slightly different catalog name still links.
        comp = Component.query.filter(Component.name.like(f'%{name.split("(")[0].strip()}%')).first()
    return comp


def match_build(build):
    """Pick the parts list for a build by its type, else by a keyword in its name."""
    if build.build_type in BUILD_PARTS:
        return BUILD_PARTS[build.build_type]
    name = (build.name or '').lower()
    for key in BUILD_PARTS:
        if key.lower() in name:
            return BUILD_PARTS[key]
    return None


def main():
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        builds = PcBuild.query.all()
        if not builds:
            print('No PcBuild rows found. Nothing to attach.')
            return

        total_links = 0
        for build in builds:
            parts = match_build(build)
            if not parts:
                print(f'  build id={build.id} ({build.name!r}) — no matching parts list, skipped')
                continue

            attached, missing, total_price = 0, [], 0
            for part_name in parts:
                comp = find_component(part_name)
                if not comp:
                    missing.append(part_name)
                    continue
                total_price += float(comp.price or 0)
                existing = BuildComponent.query.filter_by(
                    pc_build_id=build.id, component_id=comp.id
                ).first()
                if not existing:
                    db.session.add(BuildComponent(pc_build_id=build.id, component_id=comp.id, quantity=1))
                    attached += 1
                    total_links += 1

            # Reflect the real parts cost on the build.
            if total_price > 0:
                build.total_price = total_price

            label = build.name.encode('ascii', 'replace').decode()
            print(f'  build id={build.id} ({label}): +{attached} parts, total Rs.{total_price:.0f}'
                  + (f'  MISSING: {missing}' if missing else ''))

        db.session.commit()
        print(f'\nDone. New build-component links: {total_links}.')


if __name__ == '__main__':
    main()
