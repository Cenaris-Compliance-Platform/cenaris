import re
import os
from pathlib import Path

p = Path('migrations/versions')
revisions = {}
for f in p.glob('*.py'):
    txt = f.read_text(encoding='utf-8')
    rev_m = re.search(r"^revision\s*=\s*'([0-9a-fA-F]+)'", txt, re.M)
    down_m = re.search(r"^down_revision\s*=\s*(.+)$", txt, re.M)
    rev = rev_m.group(1) if rev_m else None
    down = None
    if down_m:
        val = down_m.group(1).strip()
        # normalize None
        if val == 'None':
            down = None
        else:
            # evaluate tuples or strings safely
            # remove whitespace
            val = val.rstrip(',')
            try:
                # ast literal_eval
                import ast
                parsed = ast.literal_eval(val)
                if isinstance(parsed, tuple):
                    down = list(parsed)
                elif parsed is None:
                    down = None
                else:
                    down = [parsed]
            except Exception:
                down = [val.strip("()\'\" ")]
    revisions[rev] = down

all_revs = set(r for r in revisions.keys() if r)
referenced = set()
for k, v in revisions.items():
    if v:
        for x in v:
            if x:
                referenced.add(x)

heads = sorted(list(all_revs - referenced))
print('All revisions:')
for r in sorted(all_revs):
    print('  ', r)
print('\nReferenced (down_revision values):')
for r in sorted(referenced):
    print('  ', r)
print('\nComputed heads:')
for h in heads:
    print('  ', h)

# Also print merge revisions (those with tuple down_revision)
print('\nMerge revisions (down_revision tuples):')
for k, v in revisions.items():
    if v and len(v) > 1:
        print('  ', k, '->', v)
