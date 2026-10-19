WIRE JUDGE GAME BALANCE

Edit game_stats.json in the same folder as game_settings.py, save it,
then completely close and restart Wire Judge to apply changes.
The supplied values preserve the current balance.

Sections:
  friendly_aircraft / enemy_aircraft: HP, speed, fuel capacity/burn,
    CMS, hardpoints, bomb bays, price, visual/radar ranges and capabilities.
  speed_modes: Eco, Mil and AB speed/fuel-burn multipliers.
  aircraft_behavior: acceleration, turns, takeoff/landing, RTB and defaults.
  ground_units: health, ranges, ammo, power, prices and firing rates.
  missiles / missile_behavior: damage, spread, health, launch/max ranges,
    speed, boost, drag, turning, salvo spacing and rounds per hardpoint.
  bombs / bomb_behavior: damage/spread, health, rounds per bay, drag/drop range.
  guns / flak: bullet speed/damage/spread and shell/fragment stats.
  countermeasures / drone_impact: success chance, timing and impact damage.
  tanker: refueling radius and fuel transferred per second.
  ground_crew: repair/rearm times, crews and refueling rates.
  logistics: helicopter speeds/counts and healing per delivery.
  economy: starting money, sell refund fraction and kill rewards.
  upgrades: capacities, income, costs and airfield unlocks.
  default_loadouts / enemy_default_loadouts: starting weapon selections.
  world: building radius, full-map scale and RWR settings.

Units:
  Speed is knots, range is NM, time is simulated seconds, money is dollars.
  Fuel burn and fueling are fuel units per simulated second.
  Fractions: 0.20 = 20%; 0.50 = 50%.
  Fire rate: rounds/shells per second. 0.5 = one shot every two seconds.
  Arrays with five entries are levels 1-5. Upgrade costs have four entries,
  for buying levels 2-5. Keep those array lengths and the existing key names.

Mil endurance in hours = fuel_capacity / fuel_burn_units_per_second / 3600.
Example: Fighter fuel 7000 and burn 1.1111111111 gives about 1.75 hours.
KC-49 uses one shared fuel pool for its own burn and fuel it transfers.
Enemy aircraft override friendly stats; unlimited_fuel=true forces zero burn.

Ground launch range is limited by both the ground unit range and its
missile launch_range_nm. max_range_nm is missile flight range.
SAM/SAAW cadence uses shot_interval_seconds and max_inflight_missiles.
HARM/Sidearm use range-based coast drag by default; set
missile_behavior.anti_radar_range_based_drag=false to use their configured
coast_deceleration_knots_per_second instead.

Loadout labels use the existing weapon names. hardpoint_count and bay_count
control rounds per slot; labels update automatically. Changing slot counts
trims extra default slots or adds Empty ones.

Invalid JSON or invalid settings produce an error naming the file and setting.
Settings affect the game only; replay analysis and scoring are unchanged.

ICBM SILOS AND ENEMY RELOADS
  Debug: Spawn Enemy ICBM Silo. Inspect a silo to switch Engagement On/Off.
  Silos have unlimited range and target the friendly airfield without sensors.
  The ICBMs target toggle is available for SAMs, CWIS, flak and combat aircraft.
  Aircraft intercept using armed AIM-120 or AIM-9 weapons.
  icbm controls missile health, launch/max speed, acceleration and impact damage.
  Default acceleration is 5 knots/second (30 to 850 knots in 164 seconds).
  ICBM Silo settings control HP, engagement enabled on spawn, and reload time.
  Its kill reward is in economy.kill_rewards.
  Enemy weapon pools refill after reload_seconds when empty. Each missile kind,
  bomb size and SAAW gun/missile pool has its own countdown. Friendly units still
  use logistics or ground crews. Empty pools refill even if engagement is off.

GROUND UNIT TEAMS AND MINIMUM RANGES
- ground_units controls friendly ground units.
- enemy_ground_units controls enemy ground units independently (complete settings, no inheritance).
- Each ground unit has min_engagement_range_nm; 0 permits close engagements. SAM, LR SAM, CIWS and other new entries start at 0; PAC-3 stays 5 and Flak stays 1.5 on both tables.
- Minimum range gates weapons; radar minimum range creates a detection blind zone. Noncombat buildings store the field without firing behavior.
- Missile, gun and shrapnel weapon damage/flight settings remain in their existing shared weapon sections.
- Restart the application to apply edits.

SUICIDE DRONES
The enemy-only Suicide Drone has its complete stats under enemy_aircraft. It has no friendly_aircraft entry and cannot be purchased by the player. RQ-9B is the separate friendly scout. Target buttons labelled Suicide Drones refer to the enemy suicide unit.

SPEED-BASED FUEL BURN
Actual airborne fuel use follows current speed. Eco/Mil/AB burn_multiplier values define the reference rates; AB defaults to twice Mil. aircraft_behavior.fuel_ab_ramp_exponent controls how quickly burn rises between Mil and AB (0.5 gives a quick initial rise). Ground states and eligible tanker refueling retain zero flight burn.

SELECTED FRIENDLY RANGE HIGHLIGHTS
Selected friendly units draw steady outlines at their actual range and cone width, using the same colors and patterns as the coverage overlays. Their complete boundaries are drawn separately above the merged coverage, including sections inside or overlapping other outlines.

ENEMY DRONE LAUNCHER
Drone Launcher is enemy-only, with its own entry under enemy_ground_units. It holds 3 Suicide Drones, launches one every 3 simulated seconds, and rearms the full magazine 300 seconds after the last launch. Launched drones and debug-spawned aircraft fly directly toward the airfield, acquiring targets only through their normal sensors. On reaching their destination they orbit at a radius large enough for maximum speed. Launcher health starts at 50. Spawn it from Debug; See All exposes its engagement toggle.

DIRECT TO
Player aircraft use Direct To to fly to a clicked waypoint and then loiter. The destination orbit radius accounts for maximum aircraft speed, normal bank and turn-rate limits, and the orbit speed cap. Combat can interrupt navigation; aircraft resume their route after disengaging.
