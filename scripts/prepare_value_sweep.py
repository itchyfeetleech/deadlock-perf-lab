"""Prepare the community-requested numeric CVAR sweep; never launch the game."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from deadlock_perf_lab.planning import make_plan, verify_plan
from deadlock_perf_lab.profiles import add_profile, catalog
from deadlock_perf_lab.storage import LabError, digest, fingerprint, write_json
from deadlock_perf_lab.sweep import variants
from deadlock_perf_lab.workspace import load_workspace


def prepare(workspace: Path, matrix: Path, rounds: int = 3) -> Path:
    workspace = workspace.resolve()
    config = load_workspace(workspace)
    if config['scenario']['mode'] != 'replay':
        raise LabError('This sweep requires a replay scenario in lab.json.')
    base = Path(config['install']) / 'game/citadel/gameinfo.gi'
    with matrix.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    profiles = variants(base.read_text(), rows)
    available = catalog(workspace)
    base_hash = digest(base)
    # Reuse identical profiles on a future repeat; never replace existing ones.
    for profile in profiles:
        profile['base_sha256'] = base_hash
        existing = available.get(profile['id'])
        if existing and existing != profile:
            raise LabError(f"{profile['id']}: existing profile differs; choose new matrix IDs.")
    for profile in profiles:
        if profile['id'] not in available:
            add_profile(workspace, profile)
    session, plan = make_plan(workspace, [p['id'] for p in profiles], rounds, 134987,
                              experimental=True)
    # The user requested three controls total, one per repeat round. Keep the
    # seeded treatment order; move that round's control through the experiment.
    schedule = []
    for number in range(1, rounds + 1):
        order = [i['case'] for i in plan['schedule'] if i['round'] == number and i['case'] != 'baseline']
        position = round((number - 1) * len(order) / (rounds - 1)) if rounds > 1 else 0
        order.insert(position, 'baseline')
        start = len(schedule)
        schedule.extend({'index': start + offset + 1, 'round': number, 'case': case}
                        for offset, case in enumerate(order))
    plan['schedule'] = schedule
    plan['context']['scenario'].update(tick=134987, sample_s=10, warmup_s=10, settle_s=2, cooldown_s=0)
    plan['context_key'] = fingerprint(plan['context'])
    plan['baseline_policy'] = 'One baseline per round; descriptive averages, no bracketed verdict.'
    plan['value_sweep'] = {'matrix_sha256': digest(matrix), 'cvars': sorted({r['cvar'] for r in rows}),
                           'candidate_values': len(profiles), 'purpose': 'Independent numeric value screening'}
    plan.pop('plan_sha256')
    plan['plan_sha256'] = fingerprint(plan)
    verify_plan(plan)
    write_json(session / 'plan.json', plan)
    write_json(session / 'status.json', {'state': 'planned', 'completed': 0, 'total': len(schedule)})
    pointer = workspace / 'research/particle-values/session.txt'
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(session) + '\n')
    return session


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path('.lab'))
    parser.add_argument('--matrix', type=Path, default=Path('examples/particle-value-matrix.csv'))
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    print(prepare(args.workspace, args.matrix, args.rounds))
    print('Prepared only. The benchmark has NOT been launched.')
