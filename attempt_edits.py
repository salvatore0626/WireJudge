"""Persist editable attempt ranges without changing the replay."""
import json
from pathlib import Path
from engine import full_track,attempt_from_range

def automatic_id(attempt):
    return f'auto:{attempt.entity_id}:{attempt.anchor_time:.3f}'

class AttemptEdits:
    def __init__(self,path):
        self.path=Path(path)
        try:
            value=json.loads(self.path.read_text())
            self.rows=value if isinstance(value,list) else []
        except (OSError,ValueError):self.rows=[]
        self.warnings=[]

    def apply(self,automatic,tracks,carrier,settings):
        lookup={tr['id']:tr for tr in tracks};cache={};result=[];used=set();self.warnings=[]
        rows=[r for r in self.rows if isinstance(r,dict) and r.get('carrier')==carrier['id']]
        def rebuild(row):
            entity=row['entity']
            if entity not in cache:cache[entity]=full_track(lookup[entity],carrier,settings)
            return attempt_from_range(cache[entity],float(row['start']),float(row['end']),
                                      float(row['anchor']),row['id'],row.get('status','Edited attempt'))
        for a in automatic:
            a.edit_id=automatic_id(a)
            matches=[(i,r) for i,r in enumerate(rows) if not r.get('manual')
                     and r.get('entity')==a.entity_id and abs(r.get('anchor',-1e9)-a.anchor_time)<=10]
            if not matches:result.append(a);continue
            i,row=min(matches,key=lambda pair:abs(pair[1]['anchor']-a.anchor_time));used.add(i)
            if row.get('deleted'):continue
            try:result.append(rebuild(row))
            except (KeyError,ValueError,TypeError) as error:
                self.warnings.append(str(error));result.append(a)
        for i,row in enumerate(rows):
            if i in used or row.get('deleted'):continue
            try:result.append(rebuild(row))
            except (KeyError,ValueError,TypeError) as error:self.warnings.append(str(error))
        return sorted(result,key=lambda a:(a.player.casefold(),a.start))

    def save_player(self,carrier,player,working,automatic):
        def row(a,deleted=False):
            return dict(carrier=carrier,player=player,entity=a.entity_id,
                        id=a.edit_id or automatic_id(a),anchor=a.anchor_time,start=a.start,
                        end=a.end,status=a.status,manual=a.edit_id.startswith('manual:'),deleted=deleted)
        own=lambda r:isinstance(r,dict) and r.get('carrier')==carrier and r.get('player','').casefold()==player.casefold()
        saved=[r for r in self.rows if not own(r)]
        saved.extend(row(a) for a in working)
        deleted=[r for r in self.rows if own(r) and r.get('deleted')]
        for a in automatic:
            if a.player.casefold()!=player.casefold():continue
            present=any(not b.edit_id.startswith('manual:') and b.entity_id==a.entity_id
                        and abs(b.anchor_time-a.anchor_time)<=10 for b in working)
            if not present and not any(r.get('entity')==a.entity_id and abs(r.get('anchor',-1e9)-a.anchor_time)<=10 for r in deleted):
                deleted.append(row(a,True))
        # An active range restores a previously deleted auto attempt.
        deleted=[r for r in deleted if not any(not a.edit_id.startswith('manual:') and a.entity_id==r.get('entity')
                 and abs(a.anchor_time-r.get('anchor',-1e9))<=10 for a in working)]
        saved.extend(deleted)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(saved,indent=2,allow_nan=False));temporary.replace(self.path)
        self.rows=saved
