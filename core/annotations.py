"""User-entered wire annotations, keyed by replay content and closest-pass time."""
import hashlib
import json
from pathlib import Path

WIRE_OPTIONS = ('', 'Bolter', '1', '2', '3', '4')

def replay_digest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

class Annotations:
    def __init__(self, path):
        self.path = Path(path)
        try:
            rows = json.loads(self.path.read_text())
            self.rows = [r for r in rows if isinstance(r, dict)
                         and r.get('wire') in WIRE_OPTIONS
                         and isinstance(r.get('carrier'), int)
                         and isinstance(r.get('entity'), int)
                         and isinstance(r.get('time'), (float, int))]
        except (OSError, ValueError, TypeError):
            self.rows = []

    def find(self, carrier, attempt):
        if attempt.edit_id.startswith('manual:'):
            return next((r for r in self.rows if r['carrier']==carrier and r.get('edit_id')==attempt.edit_id),None)
        matches = [r for r in self.rows if r['carrier'] == carrier
                   and r['entity'] == attempt.entity_id
                   and not r.get('edit_id','').startswith('manual:')
                   and abs(r['time'] - attempt.anchor_time) <= 10]
        return min(matches, key=lambda r: abs(r['time'] - attempt.anchor_time)) if matches else None

    def get(self, carrier, attempt):
        row = self.find(carrier, attempt)
        return row['wire'] if row else ''

    def set(self, carrier, attempt, wire):
        if wire not in WIRE_OPTIONS:
            raise ValueError('Choose an empty wire, Bolter, or wire 1, 2, 3, or 4.')
        rows = [dict(r) for r in self.rows]
        previous = self.find(carrier, attempt)
        if previous:
            rows[self.rows.index(previous)]['wire'] = wire
        else:
            rows.append(dict(carrier=carrier, entity=attempt.entity_id,
                             time=attempt.anchor_time, wire=wire,edit_id=attempt.edit_id))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2, allow_nan=False))
        temporary.replace(self.path)
        self.rows = rows
