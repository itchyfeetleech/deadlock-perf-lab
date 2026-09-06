"""Build the numeric-sweep community report from verified captures (requires matplotlib)."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
from html import escape
import json
import math
import os
from pathlib import Path
import statistics as stats

from deadlock_perf_lab.capture import read_mangohud
from deadlock_perf_lab.planning import verify_plan
from deadlock_perf_lab.storage import LabError, read_json

ORDER = [
    ('r_size_cull_threshold', 'Object size culling'),
    ('lb_sun_csm_size_cull_threshold_texels', 'Sun shadow size culling'),
    ('r_particle_max_size_cull', 'Particle size culling'),
    ('cl_particle_max_count', 'Particle count'),
    ('cl_particle_fallback_base', 'Particle fallback base'),
    ('cl_particle_fallback_multiplier', 'Particle fallback multiplier'),
    ('cl_particle_sim_fallback_threshold_ms', 'Simulation fallback threshold'),
    ('cl_particle_sim_fallback_base_multiplier', 'Simulation fallback multiplier'),
]
METRICS = ['avg_fps', 'low_1_fps', 'low_01_fps', 'p99_frame_ms']


def collect(session: Path) -> dict:
    plan = read_json(session / 'plan.json')
    verify_plan(plan)
    schedule = {item['index']: item for item in plan['schedule']}
    records = []
    for path in sorted((session / 'runs').glob('*/result.json')):
        r = read_json(path)
        if r['status'] != 'ok' or r.get('synthetic'):
            raise LabError(f'Incomplete or synthetic capture: {path}')
        item = schedule.get(r['index'])
        profile = plan['profiles'][r['case']]
        if (not item or any(r[k] != item[k] for k in ('case', 'round'))
                or r['context_key'] != plan['context_key'] or r['profile_sha256'] != profile['sha256']):
            raise LabError(f'Capture does not match the frozen plan: {path}')
        metadata = r['capture_metadata']
        capture = read_mangohud(path.parent / r['raw_capture'], start_s=metadata['start_s'],
                               duration_s=metadata['requested_duration_s'], interval_ms=0)
        measured = capture.metrics(1000 / plan['context']['scenario']['budget_fps'])
        if capture.metadata['sha256'] != r['capture_sha256']:
            raise LabError(f'Raw capture hash mismatch: {path}')
        if any(not math.isclose(measured[k], r['metrics'][k], rel_tol=1e-10) for k in METRICS):
            raise LabError(f'Metric recomputation mismatch: {path}')
        records.append({k: r[k] for k in ('index', 'round', 'case', 'started_at', 'finished_at',
                                        'capture_sha256', 'profile_sha256', 'quality_blockers', 'warnings')} | {
            'cvar': profile.get('cvar', ''), 'value': profile.get('requested_value', ''),
            **{k: measured[k] for k in METRICS}})
    if Counter(r['index'] for r in records) != Counter(schedule.keys()):
        raise LabError('Missing or duplicated scheduled captures.')
    if len(records) != 99 or Counter(r['case'] for r in records) != Counter({k: 3 for k in plan['profiles']}):
        raise LabError('This report expects 32 values with three repeats and three baselines.')
    rows = []
    for case, profile in plan['profiles'].items():
        runs = [r for r in records if r['case'] == case]
        fps = [r['avg_fps'] for r in runs]
        rows.append({'case': case, 'cvar': profile.get('cvar', ''),
                     'value': profile.get('requested_value', ''), 'runs': runs,
                     'mean': {k: stats.fmean(r[k] for r in runs) for k in METRICS},
                     'fps_cv_pct': stats.stdev(fps) / stats.fmean(fps) * 100})
    baseline = next(r for r in rows if r['case'] == 'baseline')
    for row in rows:
        row['delta_pct'] = (row['mean']['avg_fps'] / baseline['mean']['avg_fps'] - 1) * 100
    return {'session': session.name, 'context_key': plan['context_key'], 'plan_sha256': plan['plan_sha256'],
            'build_id': plan['context']['game']['build_id'], 'baseline': baseline,
            'rows': rows, 'records': records}


def plot(data: dict, output: Path) -> None:
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/deadlock-report-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'text.color': '#eef3fa', 'axes.labelcolor': '#b7c6d8',
                         'xtick.color': '#b7c6d8', 'ytick.color': '#e4edf7', 'font.size': 11,
                         'svg.fonttype': 'none'})
    fig, axes = plt.subplots(4, 2, figsize=(16, 16), facecolor='#0c1420')
    fig.subplots_adjust(top=.83, bottom=.115, left=.075, right=.935, hspace=.85, wspace=.28)
    base = data['baseline']['mean']['avg_fps']
    span = [(r['avg_fps'] / base - 1) * 100 for r in data['baseline']['runs']]
    for ax, (cvar, title) in zip(axes.flat, ORDER):
        rows = sorted((r for r in data['rows'] if r['cvar'] == cvar), key=lambda r: float(r['value']))
        ax.set_facecolor('#101e2e')
        ax.axvspan(min(span), max(span), color='#8091ad', alpha=.18, zorder=0)
        ax.axvline(0, color='#97abc6', lw=.8)
        ax.set_xlim(-13, 12)
        ax.set_xticks([-10, -5, 0, 5, 10])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:+g}%' if v else '0%'))
        ax.set_yticks(range(4), [r['value'] for r in rows])
        ax.set_ylim(3.65, -.65)
        ax.set_title(title, loc='left', fontsize=14, fontweight='bold', pad=30)
        ax.text(0, 1.06, cvar, fontsize=9, color='#a8bad1', transform=ax.transAxes)
        ax.grid(axis='x', color='#344358', alpha=.3)
        ax.set_axisbelow(True)
        for y, row in enumerate(rows):
            delta = row['delta_pct']
            color = '#61dbb2' if delta >= 0 else '#ff9b8a'
            ax.barh(y, delta, height=.5, color=color, alpha=.72)
            points = [(r['avg_fps'] / base - 1) * 100 for r in row['runs']]
            ax.scatter(points, [y - .13, y, y + .13], s=18, facecolors='#f4f7ff', edgecolors='#0c1420', lw=.5, zorder=3)
            x = max(delta, max(points)) + .35 if delta >= 0 else min(delta, min(points)) - .35
            align = 'left' if delta >= 0 else 'right'
            if delta < -7:
                x, align = -7, 'left'
            ax.text(x, y, f'{delta:+.2f}%', va='center', ha=align, fontsize=10, fontweight='bold')
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0, pad=7)
    fig.text(.065, .961, 'DEADLOCK / NUMERIC CVAR SWEEP', fontsize=12, color='#61dbb2', weight='bold')
    fig.text(.065, .928, 'Which values moved performance?', fontsize=29, weight='bold')
    fig.text(.065, .899, f'8 commands · 32 tested values · 3 captures per value · baseline {base:.2f} FPS', fontsize=14, color='#bbc9db')
    fig.text(.065, .073, 'Average FPS change vs. baseline mean  •  higher is better', fontsize=14, weight='bold')
    fig.text(.065, .050, 'Bars: three-run means. Dots: individual captures. Shaded band: observed baseline range, not a confidence interval.', fontsize=10, color='#b7c6d8')
    fig.text(.065, .032, '9800X3D / RX 9070 · Linux/Proton · 1280×720 · tick 134987 · 10-second samples · September 6, 2026', fontsize=10, color='#b7c6d8')
    fig.text(.065, .015, 'Exploratory, one scene. Requested CVAR values lack live readback; camera and visual effects require review. No significance claim.', fontsize=9, color='#b7c6d8')
    for suffix in ('png', 'svg'):
        fig.savefig(output / f'particle-values-summary.{suffix}', dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def publish(session: Path, root: Path) -> None:
    data = collect(session)
    output = root / 'results'
    output.mkdir(exist_ok=True)
    (output / 'particle-values-data.json').write_text(json.dumps(data, indent=2) + '\n')
    columns = ['case', 'cvar', 'value', 'runs', *METRICS, 'delta_avg_fps_pct', 'fps_cv_pct', 'round_1_fps',
               'round_2_fps', 'round_3_fps', 'quality_notes']
    with (output / 'particle-values-averages.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        for row in data['rows']:
            writer.writerow({k: row[k] for k in ('case', 'cvar', 'value', 'fps_cv_pct')} | {
                'runs': len(row['runs']), **row['mean'], 'delta_avg_fps_pct': row['delta_pct'],
                **{f"round_{r['round']}_fps": r['avg_fps'] for r in row['runs']},
                'quality_notes': ' | '.join(sorted({n for r in row['runs'] for n in r['quality_blockers']}))})
    b = data['baseline']
    def find(case):
        return next(r for r in data['rows'] if r['case'] == case)
    best = find('pv8-object-size-24')
    particle = [r['delta_pct'] for r in data['rows'] if r['cvar'] == 'r_particle_max_size_cull']
    fallback = [r['delta_pct'] for r in data['rows'] if 'fallback' in r['cvar']]
    baseline_runs = ' → '.join(f"{r['avg_fps']:.2f}" for r in b['runs'])
    baseline_span = (max(r['avg_fps'] for r in b['runs']) - min(r['avg_fps'] for r in b['runs'])) / b['mean']['avg_fps'] * 100
    sections = []
    for cvar, title in ORDER:
        rows = sorted((r for r in data['rows'] if r['cvar'] == cvar), key=lambda r: float(r['value']))
        body = ''
        for r in rows:
            m = r['mean']
            sign = 'pos' if r['delta_pct'] >= 0 else 'neg'
            points = ' · '.join(f"{v['avg_fps']:.1f}" for v in r['runs'])
            body += (f'<tr><th scope="row">{escape(r["value"])}</th><td>{m["avg_fps"]:.2f}</td>'
                     f'<td class="{sign}">{r["delta_pct"]:+.2f}%</td><td>{m["low_1_fps"]:.2f}</td>'
                     f'<td>{m["low_01_fps"]:.2f}</td><td>{m["p99_frame_ms"]:.3f}</td>'
                     f'<td>{points}</td><td>{r["fps_cv_pct"]:.2f}%</td></tr>')
        sections.append(f'<section class="command" id="{cvar}"><h3>{title}</h3><code>{cvar}</code>'
                        '<div class="scroll"><table><thead><tr><th>Value</th><th>Avg FPS</th><th>Δ FPS</th>'
                        '<th>1% low</th><th>0.1% low</th><th>P99 ms ↓</th><th>FPS · rounds 1 / 2 / 3</th><th>FPS CV</th>'
                        f'</tr></thead><tbody>{body}</tbody></table></div></section>')
    notes = f'''<p><code>r_size_cull_threshold 2.4</code> had the highest observed mean: <strong>{best['mean']['avg_fps']:.2f} FPS ({best['delta_pct']:+.2f}%)</strong>, with {best['mean']['low_1_fps']:.2f} FPS at the 1% low. The four tested values showed increasing average FPS. This is the top tested value, not an established optimum; visual effects still need checking.</p>
<p><code>cl_particle_max_count</code> at 250, 500 and 1000 averaged roughly 10% below baseline. At 2000 the difference was {find('pv8-particle-count-2000')['delta_pct']:+.2f}%. The lower tested counts produced the largest observed losses.</p>
<p>All four <code>r_particle_max_size_cull</code> candidates averaged below baseline ({min(particle):+.2f}% to {max(particle):+.2f}%). Fallback candidates ranged from {min(fallback):+.2f}% to {max(fallback):+.2f}%, with no clear value trend. <code>lb_sun_csm_size_cull_threshold_texels 60</code> averaged {find('pv8-shadow-size-60')['delta_pct']:+.2f}%.</p>
<p>Baseline captures were <strong>{baseline_runs} FPS</strong>, a {baseline_span:.2f}% range relative to their mean. Small differences are therefore hard to distinguish from run variation and drift. These observations do not isolate CPU savings from GPU changes.</p>'''
    options = ''.join(f'<option value="{cvar}">{title}</option>' for cvar, title in ORDER)
    template = (Path(__file__).with_name('value_sweep_report.html')).read_text()
    values = {'BASE_FPS': f"{b['mean']['avg_fps']:.2f}", 'BASE_LOW': f"{b['mean']['low_1_fps']:.2f}",
              'BASE_LOW01': f"{b['mean']['low_01_fps']:.2f}", 'BASE_P99': f"{b['mean']['p99_frame_ms']:.3f}",
              'NOTES': notes, 'SECTIONS': '\n'.join(sections), 'OPTIONS': options,
              'CONTEXT': data['context_key'], 'SESSION': data['session'], 'BUILD': data['build_id']}
    for key, value in values.items():
        template = template.replace('{{' + key + '}}', value)
    (root / 'particle-values.html').write_text(template)
    start = min(datetime.fromisoformat(r['started_at']) for r in data['records'])
    end = max(datetime.fromisoformat(r['finished_at']) for r in data['records'])
    (output / 'particle-values-provenance.md').write_text(f'''# Numeric sweep — September 6, 2026

[Report](https://itchyfeetleech.github.io/deadlock-perf-lab/particle-values.html) · [CSV](particle-values-averages.csv) · [Full per-run metrics and hashes](particle-values-data.json) · [PNG](particle-values-summary.png) · [SVG](particle-values-summary.svg)

Session `{data['session']}` completed all 99 planned captures. All capture hashes, profile hashes, context keys, schedule indices and repeats were checked. Average FPS, 1% low, 0.1% low and P99 frame time were recomputed from each raw capture and matched the saved metrics. All 99 captures are included exactly once. Elapsed time: {(end-start).total_seconds()/60:.1f} minutes.

Context SHA-256: `{data['context_key']}`. Plan SHA-256: `{data['plan_sha256']}`. Game build: `{data['build_id']}`.

Each of 32 variants changes one CVAR and has three captures. Three baseline captures occur at indices 1, 50 and 99. Means weight captures equally. FPS difference is 100 × (variant mean / baseline mean − 1). CV is sample standard deviation / mean × 100. P99 is shown in milliseconds; lower is better. The baseline is the original installed configuration; default values for hidden CVARs are not live-verified. No old-session captures are mixed into these results.

The run deliberately uses one baseline per round. The native report's paired/bracketed verdict is not applicable to this schedule; this publication uses descriptive means. Three repeats do not establish significance. All 96 treatment captures lack individual CVAR readback, and all 99 flag camera/progression review. The public JSON and CSV retain those quality notes. FPS does not isolate CPU time or establish acceptable visual quality.

Reproduce with `PYTHONPATH=src python scripts/publish_value_sweep.py SESSION`, with matplotlib installed. The generator validates the source and writes this report, the webpage, data exports and both plot formats.
''')
    plot(data, output)
    print(f'Published artifacts built: {len(data["records"])} verified captures, 32 values, 8 CVARs.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    publish(args.session, args.root)
