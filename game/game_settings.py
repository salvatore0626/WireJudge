"""Load game balance once per application launch."""
import math
from .game_config import SCHEMA, STATS_PATH, load_stats

STATS = load_stats()


def aircraft_specs(enemy=False):
    result={}
    bases=STATS['friendly_aircraft']
    kinds=dict.fromkeys([*bases,*STATS['enemy_aircraft']]) if enemy else bases
    for kind in kinds:
        base=bases.get(kind,{})
        s={**base, **(STATS['enemy_aircraft'].get(kind,{}) if enemy else {})}
        result[kind]={**s, 'speed':s['speed_knots'], 'fuel':math.inf if s.get('unlimited_fuel') else s['fuel_capacity'],
                      'burn':0 if s.get('unlimited_fuel') else s['fuel_burn_units_per_second'], 'bays':s['bomb_bays']}
    return result


def crew_repair_seconds(level):return STATS['ground_crew']['repair_seconds_per_hp'][level-1]
def crew_weapon_seconds(level):return STATS['ground_crew']['rearm_seconds_per_weapon'][level-1]
def crew_count(level):return STATS['ground_crew']['crews_by_level'][level-1]


def loadout_label(value,hardpoint_counts=None):
    if value == 'Empty':return value
    for kind in ('AIM-120','AIM-9','AGM-88','Sidearm'):
        if kind in value:
            name='AIM-120C' if kind=='AIM-120' else kind
            count=(hardpoint_counts or {}).get(kind,STATS['missiles'][kind]['hardpoint_count'])
            return f'{count}× {name}'
    for weight, spec in STATS['bombs'].items():
        if weight in value.replace(',',''):
            return f"{spec['bay_count']}× {int(weight):,} lb Bomb"
    return value


def ground_stats(key,enemy=False):
    return STATS['enemy_ground_units' if enemy else 'ground_units'][key]
