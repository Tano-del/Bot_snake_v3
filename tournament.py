
import itertools
import json
import os
import sys
from statistics import mean

import run_v3
from simulator import run_batch, simulate_match

OUT_DIR = 'variants'
os.makedirs(OUT_DIR, exist_ok=True)

GRID = {
    'APPLE_MULT': [5, 10, 20],
    'KILL_MULT': [5, 10, 20],
    'SPACE_KILL_FACTOR': [20, 50, 100],
    'TURTLE_THRESHOLD': [100, 200, 400],
}

def iter_variants(grid):
    keys = list(grid.keys())
    for values in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(run_v3.CONFIG)  
        for k, v in zip(keys, values):
            cfg[k] = v
        yield cfg

def evaluate_variant(variant_cfg, matches=20):
    baseline = dict(run_v3.CONFIG)

    stats = {'A_wins': 0, 'B_wins': 0, 'sum_score_a': 0, 'sum_score_b': 0}
    for i in range(matches):
        r = simulate_match(config_a=baseline, config_b=variant_cfg)
        if r['winner'] == 'A':
            stats['A_wins'] += 1
        else:
            stats['B_wins'] += 1
        stats['sum_score_a'] += r['score_a']
        stats['sum_score_b'] += r['score_b']
    return stats

def main(matches_per_variant=20, keep_top=10):
    results = []
    variants = list(iter_variants(GRID))
    total = len(variants)
    print(f"Running {total} variants, {matches_per_variant} matches each")
    for idx, var in enumerate(variants, 1):
        print(f"[{idx}/{total}] Evaluating variant: {var}")
        stats = evaluate_variant(var, matches=matches_per_variant)
        b_win_rate = stats['B_wins'] / matches_per_variant
        avg_score_b = stats['sum_score_b'] / matches_per_variant
        row = {'variant': var, 'B_win_rate': b_win_rate, 'avg_score_b': avg_score_b, 'raw': stats}
        results.append(row)
        with open(os.path.join(OUT_DIR, f'result_{idx}.json'), 'w') as f:
            json.dump(row, f)

    results.sort(key=lambda r: (r['B_win_rate'], r['avg_score_b']), reverse=True)
    csv_path = os.path.join(OUT_DIR, 'results.csv')
    with open(csv_path, 'w') as f:
        f.write('rank,B_win_rate,avg_score_b,variant\n')
        for rank, r in enumerate(results[:keep_top], 1):
            f.write(f"{rank},{r['B_win_rate']:.3f},{r['avg_score_b']:.2f},{json.dumps(r['variant'])}\n")

    for rank, r in enumerate(results[:keep_top], 1):
        path = os.path.join(OUT_DIR, f'variant_top_{rank}.json')
        with open(path, 'w') as f:
            json.dump({'rank': rank, 'metrics': {'B_win_rate': r['B_win_rate'], 'avg_score_b': r['avg_score_b']}, 'variant': r['variant']}, f, indent=2)

    print('Tournament complete. Top variants saved to', OUT_DIR)

if __name__ == '__main__':
    matches = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    main(matches, keep)
