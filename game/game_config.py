"""Shared game configuration schema and validation; safe to import without loading a file."""
import json
import sys
from copy import deepcopy
import math
from pathlib import Path

# PyInstaller's __file__ points into the extracted bundle. Prefer an editable
# config in its game folder (or the legacy EXE folder) when present;
# otherwise use the bundled default.
STATS_PATH = Path(__file__).resolve().with_name('game_stats.json')
if getattr(sys,'frozen',False):
    _install_dir=Path(sys.executable).resolve().parent
    for _external_stats in (_install_dir/'game'/'game_stats.json',_install_dir/'game_stats.json'):
        if _external_stats.is_file():
            STATS_PATH=_external_stats
            break

# Shape and types only: balance values live exclusively in the JSON.
SCHEMA = {'friendly_aircraft': {'RQ-9B': {'health': 'positive',
                                 'speed_knots': 'positive',
                                 'fuel_capacity': 'number',
                                 'fuel_burn_units_per_second': 'number',
                                 'hardpoints': 'integer',
                                 'bomb_bays': 'integer',
                                 'cms': 'integer',
                                 'price': 'number',
                                 'visual_range_nm': 'number',
                                 'radar_range_nm': 'number',
                                 'radar_angle_degrees': 'number',
                                 'afterburner': 'boolean',
                                 'can_refuel': 'boolean'},
                       'Suicide Drone': {'health': 'positive',
                                 'speed_knots': 'positive',
                                 'fuel_capacity': 'number',
                                 'fuel_burn_units_per_second': 'number',
                                 'hardpoints': 'integer',
                                 'bomb_bays': 'integer',
                                 'cms': 'integer',
                                 'price': 'number',
                                 'visual_range_nm': 'number',
                                 'radar_range_nm': 'number',
                                 'radar_angle_degrees': 'number',
                                 'afterburner': 'boolean',
                                 'can_refuel': 'boolean'},
                       'Fighter': {'health': 'positive',
                                   'speed_knots': 'positive',
                                   'fuel_capacity': 'number',
                                   'fuel_burn_units_per_second': 'number',
                                   'hardpoints': 'integer',
                                   'bomb_bays': 'integer',
                                   'cms': 'integer',
                                   'price': 'number',
                                   'visual_range_nm': 'number',
                                   'radar_range_nm': 'number',
                                   'radar_angle_degrees': 'number',
                                   'afterburner': 'boolean',
                                   'can_refuel': 'boolean'},
                       'Bomber': {'health': 'positive',
                                  'speed_knots': 'positive',
                                  'fuel_capacity': 'number',
                                  'fuel_burn_units_per_second': 'number',
                                  'hardpoints': 'integer',
                                  'bomb_bays': 'integer',
                                  'cms': 'integer',
                                  'price': 'number',
                                  'visual_range_nm': 'number',
                                  'radar_range_nm': 'number',
                                  'radar_angle_degrees': 'number',
                                  'afterburner': 'boolean',
                                  'can_refuel': 'boolean'},
                       'Interceptor': {'health': 'positive',
                                       'speed_knots': 'positive',
                                       'fuel_capacity': 'number',
                                       'fuel_burn_units_per_second': 'number',
                                       'hardpoints': 'integer',
                                       'bomb_bays': 'integer',
                                       'cms': 'integer',
                                       'price': 'number',
                                       'visual_range_nm': 'number',
                                       'radar_range_nm': 'number',
                                       'radar_angle_degrees': 'number',
                                       'afterburner': 'boolean',
                                       'can_refuel': 'boolean'},
                       'AWACS': {'health': 'positive',
                                 'speed_knots': 'positive',
                                 'fuel_capacity': 'number',
                                 'fuel_burn_units_per_second': 'number',
                                 'hardpoints': 'integer',
                                 'bomb_bays': 'integer',
                                 'cms': 'integer',
                                 'price': 'number',
                                 'visual_range_nm': 'number',
                                 'radar_range_nm': 'number',
                                 'radar_angle_degrees': 'number',
                                 'afterburner': 'boolean',
                                 'can_refuel': 'boolean'},
                       'KC-49': {'health': 'positive',
                                 'speed_knots': 'positive',
                                 'fuel_capacity': 'number',
                                 'fuel_burn_units_per_second': 'number',
                                 'hardpoints': 'integer',
                                 'bomb_bays': 'integer',
                                 'cms': 'integer',
                                 'price': 'number',
                                 'visual_range_nm': 'number',
                                 'radar_range_nm': 'number',
                                 'radar_angle_degrees': 'number',
                                 'afterburner': 'boolean',
                                 'can_refuel': 'boolean'}},
 'enemy_aircraft': {'Fighter': {'health': 'positive',
                                'speed_knots': 'positive',
                                'unlimited_fuel': 'boolean',
                                'fuel_burn_units_per_second': 'number',
                                'cms': 'integer',
                                'reload_seconds': 'positive'},
                    'Bomber': {'health': 'positive',
                               'speed_knots': 'positive',
                               'unlimited_fuel': 'boolean',
                               'fuel_burn_units_per_second': 'number',
                               'cms': 'integer',
                               'reload_seconds': 'positive'},
                    'Suicide Drone': {'health': 'positive',
                              'speed_knots': 'positive',
                              'unlimited_fuel': 'boolean',
                              'fuel_burn_units_per_second': 'number',
                              'cms': 'integer',
                              'reload_seconds': 'positive'}},
 'speed_modes': {'Eco': {'speed_multiplier': 'number', 'burn_multiplier': 'number'},
                 'Mil': {'speed_multiplier': 'number', 'burn_multiplier': 'number'},
                 'AB': {'speed_multiplier': 'number', 'burn_multiplier': 'number'}},
 'aircraft_behavior': {'default_orbit_radius_nm': 'number',
                       'default_engagement_range_nm': 'number',
                       'engagement_range_options_nm': {'$list': 'number', '$length': None},
                       'default_air_weapons_per_target': 'number',
                       'default_ground_weapons_per_target': 'number',
                       'acceleration_knots_per_second': 'number',
                       'deceleration_knots_per_second': 'number',
                       'rtb_eco_distance_nm': 'number',
                       'rtb_alert_fuel_multiplier': 'number',
                       'rtb_alert_extra_seconds': 'number',
                       'rtb_reserve_extra_seconds': 'number',
                       'bomb_turn_slow_distance_nm': 'number',
                       'bomb_turn_slow_angle_degrees': 'number',
                       'bomb_turn_speed_knots': 'number',
                       'normal_bank_degrees': 'positive',
                       'normal_turn_limit_degrees_per_second': 'positive',
                       'combat_bank_degrees': 'positive',
                       'combat_turn_limit_degrees_per_second': 'positive',
                       'takeoff_target_speed_knots': 'positive',
                       'liftoff_speed_knots': 'positive',
                       'takeoff_acceleration_knots_per_second': 'positive',
                       'rollout_deceleration_knots_per_second': 'positive',
                       'rtb_pattern_speed_knots': 'positive',
                       'approach_speed_knots': 'positive',
                       'final_speed_knots': 'positive',
                       'touchdown_max_speed_knots': 'positive',
                       'bomb_turn_deceleration_knots_per_second': 'positive',
                       'takeoff_straight_distance_nm': 'positive'},
 'ground_units': {'Airfield': {'health': 'positive', 'visual_range_nm': 'number', 'visual_range_per_upgrade_nm': 'number', 'runway_length_nm': 'number', 'runway_width_feet': 'number'},
                  'Radar': {'health': 'positive',
                            'range_nm': 'positive',
                            'power': 'integer',
                            'price': 'number',
                            'reload_seconds': 'positive'},
                  'LR Radar': {'health': 'positive',
                               'range_nm': 'positive',
                               'power': 'integer',
                               'price': 'number',
                               'reload_seconds': 'positive'},
                  'EWR': {'health': 'positive', 'power': 'integer', 'price': 'number', 'reload_seconds': 'positive',
                          'configuration_points': 'integer', 'default_range_points': 'integer',
                          'range_per_point_nm': 'positive', 'width_per_point_degrees': 'positive',
                          'rotation_degrees_per_minute': 'positive'},
                  'SAM': {'health': 'positive',
                          'range_nm': 'positive',
                          'ammo': 'integer',
                          'power': 'integer',
                          'price': 'number',
                          'shot_interval_seconds': 'number',
                          'max_inflight_missiles': 'integer',
                          'reload_seconds': 'positive'},
                  'LR SAM': {'health': 'positive',
                             'range_nm': 'positive',
                             'ammo': 'integer',
                             'power': 'integer',
                             'price': 'number',
                             'shot_interval_seconds': 'number',
                             'max_inflight_missiles': 'integer',
                             'reload_seconds': 'positive'},
                  'SAAW': {'health': 'positive',
                           'range_nm': 'positive',
                           'ammo': 'integer',
                           'power': 'integer',
                           'price': 'number',
                           'gun_range_nm': 'number',
                           'gun_ammo': 'integer',
                           'gun_rounds_per_second': 'positive',
                           'shot_interval_seconds': 'number',
                           'max_inflight_missiles': 'integer',
                           'reload_seconds': 'positive'},
                  'CIWS': {'health': 'positive',
                           'range_nm': 'positive',
                           'visual_range_nm': 'number',
                           'ammo': 'integer',
                           'power': 'integer',
                           'price': 'number',
                           'rounds_per_second': 'positive',
                           'reload_seconds': 'positive'},
                  'Flak': {'health': 'positive', 'min_engagement_range_nm':'number',
                           'range_nm': 'positive',
                           'visual_range_nm': 'number',
                           'ammo': 'integer',
                           'power': 'integer',
                           'price': 'number',
                           'shells_per_second': 'positive',
                           'reload_seconds': 'positive'},
                  'Factory': {'health': 'positive', 'reload_seconds': 'positive'},
                  'Bunker': {'health': 'positive', 'reload_seconds': 'positive'},
                  'ICBM Silo': {'health': 'positive', 'reload_seconds': 'positive', 'launch_enabled': 'boolean'}},
 'missiles': {'AIM-120': {'damage': 'number',
                          'damage_spread_fraction': 'fraction',
                          'launch_range_nm': 'positive',
                          'max_range_nm': 'positive',
                          'health': 'positive',
                          'boost_seconds': 'positive',
                          'speed_knots': 'positive',
                          'coast_deceleration_knots_per_second': 'number',
                          'hardpoint_count': 'integer'},
              'AIM-9': {'damage': 'number',
                        'damage_spread_fraction': 'fraction',
                        'launch_range_nm': 'positive',
                        'max_range_nm': 'positive',
                        'health': 'positive',
                        'boost_seconds': 'positive',
                        'speed_knots': 'positive',
                        'coast_deceleration_knots_per_second': 'number',
                        'hardpoint_count': 'integer'},
              'SAM': {'damage': 'number',
                      'damage_spread_fraction': 'fraction',
                      'launch_range_nm': 'positive',
                      'max_range_nm': 'positive',
                      'health': 'positive',
                      'boost_seconds': 'positive',
                      'speed_knots': 'positive',
                      'coast_deceleration_knots_per_second': 'number'},
              'SM1': {'damage': 'number',
                      'damage_spread_fraction': 'fraction',
                      'launch_range_nm': 'positive',
                      'max_range_nm': 'positive',
                      'health': 'positive',
                      'boost_seconds': 'positive',
                      'speed_knots': 'positive',
                      'coast_deceleration_knots_per_second': 'number'},
              'AGM-88': {'damage': 'number',
                       'damage_spread_fraction': 'fraction',
                       'launch_range_nm': 'positive',
                       'max_range_nm': 'positive',
                       'health': 'positive',
                       'boost_seconds': 'positive',
                       'speed_knots': 'positive',
                       'coast_deceleration_knots_per_second': 'number',
                       'hardpoint_count': 'integer'},
              'Sidearm': {'damage': 'number',
                          'damage_spread_fraction': 'fraction',
                          'launch_range_nm': 'positive',
                          'max_range_nm': 'positive',
                          'health': 'positive',
                          'boost_seconds': 'positive',
                          'speed_knots': 'positive',
                          'coast_deceleration_knots_per_second': 'number',
                          'hardpoint_count': 'integer'},
              'LR SAM': {'damage': 'number',
                         'damage_spread_fraction': 'fraction',
                         'launch_range_nm': 'positive',
                         'max_range_nm': 'positive',
                         'health': 'positive',
                         'boost_seconds': 'positive',
                         'speed_knots': 'positive',
                         'coast_deceleration_knots_per_second': 'number'}},
 'missile_behavior': {'salvo_interval_seconds': 'positive',
                      'hit_radius_nm': 'number',
                      'turn_limit_degrees_per_second': 'number',
                      'turn_g_limit': 'number',
                      'turn_drag_knots_per_degree': 'number',
                      'lost_lock_seconds': 'number',
                      'self_destruct_seconds': 'number',
                      'min_coast_speed_knots': 'number',
                      'aim9_close_turn_range_nm': 'number',
                      'aim9_close_turn_multiplier': 'number',
                      'anti_radar_range_based_drag': 'boolean'},
 'bombs': {'250': {'damage': 'number',
                   'damage_spread_fraction': 'fraction',
                   'health': 'positive',
                   'bay_count': 'integer'},
           '500': {'damage': 'number',
                   'damage_spread_fraction': 'fraction',
                   'health': 'positive',
                   'bay_count': 'integer'},
           '2000': {'damage': 'number',
                    'damage_spread_fraction': 'fraction',
                    'health': 'positive',
                    'bay_count': 'integer'},
           '1000': {'damage': 'number',
                    'damage_spread_fraction': 'fraction',
                    'health': 'positive',
                    'bay_count': 'integer'}},
 'bomb_behavior': {'drag_per_second': 'positive',
                   'drop_range_nm': 'number',
                   'hit_radius_nm': 'number',
                   'alignment_degrees': 'number'},
 'guns': {'bullet_speed_knots': 'positive',
          'dispersion_degrees': 'number',
          'damage_min': 'integer',
          'damage_max': 'integer',
          'hit_radius_nm': 'number'},
 'flak': {'shell_speed_knots': 'positive',
          'dispersion_degrees': 'number',
          'fragment_count_min': 'integer',
          'fragment_count_max': 'integer',
          'fragment_speed_knots': 'positive',
          'fragment_range_nm': 'positive',
          'fragment_damage_min': 'integer',
          'fragment_damage_max': 'integer',
          'fragment_hit_radius_nm': 'number'},
 'drone_impact': {'damage': 'number', 'damage_spread_fraction': 'fraction'},
 'countermeasures': {'success_probability': 'fraction',
                     'burst_cooldown_seconds': 'number',
                     'burst_flare_count': 'integer',
                     'burst_duration_seconds': 'number',
                     'lead_seconds_min': 'number',
                     'lead_seconds_max': 'number'},
 'tanker': {'refuel_radius_nm': 'positive', 'transfer_units_per_second': 'positive'},
 'ground_crew': {'repair_seconds_per_hp': {'$list': 'number', '$length': 5},
                 'rearm_seconds_per_weapon': {'$list': 'number', '$length': 5},
                 'crews_by_level': {'$list': 'number', '$length': 5},
                 'refuel_units_per_second_level1': 'positive',
                 'refuel_increase_fraction_per_level': 'number'},
 'logistics': {'speed_knots': 'positive',
               'helicopters_by_level': {'$list': 'number', '$length': 5},
               'heal_per_delivery': 'number'},
 'economy': {'starting_money': 'number',
             'sell_refund_fraction': 'fraction',
             'kill_rewards': {'Factory': 'number',
                              'Bunker': 'number',
                              'Fighter': 'number',
                              'Interceptor': 'number',
                              'Suicide Drone': 'number',
                              'RQ-9B': 'number',
                              'Bomber': 'number',
                              'Radar': 'number',
                              'LR Radar': 'number',
                              'EWR': 'number',
                              'SAM': 'number',
                              'LR SAM': 'number',
                              'SAAW': 'number',
                              'Flak': 'number',
                              'CIWS': 'number',
                              'ICBM Silo': 'number',
                              'ICBM': 'number'}},
 'upgrades': {'power_capacity_by_level': {'$list': 'number', '$length': 5},
              'hangars_by_level': {'$list': 'number', '$length': 5},
              'factory_income_per_minute_by_level': {'$list': 'number', '$length': 5},
              'prices': {'Power': {'$list': 'number', '$length': 4},
                         'Hangars': {'$list': 'number', '$length': 4},
                         'Factory': {'$list': 'number', '$length': 4},
                         'Logistics': {'$list': 'number', '$length': 4},
                         'Ground Crew': {'$list': 'number', '$length': 4},
                         'Airfield': {'$list': 'number', '$length': 4}},
              'airfield_unlocks': {'1': {'$list': 'text', '$length': None},
                                   '2': {'$list': 'text', '$length': None},
                                   '3': {'$list': 'text', '$length': None},
                                   '4': {'$list': 'text', '$length': None},
                                   '5': {'$list': 'text', '$length': None}}},
 'default_loadouts': {'Fighter': {'hardpoints': {'$list': 'text', '$length': None},
                                  'bays': {'$list': 'text', '$length': None}},
                      'Interceptor': {'hardpoints': {'$list': 'text', '$length': None},
                                      'bays': {'$list': 'text', '$length': None}},
                      'Bomber': {'hardpoints': {'$list': 'text', '$length': None},
                                 'bays': {'$list': 'text', '$length': None}}},
 'world': {'build_radius_nm': 'number',
           'radius_nm': 'number',
           'rwr_range_nm': 'positive',
           'rwr_update_seconds': 'positive',
           'rwr_range_error_fraction': 'fraction',
           'rwr_bearing_error_degrees': 'number',
           'rwr_baseline_nm': 'positive',
           'scope_refresh_seconds': 'positive'},
 'enemy_default_loadouts': {'Fighter': {'hardpoints': {'$list': 'text', '$length': None},
                                        'bays': {'$list': 'text', '$length': None}},
                            'Bomber': {'hardpoints': {'$list': 'text', '$length': None},
                                       'bays': {'$list': 'text', '$length': None}}},
 'icbm': {'health': 'positive',
          'launch_speed_knots': 'positive',
          'speed_knots': 'positive',
          'acceleration_knots_per_second': 'positive',
          'damage': 'number',
          'damage_spread_fraction': 'fraction',
          'hit_radius_nm': 'positive'}}


def _validate(value, rule, path):
    if isinstance(rule, dict) and '$list' in rule:
        if not isinstance(value, list) or (rule['$length'] is not None and len(value) != rule['$length']):
            raise ValueError(f'{path}: expected a list of {rule["$length"] or "any number of"} entries')
        for i, entry in enumerate(value):
            _validate(entry, rule['$list'], f'{path}[{i}]')
    elif isinstance(rule, dict):
        if not isinstance(value, dict):raise ValueError(f'{path}: expected an object')
        for key, child in rule.items():
            if key not in value:raise ValueError(f'{path}.{key}: missing setting')
            _validate(value[key], child, f'{path}.{key}')
        extra=set(value)-set(rule)-{'_help'}
        if extra:raise ValueError(f'{path}: unknown settings: {sorted(extra)}')
    elif rule == 'boolean':
        if not isinstance(value, bool):raise ValueError(f'{path}: expected true or false')
    elif rule == 'text':
        if not isinstance(value, str):raise ValueError(f'{path}: expected text')
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{path}: expected a finite number')
        if value < 0 or (rule == 'positive' and value == 0):raise ValueError(f'{path}: must be {"> 0" if rule == "positive" else ">= 0"}')
        if rule == 'fraction' and value > 1:raise ValueError(f'{path}: must be between 0 and 1')
        if rule == 'integer' and (not isinstance(value, int)):raise ValueError(f'{path}: expected a whole number')


AUDIO_DEFAULTS={'enabled': True, 'master_volume': 1.0, 'full_volume_zoom_nm': 10, 'quiet_zoom_nm': 75, 'quiet_volume': 0.1, 'barely_audible_zoom_nm': 100, 'barely_audible_volume': 0.02, 'max_voices': 16, 'events': {'ciws_fire': {'file': 'game_ciws_fire', 'volume': 0.6, 'cooldown_seconds': 0.08}, 'flak_fire': {'file': 'game_flak_fire', 'volume': 0.85, 'cooldown_seconds': 0.06}, 'flak_burst': {'file': 'game_flak_burst', 'volume': 0.65, 'cooldown_seconds': 0.04}, 'aircraft_missile': {'file': 'game_aircraft_missile', 'volume': 0.75, 'cooldown_seconds': 0.05}, 'missile_explosion': {'file': 'game_missile_explosion', 'volume': 0.8, 'cooldown_seconds': 0.05}, 'icbm_launch': {'file': 'game_icbm_launch', 'volume': 0.9, 'cooldown_seconds': 0.3}, 'bomb_250': {'file': 'game_bomb_250', 'volume': 0.55, 'cooldown_seconds': 0.06}, 'bomb_500': {'file': 'game_bomb_500', 'volume': 0.7, 'cooldown_seconds': 0.06}, 'bomb_1000': {'file': 'game_bomb_1000', 'volume': 0.85, 'cooldown_seconds': 0.06}, 'bomb_2000': {'file': 'game_bomb_2000', 'volume': 1.0, 'cooldown_seconds': 0.06}, 'buy_aircraft': {'file': 'game_buy_aircraft', 'volume': 0.75, 'cooldown_seconds': 0}, 'place_unit': {'file': 'game_place_unit', 'volume': 0.7, 'cooldown_seconds': 0}, 'upgrade': {'file': 'game_upgrade', 'volume': 0.85, 'cooldown_seconds': 0}}}


def apply_balance_update(data):
    """One-time requested balance changes when migrating old SAM missile names."""
    weapons={'AIM-120':(60,.05),'AIM-9':(40,.40),'MIM-23':(100,.20),'MIM-104':(150,.20),
             'PAC-3 MSE':(200,.25),'Sidearm':(35,.10),'AGM-88':(75,.05)}
    bombs={'250':(20,.15),'500':(50,.10),'1000':(150,.08),'2000':(500,.20)}
    for group,values in (('missiles',weapons),('bombs',bombs)):
        for kind,(damage,spread) in values.items():
            if kind in data.get(group,{}):
                data[group][kind].update(damage=damage,damage_spread_fraction=spread)
    health={'Factory':15,'Bunker':50,'Radar':15,'LR Radar':25,'CIWS':15,'Flak':20,
            'SAAW':20,'SAM':20,'LR SAM':25,'Drone Launcher':20,'ICBM Silo':150}
    for group in ('ground_units','enemy_ground_units'):
        for kind,spec in data.get(group,{}).items():
            if kind in health:spec['health']=health[kind]
            if kind in ('Radar','LR Radar'):spec['range_nm']=40 if kind=='Radar' else 60
            if kind in ('SAM','LR SAM','PAC-3'):
                minimum,maximum={'SAM':(4,32),'LR SAM':(6,60),'PAC-3':(10,75)}[kind]
                spec.update(min_engagement_range_nm=minimum,range_nm=maximum)
    for kind,maximum in (('MIM-23',32),('MIM-104',60),('PAC-3 MSE',75)):
        if kind in data.get('missiles',{}):data['missiles'][kind].update(launch_range_nm=maximum,max_range_nm=maximum)
    for kind,count in (('AIM-120',2),('AIM-9',3)):
        if kind in data.get('missiles',{}):data['missiles'][kind]['hardpoint_count']=count
        for group in ('friendly_aircraft','enemy_aircraft'):
            for spec in data.get(group,{}).values():
                counts=spec.get('hardpoint_loadout_counts',{})
                if kind in counts:counts[kind]=count
    for group in ('default_loadouts','enemy_default_loadouts'):
        for loadout in data.get(group,{}).values():
            loadout['hardpoints']=['2× AIM-120C' if 'AIM-120' in v else '3× AIM-9' if 'AIM-9' in v else v for v in loadout.get('hardpoints',[])]
    return data


OBJECTIVE_DEFAULTS=[
 {'id':'build_flak','title':'Build a flak cannon.','type':'build','target':'Flak','amount':1,'weapon':'Any','reward':1000},
 {'id':'buy_fighter','title':'Buy a fighter from the Hangar menu.','type':'build','target':'Fighter','amount':1,'weapon':'Any','reward':1000},
 {'id':'bomb_factories','title':'Destroy 3 Factories using bombs.','type':'kill','target':'Factory','amount':3,'weapon':'Bombs','reward':2500},
 {'id':'enemy_airfield','title':'Locate and destroy the enemy airfield.','type':'kill','target':'Airfield','amount':1,'weapon':'Any','reward':10000}]

PLAYER_SILO_DEFAULTS={'health':150,'price':5000,'power':5,'min_engagement_range_nm':35,'reload_seconds':600,'countdown_seconds':10}
PLAYER_WARHEAD_DEFAULTS={
    'Conventional':{'price':5000,'blast_radius_nm':1,'center_damage':500,'edge_damage':20},
    'Cluster':{'price':12000,'coverage_radius_nm':10,'burst_distance_nm':10,'count':8,'max_per_target':3,'damage':100,'damage_spread_fraction':0.3,'submunition_health':5,'impact_radius_nm':0.18},
    'Nuclear':{'price':20000,'blast_radius_nm':15,'center_damage':1000,'edge_damage':10}}


def migrate_stats(data):
    """Accept older balance files without discarding customized values."""
    data.setdefault('campaign',{}).setdefault('runway_description','')
    data.setdefault('objectives',deepcopy(OBJECTIVE_DEFAULTS))
    for objective in data['objectives']:
        if objective.get('weapon')=='HARM':objective['weapon']='AGM-88'
        if objective.get('type')=='upgrade' and objective.get('target')=='Power':objective['target']='Generator'
    data.setdefault('logistics',{}).setdefault('reload_speed_multipliers_by_level',[1,1.5,2.5,3.5,5])
    data.setdefault('economy',{}).setdefault('kill_rewards',{}).setdefault('Airfield',10000)
    data.setdefault('ground_units',{}).setdefault('Missile Silo',deepcopy(PLAYER_SILO_DEFAULTS))
    data.setdefault('player_warheads',deepcopy(PLAYER_WARHEAD_DEFAULTS))
    data.setdefault('player_strike_missile',{key:data['icbm'][key] for key in ('health','launch_speed_knots','speed_knots','acceleration_knots_per_second','hit_radius_nm')})
    unlocks=data.get('upgrades',{}).get('airfield_unlocks',{})
    if not any('Missile Silo' in values for values in unlocks.values()):unlocks.setdefault('3',[]).append('Missile Silo')
    data.setdefault('audio',deepcopy(AUDIO_DEFAULTS))
    data['audio'].setdefault('events',{})
    data['audio']['events'].setdefault('drone_impact',deepcopy(AUDIO_DEFAULTS['events']['drone_impact']))
    data['audio']['events'].setdefault('radar_ping',deepcopy(AUDIO_DEFAULTS['events']['radar_ping']))
    for event in ('silo_conventional_impact','silo_cluster_impact','silo_nuclear_impact','objective_complete','achievement_unlocked','kill_reward'):
        data['audio']['events'].setdefault(event,deepcopy(AUDIO_DEFAULTS['events'][event]))
    data['audio'].setdefault('kill_reward_scaling',{})
    for key,value in AUDIO_DEFAULTS['kill_reward_scaling'].items():data['audio']['kill_reward_scaling'].setdefault(key,value)
    for key in ('center_falloff_enabled','edge_volume','silence_distance_frames','center_falloff_exponent'):
        data['audio'].setdefault(key,AUDIO_DEFAULTS[key])
    for key,value in {'command_turn_speed_fraction':0.65,'command_turn_angle_degrees':10,'command_turn_deceleration_knots_per_second':20,'fast_turn_multiplier':1.1}.items():
        data.get('aircraft_behavior',{}).setdefault(key,value)
    data.get('world',{}).setdefault('coverage_refresh_seconds',0.5)
    data.get('missile_behavior',{}).setdefault('anti_radar_shutdown_scatter_nm_per_nm',0.12)
    missiles=data.get('missiles',{})
    if 'AIM-120' in missiles:missiles['AIM-120'].setdefault('pitbull_range_nm',10)
    rebalance='SAM' in missiles or 'LR SAM' in missiles
    for old,new in (('SAM','MIM-23'),('LR SAM','MIM-104')):
        if old in missiles:
            if new in missiles:raise ValueError(f'Use only {new}, not both {old} and {new}')
            missiles[new]=missiles.pop(old)
    if 'HARM' in missiles:
        if 'AGM-88' in missiles:raise ValueError('Use only AGM-88, not both HARM and AGM-88')
        missiles['AGM-88']=missiles.pop('HARM')
    for group in ('default_loadouts','enemy_default_loadouts'):
        for loadout in data.get(group,{}).values():
            loadout['hardpoints']=[v.replace('HARM','AGM-88') for v in loadout.get('hardpoints',[])]
    for values in data.get('upgrades',{}).get('airfield_unlocks',{}).values():
        for i,value in enumerate(values):
            if value=='HARM':values[i]='AGM-88'
    for group in ('friendly_aircraft','enemy_aircraft'):
        for spec in data.get(group,{}).values():
            counts=spec.get('hardpoint_loadout_counts',{})
            if 'HARM' in counts:counts['AGM-88']=counts.pop('HARM')
    for group in ('ground_units','enemy_ground_units'):
        flak=data.get(group,{}).get('Flak',{})
        if 'radar_range_nm' in flak:
            flak.setdefault('visual_range_nm',flak.pop('radar_range_nm'))
        ciws=data.get(group,{}).get('CIWS',{})
        if 'visual_range_nm' in ciws:
            ciws.setdefault('radar_range_nm',ciws.pop('visual_range_nm'))
    saaw=data.get('enemy_ground_units',{}).get('SAAW')
    if saaw is not None:saaw.setdefault('radar_range_nm',saaw.get('range_nm',8))
    if rebalance:apply_balance_update(data)
    for group in ('ground_units','enemy_ground_units'):
        for unit in data.get(group,{}).values():unit.setdefault('description','')
    return data


def load_stats(path=STATS_PATH):
    try:
        def unique_keys(pairs):
            result={}
            for key, value in pairs:
                if key in result:raise ValueError(f'duplicate setting: {key}')
                result[key]=value
            return result
        with Path(path).open(encoding='utf-8') as handle:
            data=json.load(handle, object_pairs_hook=unique_keys)
        migrate_stats(data)
        _validate(data, SCHEMA, 'settings')
        audio=data['audio']
        scaling=audio['kill_reward_scaling']
        if scaling['max_reward']<=scaling['min_reward']:raise ValueError('audio.kill_reward_scaling: max reward must exceed min reward')
        if scaling['max_volume_multiplier']<scaling['min_volume_multiplier']:raise ValueError('audio.kill_reward_scaling: max volume multiplier must be at least min volume multiplier')
        if not audio['full_volume_zoom_nm']<audio['quiet_zoom_nm']<audio['barely_audible_zoom_nm']:raise ValueError('audio: zoom anchors must increase')
        if audio['barely_audible_volume']>audio['quiet_volume']:raise ValueError('audio: barely audible volume must not exceed quiet volume')
        if audio['silence_distance_frames']<=1:raise ValueError('audio.silence_distance_frames must be greater than 1')
        if not 1<=audio['max_voices']<=32:raise ValueError('audio.max_voices must be between 1 and 32')
        for event,spec in audio['events'].items():
            if not spec['file'] or any(c in spec['file'] for c in ('/','\\',':')) or spec['file'] in ('.','..'):raise ValueError(f'audio.events.{event}: use a WAV filename without extension or directory')
        for group, pairs in (('guns', [('damage_min','damage_max')]), ('flak', [('fragment_count_min','fragment_count_max'),('fragment_damage_min','fragment_damage_max')]), ('countermeasures',[('lead_seconds_min','lead_seconds_max')])):
            for low, high in pairs:
                if data[group][low]>data[group][high]:raise ValueError(f'{group}.{low} must not exceed {high}')
        if data['countermeasures']['burst_flare_count']<2:raise ValueError('countermeasures.burst_flare_count must be at least 2')
        for key in ('crews_by_level',):
            if any(not isinstance(x,int) or x<1 for x in data['ground_crew'][key]):raise ValueError(f'ground_crew.{key}: use positive whole numbers')
        for group,key in (('logistics','helicopters_by_level'),('upgrades','hangars_by_level'),('upgrades','power_capacity_by_level')):
            if any(not isinstance(x,int) or x<1 for x in data[group][key]):raise ValueError(f'{group}.{key}: use positive whole numbers')
        for key in ('repair_seconds_per_hp','rearm_seconds_per_weapon'):
            if any(x<=0 for x in data['ground_crew'][key]):raise ValueError(f'ground_crew.{key}: times must be positive')
        for group,key in (('ground_crew','crews_by_level'),('logistics','helicopters_by_level'),('upgrades','hangars_by_level'),('upgrades','power_capacity_by_level')):
            values=data[group][key]
            if values!=sorted(values):raise ValueError(f'{group}.{key}: values must not decrease with upgrades')
        if not 0<data['aircraft_behavior']['command_turn_speed_fraction']<=1:raise ValueError('command_turn_speed_fraction must be greater than 0 and at most 1')
        if not 0<data['aircraft_behavior']['defensive_speed_min_fraction']<=data['aircraft_behavior']['defensive_speed_max_fraction']:raise ValueError('defensive speed fractions must be positive and minimum must not exceed maximum')
        for key in ('normal_bank_degrees','combat_bank_degrees'):
            if data['aircraft_behavior'][key]>=89:raise ValueError(f'aircraft_behavior.{key}: must be below 89 degrees')
        for k,unit in data['ground_units'].items():
            if 'max_inflight_missiles' in unit and unit['max_inflight_missiles']<1:raise ValueError(f'ground_units.{k}.max_inflight_missiles: must be positive')
        for k,spec in data['missiles'].items():
            if spec['launch_range_nm']>spec['max_range_nm']:raise ValueError(f'missiles.{k}: launch range must not exceed maximum range')
        ids=set()
        upgrade_targets={'Airfield','Generator','Factory','Hangars','Ground Crew','Logistics'}
        objective_targets={'upgrade':upgrade_targets,
            'build':(set(data['friendly_aircraft'])|set(data['ground_units']))-{'Airfield'},
            'kill':set(data['enemy_aircraft'])|set(data['enemy_ground_units'])|{'Airfield'},
            'locate':set(data['enemy_aircraft'])|set(data['enemy_ground_units'])|{'Airfield','ICBM'}}
        weapons={'Any','Bombs','AIM-120','AIM-9','AGM-88','Sidearm','CIWS','Flak','Conventional','Cluster','Nuclear',*[f'{w} lb Bomb' for w in data['bombs']]}
        for o in data['objectives']:
            if not o['id'].strip() or o['id'] in ids:raise ValueError('Objectives need unique nonempty IDs')
            ids.add(o['id'])
            if not o['title'].strip() or o['type'] not in ('build','kill','upgrade','locate'):raise ValueError('Objectives need a title and build, kill, upgrade or locate type')
            if o['amount']<1:raise ValueError('Objective amount must be at least 1')
            if o['target'] not in objective_targets[o['type']]:raise ValueError(f'Invalid objective target: {o["target"]}')
            if o['type']=='upgrade' and o['amount']>5:raise ValueError('Upgrade objective level must be at most 5')
            if o['weapon'] not in weapons:raise ValueError('Invalid objective weapon filter')
        strike=data['player_strike_missile']
        if strike['launch_speed_knots']>strike['speed_knots']:raise ValueError('player_strike_missile: launch speed must not exceed top speed')
        for name in ('Conventional','Nuclear'):
            warhead=data['player_warheads'][name]
            if warhead['edge_damage']>warhead['center_damage']:raise ValueError(f'player_warheads.{name}: edge damage must not exceed center damage')
        cluster=data['player_warheads']['Cluster']
        if cluster['count']<1 or cluster['max_per_target']<1:raise ValueError('Cluster: count and maximum per target must be positive')
        options=data['aircraft_behavior']['engagement_range_options_nm']
        if not options or any(x<=0 for x in options):raise ValueError('engagement_range_options_nm must contain positive ranges')
        for k,loadout in {**data['default_loadouts'],**data['enemy_default_loadouts']}.items():
            for label in loadout['hardpoints']:
                if label!='Empty' and not any(w in label for w in ('AIM-120','AIM-9','AGM-88','Sidearm')):raise ValueError(f'{k}: unknown hardpoint loadout {label}')
            for label in loadout['bays']:
                if label!='Empty' and not any(w in label.replace(',','') for w in data['bombs']):raise ValueError(f'{k}: unknown bomb loadout {label}')
        if data['missiles']['PAC-3 MSE']['launch_speed_knots']>data['missiles']['PAC-3 MSE']['speed_knots']:raise ValueError('PAC-3 MSE: launch speed must not exceed top speed')
        if data['ground_units']['Flak']['min_engagement_range_nm']>data['ground_units']['Flak']['range_nm']:raise ValueError('Flak: minimum engagement range must not exceed maximum range')
        if data['ground_units']['PAC-3']['min_engagement_range_nm']>data['ground_units']['PAC-3']['range_nm']:raise ValueError('PAC-3: minimum engagement range must not exceed maximum range')
        if data['ground_units']['PAC-3']['cone_width_degrees']>360:raise ValueError('PAC-3: cone width must not exceed 360 degrees')
        ewr=data['ground_units']['EWR']
        if ewr['configuration_points']<2 or not 1<=ewr['default_range_points']<ewr['configuration_points']:raise ValueError('EWR: reserve at least one point for range and width')
        if (ewr['configuration_points']-1)*ewr['width_per_point_degrees']>360:raise ValueError('EWR: maximum width must not exceed 360 degrees')
        if data['icbm']['launch_speed_knots']>data['icbm']['speed_knots']:raise ValueError('icbm.launch_speed_knots must not exceed speed_knots')
        campaign=data['campaign']
        if campaign['random_factories_start_count'] and campaign['core_factory_min_radius_nm']>=campaign['safe_radius_nm']:raise ValueError('campaign core factory minimum radius must be inside the safe core')
        if not campaign['tiers']:raise ValueError('campaign.tiers must contain at least one zone')
        if campaign['placement_attempts']<1:raise ValueError('campaign.placement_attempts must be positive')
        if campaign['garrison_radius_nm']<campaign['unit_separation_nm']:raise ValueError('campaign garrison radius must cover unit separation')
        for i,tier in enumerate(campaign['tiers']):
            pairs=[tier['airfields'],tier['outposts'],*tier['airfield_ground'].values(),*tier['outpost_ground'].values(),*tier['wave_aircraft'].values()]
            if any(pair[0]>pair[1] for pair in pairs):raise ValueError(f'campaign.tiers[{i}]: minimum count exceeds maximum')
            if tier['airfields'][0]<1:raise ValueError(f'campaign.tiers[{i}]: each zone needs at least one runway')
        for group in ('ground_units','enemy_ground_units'):
            for key,unit in data[group].items():
                maximum=unit.get('range_nm')
                if key=='EWR':
                    if unit['configuration_points']<2 or not 1<=unit['default_range_points']<unit['configuration_points']:raise ValueError(f'{group}.EWR: reserve at least one point for range and width')
                    if (unit['configuration_points']-1)*unit['width_per_point_degrees']>360:raise ValueError(f'{group}.EWR: maximum width must not exceed 360 degrees')
                    maximum=(unit['configuration_points']-1)*unit['range_per_point_nm']
                if maximum is not None and unit['min_engagement_range_nm']>maximum:raise ValueError(f'{group}.{key}: minimum range must not exceed maximum range')
                if key=='PAC-3' and unit['cone_width_degrees']>360:raise ValueError(f'{group}.PAC-3: cone width must not exceed 360 degrees')
                if 'max_inflight_missiles' in unit and unit['max_inflight_missiles']<1:raise ValueError(f'{group}.{key}: max_inflight_missiles must be positive')
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f'Cannot load game balance settings from {path}: {exc}') from exc


SCHEMA['ground_units']['PAC-3']={**SCHEMA['ground_units']['SAM'], 'cone_width_degrees':'positive','rotation_degrees_per_second':'positive','min_engagement_range_nm':'number'}
SCHEMA['missiles']['PAC-3 MSE']={**SCHEMA['missiles']['SAM'], 'turn_limit_degrees_per_second':'positive','launch_speed_knots':'positive','min_turn_speed_fraction':'fraction'}

SCHEMA['aircraft_behavior']['defensive_range_nm']='number'
SCHEMA['aircraft_behavior']['defensive_turn_angle_degrees']='positive'

for _ground_rule in SCHEMA['ground_units'].values():_ground_rule['min_engagement_range_nm']='number'
SCHEMA['enemy_ground_units']={key:dict(rule) for key,rule in SCHEMA['ground_units'].items() if key!='PAC-3'}
# Keep only playable friendly types and current enemy types in the settings model.
for _key in ('Factory','Bunker','SAAW','ICBM Silo'):SCHEMA['ground_units'].pop(_key)
for _key in ('Airfield','EWR'):SCHEMA['enemy_ground_units'].pop(_key)
for _group in ('ground_units','enemy_ground_units'):
    for _key,_rule in SCHEMA[_group].items():
        if _key in ('Radar','LR Radar','EWR','Factory','Bunker'):_rule.pop('reload_seconds',None)
        if _key in ('Airfield','Factory','Bunker'):_rule.pop('min_engagement_range_nm',None)
        if _group=='enemy_ground_units':
            _rule.pop('price',None);_rule.pop('power',None)
for _key in ('EWR','RQ-9B'):SCHEMA['economy']['kill_rewards'].pop(_key)
SCHEMA['enemy_ground_units']['Drone Launcher']={'health':'positive','ammo':'integer','shot_interval_seconds':'positive','reload_seconds':'positive','launch_enabled':'boolean','min_engagement_range_nm':'number'}

SCHEMA['aircraft_behavior']['defensive_speed_min_fraction']='fraction'
SCHEMA['aircraft_behavior']['defensive_speed_max_fraction']='fraction'

_suicide_drone_base=SCHEMA['friendly_aircraft'].pop('Suicide Drone')
SCHEMA['enemy_aircraft']['Suicide Drone']={**_suicide_drone_base,**SCHEMA['enemy_aircraft']['Suicide Drone']}
SCHEMA['enemy_aircraft']['Suicide Drone'].pop('price',None)

SCHEMA['aircraft_behavior']['fuel_ab_ramp_exponent']='positive'


SCHEMA['world']['aircraft_wreck_lifetime_seconds']='positive'
SCHEMA['enemy_aircraft']['Interceptor']=dict(SCHEMA['enemy_aircraft']['Fighter'])
SCHEMA['enemy_aircraft']['Fighter']['hardpoints']='integer'
SCHEMA['enemy_aircraft']['Fighter']['hardpoint_loadout_counts']={'Sidearm':'integer'}
_campaign_ground_types=('Factory','Bunker','Radar','LR Radar','SAM','LR SAM','Flak','SAAW','CIWS','Drone Launcher','ICBM Silo')
_campaign_pair={'$list':'integer','$length':2}
SCHEMA['campaign']={key:'positive' for key in ('band_width_nm','unit_separation_nm','base_separation_nm','garrison_radius_nm','runway_length_nm','runway_width_nm','runway_health','first_wave_delay_seconds','wave_interval_seconds')}
SCHEMA['campaign'].update({'safe_radius_nm':'number','aircraft_clearance_nm':'number','placement_attempts':'integer','random_seed':'integer','runway_health_per_band':'number','core_factory_min_radius_nm':'number','random_factories_start_count':'integer','random_factories_growth_fraction':'number','wave_interval_growth_fraction':'number','infinite_growth_fraction':'number','show_bands':'boolean','tiers':{'$list':{'airfields':_campaign_pair,'outposts':_campaign_pair,'airfield_ground':{k:_campaign_pair for k in _campaign_ground_types},'outpost_ground':{k:_campaign_pair for k in _campaign_ground_types},'wave_aircraft':{k:_campaign_pair for k in ('Fighter','Interceptor','Bomber','Suicide Drone')}},'$length':None}})


# CIWS uses radar; Flak keeps the Optical range under its compatible visual key.
for _group in ('ground_units','enemy_ground_units'):
    SCHEMA[_group]['CIWS']['radar_range_nm']=SCHEMA[_group]['CIWS'].pop('visual_range_nm')
SCHEMA['enemy_ground_units']['SAAW']['radar_range_nm']='number'

SCHEMA['audio']={'enabled':'boolean','master_volume':'fraction','full_volume_zoom_nm':'positive','quiet_zoom_nm':'positive','quiet_volume':'fraction','barely_audible_zoom_nm':'positive','barely_audible_volume':'fraction','max_voices':'integer','events':{key:{'file':'text','volume':'fraction','cooldown_seconds':'number'} for key in AUDIO_DEFAULTS['events']}}

AUDIO_DEFAULTS['events']['drone_impact']={'file':'game_drone_impact','volume':0.8,'cooldown_seconds':0.06}
SCHEMA['audio']['events']['drone_impact']={'file':'text','volume':'fraction','cooldown_seconds':'number'}
SCHEMA['missile_behavior']['anti_radar_shutdown_scatter_nm_per_nm']='number'

AUDIO_DEFAULTS.update({'center_falloff_enabled': True, 'edge_volume': 0.25, 'silence_distance_frames': 1.5, 'center_falloff_exponent': 1.5})
SCHEMA['audio'].update({'center_falloff_enabled':'boolean','edge_volume':'fraction','silence_distance_frames':'positive','center_falloff_exponent':'positive'})
AUDIO_DEFAULTS['events']['radar_ping']={'file':'sound9','volume':1.0,'cooldown_seconds':0.06}
SCHEMA['audio']['events']['radar_ping']={'file':'text','volume':'fraction','cooldown_seconds':'number'}

SCHEMA['aircraft_behavior'].update({'command_turn_speed_fraction':'fraction','command_turn_angle_degrees':'positive','command_turn_deceleration_knots_per_second':'positive','fast_turn_multiplier':'positive'})
SCHEMA['world']['coverage_refresh_seconds']='positive'

SCHEMA['missiles']['MIM-23']=SCHEMA['missiles'].pop('SAM')
SCHEMA['missiles']['MIM-104']=SCHEMA['missiles'].pop('LR SAM')
SCHEMA['missiles']['AIM-120']['pitbull_range_nm']='positive'
SCHEMA['economy']['kill_rewards']['Airfield']='number'

SCHEMA['ground_units']['Missile Silo']={'health':'positive','price':'number','power':'integer','min_engagement_range_nm':'number','reload_seconds':'positive','countdown_seconds':'positive'}
SCHEMA['player_strike_missile']={key:'positive' for key in ('health','launch_speed_knots','speed_knots','acceleration_knots_per_second','hit_radius_nm')}
SCHEMA['player_warheads']={name:{key:('integer' if key in ('count','max_per_target') else 'fraction' if key=='damage_spread_fraction' else 'number' if key in ('price','center_damage','edge_damage','damage') else 'positive') for key in values} for name,values in PLAYER_WARHEAD_DEFAULTS.items()}

for _name,_volume,_cooldown in (('conventional',0.9,0.06),('cluster',0.65,0.04),('nuclear',1.0,0.5)):
    _event=f'silo_{_name}_impact'
    AUDIO_DEFAULTS['events'][_event]={'file':f'game_{_event}','volume':_volume,'cooldown_seconds':_cooldown}
    SCHEMA['audio']['events'][_event]={'file':'text','volume':'fraction','cooldown_seconds':'number'}

SCHEMA['logistics']['reload_speed_multipliers_by_level']={'$list':'positive','$length':5}

SCHEMA['objectives']={'$list':{'id':'text','title':'text','type':'text','target':'text','amount':'integer','weapon':'text','reward':'number'},'$length':None}
AUDIO_DEFAULTS['events']['objective_complete']={'file':'game_objective_complete','volume':0.8,'cooldown_seconds':0}
SCHEMA['audio']['events']['objective_complete']={'file':'text','volume':'fraction','cooldown_seconds':'number'}

AUDIO_DEFAULTS['events']['achievement_unlocked']={'file':'game_achievement_unlocked','volume':0.8,'cooldown_seconds':0}
AUDIO_DEFAULTS['events']['kill_reward']={'file':'game_kill_reward','volume':0.8,'cooldown_seconds':0}
AUDIO_DEFAULTS['kill_reward_scaling']={'min_reward':0,'max_reward':10000,'min_volume_multiplier':0.2,'max_volume_multiplier':1.0}
for _event in ('achievement_unlocked','kill_reward'):
    SCHEMA['audio']['events'][_event]={'file':'text','volume':'fraction','cooldown_seconds':'number'}
SCHEMA['audio']['kill_reward_scaling']={key:'number' for key in AUDIO_DEFAULTS['kill_reward_scaling']}

# Building descriptions are editable independently for friendly/enemy types.
for _group in ('ground_units','enemy_ground_units'):
    for _rule in SCHEMA[_group].values():_rule['description']='text'
SCHEMA['campaign']['runway_description']='text'
