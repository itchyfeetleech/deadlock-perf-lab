"""Export descriptive per-value averages without hiding incomplete captures."""
import argparse
import csv
from pathlib import Path
import statistics

from deadlock_perf_lab.storage import digest, read_json, LabError


def summarize(session: Path) -> Path:
    plan = read_json(session / 'plan.json')
    grouped = {case: [] for case in plan['profiles']}
    for path in sorted((session / 'runs').glob('*/result.json')):
        record = read_json(path)
        if record.get('status') != 'ok' or not record.get('metrics'):
            continue
        if (record['context_key'] != plan['context_key'] or record.get('synthetic')
                or digest(path.parent / record['raw_capture']) != record['capture_sha256']):
            raise LabError(f'Capture provenance does not match: {path}')
        grouped[record['case']].append(record)

    def mean(records, key):
        values = [r['metrics'][key] for r in records if r['metrics'].get(key) is not None]
        return statistics.fmean(values) if values else None

    baseline = mean(grouped['baseline'], 'avg_fps')
    rows = []
    for case, records in grouped.items():
        profile = plan['profiles'][case]
        fps = mean(records, 'avg_fps')
        rows.append({'case': case, 'cvar': profile.get('cvar', ''), 'value': profile.get('requested_value', ''),
                     'runs': len(records), 'planned_repeats': plan['rounds'], 'mean_avg_fps': fps,
                     'delta_vs_baseline_pct': (fps / baseline - 1) * 100 if fps and baseline else None,
                     'mean_1pct_low_fps': mean(records, 'low_1_fps'),
                     'mean_01pct_low_fps': mean(records, 'low_01_fps'),
                     'mean_p99_frame_ms': mean(records, 'p99_frame_ms'),
                     'quality_notes': ' | '.join(sorted({m for r in records for m in r.get('quality_blockers', [])}))})
    rows.sort(key=lambda r: (r['cvar'], float(r['value']) if r['value'] else 0))
    destination = session / 'report/value-sweep-averages.csv'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', nargs='?', type=Path)
    args = parser.parse_args()
    selected = args.session or Path(Path('.lab/research/particle-values/session.txt').read_text().strip())
    print(summarize(selected))
