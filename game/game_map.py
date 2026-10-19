"""Standalone game-map foundation; independent of replay files and scoring."""
from dataclasses import dataclass, field
from .game_settings import STATS, crew_repair_seconds, crew_weapon_seconds, crew_count, loadout_label, ground_stats
import math
import random
import time
import tkinter as tk
from tkinter import ttk, font as tkfont
from ui.plots import BG, PANEL, TEXT, MUTED
from .game_radar import footprint, union_outline, range_paths, coverage_outline
from .game_aircraft_inspector import AircraftInspector
from .game_ground_inspector import GroundInspector, HealthInspector, AmmoInspector, ConfidenceInspector
from .game_icbm_inspector import ICBMInspector, ICBMSiloInspector, ProjectileInspector, HelicopterInspector
from .game_world import RWR, RWRSignal, RWR_RANGE_NM
from .game_campaign import Campaign, EnemyRunway
from .game_results import ResultBoard, results_header
from .game_start import StartScene
from .game_fullscreen import GameFullscreen
from .game_grid import grid_image
from .game_logistics import logistics_reload_multiplier, LogisticsFleet, LogisticsHelicopter, LOGISTICS_LEVELS, LOGISTICS_UPGRADE_COSTS, helipad_position
from .game_audio import GameAudio, kill_reward_gain
from .game_progress import ProgressUI
from .game_player_silo import PlayerSiloUI, PlayerMissileSilo, PlayerStrike
from .game_combat import CombatWorld, Factory, Bunker, DroneLauncher, ICBMSilo, ICBM, Missile, Bomb, TARGET_TYPES, ENGAGEMENT_RANGES
from .game_aircraft import rtb_alert_fuel, bomb_bay_allowed, Aircraft, AIRCRAFT_TYPES, AIRCRAFT_PRICE, AirOperations, parking_position, formation_position, REFUEL_RADIUS_NM, ground_refuel_rate
from replay.replay_style import AIRCRAFT_SIZE, AIRCRAFT_TRAIL_WIDTH, aircraft_marker
from matplotlib.markers import MarkerStyle
from matplotlib.font_manager import findfont
from PIL import Image, ImageDraw, ImageFont, ImageTk

ZOOM_WIDTHS_NM = tuple(sorted({w for w in (5,10,15,25,50,75,100,150,250,400,500,750,1500,2500) if w<=min(2500,2*STATS['world']['radius_nm'])} | {min(2500,2*STATS['world']['radius_nm'])}))
FEET_PER_NM = 6076.115485564304
BUILD_RADIUS_NM = STATS['world']['build_radius_nm']
SAM_COST = STATS['ground_units']['SAM']['price']
RADAR_COST = STATS['ground_units']['Radar']['price']
RADAR_RANGE_NM = STATS['ground_units']['Radar']['range_nm']
HANGAR_LEVELS = tuple(STATS['upgrades']['hangars_by_level'])
HANGAR_UPGRADE_COSTS = tuple(STATS['upgrades']['prices']['Hangars'])
POWER_LEVELS = tuple(STATS['upgrades']['power_capacity_by_level'])
FACTORY_INCOME = tuple(STATS['upgrades']['factory_income_per_minute_by_level'])
FACTORY_UPGRADE_COSTS = tuple(STATS['upgrades']['prices']['Factory'])
BUILD_BUTTON_ICON_DATA = {'SAM Launcher': 'iVBORw0KGgoAAAANSUhEUgAAAJ0AAAAYCAYAAADgW/+9AAAFk0lEQVR4nO2Ze4hVRRzHP7utmU32IHNUlBqU0pulZRFYRhiVFdUWlGjRlgapcS1Pjz+koExyMbuKp4zeK0qxVFSk0hOiJ4XUWno0EUez1p2SUnLSzfT2x8zN4+3u7jl3LXucDxx2z/nNb85vzvnOb+Z3LmRkZGRkZGRkZPwTKbbmi0nb1v6VgWT8P0gjOMhEl3EIyESX0S3SZjnIRHcA2tg2bezwQx3Hf506AG3s2cDDwJnANuAFYI6SYme8sTb2PWAE0E9J0R67vhrIAYOVFDp2/SNgNHCGkqKl/Ober1FJsfTgDuvfSxCFjUBjIZffXnb9VeAqf/pEIZefErP1Bp4CrgC2A7MLufzjSe3VUk2WA6jVxvYElgPvAoOA84EdwDXxhtrYk4BzAANcWaGvtcBNsfanAH2B9gptM8oIonBUEIUfAwHwRRCF04IorCnZC7l8fSGXrwEeq+BeACQwGLgemBtE4ZgU9tRUElyxNV8sPyr51gEKOAGY67PXDmBuhbY3Am8CnwINwItl9sXAVG3s/UqKIjAJaALuq2ZQ2tiVwCicaFcBU5UUn3vbb8BAJUWbP18A7FRS3OvP24B5wM24ibQCaFBStGtjBwDzgbF+rHcoKZbFbj1OG9tc7uf7lUAIXAjsBBYoKebH7vmIfzb9lBR9Ug55KfAM8AmwBJgM9AdaO3MKorAHMAG4rJDLtwFtQRQ2+zg+6MqeMsZU1AzYP2ni1AKbcdlrjjb2FG1sxYY40TX74xL/AuJs9H2N1cYehptRi6sNWElxlpKiBjgOJ95m329SLgPGAUOB04AbtLG1wGs4wQwHLsYJqFM/AP9cXsE9qyHAJbhJdnnM92rg8ioEBzAAeBXYA2wq5PL5Qi7fqeA8JwECaIldawFOTWhPTbXLaolaJcUu4AKgH07527SxT2pjjy810saeh3soryspNvqgJ1bo7zlcdrkUWK2k+LY7wQEoKXYpKR4HDsO97KTMUlJsUVK04l7mcNx+9GRgmpLCKCk2KilmJPADOB0YhsuMPykp1gELgGvLfDd3FJA29g1t7OwOzPNwE/pcYHQQhYcnHOdR/u/PsWs7gN4J7WnjTERHWQ589aqkWKekmKik6Ivbtw3BpfoSDcDyWGFRSs/lvARcBNwOPNudoLWxU7Wx67Wx7drYIm4b0D9FF9ti/+8CeuGWzC3xIiihH8CJwLFAuzZ2rzZ2H25/NSjW/rsU8R1AIZd/EBgP/IhbVVYHUTg0gWvpncRFdAz7RdaVPRVJslxnggNfvcZRUmzQxi4CHgXQxvYCrgOO9i//D7SxI5QUq2K+Vhu7DKjHLWNV4YuQh3BL2JdKit3aWB2LdzdwRMylD/sfbmdsAQZpY3t2IbyOfFtxe8mOHnynL0RJMa4zeyGX3xBE4VqgEbgbmAZM7yKuTcAvwEjgfX9tJLAmoT1VnJUElXa5rdPGDgNmAgt9IP2BqcBK36Yet5nvqaT4teSojX0LNyPvLAt4Mm4T3B0EsBdX3tdpY+/C7U1KfAVM0sY2AmNwlXYhQb8twHpgkTZ2JnAkML3CEluJVcA3wCP+vvtwVXwvJUWlijIV/pPILKAHMBA3rhVd+RVy+T1BFL4APBBE4QTcXnQ8bm/apb27lAuuqywHbnn9Gje4hcAPwIfAVuAW36YBaIoLzvMEcL029k/ZMiVLtLHF2NHkq9Qm4DOcSAZz4MycjhPaVmAK8HKSG/kMVY9bJiNcNf5OQt993rcvTvRrcN8gm5P4J+BpYBGQB97295hfMgZRODuIwiJwG3BrEIVF/00PYAbwPa6Yex64p5DLxyvTruwHhSSCy/gHEkRhYxCFxx7qOJLS2fe4jsh+Bsuomu5+OsnISE01WS4jo1tU/dvrwQ4k4/9BluEy/nYy0WX8q/gdSq5V9zJgMtcAAAAASUVORK5CYII=', 'Radar': 'iVBORw0KGgoAAAANSUhEUgAAAHkAAAAYCAYAAADeUlK2AAADzUlEQVR4nO2YTYgcRRTHf+smXtr4hdBxTSCNoqH1EEwOoojelKi44iEoRA+CGmMLFomePERXGXBtDyUufmEkQdmDuOIlQfBgEPGTaDYdCCG1El22NEj8KDWEZTxUjemdzM70dHp7wNTv0nS9etWv+t/vVVWDx+PxeDyeXjRnk+ZS+51X5gGeaqhDYPAinxN4kQdEXVkMSyCy0mZcadOoelxPeZYBKG2mgWtd23HgE+DxKAx+GVRg/SIy2QAaaZycaGufAu52t6+lcfJozrYCeAO4CzgBjKVxMlHUXpY6sxicyI7NURjsVtqsBiaBBvBQmUHrRGRyPSCBDcAmkckXgYk0ti8kjZNR1+8VFs4XIAVC4EpgLfCRyOR0Gif7Ctr7ppNQndqGRuRQFX5w5qSJwuCY0uZD4N5Wm9Lma2A9cBL4DtgShcG3zhYDb2NfwmfYSjBb0HcOeAl4EFgZhcFl7fEUYDfwFvA5sAv7YV6ej6ETIpPLgfuAjWmczAFzIpOTLpZ9vewl4ixMJ6HOxu+MNVlpswoYBb5qtUVhsCEKgyHgEmAnMKm0GVbaDAMfAHuB1diXfX9+vMV8c13uAe4oKTDACDAFnAJm0jhJ0jjpKrBjDRAA+3Nt+zm9bPWy903dZbpFXuRdSpsmcAybddvaO0dh8HcUBhPAMHAVNkMvBXZEYfB7FAbvA3s6PaiDb4tnozD4YbEAlTZ7lDZjXeYwjl1ebgJuFJk8v0vfPBe46x+5tt+AFQXt/cZZiKqzGBaKvNnd3wBcB9zSMihttihtDittTroPIcKWxBHgxygM5nPjzOQf0MW3xU9lJtUijZPngE3Ar8ADwLTI5NoCrn+6a160izgtai97XxTJxk5ClfXLs2BNjsKgCXyhtHkeGFfa7AWuBl4AbgO+j8LgH6WNcr6zwBVKm+Gc0GuAaQClzTVdfP+bR7cAozC4vdck0zg5IjJ5CLtZ3A48BjzRw20G+AtYB3zq2tYBBwva+4qzSgGr+uP1Ojbb7sSuS/PYI8Qypc02rJAA32BL2DNKmwuVNqNAfrLdfCtBZHJKZPJ6YDmwCriZHpsugDROTgHvATtEJleKTN6KrQjvFLGfLe1CFS3TZfw6ihyFgQFeBZ52O+GdwJfAYexx4qDrN4/dOG3EruUPA+/mxlnUt0LedLEmwMfAAeDlllFkckxksglsBR4RmWy6MzXAk8DPwFEX91Ntx6Ne9kpYinX4f4nIZENk8uJBx1GU5mzSLLNrLuPn/10PgEEdpTw1UmcWewZE3Znsy3XN+FJ9DuBF9iwJ/wLFQe096aBD1gAAAABJRU5ErkJggg==', 'LR Radar': 'iVBORw0KGgoAAAANSUhEUgAAAKgAAAAYCAYAAABugbbBAAAEHElEQVR4nO2ZT2gdRRzHPzGpl7H+o7A1ttBF0bJ6KG0PoojelKoY8VAUqgdBrXUFl/rn4qEa5YFxPawY/IeRBCUHMeKlRfBgEfEvtaYrlNKJ1IaMitQ/o5YSnoedR5e4eW/evoTspvOB8Hjz+30nv935vpnZWXA4HA6Hw+FwVJnmbNhcbbrzyvwDR/Wossl60TmDOiqNM+gqoOqzYC+6ShtUKj0ilW6sdB2OlWMAQCo9DTR8T0wsTDCxa8zXX4FPgEd9T/xS1GG3+VUkSpMG0IiD8NSC9ingTvP1tTgIH87F1gJvAHcAp4DhOAhHbeNlqcMs2ItuwDJvl++JCan0RmASaAAPLGF+JYjSZBuQANuBnVGavAiMxkF2c+MgHDJ5r/D/excDHnAFsBn4KEqT6TgID1rGu6Zo0Iva+gaTvjrqwN6gAPieOCGV/hC4u2y+VPprYBtwGvgO2O174lsTC4C3yQbwM7IZeNZSOwe8BNwPrPc9sa6bazNMAG8BnwPjZD+qy/I1FBGlyRrgHmBHHIRzwFyUJpOmloOd4iXqtKZo0Ouk62oPKpXeAAwBX5XN9z2x3fdEH3AJMAZMSqX7pdL9wAfAAWAjmVHuzfe3mDaXchdwW0lzAgwCU8AZYCYOwjAOwrbmNGwCBHAo13aIs1udTvGuqcsSXVbXwtag41LpJnCCbPba22u+74l/fE+MAv3AlWQz46XAPt8Tf/ieeB/YX9R5gbbFs74nflysKKn0fqn0cJu6R8i2JDcA10dpcn67i8xxgfn8M9f2O7DWMt5tnVZUZRbsRWdr0F0m9zrgWuCmsvlS6d1S6aNS6dPGxD7ZMjoI/OR7Yj7Xz0y+0zbaFictr6eQOAifA3YCvwH3AdNRmmy2kP5lPvOGu4izhuwU7wqbWalo0Ouiy2O9B/U90QS+kEo/D4xIpQ+YNut84CrgBeAW4LDviX+l0tLUMQtcLpXuz5l0EzANIJW+uo22Rdsb4nvi1k7XGQfhsShNfiB7sHsCeAR4rINsBvgb2AJ8atq2AEcs413VWQUTLacuT5lz0NfJZq3bS+QLYJ7smGVAKr2XzIQA35Ate89IpS+USg8B+YFqp10SojSZitJkK7AG2ADcSIcHJIA4CM8A7wH7ojRZH6XJzWQz8Ts28V5ZOOi2S20ddHmDjkulm7m/sSKB7wkNvAo8ZVNUPt88cY8BXwJHyY5cjpi8ebKHnB1ke9cHgXdz/SyqXULeNLWGwMfA98DLrWCUJsNRmjSBPcBDUZo0zZkpwOPAz8BxU/eTC46QOsWXhCrtH5dD5yA7qI/S5OKVrsOW5mzYLPO0XAddpV91OjpTl2Oj5X6TdE4RB+HTK11Dt9RliXZL+zlGXWbCsjq3xNeYupis17dJjppSF6M5gzpWLf8BowiXXjQSLSkAAAAASUVORK5CYII=', 'LR SAM': 'iVBORw0KGgoAAAANSUhEUgAAAIMAAAAYCAYAAADZPE7mAAAEP0lEQVR4nO2Zf4gVVRTHP1uaxM0KJK+KgRcDdSq0IgrLiiD6QT+2/ihU2q0MKmuKpl8QQVQbLptM4JSh/dpNSYQIxZQsCskKoqCNtrFAvIaydVPCpW5h/vH6Y+a5l9fsvpnX27cbzQcey7vne+47O+fMOffNg5KSkpKSkpL/OpVBvzLWfic08gElraUVhQBlMZQ4lMUwwWlVV4CyGEocJgFoYweAbiXFxlpBajs7fXsY+Bh4QElxKGtDbeyFwAvA+al+E7BKSfF7jW4XsBCYoaQ4WvN5HjBXSaGd9c+AxcB5Sor+Rv5ZgCCOuoHu0POP1KxvAW5K364LPf9exzYVeBW4ATgCdIWe/0pee6O0sitA/s5wu5KijSTBZwLdWSJt7BRgO/BRqrsMGAJuqdHNAS4CDHBjxlZ7gDsc/TxgOnA0Q5uLII4uCOLocyAAvg7iaGUQR21Ve+j57aHntwEvZ7iHgATmAsuBniCOlhSwFyYroZVBv1L7apYfFBwTSooDwFbg3JEkwBlAj5JiSElxUEnRo6R4q0bXAewE+oDOjH36gA5tbDVZdwG9RWLNYCPwLhABNwMLgJn1nII4mgwsBZ4OPf/n0PN3AZurcdezjyVts4aLuRl+hYpBGzsbaAe+HEHyI8ndvkobO89JZi0dJBdsM3C1NlbW2Pele12pjT2R5G7rKxJrBrOALcAxYH/o+X7o+YM5/OYAAuh31voZHp317IVp9XiokrcYNmhjK8ABklb9aJZISfEncAUwA9gNHNbGrtfGTqtqtLGXkiRmm5JiH8mFW5ax3ZvAncC1wICS4uBoAWpj39fGdo0iWU1SfJcAi4M4Omm0/RxOSf/+5qwNAVNz2ovGmYtmdwUocGZItRcD5wCXjyRUUnyvpFimpJhOci44C3jdkXQC250D5Ugt9R3gKuAh4I2ccY5I6PnPAbcBv5J0poEgjubncK3G6Sb3NIaTX89eiDx3d1ZCG/VzmVRvgypKigrwhTb2eWC1NnZnujaaz15t7FrgJQBt7MnArcCpaac5jjZ2oZLiG8fXamPfIxlLW3PEd009Tej5e4M42kNyAH4MWAk8WMdtP/AHsAj4JF1bBHyX014ozmYmuujYyF0MDuuBp4DrgW2uQRu7AHgSWENyMWYC9wFfpZJ2kjEzRUnxl+P3Acnd+oi7n5JiBbCigRj/QfrV8VlgMjAbWALsqOcXev6xII42Ac8EcbQUmE/SYa7LY/+31CY073hoxM8dExu0sRXn1ZvloKSwwFrgiQzzDyQXeA1wCPgU+Am4O7V3Ar1uIaSsA5ZrYxspzry8RhK3D3wIfAu8WDUGcdQVxFEFuB+4J4ijSvpMAuBh4BeSg+3bwOOh5+929q5nbwpjcU74XxPEUXcQR6ePdxx5Ge25QLP9ysfRE5jx+opZMgFpZVcomeBM1N8mSlpMOSJKjlMWQ8m48jcBFAgJzuKGlQAAAABJRU5ErkJggg==', 'CIWS': 'iVBORw0KGgoAAAANSUhEUgAAAGcAAAAYCAYAAADnNePtAAAD70lEQVR4nO3YXawccxjH8c+pIjIapNFpGxKDRC2Rhgjpi4graSKEhCDhAkWZCyMEqQtUWtWsxHiJl/aGeIkLbogEkZ6iEYREDdIydXMYSlqMhkaOi9nV7WbPObtbrZL5JpPdfZ55dn7/+c0z+8xSU1NTU1MzPONj8Xi/+07bl0Jq9mQQY6jNOaCpzdlPDNo11OYc0Exvv8mL8hLchtOwA+9geRQGX+ZFuQmrojB4Ni/KO7E4CoMlHbWbsblH7O4oDF7Ii/JMPIjTsQ3PY2UUBr8OKzzJ0lVY1WzE27vir+DC1scnmo34ho7cDDyFC7AdK5qN+PF+88MyTNfQ6py8KJdiHZ5EpDLoOdzco2YUC/OiPKhVOxsH4/Su2IkYzYvyULyKt3AszlGZf/EwgpMsPSPJ0veQ4OMkS5clWTrSzjcb8UXNRjyCR3uUNxHiBFyJ1UmWLh4gPzC9jBkfi8e7t1610/OiPAwP4NYoDNZ15F5ubd18oDJjPj5Sney3cXxX7KsoDMbyopyHo7E6CoPfVcasHmqlFc9iLTbiGVyDORibrCjJ0oNxOZY0G/F3+C7J0hdxNTZMld8LvVMyMnf3xdXJNJyBI/FiP18UhcEfeF9lgNbrBtVtsDM22nr/DQqszIvypLwoewoZgLl4BbuwtdmI42YjntSYFschwCcdsU9wSp/5gRn2dtZmGmaijMLglwHq1tttxGKVORu6YushCoOdOBezW/tsy4vyybwoZ/b64rwoX8+LcsUkx16jupAWYkGSpYf0qfnw1mvnOndgRp/5QXX2xURdQ2XOjwjyouwpYgJGsSgvyqNwdBQGm/EeFrRip9rdOaIw+CIKgyuiMJiFs1S/R2sHXwrNRnwfLsNPuAqbkiyd10dpe/joXOcRdpsxVX4g+umayYyhMucj1WRy6QDH3qgSvhTvQhQGP6vu+0sxFoVB3qswCoMteAxnT5A/PwqD5ZMdvNmIt+Bz3ICXsKwPzVvxm+p3sc18fNZnfiCdI3PTke6tD417MD0Kg515Ud6BNXlR/qmarGARzovCIO4hbGdelB+qJqb7O1LvtGJvtgN5UZ6Mu/CwaqFzcCM+HFQsf4/K96qGkmNUt9DXpqprNuJdSZY+j3uSLL0c81QduKSf/N7S3Un9mDUNojB4AtepTto3+FQ1uTwySe16zFIZ0mZDKzbaEftSdfIexg+t/b/FtVOJm4CnVZ0X442W1ofaySRLVyRZOo6bcH2SpeOtZyK4Bd/ja9Wjwu3NRtw5iU2V/0cYpov+UyRZuirJ0iP/bR39MtnzzETUf9/sB/Z2pK7ZhwzTNTX7ib36b61m31F3zAFMbc7/lL8AoyWgQuQOg0wAAAAASUVORK5CYII='}
UPGRADE_ICON_DATA = {'Factory': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAABn0lEQVR4nO3VvWsVQRQF8F8kNhamUhTUWASERRQk2IggFnamUVsRRay2cLAU/A8WcSsFbWytFIlFtNDCQhsFBxGLFH484UUsREKEPIvdB2HdXTNgCsEDU8zce8+Ze+fODP/xNxFi+THEcpgSsylRYyLRf+MFegNCLLfgPE5iH/bUMQO8xUs8wrMiy1faOCZ7yKexgJkW8456HMMVXMb1Np6+Et3pIE9Cq0CI5XYcX7P0HPvxCUvYhsO4hHksdwl0lWhnY363yPI3IZYjKLJ8iCFe4FZfBl0CXxrzEGI5wOY+sjZ0dlGI5VMcbTGN8FrVQfO4X2T5zy6evkM+i9ixqYO4gHt4F2I520Xyp3swiVM4jSN+P5sxPmOmyPIfSQItgh+wFVdxUdVZY8wVWf6gGZP6VMBKkeU3VCVci91tzq1dFGJ5ALfxEI+xqCrD2D6FM42wpXULqDKbrce1em1VVdIJfGv4f1c9K+sW6BJtwzLOFVmelMErHMIJ1V3Yi12Yqu1f8R5PcLPI8sWEjXYjxHKw0T/aaqJ/ssAoVeDfxy9JrWawkl1U4wAAAABJRU5ErkJggg==', 'Hangars': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAuUlEQVR4nM2U2w2AMAhFxThTd+sE7tal6pdJgxe4aKryZeVxKFCWZbJIxnhvvZ/ftQjlu2YzykoawGaeBozlQefHgLsyHUDL1BJZwRjI9z2Isoz0LsB7uePZg5gAZi0wEAjI7JwIcgFYwb0x9ezWyGlvvXtjeuosyIYcaxFhH9IYEPm5PahFhOnBeFutN2/A5X710ZANGT0RHeN/qyK7Vc2S6JFFgfR/VGLYZARDzswohwCv8d54viYHLiCX67h8LbYAAAAASUVORK5CYII=', 'Logistics': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAlElEQVR4nO1Uyw3AIAiFpgu4gkN1SIdyBUewJxPSAGILSQ++kxJ4/AHY2PgKpJ+rtu5FXHJCAIDDi9AFV219NcszIojxLjmhuUTUUMqEk5kcSGV5OuV0kBNyJGMqZo5LTkht1Aw0ck7O6bk1mZJLAbHQRtMytiZPGsks2vBNXuoBjda60eEZiPV7c1m5fvzrmm6E4AYRi1BR37oFQAAAAABJRU5ErkJggg==', 'Ground Crew': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAo0lEQVR4nO1UMQ6AIAwsxo0HMPP/RzHzAGacSCpQKAUSSbwJbbnjjirA6VAjzc6HiJ+t0d39l5SceicSwETWaIVP3hNhO0jktfUyAQmGBHAcnPwBBqaIIuxFNRXR0jEdIcW4ew2trFOtJUoW8tmX9lUj4pLn9Zrb5h1w8271FQLc+aaQ7ycdWKMVV8z5ECkX3/pV/AJbUNz87JgCvL+L7Q7OxwMGE0vnbtHpjQAAAABJRU5ErkJggg=='}
UPGRADE_ATTRIBUTES = {"Power":"power_level", "Hangars":"hangar_level", "Factory":"factory_level", "Logistics":"logistics_level", "Ground Crew":"ground_crew_level", "Airfield":"level"}
AIRFIELD_UNLOCKS={int(level):tuple(items) for level,items in STATS['upgrades']['airfield_unlocks'].items()}
UNLOCK_LEVELS={item:level for level,items in AIRFIELD_UNLOCKS.items() for item in items}
AIRCRAFT_BUY_ORDER=tuple(sorted(('Fighter','Interceptor','Bomber','RQ-9B','AWACS','KC-49'),key=lambda kind:UNLOCK_LEVELS.get(kind,1)))

SAM_COLOR = '#b18aff'
CIWS_COLOR = '#ffd52a'
SAM_RANGE_NM = STATS['ground_units']['SAM']['range_nm']
AIRCRAFT_COLORS = (
    ('Blue','#438cff'),('Sky Blue','#87caff'),('Cyan','#56deef'),
    ('Teal','#42bdb3'),('Green','#72d693'),('Lime','#b4e46b'),
    ('Orange','#ff9a48'),('Amber','#ffc05a'),('Lemon','#ffe66d'),
    ('Red','#ef6262'),('Coral','#ff9689'),('Violet','#aa8aff'),
    ('Rose','#ee8aca'),('Pink','#ffc1dc'),('White','#dfe9f5'),
)
HARDPOINT_LOADOUTS = tuple(loadout_label(v) for v in ('Empty','2× AIM-9','1× AIM-120C','2× AGM-88','2× Sidearm'))
BAY_LOADOUTS = tuple(loadout_label(v) for v in ('Empty','4× 250 lb Bomb','2× 500 lb Bomb','1× 1,000 lb Bomb','1× 2,000 lb Bomb'))
DEFAULT_LOADOUTS={k:([loadout_label(v) for v in s['hardpoints']],[loadout_label(v) for v in s['bays']]) for k,s in STATS['default_loadouts'].items()}
AIRCRAFT_DESCRIPTIONS={
    'Fighter':'A versatile aircraft for air combat and ground strikes. Carries missiles and one bomb bay.',
    'Bomber':'Carries the largest bomb load for attacking ground targets. Slower than fighters, with two missile hardpoints for defense.',
    'Interceptor':'The fastest aircraft, built to catch and engage airborne threats. Carries missiles with a shorter fuel endurance.',
    'AWACS':'Provides long-range visual air contacts in every direction. Unarmed and designed to support the rest of your force.',
    'KC-49':f"An airborne tanker that refuels nearby compatible aircraft. Form up on it to replenish fuel. Carries {AIRCRAFT_TYPES['KC-49']['fuel']:,} fuel units, shared between its own flight and refueling. Endurance and range assume no fuel is transferred.",
    'RQ-9B':'A slow, unarmed scout with 100 NM visual coverage. Finds air and ground targets while using very little fuel.',
}

def aircraft_mil_performance_text(spec):
    speed=spec['speed']*STATS['speed_modes']['Mil']['speed_multiplier']
    burn=spec['burn']*STATS['speed_modes']['Mil']['burn_multiplier']
    hours=spec['fuel']/burn/3600 if burn else math.inf
    if math.isfinite(hours):
        total_minutes=round(hours*60);h,m=divmod(total_minutes,60)
        endurance=f'{h}h {m:02d}m';distance=f'{hours*speed:,.0f} NM'
    else:endurance='Unlimited';distance='Unlimited'
    return f'Mil Speed: {speed:g} knots\nEndurance (Mil): {endurance}\nMax Range (Mil): {distance}'



@dataclass
class Airfield:
    name: str = 'Airfield'
    x: float = 0.
    y: float = 0.
    runway_length: float = None
    runway_width_ft: float = None
    level: int = 1
    power_level: int = 1
    hangar_level: int = 1
    factory_level: int = 1
    logistics_level: int = 1
    ground_crew_level: int = 1
    health: float = None
    category: str = 'Ground'
    enemy: bool = False

    def __post_init__(self):
        if self.health is None:self.health=self.max_health
        if self.runway_length is None:self.runway_length=self.stats['runway_length_nm']
        if self.runway_width_ft is None:self.runway_width_ft=self.stats['runway_width_feet']

    @property
    def stats(self):return ground_stats('Airfield',self.enemy)

    @property
    def min_engagement_range_nm(self):return self.stats.get('min_engagement_range_nm',0)

    @property
    def max_health(self):return self.stats['health']

    @property
    def alive(self):return self.health>0

    @property
    def visual_range_nm(self):
        stats=self.stats
        return stats['visual_range_nm']+(self.level-1)*stats['visual_range_per_upgrade_nm']

    def visual_detects(self,x,y):
        return self.alive and math.hypot(x-self.x,y-self.y)<=self.visual_range_nm

    @property
    def runway_width(self):
        return self.runway_width_ft / FEET_PER_NM

    def runway_corners(self):
        half_width, half_length = self.runway_width/2, self.runway_length/2
        return [(self.x-half_width,self.y-half_length),
                (self.x+half_width,self.y-half_length),
                (self.x+half_width,self.y+half_length),
                (self.x-half_width,self.y+half_length)]


@dataclass
class Building:
    id: int
    x: float
    y: float
    width: float = .4
    length: float = .4
    health: float = None
    category: str = 'Ground'

    def __post_init__(self):
        if self.health is None:self.health=self.max_health

    @property
    def max_health(self):return 100

    @property
    def alive(self):return self.health>0

    @property
    def stats_key(self):
        if isinstance(self,PAC3):return 'PAC-3'
        if isinstance(self,Flak):return 'Flak'
        if isinstance(self,CIWS):return 'CIWS'
        if isinstance(self,SAAW):return 'SAAW'
        if isinstance(self,Radar):return 'EWR' if self.early_warning else 'LR Radar' if self.long_range else 'Radar'
        return 'LR SAM' if self.long_range else 'SAM'

    @property
    def stats(self):return ground_stats(self.stats_key,getattr(self,'enemy',False))

    @property
    def min_engagement_range_nm(self):return self.stats.get('min_engagement_range_nm',0)

    @property
    def price(self):return 0 if getattr(self,'enemy',False) else self.stats['price']

    def corners(self):
        return [(self.x+dx*self.width/2,self.y+dy*self.length/2)
                for dx,dy in ((-1,-1),(1,-1),(1,1),(-1,1))]


@dataclass
class Radar(Building):
    category: str = 'Radars'
    def __post_init__(self):
        super().__post_init__()
        if self.range_points is None:self.range_points=self.stats['default_range_points'] if self.early_warning else 0

    long_range: bool = False
    enemy: bool = False
    enabled: bool = True
    sweep_angle: float = 0.
    early_warning: bool = False
    range_points: int = None
    bearing: float = 0.
    desired_bearing: float = 0.
    auto_rotate: bool = False
    rotation_direction: int = 1
    track_target: object = None
    previous_tracking_mode: object = None

    def start_tracking(self,target):
        if not self.early_warning or not target.alive or not getattr(target,'enemy',False):return False
        if self.track_target is None:self.previous_tracking_mode=(self.desired_bearing,self.auto_rotate,self.rotation_direction)
        self.track_target=target;return True

    def stop_tracking(self):
        self.track_target=None
        if self.previous_tracking_mode is not None:
            self.desired_bearing,self.auto_rotate,self.rotation_direction=self.previous_tracking_mode
            self.previous_tracking_mode=None

    @property
    def max_health(self):return self.stats['health']

    @property
    def radar_emitting(self):return self.alive and self.enabled

    @property
    def range_nm(self):
        return self.range_points*self.stats['range_per_point_nm'] if self.early_warning else self.stats['range_nm']

    @property
    def width_points(self):return self.stats['configuration_points']-self.range_points if self.early_warning else 0

    @property
    def radar_angle_deg(self):return self.width_points*self.stats['width_per_point_degrees'] if self.early_warning else 360.

    def radar_detects(self,x,y):
        if not self.radar_emitting or not self.min_engagement_range_nm<=math.hypot(x-self.x,y-self.y)<=self.range_nm:return False
        if not self.early_warning:return True
        angle=math.atan2(x-self.x,y-self.y)
        return abs((angle-self.bearing+math.pi)%math.tau-math.pi)<=math.radians(self.radar_angle_deg)/2+1e-9

    def shift_points(self,delta):
        if not self.early_warning:return False
        value=self.range_points+delta
        if not 1<=value<self.stats['configuration_points']:return False
        self.range_points=value;return True

    def advance_bearing(self,seconds):
        if not self.early_warning or not self.alive:return
        step=math.radians(self.stats['rotation_degrees_per_minute'])*max(0,seconds)/60
        if self.track_target is not None:
            if not self.track_target.alive:self.stop_tracking()
            else:self.desired_bearing=math.atan2(self.track_target.x-self.x,self.track_target.y-self.y)%math.tau
        if self.auto_rotate and self.track_target is None:
            if self.enabled:self.bearing=(self.bearing+step*self.rotation_direction)%math.tau
            self.desired_bearing=self.bearing
            return
        error=(self.desired_bearing-self.bearing+math.pi)%math.tau-math.pi
        self.bearing=(self.bearing+max(-step,min(step,error)))%math.tau

    @property
    def power(self):
        return 0 if self.enemy else self.stats['power']

    @property
    def name(self):
        return ('Enemy ' if self.enemy else '')+('Early Warning Radar' if self.early_warning else 'LR Radar' if self.long_range else 'Radar')


@dataclass
class SAMLauncher(Building):
    missile_kind: str = 'MIM-23'
    def __post_init__(self):
        super().__post_init__()
        if self.ammo is None:self.ammo=self.stats['ammo']
        if self.ammo_capacity is None:self.ammo_capacity=self.stats['ammo']

    ammo: int = None
    ammo_capacity: int = None
    width: float = .32
    length: float = .32
    enemy: bool = False
    preferred_targets: set = field(default_factory=lambda: {"Suicide Drones", "Bombers", "Fighters", "ICBMs"})
    heading: float = 0.
    target_heading: float = 0.
    next_look: float = 0.
    long_range: bool = False

    @property
    def max_health(self):return self.stats['health']

    @property
    def range_nm(self):
        return self.stats['range_nm']

    @property
    def power(self):
        return 0 if self.enemy else self.stats['power']

    @property
    def name(self):
        return ('Enemy ' if self.enemy else '')+('LR SAM' if self.long_range else 'SAM Launcher')


    def accepts_target(self, kind, x, y, *, on_datalink):
        return (on_datalink and kind in self.preferred_targets
                and self.min_engagement_range_nm<=math.hypot(x-self.x,y-self.y)<=self.range_nm)


@dataclass
class PAC3(SAMLauncher):
    def __post_init__(self):
        if self.enemy:raise ValueError('PAC-3 is a player-only unit')
        super().__post_init__()

    missile_kind: str = 'PAC-3 MSE'
    enabled: bool = True
    preferred_targets: set = field(default_factory=lambda: {'Bombers','Fighters','ICBMs'})
    bearing: float = 0.
    desired_bearing: float = 0.

    @property
    def name(self):return 'PAC-3 SAM Launcher'

    @property
    def radar_angle_deg(self):return self.stats['cone_width_degrees']

    def radar_detects(self,x,y):
        if not self.alive or not self.enabled or math.hypot(x-self.x,y-self.y)>self.range_nm:return False
        error=(math.atan2(x-self.x,y-self.y)-self.bearing+math.pi)%math.tau-math.pi
        return abs(error)<=math.radians(self.radar_angle_deg)/2+1e-9

    def accepts_target(self,kind,x,y,*,on_datalink):
        return (on_datalink and kind in self.preferred_targets
                and math.hypot(x-self.x,y-self.y)>=self.stats['min_engagement_range_nm']
                and self.radar_detects(x,y))

    def advance_bearing(self,seconds):
        if not self.alive:return
        step=math.radians(self.stats['rotation_degrees_per_second'])*max(0,seconds)
        error=(self.desired_bearing-self.bearing+math.pi)%math.tau-math.pi
        self.bearing=(self.bearing+max(-step,min(step,error)))%math.tau
        self.heading=math.pi/2-self.bearing


@dataclass
class SAAW(SAMLauncher):
    category: str = 'Radars'
    def __post_init__(self):
        super().__post_init__()
        for key in ('gun_range_nm','gun_ammo','gun_ammo_capacity'):
            if getattr(self,key) is None:setattr(self,key,self.stats['gun_ammo' if key=='gun_ammo_capacity' else key])

    enemy: bool = True
    missile_kind: str = 'SM1'
    enabled: bool = True
    gun_range_nm: float = None
    gun_ammo: int = None
    gun_ammo_capacity: int = None
    shot_timer: float = 0.
    attack_target: object = None
    preferred_targets: set = field(default_factory=lambda: {'Fighters','Bombers','Suicide Drones','Missiles','Bombs','ICBMs'})

    @property
    def radar_range_nm(self):return self.stats['radar_range_nm']

    def radar_detects(self,x,y):
        return self.radar_emitting and math.hypot(x-self.x,y-self.y)<=self.radar_range_nm

    @property
    def radar_emitting(self):return self.alive and self.enabled

    @property
    def range_nm(self):return self.stats['range_nm']

    @property
    def max_health(self):return self.stats['health']

    @property
    def power(self):return 0 if self.enemy else self.stats['power']

    @property
    def name(self):return 'Enemy SAAW' if self.enemy else 'SAAW'


def dollars(value):
    return f'${value:,.0f}' if value==int(value) else f'${value:,.2f}'


def upgrade_cost(level):
    return STATS['upgrades']['prices']['Power'][level-1]


@dataclass
class CIWS(Building):
    category: str = 'Radars'
    enabled: bool = True
    def __post_init__(self):
        super().__post_init__()
        for key in ('range_nm','visual_range_nm','power','ammo','ammo_capacity'):
            if getattr(self,key) is not None:continue
            value=0 if key=='power' and self.enemy else self.stats.get('visual_range_nm',0) if key=='visual_range_nm' else self.stats['ammo' if key=='ammo_capacity' else key]
            setattr(self,key,value)

    enemy: bool = False
    preferred_targets: set = field(default_factory=lambda: {'Fighters','Bombers','Suicide Drones','Missiles','Bombs','ICBMs'})
    shot_timer: float = 0.
    attack_target: object = None
    range_nm: float = None
    visual_range_nm: float = None
    power: int = None
    ammo: int = None
    ammo_capacity: int = None
    name: str = 'CIWS'
    heading: float = 0.
    target_heading: float = 0.
    next_look: float = 0.

    @property
    def max_health(self):return self.stats['health']

    @property
    def radar_range_nm(self):return self.stats.get('radar_range_nm',0)

    @property
    def radar_emitting(self):return self.alive and self.enabled and self.radar_range_nm>0

    def radar_detects(self,x,y):
        return self.radar_emitting and math.hypot(x-self.x,y-self.y)<=self.radar_range_nm

    def visual_detects(self,x,y):
        return self.alive and self.visual_range_nm>0 and math.hypot(x-self.x,y-self.y)<=self.visual_range_nm


@dataclass
class Flak(CIWS):
    category: str = 'Ground'
    power: int = None
    range_nm: float = None
    visual_range_nm: float = None
    ammo: int = None
    ammo_capacity: int = None
    shot_kind: str = 'flak'
    enabled: bool = True
    name: str = 'Flak Cannon'
    preferred_targets: set = field(default_factory=lambda: {'Fighters','Bombers','Suicide Drones','ICBMs'})

    @property
    def radar_range_nm(self):return 0.

    def radar_detects(self,x,y):
        return False

    @property
    def radar_emitting(self):return False

    @property
    def max_health(self):return self.stats['health']


class GameMapPage(ProgressUI,PlayerSiloUI,ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app = app
        self.airfield = Airfield()
        self.logistics=LogisticsFleet();self.logistics.sync(LOGISTICS_LEVELS[self.airfield.logistics_level-1],self.airfield)
        self.center = [self.airfield.x,self.airfield.y]
        self.view_width = 10.
        self.grid_opacity=.30;self.grid_opacity_job=None
        self.grid_photo=None;self.grid_photo_key=None;self.grid_labels=[]
        self.playing = False
        self.run_started=False;self.run_result=None
        self.show_bands=STATS['campaign']['show_bands']
        self.play_speed = 1
        self.elapsed = 0.
        self.active = False
        self.job = None
        self.draw_job = None
        self.last_tick = time.monotonic()
        self.drag = None
        self.selected = self.airfield
        self.money = STATS['economy']['starting_money']
        self.aircraft = {}
        self.aircraft_drag=None
        self.operations=AirOperations()
        self.game_audio=GameAudio(lambda:(self.app.settings.sound_effects,self.app.settings.sound_volume))
        self.game_audio.set_muted(getattr(self.app,'game_audio_muted',False))
        self.combat=CombatWorld();self.operations.combat=self.combat
        self.player_silos=self.combat.player_silos;self.placing_player_silo=False;self.silo_target_picker=None
        self.combat.sound_callback=self.play_game_sound
        self.combat.ground_targets=[self.airfield]
        self.campaign=Campaign(self.combat,self.airfield,self.spawn_campaign_ground)
        self.combat.campaign=self.campaign
        self.rwr=RWR();self.log_entries=[]
        self.factory_spawn_kind="Factory"
        self.placing_factory=False
        self.debug_kill_mode=False
        self.placing_enemy=False
        self.enemy_spawn_kind='Fighter'
        self.left_menu="Build"
        self.movement_mode=None
        self.pending_path=[]
        self.map_aircraft_buttons={}
        self.aircraft_status_job=None;self.aircraft_button_health={};self.aircraft_damage_times={}
        self.last_inspector_update=0.
        self.follow_enabled=False
        self.radar_overlay=True
        self.point_defence_overlay=True;self.point_defence_key=None;self.point_defence_paths=[];self.point_defence_items=[];self.enemy_point_defence_paths=[];self.enemy_point_defence_items=[];self.selected_point_defence_items=[];self.placement_point_defence_items=[]
        self.sam_overlay=True
        self.sam_coverage_key=None;self.sam_coverage_paths=[];self.sam_coverage_items=[];self.selected_sam_coverage_items=[];self.enemy_sam_coverage_items=[]
        self.visual_overlay=True;self.visual_coverage_items=[]
        self.visual_coverage_key=None;self.visual_coverage_paths=[];self.visual_coverage_updated=-1.
        self.selected_range_items={'line':[],'oval':[]};self.selected_range_key=None
        self.placement_radar_items=[];self.radar_preview_job=None
        self.ping_sweep_time=None
        self.see_all=False
        self.last_shortcut=(None,0.)
        self.held_shortcuts=set()
        self.shortcut_release_jobs={}
        self.aircraft_slot = 0
        self.aircraft_menu_open = False
        self.sams = []
        self.sam_glyphs = {}
        self.ciws_glyphs = {}
        self.random = random.Random()
        self.ciws=[];self.placing_ciws=False;self.placing_gun_kind='CIWS'
        self.radars = []
        self.radar_sweeps = {}
        self.coverage_key = None
        self.coverage_paths = []
        self.coverage_updated = -1.
        self.coverage_items=[];self.enemy_radar_coverage_items=[]
        self.selected_coverage_items=[]
        self.last_background_draw=0.
        marker=MarkerStyle(aircraft_marker(0,1))
        self.aircraft_vertices=marker.get_path().transformed(marker.get_transform()).vertices[:-1]
        self.trail_palette={} 
        self.placing_radar = False
        self.placing_sam = False
        self.pointer = None
        self.placing_lr = False
        self.placing_ewr = False
        self.placing_pac3 = False
        self.ewr_track_picker=None

        body=ttk.Panedwindow(self,orient='horizontal')
        body.pack(fill='both',expand=True,pady=(4,0))
        left=ttk.Frame(body,width=310)
        menu_row=ttk.Frame(left);menu_row.pack(fill='x',pady=(0,5))
        self.left_menu_buttons={}
        style=ttk.Style(self)
        style.configure('GameSell.TButton',background='#b63f46',foreground='#ffffff')
        style.map('GameSell.TButton',background=[('active','#d34b53'),('pressed','#9d343b')],foreground=[('disabled',MUTED)])
        style.configure('GamePurchaseReady.TButton',background=PANEL,foreground=TEXT,bordercolor='#438cff',borderwidth=2,relief='solid')
        style.map('GamePurchaseReady.TButton',background=[('active',PANEL),('pressed',PANEL)],bordercolor=[('active','#438cff'),('pressed','#438cff')])
        style.configure('GameUpgradeReady.TButton',background=PANEL,foreground=TEXT,bordercolor='#438cff',borderwidth=2,relief='solid',anchor='w',padding=(8,4))
        style.map('GameUpgradeReady.TButton',background=[('active',PANEL),('pressed',PANEL)],bordercolor=[('active','#438cff'),('pressed','#438cff')],foreground=[('disabled',MUTED)])
        style.configure('GameLockedBuild.TButton',background=PANEL,foreground=MUTED)
        style.map('GameLockedBuild.TButton',background=[('disabled',PANEL)],foreground=[('disabled',MUTED)])
        for i,name in enumerate(('Airfield','Build','Hangar','Unit List','Log','Objectives')):
            button=ttk.Button(menu_row,text=name,width=10 if name=='Objectives' else 7,command=lambda n=name:self.show_left_menu(n))
            button.grid(row=i//3,column=i%3,sticky='ew',padx=1,pady=1);self.left_menu_buttons[name]=button
        for column in range(3):menu_row.columnconfigure(column,weight=1)
        self.sidebar=ttk.Panedwindow(left,orient='vertical',width=310)
        self.sidebar.pack(fill='both',expand=True)
        right=ttk.Frame(body,padding=(10,0,0,0))
        self.right_panel=right
        body.add(left,weight=0);body.add(right,weight=1)
        self.menu_host=ttk.Frame(self.sidebar)
        self.build_scroll_panel,build,self.build_scroll_canvas=self.create_scroll_menu()
        self.build_panel=build
        self.build_scroll_panel.pack(fill='both',expand=True)
        inspector_host=ttk.Frame(self.sidebar)
        self.inspector_host=inspector_host
        self.inspector_sash=None
        inspector_canvas=tk.Canvas(inspector_host,background=BG,highlightthickness=0,width=270,height=250)
        inspector_bar=ttk.Scrollbar(inspector_host,orient='vertical',command=inspector_canvas.yview)
        inspector_bar.pack(side='right',fill='y');inspector_canvas.pack(side='left',fill='both',expand=True)
        inspector_canvas.configure(yscrollcommand=inspector_bar.set)
        inspector=ttk.Frame(inspector_canvas,padding=10)
        inspector_window=inspector_canvas.create_window(0,0,window=inspector,anchor='nw')
        inspector.bind('<Configure>',lambda e:inspector_canvas.configure(scrollregion=inspector_canvas.bbox('all')))
        inspector_canvas.bind('<Configure>',lambda e:inspector_canvas.itemconfigure(inspector_window,width=e.width))
        def scroll_inspector(event):
            if event.delta:inspector_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
            return 'break'
        inspector_canvas.bind('<MouseWheel>',scroll_inspector)
        self.sidebar.add(self.menu_host,weight=1);self.sidebar.add(inspector_host,weight=1)
        ttk.Label(build,text='BUILD MENU',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        self.cash_text=tk.StringVar(value=dollars(self.money))
        self.build_power_images={n:self.power_image(n) for n in (1,2,4)}
        self.build_button_images={key:self.build_unit_image(key) for key in ('Radar','LR Radar','EWR','SAM','LR SAM','PAC-3','CIWS','Flak','Missile Silo')}
        self.upgrade_icons={kind:tk.PhotoImage(master=self,data=data) for kind,data in UPGRADE_ICON_DATA.items()}
        self.upgrade_icons["Power"]=self.build_power_images[1]
        self.sam_button=ttk.Button(build,text='',image=self.build_button_images['SAM'],compound='center',command=self.toggle_sam)
        self.radar_button=ttk.Button(build,text='',image=self.build_button_images['Radar'],compound='center',command=self.toggle_radar)
        self.lr_radar_button=ttk.Button(build,text='',image=self.build_button_images['LR Radar'],compound='center',command=lambda:self.toggle_radar(True))
        self.lr_sam_button=ttk.Button(build,text='',image=self.build_button_images['LR SAM'],compound='center',command=lambda:self.toggle_sam(True))
        self.ciws_button=ttk.Button(build,text='',image=self.build_button_images['CIWS'],compound='center',command=self.toggle_ciws)
        self.flak_button=ttk.Button(build,text='',image=self.build_button_images['Flak'],compound='center',command=lambda:self.toggle_ciws('Flak'))
        self.ewr_button=ttk.Button(build,image=self.build_button_images['EWR'],compound='center',command=lambda:self.toggle_radar(early_warning=True))
        self.pac3_button=ttk.Button(build,image=self.build_button_images['PAC-3'],compound='center',command=lambda:self.toggle_sam(pac3=True))
        self.init_player_silo_controls(inspector,build)
        build_buttons=(('SAM',self.sam_button),('Radar',self.radar_button),('LR Radar',self.lr_radar_button),('LR SAM',self.lr_sam_button),('CIWS',self.ciws_button),('Flak',self.flak_button),('EWR',self.ewr_button),('PAC-3',self.pac3_button),('Missile Silo',self.player_silo_button))
        for index,(kind,button) in enumerate(sorted(build_buttons,key=lambda item:UNLOCK_LEVELS.get(item[0],1))):
            button.pack(fill='x',pady=(6 if index else 0,0))
        self.cancel_button=ttk.Button(build,text='Cancel Placement',command=self.cancel_placement)
        self.airfield_scroll_panel,self.airfield_panel,self.airfield_scroll_canvas=self.create_scroll_menu()
        self.airfield_menu_title=tk.StringVar(value=f'Airfield Level {self.airfield.level}')
        ttk.Label(self.airfield_panel,textvariable=self.airfield_menu_title,font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        self.airfield_upgrade_buttons={}
        for kind in ('Power','Hangars','Factory','Logistics','Ground Crew'):
            button=ttk.Button(self.airfield_panel,image=self.upgrade_icons[kind],compound='left',style='GameUpgrade.TButton',command=lambda k=kind:self.upgrade(k))
            button.pack(fill='x',pady=3);self.airfield_upgrade_buttons[kind]=button
        ttk.Label(self.airfield_panel,text='Income',font=('Helvetica',10,'bold')).pack(anchor='w',pady=(14,2))
        self.airfield_menu_text=tk.StringVar()
        income_row=ttk.Frame(self.airfield_panel);income_row.pack(anchor='w',pady=(0,8))
        ttk.Label(income_row,textvariable=self.airfield_menu_text,foreground='#72d693').pack(side='left')
        ttk.Label(income_row,text='/min').pack(side='left')
        ttk.Label(self.airfield_panel,text='Ground crew',font=('Helvetica',10,'bold')).pack(anchor='w',pady=(6,2))
        self.crew_text=tk.StringVar()
        ttk.Label(self.airfield_panel,textvariable=self.crew_text,justify='left').pack(anchor='w',pady=(0,10))
        self.airfield_resources=tk.Canvas(self.airfield_panel,background=BG,highlightthickness=0,height=32)
        self.airfield_resources.pack(fill='x',pady=(4,0))
        self.airfield_level_button=ttk.Button(self.airfield_panel,command=lambda:self.upgrade('Airfield'))
        self.airfield_level_button.pack(fill='x',pady=(14,3))
        self.airfield_unlock_text=tk.StringVar()
        self.unlock_hosts=[ttk.Frame(self.airfield_panel)]
        self.unlock_hosts[0].pack(fill='x',pady=(0,8))
        self.debug_scroll_panel,self.debug_panel,self.debug_scroll_canvas=self.create_scroll_menu()
        ttk.Label(self.debug_panel,text='DEBUG',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        ttk.Button(self.debug_panel,text='+$5,000',command=self.debug_add_money).pack(fill='x',pady=(0,10))
        self.factory_button=ttk.Button(self.debug_panel,text=f'Spawn Enemy Factory · {STATS["enemy_ground_units"]["Factory"]["health"]:g} HP',command=self.toggle_factory)
        self.factory_button.pack(fill='x')
        self.bunker_button=ttk.Button(self.debug_panel,text=f'Spawn Enemy Bunker · {STATS["enemy_ground_units"]["Bunker"]["health"]:g} HP',command=lambda:self.toggle_factory('Bunker'))
        self.bunker_button.pack(fill='x',pady=(6,0))
        self.enemy_button=ttk.Button(self.debug_panel,text='Spawn Enemy Fighter',command=self.toggle_enemy)
        self.enemy_button.pack(fill='x',pady=(6,0))
        self.enemy_interceptor_button=ttk.Button(self.debug_panel,text='Spawn Enemy Interceptor',command=lambda:self.toggle_enemy('Interceptor'))
        self.enemy_interceptor_button.pack(fill='x',pady=(6,0))
        self.drone_button=ttk.Button(self.debug_panel,text='Spawn Enemy Suicide Drone',command=lambda:self.toggle_enemy('Suicide Drone'))
        self.drone_button.pack(fill='x',pady=(6,0))
        self.enemy_bomber_button=ttk.Button(self.debug_panel,text='Spawn Enemy Bomber',command=lambda:self.toggle_enemy('Bomber'))
        self.enemy_bomber_button.pack(fill='x',pady=(6,0))
        self.enemy_radar_button=ttk.Button(self.debug_panel,text='Spawn Enemy Radar',command=lambda:self.toggle_enemy('Radar'))
        self.enemy_radar_button.pack(fill='x',pady=(6,0))
        self.enemy_lr_radar_button=ttk.Button(self.debug_panel,text='Spawn Enemy LR Radar',command=lambda:self.toggle_enemy('LR Radar'))
        self.enemy_lr_radar_button.pack(fill='x',pady=(6,0))
        self.enemy_ciws_button=ttk.Button(self.debug_panel,text='Spawn Enemy CIWS',command=lambda:self.toggle_enemy('CIWS'))
        self.enemy_ciws_button.pack(fill='x',pady=(6,0))
        self.enemy_flak_button=ttk.Button(self.debug_panel,text='Spawn Enemy Flak',command=lambda:self.toggle_enemy('Flak'))
        self.enemy_flak_button.pack(fill='x',pady=(6,0))
        self.enemy_saaw_button=ttk.Button(self.debug_panel,text='Spawn Enemy SAAW',command=lambda:self.toggle_enemy('SAAW'))
        self.enemy_saaw_button.pack(fill='x',pady=(6,0))
        self.enemy_sam_button=ttk.Button(self.debug_panel,text='Spawn Enemy SAM',command=lambda:self.toggle_enemy('SAM'))
        self.enemy_sam_button.pack(fill='x',pady=(6,0))
        self.enemy_lr_sam_button=ttk.Button(self.debug_panel,text='Spawn Enemy LR SAM',command=lambda:self.toggle_enemy('LR SAM'))
        self.enemy_lr_sam_button.pack(fill='x',pady=(6,0))
        self.enemy_drone_launcher_button=ttk.Button(self.debug_panel,text='Spawn Enemy Drone Launcher',command=lambda:self.toggle_enemy('Drone Launcher'))
        self.enemy_drone_launcher_button.pack(fill='x',pady=(6,0))
        self.enemy_silo_button=ttk.Button(self.debug_panel,text='Spawn Enemy ICBM Silo',command=lambda:self.toggle_enemy('ICBM Silo'))
        self.enemy_silo_button.pack(fill='x',pady=(6,0))
        self.enemy_icbm_button=ttk.Button(self.debug_panel,text='Spawn Enemy ICBM',command=lambda:self.toggle_enemy('ICBM'))
        self.enemy_icbm_button.pack(fill='x',pady=(6,0))
        self.see_all_button=ttk.Button(self.debug_panel,text='See All',command=self.toggle_see_all)
        self.see_all_button.pack(fill='x',pady=(10,0))
        ttk.Button(self.debug_panel,text='Cancel',command=self.cancel_placement).pack(fill='x',pady=(5,0))
        self.debug_kill_button=ttk.Button(self.debug_panel,text='Kill Tool',command=self.toggle_debug_kill)
        self.debug_kill_button.pack(fill='x',pady=(8,0))
        self.bands_button=ttk.Button(self.debug_panel,text='Show Zones',style='GamePlay.TButton' if self.show_bands else 'TButton',command=self.toggle_bands)
        self.bands_button.pack(fill='x',pady=(6,0))
        self.log_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.log_panel,text='LOG',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        log_scroll=ttk.Scrollbar(self.log_panel);log_scroll.pack(side='right',fill='y')
        self.log_text=tk.Text(self.log_panel,background=BG,foreground=TEXT,wrap='word',width=30,height=12,relief='flat',state='disabled',yscrollcommand=log_scroll.set)
        self.log_text.pack(fill='both',expand=True);log_scroll.configure(command=self.log_text.yview)
        self.log_text.tag_configure('damage',foreground='#ef6262')
        self.log_text.tag_configure('cost',foreground='#ef6262')
        self.log_text.tag_configure('purchase',foreground='#ffffff')
        self.log_text.tag_configure('upgrade',foreground='#67b7ff')
        self.log_text.tag_configure('enemy_kill',foreground='#ef6262')
        self.log_text.tag_configure('reward',foreground='#72d693')
        self.unit_list_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.unit_list_panel,text='UNIT LIST',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        self.unit_tree=ttk.Treeview(self.unit_list_panel,show='tree',selectmode='browse',height=8)
        unit_scroll=ttk.Scrollbar(self.unit_list_panel,orient='vertical',command=self.unit_tree.yview)
        unit_scroll.pack(side='right',fill='y');self.unit_tree.pack(fill='both',expand=True)
        self.unit_tree.configure(yscrollcommand=unit_scroll.set)
        for key,label in (('friendly','Friendly Units'),('datalink','Enemy · Data Link'),('visual','Enemy · Optical')):
            self.unit_tree.insert('', 'end',iid=key,text=label,open=True)
        self.unit_list_signature=None;self.unit_list_units={}
        self.unit_tree.bind('<<TreeviewSelect>>',self.select_list_unit)
        ttk.Button(inspector,text='← Back to Unit List',command=lambda:self.show_left_menu('Unit List')).pack(fill='x',pady=(0,8))
        self.inspector_title=tk.StringVar(value='Inspector')
        self.inspector_heading=ttk.Label(inspector,textvariable=self.inspector_title,font=('Helvetica',11,'bold'))
        self.inspector_heading.pack(anchor='w',pady=(0,10))
        self.inspector_text=tk.StringVar()
        self.aircraft_instruments=AircraftInspector(inspector,self.toggle_aircraft_weapon)
        self.ground_instruments=GroundInspector(inspector)
        self.ewr_controls=ttk.Frame(inspector)
        self.ewr_point_text=tk.StringVar()
        ttk.Label(self.ewr_controls,textvariable=self.ewr_point_text,justify='center',wraplength=270).pack(fill='x')
        self.ewr_points=tk.Canvas(self.ewr_controls,height=18,background=BG,highlightthickness=0)
        self.ewr_points.pack(fill='x',pady=3)
        arrows=ttk.Frame(self.ewr_controls);arrows.pack(fill='x',pady=4)
        self.ewr_range_button=ttk.Button(arrows,text='← Range',command=lambda:self.shift_ewr_points(1))
        self.ewr_range_button.pack(side='left',fill='x',expand=True)
        self.ewr_width_button=ttk.Button(arrows,text='Width →',command=lambda:self.shift_ewr_points(-1))
        self.ewr_width_button.pack(side='left',fill='x',expand=True)
        self.ewr_bearing_controls=ttk.Frame(inspector)
        self.ewr_bearing_text=tk.StringVar()
        ttk.Label(self.ewr_bearing_controls,textvariable=self.ewr_bearing_text).pack(fill='x')
        self.ewr_bearing_var=tk.DoubleVar(value=0)
        self.ewr_bearing_slider=ttk.Scale(self.ewr_bearing_controls,from_=0,to=360,variable=self.ewr_bearing_var,command=self.set_ewr_bearing)
        self.ewr_bearing_slider.pack(fill='x',pady=(4,8))
        self.ewr_rotate_row=ttk.Frame(self.ewr_bearing_controls)
        self.ewr_rotate_row.pack(fill='x',pady=(0,8))
        self.ewr_rotate_button=ttk.Button(self.ewr_rotate_row,text='Rotate',command=self.toggle_ewr_rotation)
        self.ewr_rotate_button.pack(side='left',fill='x',expand=True)
        self.ewr_direction_button=ttk.Button(self.ewr_rotate_row,text='Clockwise ↻',command=self.toggle_ewr_direction)
        self.ewr_direction_button.pack(side='left',fill='x',expand=True,padx=(4,0))

        self.pac3_controls=ttk.Frame(inspector)
        self.pac3_bearing_text=tk.StringVar()
        ttk.Label(self.pac3_controls,textvariable=self.pac3_bearing_text).pack(fill='x')
        self.pac3_bearing_var=tk.DoubleVar(value=0)
        self.pac3_bearing_slider=ttk.Scale(self.pac3_controls,from_=0,to=360,variable=self.pac3_bearing_var,command=self.set_pac3_bearing)
        self.pac3_bearing_slider.pack(fill='x',pady=4)
        self.pac3_ammo=AmmoInspector(inspector)
        self.icbm_instruments=ICBMInspector(inspector)
        self.projectile_instruments=ProjectileInspector(inspector)
        self.helicopter_instruments=HelicopterInspector(inspector)
        self.silo_instruments=ICBMSiloInspector(inspector)
        self.rwr_confidence=ConfidenceInspector(inspector)
        self.airfield_health=HealthInspector(inspector)
        self.inspector_label=ttk.Label(inspector,textvariable=self.inspector_text,justify='left',wraplength=270)
        self.inspector_label.pack(anchor='w',fill='x')
        self.reload_progress_panel=ttk.Frame(inspector)
        self.reload_progress_text=tk.StringVar()
        ttk.Label(self.reload_progress_panel,textvariable=self.reload_progress_text).pack(anchor='w')
        self.reload_progress_bar=ttk.Progressbar(self.reload_progress_panel,mode='determinate',maximum=100)
        self.reload_progress_bar.pack(fill='x',pady=(4,0))

        self.upgrade_panel=ttk.Frame(inspector)
        self.upgrade_buttons={}
        for kind in ('Power','Hangars','Factory','Logistics','Ground Crew'):
            button=ttk.Button(self.upgrade_panel,image=self.upgrade_icons[kind],compound='left',style='GameUpgrade.TButton',command=lambda k=kind:self.upgrade(k))
            button.pack(fill='x',pady=3);self.upgrade_buttons[kind]=button

        self.aircraft_button=ttk.Button(self.upgrade_panel,text='Aircraft',command=self.open_aircraft_menu)
        self.aircraft_button.pack(fill='x',pady=(10,3))
        self.inspector_airfield_level=ttk.Button(self.upgrade_panel,command=lambda:self.upgrade('Airfield'))
        self.inspector_airfield_level.pack(fill='x',pady=(14,3))
        unlock_host=ttk.Frame(self.upgrade_panel);unlock_host.pack(fill='x')
        self.unlock_hosts.append(unlock_host)
        self.aircraft_controls=ttk.Frame(inspector)
        self.change_loadout_button=ttk.Button(self.aircraft_controls,text='Change Loadout',command=self.open_selected_loadout)
        self.movement_text=tk.StringVar()
        row=ttk.Frame(self.aircraft_controls);row.pack(fill='x',pady=(8,4))
        self.aircraft_deploy_row=row
        self.rtb_button=ttk.Button(row,text='RTB',width=6,command=self.command_rtb)
        self.rtb_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.fence_out_button=ttk.Button(row,text='Fence Out',width=9,command=lambda:self.set_fence(False))
        self.fence_out_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.fence_in_button=ttk.Button(row,text='Fence In',width=9,command=lambda:self.set_fence(True))
        self.fence_in_button.pack(side='left',fill='x',expand=True)
        row=ttk.Frame(self.aircraft_controls);row.pack(fill='x')
        self.direct_button=ttk.Button(row,text='Direct To',width=7,command=lambda:self.start_movement('direct'))
        self.direct_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.loiter_button=ttk.Button(row,text='Loiter',width=5,command=lambda:self.start_movement('loiter'))
        self.loiter_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.patrol_button=ttk.Button(row,text='Patrol',width=5,command=lambda:self.start_movement('patrol'))
        self.patrol_button.pack(side='left',fill='x',expand=True)
        self.form_up_button=ttk.Button(self.aircraft_controls,text='Form Up',command=self.command_form_up)
        self.form_up_button.pack(fill='x',pady=(5,0))
        self.attack_button=ttk.Button(self.aircraft_controls,text='Attack',command=self.attack_command)
        self.attack_button.pack(fill='x',pady=(5,0))
        self.speed_controls=ttk.Frame(self.aircraft_controls)
        self.speed_controls.pack(fill='x',pady=(5,0))
        self.throttle_buttons={}
        for setting in ('Eco','Mil','AB'):
            button=ttk.Button(self.speed_controls,text=setting,width=3,command=lambda value=setting:self.set_aircraft_speed(value))
            button.pack(side='left',fill='x',expand=True,padx=1);self.throttle_buttons[setting]=button
        self.engagement_controls=ttk.Frame(self.aircraft_controls)
        self.engagement_controls.pack(fill='x')
        ttk.Label(self.engagement_controls,text='Targets').pack(anchor='w',pady=(10,3))
        target_row=ttk.Frame(self.engagement_controls);target_row.pack(fill='x')
        self.aircraft_target_buttons={}
        for i,kind in enumerate(TARGET_TYPES):
            button=ttk.Button(target_row,text=kind,width=9,command=lambda k=kind:self.toggle_aircraft_target(k))
            button.grid(row=i//2,column=i%2,sticky='ew',padx=1,pady=1);self.aircraft_target_buttons[kind]=button
        target_row.columnconfigure(0,weight=1);target_row.columnconfigure(1,weight=1)
        self.engagement_button=ttk.Button(self.engagement_controls,command=lambda:self.cycle_engagement('range'))
        self.engagement_button.pack(fill='x',pady=(6,2))
        self.air_salvo_button=ttk.Button(self.engagement_controls,command=lambda:self.cycle_engagement('air'))
        self.air_salvo_button.pack(fill='x',pady=2)
        self.ground_salvo_button=ttk.Button(self.engagement_controls,command=lambda:self.cycle_engagement('ground'))
        self.ground_salvo_button.pack(fill='x',pady=2)
        ttk.Label(self.aircraft_controls,textvariable=self.movement_text,wraplength=250,justify='left').pack(fill='x',pady=6)
        self.movement_cancel=ttk.Button(self.aircraft_controls,text='Cancel',command=self.cancel_movement)
        self.radar_controls=ttk.Frame(inspector)
        self.radar_toggle_button=ttk.Button(self.radar_controls,command=self.toggle_radar_power)
        self.radar_toggle_button.pack(fill='x',pady=(10,4))
        self.ewr_track_button=ttk.Button(self.radar_controls,text='Track',command=self.begin_ewr_track)
        self.resupply_button=ttk.Button(inspector,text='Resupply',command=self.request_resupply)
        self.sam_controls=ttk.Frame(inspector)
        self.pac3_engage_button=ttk.Button(self.sam_controls,text='Engage',command=self.toggle_pac3_engagement)
        ttk.Label(self.sam_controls,text='Preferred Targets').pack(anchor='w',pady=(10,4))
        self.target_buttons={}
        for kind in ('Suicide Drones','Bombers','Fighters','ICBMs'):
            button=ttk.Button(self.sam_controls,text=kind,command=lambda k=kind:self.toggle_target(k))
            button.pack(fill='x',pady=2);self.target_buttons[kind]=button
        self.ciws_controls=ttk.Frame(inspector)
        self.ciws_target_buttons={}
        for kind in ('Fighters','Bombers','Suicide Drones','Missiles','Bombs','ICBMs'):
            b=ttk.Button(self.ciws_controls,text=kind,command=lambda k=kind:self.toggle_ciws_target(k))
            b.pack(fill='x',pady=2);self.ciws_target_buttons[kind]=b
        self.silo_toggle_button=ttk.Button(inspector,command=self.toggle_silo)
        self.destroy_unit_button=ttk.Button(inspector,text='Destroy',style='GameDestroy.TButton',command=self.destroy_selected_unit)
        self.building_details_panel=ttk.LabelFrame(build,text='Details',padding=8)
        self.building_details_title=tk.StringVar()
        ttk.Label(self.building_details_panel,textvariable=self.building_details_title,font=('Helvetica',10,'bold'),wraplength=240).pack(anchor='w',pady=(0,6))
        self.building_details_text=tk.StringVar()
        self.building_details_label=ttk.Label(self.building_details_panel,textvariable=self.building_details_text,justify='left',wraplength=240)
        self.building_details_label.pack(fill='x',expand=True)
        self.building_details_label.bind('<Configure>',lambda e:self.building_details_label.configure(wraplength=max(40,e.width)))
        self.create_aircraft_menu()
        self.bind_menu_wheel(self.build_panel,self.build_scroll_canvas)
        self.bind_menu_wheel(self.airfield_panel,self.airfield_scroll_canvas)
        self.bind_menu_wheel(self.debug_panel,self.debug_scroll_canvas)
        def inspector_widgets(widget):
            yield widget
            for child in widget.winfo_children():yield from inspector_widgets(child)
        for widget in inspector_widgets(inspector):
            widget.bind('<MouseWheel>',scroll_inspector)
            widget.bind('<Button-4>',lambda e:inspector_canvas.yview_scroll(-1,'units'))
            widget.bind('<Button-5>',lambda e:inspector_canvas.yview_scroll(1,'units'))

        controls=ttk.Frame(right);controls.pack(fill='x',pady=(0,6))
        style=ttk.Style(self)
        style.configure('GamePointDefence.TButton',background='#e6bd48',foreground='#182436')
        style.map('GamePointDefence.TButton',background=[('active','#f6d369'),('pressed','#cba333')])
        style.configure('GameUpgrade.TButton',anchor='w',padding=(8,4))
        style.configure('GameDestroy.TButton',background='#a63e49',foreground='#ffffff')
        style.map('GameDestroy.TButton',background=[('active','#c24a57'),('pressed','#822c36')])
        style.configure('GamePlay.TButton',background='#27694e',foreground='#ffffff')
        style.map('GamePlay.TButton',background=[('active','#328563')])
        style.configure('GamePause.TButton',background='#e6bd48',foreground='#182436')
        style.map('GamePause.TButton',background=[('active','#f6d369')])
        style.configure('GameAB.TButton',background='#b86c28',foreground='#ffffff')
        style.map('GameAB.TButton',background=[('active','#d68535')])
        style.configure('GameFenceIn.TButton',background='#a63e49',foreground='#ffffff')
        style.map('GameFenceIn.TButton',background=[('active','#c24a57')])
        style.configure('GameSpeed.Selected.TButton',background='#286fc3',foreground='#ffffff')
        style.map('GameSpeed.Selected.TButton',background=[('active','#3689dc')])
        style.configure('GameSAMCoverage.TButton',background='#70539e',foreground='#ffffff')
        style.map('GameSAMCoverage.TButton',background=[('active','#8767b7')])
        # Pixel icons avoid font substitutions on Windows and macOS.
        self.pause_icon=tk.PhotoImage(master=self,width=24,height=20)
        self.pause_icon.put('#182436',to=(5,2,10,18));self.pause_icon.put('#182436',to=(14,2,19,18))
        self.play_icon=tk.PhotoImage(master=self,width=24,height=20)
        for x in range(6,19):
            half=max(1,round((19-x)*.6))
            self.play_icon.put('#ffffff',to=(x,10-half,x+1,10+half))
        self.play_button=ttk.Button(controls,text='    ',image=self.pause_icon,compound='center',
                                   width=4,style='GamePause.TButton',command=self.toggle_play)
        self.play_button.pack(side='left',padx=(0,8))
        self.speed_buttons={}
        for speed in (1,2,4,10):
            button=ttk.Button(controls,text=f'{speed}×',width=4,command=lambda v=speed:self.set_speed(v),
                              style='GameSpeed.Selected.TButton' if speed==1 else 'TButton')
            button.pack(side='left',padx=2);self.speed_buttons[speed]=button
        navigation=ttk.Frame(right);navigation.pack(fill='x',pady=(0,6))
        self.coverage_button=ttk.Button(controls,text='Radar',style='GamePlay.TButton',command=self.toggle_coverage)
        self.coverage_button.pack(side='left',padx=4)
        self.sam_coverage_button=ttk.Button(controls,text='SAM Coverage',style='GameSAMCoverage.TButton',command=self.toggle_sam_coverage)
        self.sam_coverage_button.pack(side='left',padx=4)
        self.point_defence_button=ttk.Button(controls,text='Point Defence',style='GamePointDefence.TButton',command=self.toggle_point_defence)
        self.point_defence_button.pack(side='left',padx=4)
        self.visual_coverage_button=ttk.Button(controls,text='Optical',style='GamePlay.TButton',command=self.toggle_visual_coverage)
        self.visual_coverage_button.pack(side='left',padx=4)
        ttk.Button(navigation,text='-',width=3,command=lambda:self.zoom(1.5)).pack(side='left',padx=2)
        self.home_icon=tk.PhotoImage(master=self,width=22,height=20)
        for y in range(2,11):
            half=y-1
            self.home_icon.put(TEXT,to=(11-half,y,12+half,y+1))
        self.home_icon.put(TEXT,to=(5,10,18,18))
        self.home_icon.put(BG,to=(10,12,14,18))
        ttk.Button(navigation,image=self.home_icon,width=3,command=self.home).pack(side='left',padx=2)
        ttk.Button(navigation,text='+',width=3,command=lambda:self.zoom(1/1.5)).pack(side='left',padx=2)
        self.follow_button=ttk.Button(navigation,text='Follow',width=7,command=self.toggle_follow)
        self.follow_button.pack(side='left',padx=(6,0))
        ttk.Button(navigation,text='Wide View',command=self.full_map).pack(side='left',padx=(8,0))
        self.zones_button=ttk.Button(navigation,text='Zones',style='GamePlay.TButton' if self.show_bands else 'TButton',command=self.toggle_bands)
        self.zones_button.pack(side='left',padx=(6,0))
        self.zoom_text=tk.StringVar(value='10 NM')
        self.zoom_select=ttk.Combobox(navigation,textvariable=self.zoom_text,values=[f'{v} NM' for v in ZOOM_WIDTHS_NM],state='readonly',width=8)
        self.zoom_select.pack(side='left',padx=8)
        self.zoom_select.bind('<<ComboboxSelected>>',lambda event:self.set_view_width(float(self.zoom_text.get().split()[0])))
        resources=ttk.Frame(right);resources.pack(fill='x',pady=(0,6))
        ttk.Label(resources,text='Money:').pack(side='left')
        ttk.Label(resources,textvariable=self.cash_text,foreground='#72d693',font=('Helvetica',11,'bold')).pack(side='left',padx=(5,0))
        ttk.Label(resources,text='Power:').pack(side='left',padx=(20,5))
        self.hud_power=tk.Canvas(resources,background=BG,highlightthickness=0,height=25,width=450)
        self.hud_power.pack(side='left')
        ttk.Label(resources,text='Crew:').pack(side='left',padx=(10,3))
        self.hud_crew=tk.Canvas(resources,background=BG,highlightthickness=0,height=25,width=105)
        self.hud_crew.pack(side='left')
        ttk.Label(resources,text='Logistics:').pack(side='left',padx=(10,3))
        self.hud_logistics=tk.Canvas(resources,background=BG,highlightthickness=0,height=25,width=105)
        self.hud_logistics.pack(side='left')
        self.contacts_text=tk.StringVar(value='Contacts: 0')
        self.band_text=tk.StringVar(value=f'Campaign · {len(STATS["campaign"]["tiers"])} zones')
        ttk.Label(right,textvariable=self.band_text,foreground=MUTED).pack(anchor='w',pady=(0,4))
        self.canvas=tk.Canvas(right,background=BG,highlightthickness=1,highlightbackground='#344258')
        self.canvas.pack(fill='both',expand=True)
        self.contacts_hud=tk.Frame(self.canvas,width=90,height=66,background=PANEL,highlightthickness=2,highlightbackground='#ef6262')
        self.contacts_hud.pack_propagate(False);self.contacts_hud.place(relx=1.,x=-10,y=10,anchor='ne')
        self.contacts_title_label=tk.Label(self.contacts_hud,text='Contacts',background=PANEL,foreground=TEXT,font=('Helvetica',10,'bold'))
        self.contacts_title_label.pack(fill='x',pady=(4,0))
        self.contacts_count_label=tk.Label(self.contacts_hud,text='0',background=PANEL,foreground='#ef6262',font=('Helvetica',19,'bold'))
        self.contacts_count_label.pack(fill='x')
        self.contacts_hud_signature=None
        style.configure('GameMute.TButton',padding=(6,3),font=('Helvetica',9))
        style.configure('GameMuted.TButton',padding=(6,3),font=('Helvetica',9),foreground='#ef6262')
        self.map_controls=ttk.Frame(self)
        self.map_controls.place(in_=self.canvas,relx=1.,rely=1.,x=-10,y=-10,anchor='se')
        self.fullscreen=GameFullscreen(self)
        self.mute_button=ttk.Button(self.map_controls,text='Unmute' if self.game_audio.muted else 'Mute',width=7,style='GameMuted.TButton' if self.game_audio.muted else 'GameMute.TButton',command=self.toggle_game_mute)
        self.mute_button.pack(side='right')
        self.fullscreen_button=ttk.Button(self.map_controls,text='Fullscreen',width=14,style='GameMute.TButton',command=self.fullscreen.toggle)
        self.fullscreen_button.pack(side='right',padx=(0,6))
        grid_controls=ttk.Frame(self.map_controls);grid_controls.pack(side='right',padx=(0,10))
        ttk.Label(grid_controls,text='Grid').pack(side='left',padx=(0,4))
        self.grid_opacity_var=tk.DoubleVar(value=30.)
        self.grid_opacity_slider=ttk.Scale(grid_controls,from_=0,to=100,length=90,
                                         variable=self.grid_opacity_var,command=self.set_grid_opacity)
        self.grid_opacity_slider.pack(side='left')
        self.grid_opacity_text=tk.StringVar(value='30%')
        ttk.Label(grid_controls,textvariable=self.grid_opacity_text,width=4).pack(side='left',padx=(4,0))
        self.canvas.bind('<Configure>',self.resized)
        self.canvas.bind('<Button-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Double-Button-1>',self.double_click_aircraft)
        self.canvas.bind('<Motion>',self.hover)
        self.canvas.bind('<Leave>',self.leave)
        self.canvas.bind('<Escape>',lambda event:self.cancel_commands())
        self.auto_prompt_panel=ttk.Frame(self.canvas,padding=6)
        self.auto_prompt_signature=None
        self.map_aircraft_bar=ttk.Frame(self.canvas)
        self.key_binding=self.winfo_toplevel().bind('<KeyPress>',self.aircraft_shortcut,add='+')
        self.key_release_binding=self.winfo_toplevel().bind('<KeyRelease>',self.release_shortcut,add='+')
        self.refresh_map_aircraft_buttons()
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda e:self.zoom(.85,(e.x,e.y)))
        self.canvas.bind('<Button-5>',lambda e:self.zoom(1/.85,(e.x,e.y)))
        self.bind('<Destroy>',self.destroyed,add='+')
        self.init_progress()
        self.refresh_inspector()
        self.show_left_menu("Build",cancel=False)
        self.create_run_screen()
        self.show_run_screen('start')
        self.request_draw()

    def spawn_campaign_ground(self,kind,x,y):
        if kind=='PAC-3':raise ValueError('PAC-3 is a player-only unit')
        if kind in ('Factory','Bunker','Drone Launcher','ICBM Silo'):
            return {'Factory':self.combat.spawn_factory,'Bunker':self.combat.spawn_bunker,'Drone Launcher':self.combat.spawn_drone_launcher,'ICBM Silo':self.combat.spawn_silo}[kind](x,y)
        if kind in ('Radar','LR Radar'):
            unit=Radar(len(self.combat.enemy_radars)+1,x,y,enemy=True,long_range=kind=='LR Radar')
            self.combat.enemy_radars.append(unit)
        else:
            cls={'SAM':SAMLauncher,'LR SAM':SAMLauncher,'SAAW':SAAW,'Flak':Flak,'CIWS':CIWS,'PAC-3':PAC3}[kind]
            kwargs={'enemy':True}
            if kind in ('SAM','LR SAM'):kwargs['long_range']=kind=='LR SAM'
            unit=cls(len(self.combat.enemy_sams)+1,x,y,**kwargs)
            if isinstance(unit,PAC3):unit.bearing=math.atan2(self.airfield.x-x,self.airfield.y-y);unit.desired_bearing=unit.bearing
            self.combat.enemy_sams.append(unit)
        return unit

    def create_run_screen(self):
        self.result_board=None;self.start_scene=None;self.run_screen_kind=None
        style=ttk.Style(self)
        style.configure('StartCard.TFrame',background='#0c1928',bordercolor='#438cff',lightcolor='#438cff',darkcolor='#438cff',borderwidth=2,relief='solid')
        style.configure('StartInterior.TFrame',background='#0c1928')
        style.configure('StartTitle.TLabel',background='#0c1928',foreground='#69adff')
        style.configure('StartSummary.TLabel',background='#0c1928',foreground=TEXT)
        style.configure('StartLaunch.TButton',background='#438cff',foreground='white',font=('Helvetica',12,'bold'),padding=(18,12))
        style.map('StartLaunch.TButton',background=[('active','#69adff'),('!disabled','#438cff')],foreground=[('!disabled','white')])
        self.run_screen=ttk.Frame(self,padding=20)
        self.run_screen.bind('<Configure>',self.resize_results)
        self.run_card=ttk.Frame(self.run_screen,padding=30)
        self.run_card.place(relx=.5,rely=.5,anchor='center')
        self.run_title=ttk.Label(self.run_card,font=('Helvetica',22,'bold'))
        self.run_title.pack(pady=(0,15))
        self.run_summary=ttk.Label(self.run_card,justify='left',font=('Helvetica',12),wraplength=520)
        self.run_summary.pack(pady=(0,20))
        self.run_actions=ttk.Frame(self.run_card);self.run_actions.pack(fill='x')

    def show_run_screen(self,kind):
        self.run_screen_kind=kind
        if self.start_scene is not None:self.start_scene.stop();self.start_scene.place_forget()
        for child in self.run_actions.winfo_children():child.destroy()
        self.run_summary.configure(font=('Helvetica',12 if kind=='start' else 10))
        if self.result_board is not None:self.result_board.stop();self.result_board.destroy();self.result_board=None
        if kind=='start':
            if self.start_scene is None:self.start_scene=StartScene(self.run_screen,self)
            self.start_scene.place(x=0,y=0,relwidth=1,relheight=1)
            self.run_card.configure(style='StartCard.TFrame',padding=26)
            self.run_actions.configure(style='StartInterior.TFrame')
            self.run_title.configure(text='Airfield Defense',style='StartTitle.TLabel',font=('Helvetica',28,'bold'),anchor='center',foreground='#69adff')
            self.run_summary.configure(text='Locate and destroy all enemy airfields while keeping yours safe.',style='StartSummary.TLabel',justify='center',anchor='center',wraplength=420)
            ttk.Button(self.run_actions,text='Start Game',style='StartLaunch.TButton',command=self.start_run).pack(fill='x')
            self.run_card.lift()
            self.resize_results()
        else:
            self.run_card.configure(style='TFrame',padding=30);self.run_actions.configure(style='TFrame')
            self.run_title.configure(style='TLabel',font=('Helvetica',22,'bold'))
            self.run_summary.configure(style='TLabel',justify='left')
            self.run_title.configure(text='VICTORY · CAMPAIGN COMPLETE' if kind=='win' else 'BASE DESTROYED',foreground='#72d693' if kind=='win' else '#ef6262')
            self.run_summary.configure(text=results_header(self.campaign,self.elapsed),wraplength=780)
            self.result_board=ResultBoard(self.run_card,self.campaign,self)
            self.result_board.pack(fill='both',expand=True,before=self.run_actions,pady=(0,12))
            self.resize_results()
            if kind=='win':ttk.Button(self.run_actions,text='Continue · Infinite Mode',style='GamePlay.TButton',command=self.continue_run).pack(fill='x',pady=(0,8))
            ttk.Button(self.run_actions,text='Restart',command=self.restart_run).pack(fill='x')
        self.run_screen.place(x=0,y=0,relwidth=1,relheight=1);self.run_screen.lift()
        self.map_controls.lift()
        if kind=='start':self.start_scene.start()

    def resize_results(self,event=None):
        if self.run_screen_kind=='start':
            width=max(180,min(420,self.winfo_width()-110))
            self.run_summary.configure(wraplength=width);self.run_title.configure(wraplength=width)
            return
        if self.result_board is None:return
        width=max(250,min(820,self.winfo_width()-100))
        height=max(120,min(430,self.winfo_height()-300))
        self.result_board.canvas.configure(width=width,height=height)
        self.run_summary.configure(wraplength=width)
        self.run_title.configure(wraplength=width)

    def start_run(self):
        if self.start_scene is not None:self.start_scene.stop()
        self.run_started=True;self.run_screen.place_forget()
        self.campaign.start(self.elapsed);self.set_speed(1)
        if not self.playing:self.toggle_play()
        self.refresh_campaign();self.request_draw()

    def finish_run(self,result):
        if self.run_result is not None:return
        self.run_result=result
        if getattr(self,'game_audio',None) is not None:self.game_audio.stop()
        if result=='loss':self.campaign.finished=True
        self.playing=False
        if self.job is not None:self.after_cancel(self.job);self.job=None
        self.play_button.configure(image=self.pause_icon,style='GamePause.TButton')
        self.show_run_screen(result)

    def continue_run(self):
        self.run_result=None;self.run_screen.place_forget()
        if self.result_board is not None:self.result_board.stop()
        self.campaign.continue_run(self.elapsed);self.last_tick=time.monotonic()
        if not self.playing:self.toggle_play()
        self.refresh_campaign();self.request_draw()

    def restart_run(self):
        was_fullscreen=self.fullscreen.active
        if was_fullscreen:self.fullscreen.exit()
        parent=self.master;index=parent.index(self)
        replacement=GameMapPage(self.app,parent)
        self.app.game_map=replacement
        parent.insert(index,replacement,text='Game');parent.forget(self)
        self.destroy();parent.select(replacement);replacement.set_active(True)
        if was_fullscreen:replacement.fullscreen.enter()

    def refresh_campaign(self):
        if not self.run_started:return
        self.campaign.observe([self.airfield,*self.aircraft.values(),*self.radars,*self.sams,*self.ciws])
        band=self.campaign.bands[-1]
        remaining=sum(r.alive for r in band.runways)
        self.band_text.set(f'Zone {band.number} · Runways remaining: {remaining}/{len(band.runways)}'+(' · Infinite' if self.campaign.infinite else ''))
        key=(band.number,remaining)
        if key!=getattr(self,'campaign_draw_key',None):self.campaign_draw_key=key;self.request_draw()
        if not self.airfield.alive:self.finish_run('loss')
        elif self.campaign.awaiting_victory:self.finish_run('win')

    def toggle_debug_kill(self):
        was=self.debug_kill_mode
        self.cancel_commands();self.debug_kill_mode=not was
        self.debug_kill_button.configure(text='Cancel Kill Tool' if self.debug_kill_mode else 'Kill Tool',style='GameDestroy.TButton' if self.debug_kill_mode else 'TButton')
        self.canvas.configure(cursor='crosshair' if self.debug_kill_mode else '')

    def debug_kill_unit(self,unit):
        if unit is None or not unit.alive:return False
        self.combat.log_airfield_damage(self.elapsed)
        if isinstance(unit,Aircraft):
            unit.destroy()
            if unit.enemy:self.combat.known_wrecks.add(id(unit))
        else:unit.health=0
        if getattr(unit,'death_wall_time',None) is None:unit.death_wall_time=time.monotonic()
        self.add_log(f'Debug killed {self.combat.unit_name(unit)}','status')
        self.combat.log_airfield_damage(self.elapsed)
        if self.run_started and self.airfield.alive:self.campaign.advance(self.elapsed)
        self.refresh_campaign();self.process_game_events()
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()
        return True

    def debug_kill_at(self,event):
        slot=self.aircraft_at(event.x,event.y)
        if slot is not None:return self.debug_kill_unit(self.aircraft_for_slot(slot))
        for weapon in [*self.combat.missiles,*self.combat.bombs,*self.combat.icbms]:
            if not weapon.alive or not self.weapon_visible(weapon):continue
            point=weapon.position(self.elapsed) if isinstance(weapon,Bomb) else (weapon.x,weapon.y)
            if math.dist((event.x,event.y),self.pixel(*point))<=12:return self.debug_kill_unit(weapon)
        for unit in reversed(self.visible_ground_units()):
            if unit.alive and self.ground_target_hit(unit,event.x,event.y,max(10,22*self.building_factor())):return self.debug_kill_unit(unit)
        x,y=self.world(event.x,event.y)
        if abs(x-self.airfield.x)<=max(.2,self.airfield.runway_width/2) and abs(y-self.airfield.y)<=self.airfield.runway_length/2:return self.debug_kill_unit(self.airfield)
        return False

    def toggle_bands(self):
        self.show_bands=not self.show_bands
        for name in ('bands_button','zones_button'):
            button=getattr(self,name,None)
            if button is not None:button.configure(style='GamePlay.TButton' if self.show_bands else 'TButton')
        self.request_draw()

    def draw_bands(self):
        if not self.show_bands:return
        cx,cy=self.pixel(self.airfield.x,self.airfield.y)
        settings=self.campaign.settings;bands=self.campaign.bands
        boundaries=[settings['safe_radius_nm']]+[b.outer for b in bands]
        active=bands[-1].number if bands and not bands[-1].completed else None
        if not bands:
            boundaries.append(settings['safe_radius_nm']+settings['band_width_nm']);active=1
        for i,radius in enumerate(boundaries):
            color='#ef6262' if active is not None and i in (active-1,active) else '#438cff'
            r=radius*self.scale()
            self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,outline=color,dash=(8,6),width=1.5,tags='campaign_bands')
            if i:
                self.canvas.create_text(cx,cy-r+12,text=f'Zone {i} · {radius:g} NM',fill=color,tags='campaign_bands')

    def update_contacts_hud(self):
        contacts=self.combat.contacts[False]
        count=sum(isinstance(contact.target,Aircraft) and contact.target.alive for contact in contacts.values())
        warning=any(m.enemy and m.alive and (self.see_all or getattr(m,'player_spotted',False) or id(m) in contacts) for m in self.combat.icbms)
        phase=bool(int(time.monotonic()*2)%2) if warning else False
        signature=(count,warning,phase)
        if signature==getattr(self,'contacts_hud_signature',None):return
        self.contacts_hud_signature=signature
        color='#ffe66d' if warning and phase else '#ef6262'
        background='#4a222a' if warning and phase else PANEL
        self.contacts_hud.configure(background=background,highlightbackground=color)
        self.contacts_title_label.configure(background=background,foreground=color if warning else TEXT)
        self.contacts_count_label.configure(text=str(count),background=background,foreground=color)

    def apply_map_layers(self):
        c=self.canvas
        if c.find_withtag('game_aircraft'):c.tag_lower('ground_markers','game_aircraft')
        # Airfields are the bottom unit layer, above only map scenery/boundaries.
        c.tag_lower('airfield_icons')
        c.tag_lower('map_background')

    def create_scroll_menu(self):
        host=ttk.Frame(self.menu_host)
        canvas=tk.Canvas(host,background=BG,highlightthickness=0,width=270,height=200)
        bar=ttk.Scrollbar(host,orient='vertical',command=canvas.yview)
        bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=bar.set)
        content=ttk.Frame(canvas,padding=10)
        window=canvas.create_window(0,0,window=content,anchor='nw')
        content.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.bind_menu_wheel(canvas,canvas)
        return host,content,canvas

    def bind_menu_wheel(self,widget,canvas):
        def scroll(event):
            if canvas.bbox('all') and canvas.bbox('all')[3]>canvas.winfo_height():
                direction=-1 if getattr(event,'num',None)==4 or getattr(event,'delta',0)>0 else 1
                canvas.yview_scroll(direction,'units')
            return 'break'
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(event,scroll)
        for child in widget.winfo_children():self.bind_menu_wheel(child,canvas)

    @property
    def aircraft_capacity(self):
        return HANGAR_LEVELS[self.airfield.hangar_level-1]

    def create_aircraft_menu(self):
        self.aircraft_panel=ttk.Frame(self.menu_host,padding=10)
        header=ttk.Frame(self.aircraft_panel);header.pack(fill='x')
        ttk.Label(header,text='AIRCRAFT',font=('Helvetica',11,'bold')).pack(side='left',padx=(5,0))
        slots=ttk.Frame(self.aircraft_panel);slots.pack(fill='x',pady=(10,6))
        self.slot_buttons=[]
        for slot in range(max(HANGAR_LEVELS)):
            button=ttk.Button(slots,text=str(slot+1),width=3,
                              style=f'GameAircraftSlot{slot}.TButton',
                              command=lambda n=slot:self.select_aircraft_slot(n))
            button.grid(row=slot//5,column=slot%5,padx=2,pady=2,sticky='nsew')
            self.slot_buttons.append(button)
            self.bind_aircraft_reordering(button,slot,'hangar')
        for col in range(5):slots.columnconfigure(col,weight=1,uniform='slots')
        scroll=ttk.Frame(self.aircraft_panel);scroll.pack(fill='both',expand=True)
        self.aircraft_canvas=tk.Canvas(scroll,background=BG,highlightthickness=0,width=270)
        bar=ttk.Scrollbar(scroll,orient='vertical',command=self.aircraft_canvas.yview)
        bar.pack(side='right',fill='y');self.aircraft_canvas.pack(side='left',fill='both',expand=True)
        self.aircraft_canvas.configure(yscrollcommand=bar.set)
        self.aircraft_content=ttk.Frame(self.aircraft_canvas,padding=(0,0,10,0))
        self.aircraft_content_window=self.aircraft_canvas.create_window(0,0,window=self.aircraft_content,anchor='nw')
        self.aircraft_content.bind('<Configure>',lambda e:self.aircraft_canvas.configure(scrollregion=self.aircraft_canvas.bbox('all')))
        self.aircraft_canvas.bind('<Configure>',lambda e:self.aircraft_canvas.itemconfigure(self.aircraft_content_window,width=e.width))
        self.aircraft_canvas.bind('<MouseWheel>',self.scroll_aircraft_menu)
        self.aircraft_canvas.bind('<Button-4>',lambda e:self.aircraft_canvas.yview_scroll(-1,'units'))
        self.aircraft_canvas.bind('<Button-5>',lambda e:self.aircraft_canvas.yview_scroll(1,'units'))

    def scroll_aircraft_menu(self,event):
        if event.delta:self.aircraft_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        return 'break'

    def show_left_menu(self,name,cancel=True):
        if name=='Debug' and not getattr(self,'debug_enabled',False):return
        if cancel:self.cancel_commands()
        self.aircraft_menu_open=False;self.aircraft_panel.pack_forget()
        for panel in (self.build_scroll_panel,self.airfield_scroll_panel,self.debug_scroll_panel,self.unit_list_panel,self.log_panel,self.progress_scroll_panel):panel.pack_forget()
        self.left_menu=name
        for key,button in self.left_menu_buttons.items():
            button.configure(style='GameSpeed.Selected.TButton' if key==('Unit List' if name=='Inspector' else name) else 'TButton')
        if name=='Inspector':
            if str(self.menu_host) in self.sidebar.panes():self.sidebar.forget(self.menu_host)
            if str(self.inspector_host) not in self.sidebar.panes():self.sidebar.add(self.inspector_host,weight=1)
        else:
            if str(self.inspector_host) in self.sidebar.panes():self.sidebar.forget(self.inspector_host)
            if str(self.menu_host) not in self.sidebar.panes():self.sidebar.add(self.menu_host,weight=1)
            if name=='Hangar':
                self.aircraft_menu_open=True;self.aircraft_panel.pack(fill='both',expand=True)
                self.refresh_aircraft_menu()
            else:
                panel={'Build':self.build_scroll_panel,'Unit List':self.unit_list_panel,'Airfield':self.airfield_scroll_panel,'Log':self.log_panel,'Debug':self.debug_scroll_panel,'Objectives':self.progress_scroll_panel}.get(name,self.airfield_scroll_panel)
                panel.pack(fill='both',expand=True)
                if name=='Objectives':self.refresh_progress_menu()
                if name=='Unit List':
                    self.unit_tree.selection_remove(self.unit_tree.selection())
                    self.refresh_unit_list()
        self.refresh_inspector();self.request_draw()

    def inspect_unit(self,unit):
        self.selected=unit
        self.show_left_menu('Inspector',cancel=False)

    def open_aircraft_menu(self):
        self.show_left_menu('Hangar')

    def close_aircraft_menu(self):
        if self.aircraft_menu_open:self.show_left_menu('Airfield',cancel=False)

    def refresh_unit_list(self):
        rows=[('friendly','airfield',self.airfield.name,self.airfield)]
        rows.extend(('friendly',f'plane{slot}',f'{slot+1} · {a.kind} · {a.state.title()}',a)
                    for slot,a in self.aircraft.items() if a.alive)
        rows.extend(('friendly',f'heli{h.id}',f'{h.name} · {h.state.title()}',h) for h in self.logistics.helicopters)
        rows.extend(('friendly',f'ciws{c.id}',f'{c.name} #{c.id}',c) for c in self.ciws if c.alive)
        rows.extend(('friendly',f'radar{r.id}',f'{r.name} #{r.id}',r) for r in self.radars if r.alive)
        rows.extend(('friendly',f'sam{s.id}',f'{s.name} #{s.id}',s) for s in self.sams if s.alive)
        rows.extend(('friendly',f'playersilo{u.id}',f'{u.name} #{u.id}',u) for u in self.player_silos if u.alive)
        for i,a in enumerate(self.combat.enemies):
            contact=self.combat.contact(a)
            if a.alive and contact is not None:
                rows.append((contact.kind,f'enemy{i}',f'{self.combat.aircraft_label(a)} · {a.kind}',a))
        for m in self.combat.icbms:
            contact=self.combat.contact(m)
            if m.alive and (contact is not None or self.weapon_visible(m)):
                rows.append(('friendly' if not m.enemy else contact.kind if contact else 'visual',f'icbm{m.number}',m.name,m))
        rows.extend(('visual',f'factory{f.id}',f'{f.name} #{f.id}',f)
                    for f in self.combat.factories if f.alive and f.id in self.combat.known)
        rows.extend(('visual',f'enemyradar{radar.id}',f'{radar.name} #{radar.id}',radar)
                    for radar in self.combat.enemy_radars if radar.alive and (self.see_all or id(radar) in self.combat.known_ground))
        rows.extend(('visual',f'enemysam{sam.id}',f'{sam.name} #{sam.id}',sam)
                    for sam in self.combat.enemy_sams if sam.alive and (self.see_all or id(sam) in self.combat.known_ground))
        signature=tuple((group,key,label,self.unit_color(unit)) for group,key,label,unit in rows)
        if signature==self.unit_list_signature:return
        self.unit_list_signature=signature
        selected=self.unit_tree.selection()
        self.unit_list_units={key:unit for group,key,label,unit in rows}
        wanted=set(self.unit_list_units)
        for group in ('friendly','datalink','visual'):
            for key in self.unit_tree.get_children(group):
                if key not in wanted:self.unit_tree.delete(key)
        for group,key,label,unit in rows:
            color=self.unit_color(unit);tag='unit_'+color.lstrip('#')
            self.unit_tree.tag_configure(tag,foreground=color)
            if self.unit_tree.exists(key):
                self.unit_tree.move(key,group,'end');self.unit_tree.item(key,text=label,tags=(tag,))
            else:self.unit_tree.insert(group,'end',iid=key,text=label,tags=(tag,))
        if selected and selected[0] in wanted:self.unit_tree.selection_set(selected[0])

    def select_list_unit(self,event=None):
        if self.left_menu!='Unit List':return
        keys=self.unit_tree.selection()
        unit=self.unit_list_units.get(keys[0]) if keys else None
        if unit is None:return
        point=self.track_display(unit) if isinstance(unit,Aircraft) else None
        if isinstance(unit,Aircraft) and unit.enemy and point is None:return
        self.cancel_commands()
        self.follow_enabled=False
        self.center=list(point[:2]) if point is not None else [unit.x,unit.y]
        self.inspect_unit(unit)
        self.refresh_follow_button()
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()

    def toggle_factory(self,kind="Factory"):
        was=self.placing_factory and self.factory_spawn_kind==kind
        self.cancel_commands()
        self.placing_factory=not was;self.factory_spawn_kind=kind
        (self.bunker_button if kind=='Bunker' else self.factory_button).configure(style='GameSpeed.Selected.TButton' if self.placing_factory else 'TButton')
        self.canvas.configure(cursor='crosshair' if self.placing_factory else '')
        self.request_draw()

    def toggle_enemy(self,kind='Fighter'):
        if kind=='EWR':return False
        was=self.placing_enemy and self.enemy_spawn_kind==kind
        self.cancel_commands();self.placing_enemy=not was;self.enemy_spawn_kind=kind
        {'Interceptor':self.enemy_interceptor_button,'LR Radar':self.enemy_lr_radar_button,'LR SAM':self.enemy_lr_sam_button,'CIWS':self.enemy_ciws_button,'Drone Launcher':self.enemy_drone_launcher_button,'ICBM':self.enemy_icbm_button,'ICBM Silo':self.enemy_silo_button,'Flak':self.enemy_flak_button,'SAAW':self.enemy_saaw_button,'Bomber':self.enemy_bomber_button,'Suicide Drone':self.drone_button,'Radar':self.enemy_radar_button,'SAM':self.enemy_sam_button,'Fighter':self.enemy_button}[kind].configure(style='GameSpeed.Selected.TButton' if self.placing_enemy else 'TButton')
        self.canvas.configure(cursor='crosshair' if self.placing_enemy else '')
        self.request_draw()

    def toggle_silo(self):
        if not isinstance(self.selected,(ICBMSilo,DroneLauncher)) or not self.selected.alive:return False
        self.selected.enabled=not self.selected.enabled
        self.refresh_inspector();self.request_draw();return True

    def toggle_see_all(self):
        self.see_all=not self.see_all
        self.see_all_button.configure(style='GamePlay.TButton' if self.see_all else 'TButton')
        self.refresh_inspector()
        self.request_draw()

    def track_display(self,a):
        if isinstance(a,ICBM):
            return (a.x,a.y,a.heading,True,a.history) if self.weapon_visible(a) else None
        if not a.enemy:return a.x,a.y,a.heading,True,a.history
        contact=self.combat.contact(a)
        if contact is None and not self.see_all:return None
        filled=contact is not None and contact.kind=='datalink'
        if self.see_all:return a.x,a.y,a.heading,filled,a.history
        return contact.x,contact.y,contact.heading,filled,contact.history

    def attack_command(self):
        if not isinstance(self.selected,Aircraft) or self.selected.enemy:return
        if self.selected.attack_target is not None:
            self.combat.cancel_attack_order(self.selected)
            self.cancel_movement();self.refresh_inspector();return
        self.start_movement('attack')

    def finish_attack(self,target,point=None):
        a=self.selected
        if not isinstance(a,Aircraft) or a.enemy or target is None or not target.alive:return
        if not isinstance(target,Factory) and (not isinstance(target,(Aircraft,Radar,SAMLauncher,CIWS)) or target.enemy==a.enemy):return
        if not self.combat.has_usable_weapon_for(a,target):
            self.combat.cancel_attack_order(a)
            self.cancel_movement();self.refresh_inspector();self.request_draw();return
        self.combat.order_attack(a,target,point)
        self.cancel_movement();self.refresh_inspector();self.request_draw()

    def aircraft_for_slot(self,slot):
        if slot>=0:return self.aircraft.get(slot)
        index=-slot-1
        units=[*self.combat.enemies,*self.combat.icbms]
        return units[index] if index<len(units) else None

    def map_aircraft(self):
        yield from self.aircraft.items()
        yield from ((-i-1,a) for i,a in enumerate([*self.combat.enemies,*self.combat.icbms]))

    def toggle_aircraft_target(self,kind):
        if not isinstance(self.selected,Aircraft):return
        targets=self.selected.target_types
        if kind in targets:targets.remove(kind)
        else:targets.add(kind)
        self.refresh_inspector()

    def toggle_aircraft_weapon(self,aircraft,kind):
        if aircraft.enemy or not aircraft.alive:return False
        if kind in aircraft.disabled_weapons:aircraft.disabled_weapons.remove(kind)
        else:aircraft.disabled_weapons.add(kind)
        self.refresh_inspector();self.request_draw();return True

    def cycle_engagement(self,kind):
        if not isinstance(self.selected,Aircraft):return
        a=self.selected
        if kind=='range':a.engagement_range=ENGAGEMENT_RANGES[(ENGAGEMENT_RANGES.index(a.engagement_range)+1)%5]
        elif kind=='air':a.air_weapons_per_target=a.air_weapons_per_target%3+1
        else:a.ground_weapons_per_target=a.ground_weapons_per_target%4+1
        self.refresh_inspector()

    def restore_inspector_sash(self):
        if not self.aircraft_menu_open and len(self.sidebar.panes())==2:
            self.sidebar.update_idletasks()
            self.sidebar.sashpos(0,self.inspector_sash)

    def refresh_slot_colors(self):
        for slot,button in enumerate(self.slot_buttons):
            available=slot<self.aircraft_capacity
            aircraft=self.aircraft.get(slot)
            color=aircraft.color if aircraft and aircraft.alive else PANEL
            rgb=[int(color[i:i+2],16) for i in (1,3,5)]
            foreground='#182436' if sum(c*w for c,w in zip(rgb,(.2126,.7152,.0722)))>155 else '#ffffff'
            if not available:foreground=MUTED
            style=ttk.Style(self);name=f'GameAircraftSlot{slot}.TButton'
            style.configure(name,background=color,foreground=foreground,padding=3,
                            borderwidth=2,relief='solid',
                            bordercolor='#ffffff' if slot==self.aircraft_slot else BG)
            style.map(name,background=[('disabled',PANEL),('active',color)],
                      foreground=[('disabled',MUTED),('active',foreground)])
            button.configure(state='normal')

    def set_aircraft_color(self,slot,color):
        aircraft=self.aircraft.get(slot)
        if aircraft is None or color not in [c for name,c in AIRCRAFT_COLORS]:return False
        aircraft.color=color
        self.refresh_map_aircraft_buttons();self.request_draw()
        self.refresh_slot_colors()
        self.refresh_color_selection()
        return True

    def refresh_color_selection(self):
        aircraft=self.aircraft.get(self.aircraft_slot)
        for color,button in getattr(self,'color_buttons',{}).items():
            selected=aircraft is not None and aircraft.color==color
            ttk.Style(self).configure(button.cget('style'),bordercolor='#ffffff' if selected else BG)
        if aircraft is not None and hasattr(self,'color_name'):
            name=next(name for name,color in AIRCRAFT_COLORS if color==aircraft.color)
            self.color_name.set(f'Aircraft Color · {name}')

    def open_selected_loadout(self):
        aircraft=self.selected
        if not isinstance(aircraft,Aircraft) or aircraft.enemy or not aircraft.in_hangar:return False
        slot=next((slot for slot,unit in self.aircraft.items() if unit is aircraft),None)
        if slot is None:return False
        self.aircraft_slot=slot
        self.show_left_menu('Hangar')
        return True

    def bind_aircraft_reordering(self,widget,slot,surface):
        widget.bind('<ButtonPress-1>',lambda event,n=slot,s=surface:self.begin_aircraft_drag(event,n,s))
        widget.bind('<B1-Motion>',self.move_aircraft_drag)
        widget.bind('<ButtonRelease-1>',self.end_aircraft_drag)

    def begin_aircraft_drag(self,event,slot,surface):
        self.aircraft_drag={'slot':slot,'surface':surface,'x':event.x_root,'y':event.y_root,'moved':False,'widget':event.widget}
        return 'break'

    def move_aircraft_drag(self,event):
        drag=self.aircraft_drag
        if drag is None:return 'break'
        aircraft=self.aircraft.get(drag['slot'])
        if aircraft is not None and aircraft.alive and math.hypot(event.x_root-drag['x'],event.y_root-drag['y'])>=6:
            drag['moved']=True;drag['widget'].configure(cursor='fleur')
        return 'break'

    def end_aircraft_drag(self,event):
        drag=self.aircraft_drag;self.aircraft_drag=None
        if drag is None:return 'break'
        drag['widget'].configure(cursor='hand2' if drag['surface']=='map' else '')
        if drag['moved']:
            widget=self.winfo_containing(event.x_root,event.y_root)
            slots={button:slot for slot,button in self.map_aircraft_buttons.items()}
            slots.update({button:slot for slot,button in enumerate(self.slot_buttons)})
            target=slots.get(widget)
            if target is not None:self.reorder_aircraft(drag['slot'],target)
        elif drag['surface']=='map':self.select_map_aircraft(drag['slot'])
        else:self.select_aircraft_slot(drag['slot'])
        return 'break'

    def reorder_aircraft(self,source,target):
        capacity=self.aircraft_capacity
        aircraft=self.aircraft.get(source)
        if source==target or not (0<=source<capacity and 0<=target<capacity) or aircraft is None or not aircraft.alive:return False
        # Insert at the destination, shifting intervening slots and preserving objects.
        contents=[(slot,self.aircraft.get(slot)) for slot in range(capacity)]
        contents.insert(target,contents.pop(source))
        mapping={old:new for new,(old,unit) in enumerate(contents)}
        reordered={slot:unit for slot,unit in self.aircraft.items() if slot>=capacity}
        for slot,(old,unit) in enumerate(contents):
            if unit is None:continue
            reordered[slot]=unit;unit.parking_slot=slot
            if unit.alive and unit.state in ('parked','servicing','queued'):unit.x,unit.y=parking_position(slot)
        self.aircraft.clear();self.aircraft.update(reordered)
        for name in ('aircraft_button_health','aircraft_damage_times'):
            records=getattr(self,name,{})
            setattr(self,name,{mapping.get(slot,slot):value for slot,value in records.items()})
        self.aircraft_slot=mapping.get(self.aircraft_slot,self.aircraft_slot)
        self.aircraft_button_states=None;self.unit_list_signature=None;self.auto_prompt_signature=None
        self.last_shortcut=(None,0.)
        self.refresh_map_aircraft_buttons();self.refresh_slot_colors()
        if self.aircraft_menu_open:self.refresh_aircraft_menu()
        if self.left_menu=='Unit List':self.refresh_unit_list()
        self.refresh_auto_prompts();self.refresh_inspector();self.request_draw()
        return True

    def select_aircraft_slot(self,slot):
        if not 0<=slot<max(HANGAR_LEVELS):return
        self.aircraft_slot=slot
        self.refresh_aircraft_menu()

    def unlocked(self,item):return self.airfield.level>=UNLOCK_LEVELS.get(item,1)

    def loadout_unlocked(self,value):
        if value=='Empty':return True
        for weapon in ('AIM-120','AIM-9','AGM-88','Sidearm'):
            if weapon in value:return self.unlocked(weapon)
        for weight in map(int,STATS['bombs']):
            if str(weight) in value.replace(',',''):return self.unlocked(f'{weight} lb bomb')
        return False

    def refresh_airfield_unlocks(self):
        level=self.airfield.level
        if hasattr(self,'airfield_menu_title'):self.airfield_menu_title.set(f'Airfield Level {level}')
        text=f'Airfield L{level} · Max Level' if level==5 else f'Upgrade Airfield to L{level+1} · {dollars(self.upgrade_price("Airfield",level))}'
        for button in (self.airfield_level_button,self.inspector_airfield_level):
            button.configure(text=text,state='normal' if self.upgrade_available('Airfield',level) else 'disabled',style='GameUpgradeReady.TButton' if self.upgrade_available('Airfield',level) else 'TButton')
        if level!=getattr(self,'unlock_display_level',None):
            self.unlock_display_level=level
            items=AIRFIELD_UNLOCKS[level+1] if level<5 else ()
            self.airfield_unlock_text.set('Unlocks:\n'+'\n'.join('+'+item for item in items) if items else 'All unlocks available.')
            for host in self.unlock_hosts:
                for child in host.winfo_children():child.destroy()
                ttk.Label(host,text='Unlocks:' if items else 'All unlocks available.').pack(anchor='w')
                for item in items:ttk.Label(host,text='+'+item,font=('Helvetica',10,'bold'),foreground='#72d693').pack(anchor='w',pady=1)
            if hasattr(self,'airfield_scroll_canvas'):self.bind_menu_wheel(self.airfield_panel,self.airfield_scroll_canvas)
        for item,button in (('Radar',self.radar_button),('LR Radar',self.lr_radar_button),('SAM',self.sam_button),('LR SAM',self.lr_sam_button),('CIWS',self.ciws_button),('Flak',self.flak_button),('EWR',self.ewr_button),('PAC-3',self.pac3_button),('Missile Silo',self.player_silo_button)):
            unlocked=self.unlocked(item)
            if not unlocked:
                button.configure(state='disabled',image='',text=f'{item} - Requires Level {UNLOCK_LEVELS.get(item,1)} Airfield',style='GameLockedBuild.TButton')
                continue
            button.configure(state='normal',text='')
            if button.cget('style')=='GameLockedBuild.TButton':button.configure(style='TButton')
            stats=STATS['ground_units'][item]
            signature=(self.money>=stats['price'],max(0,stats['power']-max(0,self.power_capacity-self.power_used)))
            if not hasattr(self,'build_image_states'):self.build_image_states={}
            image=self.build_button_images[item]
            if self.build_image_states.get(item)!=signature:image=self.build_unit_image(item)
            ready=signature[0] and signature[1]==0
            button_style=button.cget('style') if button.cget('style')=='Selected.TButton' else 'GamePurchaseReady.TButton' if ready else 'TButton'
            # Keep the old PhotoImage alive until the widget has accepted its replacement.
            button.configure(image=image,style=button_style)
            self.build_button_images[item]=image
            self.build_image_states[item]=signature

    def build_unit_image(self,key):
        s=STATS['ground_units'][key]
        return self.purchase_button_image(key,s['price'],s['power'])

    def purchase_button_image(self,title,amount,power=0):
        font=ImageFont.truetype(findfont('DejaVu Sans'),12)
        title=title+' · ';price=dollars(amount)
        width=round(font.getlength(title)+font.getlength(price))+power*12+12
        image=Image.new('RGBA',(width,26),(0,0,0,0));draw=ImageDraw.Draw(image)
        draw.text((2,5),title,fill=TEXT,font=font)
        x=2+font.getlength(title);draw.text((x,5),price,fill='#72d693' if self.money>=amount else '#ef6262',font=font)
        x+=font.getlength(price)+6
        available=max(0,self.power_capacity-self.power_used)
        for n in range(power):
            bx=x+n*12
            draw.polygon([(bx+5,2),(bx,13),(bx+4,13),(bx+2,23),(bx+10,10),(bx+6,10),(bx+8,2)],fill='#ffd52a' if n<available else '#ef6262')
        return ImageTk.PhotoImage(image,master=self)

    def build_unit_text(self,key):
        s=STATS['ground_units'][key]
        return f'{key} · {dollars(s["price"])}'

    def play_game_sound(self,event,position=None,volume_multiplier=1.):
        audio=getattr(self,'game_audio',None)
        if audio is None or not self.winfo_ismapped():return
        distance=0.
        if position is not None:
            width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
            x,y=self.pixel(*position)
            distance=max(abs(x-width/2)/(width/2),abs(y-height/2)/(height/2))
        if volume_multiplier==1.:audio.play(event,getattr(self,'view_width',10),distance)
        else:audio.play(event,getattr(self,'view_width',10),distance,volume_multiplier=volume_multiplier)

    def toggle_game_mute(self):
        self.game_audio.set_muted(not self.game_audio.muted)
        self.app.game_audio_muted=self.game_audio.muted
        self.mute_button.configure(text='Unmute' if self.game_audio.muted else 'Mute',style='GameMuted.TButton' if self.game_audio.muted else 'GameMute.TButton')

    def buy_aircraft(self,kind,rebuy=False):
        slot=self.aircraft_slot
        old=self.aircraft.get(slot)
        if kind not in AIRCRAFT_TYPES or not self.unlocked(kind) or kind=='Suicide Drone' or not 0<=slot<self.aircraft_capacity or (old is not None and old.alive) or self.money<AIRCRAFT_TYPES[kind]['price']:return False
        if rebuy and (old is None or old.alive or getattr(old,'sold',False) or old.kind!=kind):return False
        spec=AIRCRAFT_TYPES[kind]
        hardpoints,bays=DEFAULT_LOADOUTS.get(kind,(['Empty']*spec['hardpoints'],['Empty']*spec['bays']))
        hardpoints=[value if self.loadout_unlocked(value) else loadout_label('2× AIM-9') for value in hardpoints]
        bays=[value if self.loadout_unlocked(value) and bomb_bay_allowed(kind,value) else loadout_label('4× 250 lb Bomb') for value in bays]
        if rebuy:
            hardpoints=list(old.hardpoints);bays=list(old.bays)
        self.spend_money(spec["price"],f'Buy {kind} #{slot+1}')
        self.play_game_sound('buy_aircraft')
        self.aircraft[slot]=Aircraft(kind,list(hardpoints),list(bays),parking_slot=slot,state='parked',purchase_price=spec["price"])
        if rebuy:
            self.aircraft[slot].color=old.color
            self.aircraft[slot].redeploy_on_rtb=old.redeploy_on_rtb
        self.progress_action('build',kind)
        if old is not None and self.selected is old:self.selected=self.aircraft[slot]
        self.refresh_aircraft_menu();self.refresh_inspector()
        self.refresh_map_aircraft_buttons();self.request_draw()
        return True

    def sell_aircraft(self,slot):
        aircraft=self.aircraft.get(slot)
        if aircraft is None or not aircraft.in_hangar:return False
        refund=aircraft.purchase_price*STATS['economy']['sell_refund_fraction']
        self.money+=refund;self.add_log(f'Sell {aircraft.kind} #{slot+1} · +{dollars(refund)}','reward')
        aircraft.sold=True;aircraft.destroy();del self.aircraft[slot]
        if self.selected is aircraft:self.selected=self.airfield
        self.refresh_aircraft_menu();self.refresh_inspector()
        self.refresh_map_aircraft_buttons();self.request_draw()
        return True

    def set_aircraft_loadout(self,slot,group,index,value):
        aircraft=self.aircraft.get(slot)
        options=HARDPOINT_LOADOUTS if group=='hardpoints' else BAY_LOADOUTS if group=='bays' else ()
        if aircraft is None or not aircraft.in_hangar or value not in options or not self.loadout_unlocked(value):return False
        if group=='bays' and not bomb_bay_allowed(aircraft.kind,value):return False
        if aircraft.kind=='Bomber' and group=='hardpoints' and 'AIM-120' in value:return False
        stations=getattr(aircraft,group)
        if not 0<=index<len(stations):return False
        changed=aircraft.change_loadout(group,index,value,self.airfield.ground_crew_level)
        if changed:self.refresh_inspector();self.request_draw()
        return changed

    @staticmethod
    def hangar_deploy_state(aircraft):
        if aircraft.state=='queued':return 'Queued','GamePause.TButton','normal'
        if aircraft.state in ('parked','servicing'):
            return 'Deploy','GamePlay.TButton','normal' if aircraft.state=='parked' and not aircraft.needs_service else 'disabled'
        return 'Aircraft is airborne','TButton','disabled'

    def hangar_deploy(self,slot):
        aircraft=self.aircraft.get(slot)
        if aircraft is None or not aircraft.alive:return False
        if aircraft.state=='queued':changed=aircraft.cancel_departure()
        elif aircraft.state=='parked' and not aircraft.needs_service:
            aircraft.mode='loiter';aircraft.orbit_center=(0.,0.)
            aircraft.depart();changed=aircraft.state=='queued'
        else:return False
        if changed:
            self.refresh_aircraft_menu();self.refresh_inspector();self.request_draw()
        return changed

    def aircraft_menu_state(self):
        aircraft=self.aircraft.get(self.aircraft_slot)
        return (self.aircraft_slot,id(aircraft),aircraft.alive if aircraft else False,
                aircraft.in_hangar if aircraft else False,
                aircraft.state if aircraft else None,aircraft.needs_service if aircraft else False,
                aircraft.redeploy_on_rtb if aircraft else False,
                tuple((k,self.money>=s['price']) for k,s in AIRCRAFT_TYPES.items()) if aircraft is None or not aircraft.alive else None,self.airfield.level,self.aircraft_capacity)

    def refresh_aircraft_menu(self):
        self.aircraft_menu_signature=self.aircraft_menu_state()
        self.refresh_slot_colors()
        self.color_buttons={}
        self.aircraft_buy_images={}
        for widget in self.aircraft_content.winfo_children():widget.destroy()
        content=self.aircraft_content
        slot=self.aircraft_slot
        aircraft=self.aircraft.get(slot)
        if aircraft is not None and not aircraft.alive:aircraft=None
        ttk.Label(content,text=f'Slot {slot+1} · {aircraft.kind if aircraft else "Empty"}',
                  font=('Helvetica',11,'bold')).pack(anchor='w',pady=(6,8))
        if slot>=self.aircraft_capacity:
            ttk.Label(content,text='Upgrade your hangers to unlock more slots',wraplength=260,foreground=MUTED).pack(anchor='w',pady=8)
        elif aircraft is None:
            previous=self.aircraft.get(slot)
            if previous is not None and not previous.alive and not getattr(previous,'sold',False):
                ready=self.unlocked(previous.kind) and self.money>=AIRCRAFT_TYPES[previous.kind]['price']
                ttk.Button(content,text=f'Rebuy: {previous.kind}',style='GamePurchaseReady.TButton' if ready else 'TButton',
                           state='normal' if ready else 'disabled',command=lambda k=previous.kind:self.buy_aircraft(k,rebuy=True)).pack(fill='x',pady=(0,12))
            for kind in AIRCRAFT_BUY_ORDER:
                spec=AIRCRAFT_TYPES[kind]
                unlocked=self.unlocked(kind)
                card=ttk.Frame(content);card.pack(fill='x',pady=(0,12))
                ttk.Label(card,text=kind,foreground=TEXT if unlocked else MUTED,font=('Helvetica',10,'bold')).pack(anchor='w')
                ttk.Label(card,foreground=TEXT if unlocked else MUTED,text=AIRCRAFT_DESCRIPTIONS[kind],wraplength=260,justify='left').pack(anchor='w',fill='x',pady=(3,0))
                ttk.Label(card,text=aircraft_mil_performance_text(spec)+"\n"
                          f"{spec['hardpoints']} Hardpoints · {spec['bays']} Bomb Bays\n{spec['cms']} Countermeasures",justify='left',foreground=TEXT if unlocked else MUTED).pack(anchor='w',pady=3)
                if unlocked:
                    self.aircraft_buy_images[kind]=self.purchase_button_image(f'Buy {kind}',spec['price'])
                ttk.Button(card,style='GamePurchaseReady.TButton' if unlocked and self.money>=spec['price'] else 'TButton',text='' if unlocked else f'Level {UNLOCK_LEVELS.get(kind,1)} Airfield Required',image=self.aircraft_buy_images.get(kind,''),compound='center',state='normal' if unlocked and self.money>=spec["price"] else 'disabled',command=lambda k=kind:self.buy_aircraft(k)).pack(fill='x')
        else:
            spec=AIRCRAFT_TYPES[aircraft.kind]
            ttk.Label(content,text=aircraft_mil_performance_text(spec)+f"\nCountermeasures: {spec['cms']}",justify='left').pack(anchor='w',pady=(0,10))
            self.color_name=tk.StringVar()
            ttk.Label(content,textvariable=self.color_name).pack(anchor='w',pady=(0,4))
            palette=ttk.Frame(content);palette.pack(fill='x',pady=(0,10))
            self.color_buttons={}
            for index,(name,color) in enumerate(AIRCRAFT_COLORS):
                style=ttk.Style(self);style_name=f'GameAircraftColor{index}.TButton'
                style.configure(style_name,background=color,bordercolor=BG,borderwidth=2,relief='solid',padding=3)
                style.map(style_name,background=[('active',color),('pressed',color)])
                button=ttk.Button(palette,text='',width=3,style=style_name,
                                  command=lambda c=color,n=slot:self.set_aircraft_color(n,c))
                button.grid(row=index//5,column=index%5,padx=2,pady=2,sticky='nsew')
                self.color_buttons[color]=button
            for col in range(5):palette.columnconfigure(col,weight=1,uniform='palette')
            self.refresh_color_selection()
            if aircraft.in_hangar:
                hardpoint_options=tuple(value for value in HARDPOINT_LOADOUTS if self.loadout_unlocked(value) and (aircraft.kind!='Bomber' or 'AIM-120' not in value))
                bay_options=tuple(value for value in BAY_LOADOUTS if self.loadout_unlocked(value) and bomb_bay_allowed(aircraft.kind,value))
                for group,title,options in (('hardpoints','Hardpoint',hardpoint_options),('bays','Bomb Bay',bay_options)):
                    for index,value in enumerate(getattr(aircraft,group)):
                        ttk.Label(content,text=f'{title} {index+1}').pack(anchor='w',pady=(5,2))
                        font=tkfont.nametofont('TkTextFont')
                        text_width=math.ceil(max(font.measure(option) for option in options)/max(1,font.measure('0')))+1
                        combo=ttk.Combobox(content,values=options,state='readonly',width=text_width)
                        combo.set(value);combo.pack(anchor='w',pady=(0,3))
                        combo.bind('<<ComboboxSelected>>',lambda e,n=slot,g=group,i=index,c=combo:
                                   self.set_aircraft_loadout(n,g,i,c.get()))
                ttk.Button(content,style='GameSell.TButton',text=f'Sell · {dollars(aircraft.purchase_price*STATS["economy"]["sell_refund_fraction"])} refund',command=lambda n=slot:self.sell_aircraft(n)).pack(fill='x',pady=(12,0))
            else:ttk.Label(content,text='Loadout editing and selling are available in the hangar.',wraplength=260,justify='left').pack(fill='x',pady=(8,0))
            deploy_text,deploy_style,deploy_state=self.hangar_deploy_state(aircraft)
            ttk.Button(content,text=f'Redeploy after RTB: {"On" if aircraft.redeploy_on_rtb else "Off"}',
                       style='GamePlay.TButton' if aircraft.redeploy_on_rtb else 'TButton',
                       command=lambda n=slot:self.toggle_aircraft_redeploy(n)).pack(fill='x',pady=(8,0))
            ttk.Button(content,text=deploy_text,style=deploy_style,state=deploy_state,command=lambda n=slot:self.hangar_deploy(n)).pack(fill='x',pady=(8,0))
        # Wheel scrolling stays local to this panel and never zooms the map.
        def bind_wheel(widget):
            if not isinstance(widget,ttk.Combobox):
                widget.bind('<MouseWheel>',self.scroll_aircraft_menu)
                widget.bind('<Button-4>',lambda e:self.aircraft_canvas.yview_scroll(-1,'units'))
                widget.bind('<Button-5>',lambda e:self.aircraft_canvas.yview_scroll(1,'units'))
            for child in widget.winfo_children():bind_wheel(child)
        bind_wheel(content)
        self.aircraft_canvas.yview_moveto(0)

    def toggle_aircraft_redeploy(self,slot):
        aircraft=self.aircraft.get(slot)
        if aircraft is None or not aircraft.alive:return False
        aircraft.set_redeploy_on_rtb(not aircraft.redeploy_on_rtb)
        self.refresh_aircraft_menu();self.refresh_inspector();self.request_draw()
        return True

    @property
    def power_capacity(self):
        return POWER_LEVELS[self.airfield.power_level-1]

    @property
    def power_used(self):
        return sum(unit.power for unit in self.radars+self.sams+self.ciws+self.player_silos if unit.alive)

    @property
    def income_per_minute(self):
        return FACTORY_INCOME[self.airfield.factory_level-1] if self.airfield.alive else 0

    def upgrade_button_text(self,kind,level):
        if level>=5:return f'{"Generator" if kind=="Power" else kind} · Max Level'
        gain=(f'+{POWER_LEVELS[level]-POWER_LEVELS[level-1]} energy' if kind=='Power' else
              f'+{HANGAR_LEVELS[level]-HANGAR_LEVELS[level-1]} hangars' if kind=='Hangars' else
              f'{dollars(FACTORY_INCOME[level])}/min' if kind=='Factory' else
              f'{LOGISTICS_LEVELS[level]} Helis · {logistics_reload_multiplier(level+1):g}× Reload' if kind=='Logistics' else f'{crew_count(level+1)} crews')
        name='Generator' if kind=='Power' else kind
        return f'{name} L{level+1} · {gain} · {dollars(self.upgrade_price(kind,level))}'

    def upgrade_available(self,kind,level):
        return level<5 and (kind=='Airfield' or level<self.airfield.level) and self.money>=self.upgrade_price(kind,level)

    def upgrade_price(self,kind,level):
        return STATS['upgrades']['prices'][kind][min(level-1,3)]

    def unit_color(self,unit):
        if not unit.alive:return '#586070'
        if isinstance(unit,(Aircraft,LogisticsHelicopter)):return unit.color
        if isinstance(unit,PlayerMissileSilo):return '#69adff'
        if isinstance(unit,Factory) or getattr(unit,'enemy',False):return '#ef6262'
        if isinstance(unit,SAMLauncher):return SAM_COLOR
        if isinstance(unit,Radar):
            return '#6cd9af' if unit.enabled else self.muted_map_color('#6cd9af',.75)
        if isinstance(unit,Flak):return '#ffb347'
        if isinstance(unit,CIWS):return CIWS_COLOR
        return TEXT

    def draw_power_icons(self,canvas,y=12,start=2,columns=30,used_from_right=False):
        for slot in range(self.power_capacity):
            x=start+(slot%columns)*14
            row_y=y+(slot//columns)*22
            used=slot>=self.power_capacity-self.power_used if used_from_right else slot<self.power_used
            color='#586070' if used else '#ffe66d'
            canvas.create_polygon(x+7,row_y-9,x+1,row_y+1,x+6,row_y+1,x+3,row_y+10,
                                  x+12,row_y-3,x+7,row_y-3,fill=color,outline='')

    def refresh_resources(self):
        self.refresh_airfield_unlocks()
        self.cash_text.set(f'${self.money:,.0f}')
        crew_level=self.airfield.ground_crew_level
        working=sum(a.crew_active for a in self.aircraft.values() if a.state=='servicing')
        self.crew_text.set(f'Repair: {crew_repair_seconds(crew_level):g}s/HP - {crew_weapon_seconds(crew_level):g}s/Weapon\nRefuel {ground_refuel_rate(crew_level):g} units/second')
        deployed=sum(h.state!='parked' for h in self.logistics.helicopters)
        support_key=(crew_level,working,self.airfield.logistics_level,deployed)
        if support_key!=getattr(self,'support_signature',None):
            self.support_signature=support_key
            self.draw_support_icons(self.hud_crew,'crew',crew_count(crew_level),working)
            self.draw_support_icons(self.hud_logistics,'logistics',LOGISTICS_LEVELS[self.airfield.logistics_level-1],deployed)
        used=sum(a.alive for a in self.aircraft.values())
        key=(self.power_capacity,self.power_used,self.airfield.factory_level,
             self.income_per_minute,self.aircraft_capacity,used)
        if key==getattr(self,'resource_signature',None):return
        self.resource_signature=key
        self.hud_power.configure(width=self.power_capacity*14+4)
        self.hud_power.delete('all');self.draw_power_icons(self.hud_power,used_from_right=True)
        self.airfield_menu_text.set(dollars(self.income_per_minute))
        c=self.airfield_resources;c.delete('all')
        c.create_text(0,16,text='Aircraft:',anchor='w',fill=TEXT)
        # Fighter silhouette: nose, swept wings, fuselage, and tail fins.
        vertices=((0,-11),(2,-3),(8,3),(8,6),(2,3),(2,8),(5,10),
                  (5,12),(0,10),(-5,12),(-5,10),(-2,8),(-2,3),
                  (-8,6),(-8,3),(-2,-3))
        for slot in range(self.aircraft_capacity):
            points=[v for x,y in vertices for v in (65+slot*20+x,15+y)]
            c.create_polygon(*points,outline='#87caff',fill='#87caff' if slot<used else '',width=1)

    def upgrade(self,kind):
        attr=UPGRADE_ATTRIBUTES[kind]
        level=getattr(self.airfield,attr)
        if level>=5 or (kind!='Airfield' and level>=self.airfield.level):return False
        cost=self.upgrade_price(kind,level)
        if self.money<cost:return False
        self.spend_money(cost,f'{"Generator" if kind=="Power" else kind} upgrade L{level+1}','upgrade')
        setattr(self.airfield,attr,level+1)
        self.play_game_sound('upgrade')
        self.logistics.sync(LOGISTICS_LEVELS[self.airfield.logistics_level-1],self.airfield)
        self.operations.ground_crew_level=self.airfield.ground_crew_level
        if kind=='Ground Crew':
            for a in self.aircraft.values():
                if a.state!='servicing':continue
                a.retime_service(self.airfield.ground_crew_level)
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        if self.aircraft_menu_open:self.refresh_aircraft_menu()
        return True

    def toggle_radar_power(self):
        if not isinstance(self.selected,(Radar,CIWS)) or isinstance(self.selected,Flak) or not self.selected.alive:return
        self.selected.enabled=not self.selected.enabled
        if isinstance(self.selected,CIWS) and not self.selected.enabled:self.selected.attack_target=None;self.selected.shot_timer=0.
        self.coverage_key=None
        self.refresh_inspector();self.request_draw()

    def toggle_ciws_target(self,kind):
        if isinstance(self.selected,CIWS):
            if kind in self.selected.preferred_targets:self.selected.preferred_targets.remove(kind)
            else:self.selected.preferred_targets.add(kind)
            self.refresh_inspector()

    def toggle_ciws(self,kind='CIWS'):
        was=self.placing_ciws and self.placing_gun_kind==kind
        if not self.unlocked(kind):return False
        self.show_left_menu('Build',cancel=False);self.cancel_commands()
        if was:return
        self.placing_ciws=True;self.placing_gun_kind=kind;self.selected=None
        self.point_defence_button.configure(style='GamePointDefence.TButton')
        (self.flak_button if kind=='Flak' else self.ciws_button).configure(style='Selected.TButton');self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair');self.refresh_inspector();self.request_draw()

    def place_ciws(self,x,y):
        unit_type=Flak if self.placing_gun_kind=='Flak' else CIWS
        unit=unit_type(self.next_build_id('ciws',self.ciws),x,y)
        error=self.placement_error(unit)
        if error:self.inspector_text.set(error);return
        self.play_game_sound('place_unit')
        self.spend_money(unit.price,f'Build {unit.name} #{unit.id}');self.ciws.append(unit);self.progress_action('build',unit.stats_key);self.cancel_placement();self.selected=unit
        self.cash_text.set(dollars(self.money));self.refresh_inspector();self.request_draw()
        return unit

    def inspected_name(self,unit):
        if unit is None:return 'Inspector'
        if isinstance(unit,RWRSignal):return 'RWR Signal'
        if unit is self.airfield:return f'Airfield Level {unit.level}'
        if isinstance(unit,(Airfield,LogisticsHelicopter,Missile,Bomb,ICBM)):return unit.name
        if isinstance(unit,Aircraft):return self.combat.unit_name(unit)
        if isinstance(unit,EnemyRunway):return unit.name
        name=unit.name
        if getattr(unit,'enemy',False) and not name.startswith('Enemy '):name='Enemy '+name
        return f'{name} #{unit.id}'

    def building_description_text(self,unit):
        if not isinstance(unit,(Building,Factory,Airfield)):return None
        stats=unit.stats
        description=(self.campaign.settings.get('runway_description','') if isinstance(unit,EnemyRunway) else stats.get('description','')).strip()
        lines=[]
        radar=unit.range_nm if isinstance(unit,Radar) else getattr(unit,'radar_range_nm',stats.get('radar_range_nm',0))
        visual=getattr(unit,'visual_range_nm',stats.get('visual_range_nm',0))
        engagement=getattr(unit,'range_nm',stats.get('range_nm',0)) if isinstance(unit,(SAMLauncher,CIWS)) else 0
        if radar>0:lines.append(f'Radar Range: {radar:g} NM')
        if visual>0:lines.append(f'Optical Range: {visual:g} NM')
        minimum=getattr(unit,'min_engagement_range_nm',0)
        if engagement>0:
            distance=f'{minimum:g}–{engagement:g}' if minimum>0 else f'{engagement:g}'
            lines.append(f'Engagement Range: {distance} NM')
        elif isinstance(unit,PlayerMissileSilo):lines.append(f'Engagement Range: {minimum:g}+ NM (no maximum)')
        if isinstance(unit,SAAW) and unit.gun_range_nm>0:lines.append(f'Gun Engagement Range: {unit.gun_range_nm:g} NM')
        return '\n\n'.join(part for part in (description,'\n'.join(lines)) if part) or 'No description set.'

    def build_preview_unit(self):
        if self.placing_player_silo:return PlayerMissileSilo(0,0,0)
        if self.placing_radar:return Radar(0,0,0,long_range=self.placing_lr,early_warning=self.placing_ewr)
        if self.placing_sam:return self.sam_preview(0,0)
        if self.placing_ciws:return (Flak if self.placing_gun_kind=='Flak' else CIWS)(0,0,0)
        return None

    def refresh_build_details(self):
        unit=self.build_preview_unit()
        if unit is None:
            self.building_details_panel.pack_forget()
            self.build_details_signature=None
            return
        text=self.building_description_text(unit)
        signature=(unit.name,text)
        if signature==getattr(self,'build_details_signature',None):return
        self.build_details_signature=signature
        self.building_details_title.set(unit.name)
        self.building_details_text.set(text)
        self.building_details_panel.pack_forget()
        self.building_details_panel.pack(fill='x',pady=(12,4))
        # Reveal the preview beneath the list once; preserve manual scrolling after.
        self.after_idle(lambda:self.build_scroll_canvas.yview_moveto(1.))

    def buildable_reload_state(self,unit):
        if isinstance(unit,PlayerMissileSilo) and unit.alive and unit.reload_due>self.elapsed:
            remaining=unit.reload_due-self.elapsed
            return max(0.,min(1.,1-remaining/max(1e-9,unit.stats['reload_seconds']))),remaining,'Refueling'
        if (isinstance(unit,(SAMLauncher,CIWS)) and unit.alive and not unit.enemy
            and id(unit) in self.logistics.reloads):
            total=unit.stats['reload_seconds']
            progress=max(0.,min(1.,1-unit.logistics_reload_work_remaining/max(1e-9,total)))
            return progress,unit.logistics_reload_remaining,'Reloading'
        return None

    def refresh_reload_progress(self):
        state=self.buildable_reload_state(self.selected)
        if state is None:
            self.reload_progress_panel.pack_forget();return
        progress,remaining,title=state
        self.reload_progress_text.set(f'{title} · {progress:.0%} · {max(0,math.ceil(remaining))}s remaining')
        self.reload_progress_bar.configure(value=progress*100)
        self.reload_progress_panel.pack(fill='x',pady=(8,8),before=self.inspector_label)
        # The progress instrument already carries the reload timer.
        self.inspector_text.set('')

    def draw_buildable_reload_bars(self):
        fleet=getattr(self,'logistics',None)
        if fleet is None:return
        c=self.canvas
        for unit in (*fleet.reloads.values(),*self.player_silos):
            state=self.buildable_reload_state(unit)
            if state is None:continue
            progress,_,_=state
            dot=self.ground_dot_required(unit)
            x,y=self.ground_pixel(unit) if dot else self.pixel(unit.x,unit.y)
            y+=13 if dot else max(13,25*self.building_factor()*.5)
            tags=('game_combat','ground_markers',f'ground_marker_{id(unit)}','ground_reload_bar')
            c.create_rectangle(x-16,y,x+16,y+5,fill=PANEL,outline=MUTED,tags=tags)
            if progress>0:c.create_rectangle(x-15,y+1,x-15+30*progress,y+4,fill='#72d693',outline='',tags=tags)

    def refresh_inspector(self):
        self.refresh_airfield_unlocks()
        if isinstance(self.selected,RWRSignal):self.refresh_selected_rwr()
        unit=self.selected
        self.inspector_title.set(self.inspected_name(unit))
        self.inspector_heading.configure(foreground=self.unit_color(unit) if unit is not None else TEXT)
        layout=(type(unit),unit is self.airfield,getattr(unit,'enemy',False),getattr(unit,'alive',False),getattr(unit,'kind',None),self.placing_radar,self.placing_sam,self.placing_ciws,self.see_all,getattr(unit,'early_warning',False))
        layout_changed=layout!=getattr(self,'inspector_layout',None)
        if layout_changed:
            self.inspector_layout=layout
            for widget in (self.aircraft_instruments,self.ground_instruments,self.icbm_instruments,self.projectile_instruments,self.helicopter_instruments,self.silo_instruments,self.ewr_controls,self.ewr_bearing_controls,self.pac3_controls,self.pac3_ammo,self.airfield_health,self.rwr_confidence,self.resupply_button,self.upgrade_panel,self.aircraft_controls,self.sam_controls,self.radar_controls,self.ciws_controls,self.silo_toggle_button,self.destroy_unit_button,self.player_silo_panel):widget.pack_forget()
            self.engagement_controls.pack_forget();self.attack_button.pack_forget()
        self.refresh_follow_button()
        self.refresh_resources()
        for kind,button in self.airfield_upgrade_buttons.items():
            level=getattr(self.airfield,UPGRADE_ATTRIBUTES[kind])
            cost=self.upgrade_price(kind,level)
            button.configure(text=self.upgrade_button_text(kind,level),
                             state='normal' if self.upgrade_available(kind,level) else 'disabled',
                             style='GameUpgradeReady.TButton' if self.upgrade_available(kind,level) else 'GameUpgrade.TButton')
        if self.selected is self.airfield:
            self.airfield_health.update_health(self.airfield)
            self.airfield_health.pack(fill='x',before=self.inspector_label)
            self.inspector_text.set(f'Airfield Level: {self.airfield.level}\n'
                f'Position: {self.airfield.x:g}, {self.airfield.y:g} NM\n'
                f'Runway: {self.airfield.runway_length:g} NM × {self.airfield.runway_width_ft:g} ft\n\n'
                f'Generator Level {self.airfield.power_level}: {self.power_used}/{self.power_capacity} Used\n'
                f'Hangars Level {self.airfield.hangar_level}: {sum(a.alive for a in self.aircraft.values())}/{self.aircraft_capacity} Aircraft\n'
                f'Factory Level {self.airfield.factory_level}: {dollars(self.income_per_minute)}/min\n'
                f'Logistics Level {self.airfield.logistics_level}: {LOGISTICS_LEVELS[self.airfield.logistics_level-1]} Helicopters · {logistics_reload_multiplier(self.airfield.logistics_level):g}× Reload\n'
                f'Ground Crew L{self.airfield.ground_crew_level}: {crew_repair_seconds(self.airfield.ground_crew_level):g}s/HP, {crew_weapon_seconds(self.airfield.ground_crew_level):g}s/weapon')
            self.upgrade_panel.pack(fill='x',pady=(12,0))
            for kind,button in self.upgrade_buttons.items():
                level=getattr(self.airfield,UPGRADE_ATTRIBUTES[kind])
                cost=self.upgrade_price(kind,level)
                button.configure(text=self.upgrade_button_text(kind,level),
                                 state='normal' if self.upgrade_available(kind,level) else 'disabled',
                             style='GameUpgradeReady.TButton' if self.upgrade_available(kind,level) else 'GameUpgrade.TButton')
        elif isinstance(self.selected,RWRSignal):
            self.rwr_confidence.update_signal(self.selected)
            self.rwr_confidence.pack(fill='x',before=self.inspector_label)
            self.inspector_text.set('')
        elif isinstance(self.selected,PlayerMissileSilo):
            self.refresh_player_silo(self.selected)
        elif isinstance(self.selected,ICBM):
            self.icbm_instruments.update_missile(self.selected)
            self.icbm_instruments.pack(fill='x',before=self.inspector_label)
            self.inspector_text.set('')
        elif isinstance(self.selected,Aircraft):
            a=self.selected
            slot=self.aircraft_number(a)
            self.aircraft_instruments.update_aircraft(a,slot)
            self.aircraft_instruments.pack(fill='x',before=self.inspector_label)
            details=[]
            if a.defensive_missile is not None:details.append('Defensive · Break '+('right' if a.defensive_side>0 else 'left')+(f' · {a.defensive_speed:.0f} kt' if a.defensive_speed is not None else ''))
            if a.state=='servicing':details.append(f'Ground Crew: {"Working" if a.crew_active else "Waiting"} · {a.service_progress:.0%}')
            self.refresh_form_up_button()
            if a.refueling_from is not None:details.append(f'Refueling: KC-49 #{self.aircraft_number(a.refueling_from)}')
            if a.enemy and self.combat.reload_status(a,self.elapsed):details.append('Reloading: '+self.combat.reload_status(a,self.elapsed))
            if a.kind=='KC-49':details.append(f'Refuel Radius: {REFUEL_RADIUS_NM:g} NM')
            self.inspector_text.set('\n'.join(details))
            if not a.enemy and a.alive:self.aircraft_controls.pack(fill='x',pady=(6,0))
            if not a.enemy and a.in_hangar:self.change_loadout_button.pack(fill='x',before=self.aircraft_deploy_row,pady=(0,4))
            else:self.change_loadout_button.pack_forget()
            self.rtb_button.configure(text='Queued' if a.state=='queued' else 'Take' if a.state=='takeoff' else 'Deploy' if a.state in ('parked','servicing') else 'RTB',
                                      style='GamePause.TButton' if a.state=='queued' else 'GamePlay.TButton' if a.mode=='rtb' and a.state in ('rtb','approach','rollout') else 'TButton',
                                      state='disabled' if a.state=='servicing' or (a.state in ('parked','queued') and a.needs_service) else 'normal')
            combat_aircraft=a.kind in ('Fighter','Interceptor','Bomber')
            if combat_aircraft:
                self.attack_button.pack(fill='x',pady=(5,0),before=self.speed_controls)
                self.engagement_controls.pack(fill='x',after=self.speed_controls)
            self.attack_button.configure(text='Cancel Attack' if a.attack_target is not None else 'Attack',
                                         state='normal' if a.kind in ('Fighter','Interceptor','Bomber') else 'disabled')
            for kind,button in self.aircraft_target_buttons.items():
                button.configure(style='GamePlay.TButton' if kind in a.target_types else 'TButton')
            self.engagement_button.configure(text=f'Engagement Range: {a.engagement_range} NM')
            self.air_salvo_button.configure(text=f'Weapons per Target · Air: {a.air_weapons_per_target}')
            self.ground_salvo_button.configure(text=f'Weapons per Target · Ground: {a.ground_weapons_per_target}')
            if layout_changed:
                self.throttle_buttons['AB'].pack_forget()
                if a.has_afterburner:self.throttle_buttons['AB'].pack(side='left',fill='x',expand=True,padx=1)
            for setting,button in self.throttle_buttons.items():
                button.configure(style=('GameAB.TButton' if setting=='AB' else 'GamePlay.TButton') if a.effective_speed_setting==setting else 'TButton')
            self.fence_out_button.configure(style='GamePlay.TButton' if not a.fenced_in else 'TButton')
            self.fence_in_button.configure(style='GameFenceIn.TButton' if a.fenced_in else 'TButton',
                                          state='disabled' if a.mode=='rtb' else 'normal')
        elif isinstance(self.selected,(Missile,Bomb)):
            self.projectile_instruments.update_weapon(self.selected,self.elapsed)
            self.projectile_instruments.pack(fill='x',before=self.inspector_label)
            self.inspector_text.set('')
        elif isinstance(self.selected,CIWS):
            self.refresh_ground_instruments(self.selected,'flak' if isinstance(self.selected,Flak) else 'ciws')
            if not isinstance(self.selected,Flak):
                self.ewr_track_button.pack_forget()
                self.radar_toggle_button.configure(text='Radar On' if self.selected.enabled else 'Radar Off',style='GamePlay.TButton' if self.selected.enabled else 'TButton',state='normal' if self.selected.alive else 'disabled')
                if not self.selected.enemy or self.see_all:self.radar_controls.pack(fill='x')
            self.inspector_text.set(('Reloading: '+self.combat.reload_status(self.selected,self.elapsed)) if self.selected.enemy and self.combat.reload_status(self.selected,self.elapsed) else self.logistics.status(self.selected))
            if not self.selected.enemy or self.see_all:self.ciws_controls.pack(fill='x')
            for kind,b in self.ciws_target_buttons.items():
                b.configure(style='GamePlay.TButton' if kind in self.selected.preferred_targets else 'TButton')
                if layout_changed:
                    if isinstance(self.selected,Flak) and kind in ('Missiles','Bombs'):b.pack_forget()
                    else:b.pack(fill='x',pady=2)
        elif isinstance(self.selected,LogisticsHelicopter):
            h=self.selected
            self.helicopter_instruments.update_helicopter(h,self.airfield)
            self.helicopter_instruments.pack(fill='x',before=self.inspector_label)
            destination=f'{h.target.name} #{h.target.id}' if h.target is not None else 'Helipad'
            self.inspector_text.set(f'{h.state.title()}\nSpeed: {h.speed:g} knots\nDestination: {destination}')
        elif isinstance(self.selected,DroneLauncher):
            u=self.selected
            self.airfield_health.update_health(u)
            self.airfield_health.pack(fill='x',before=self.inspector_label)
            self.pac3_ammo.update_ammo(u)
            self.pac3_ammo.pack(fill='x',before=self.inspector_label)
            reload=self.combat.reload_status(u,self.elapsed)
            status='Destroyed' if not u.alive else 'Launch disabled' if not u.enabled else f'Rearming · {reload}' if reload else f'Next launch: {max(0,math.ceil(u.next_launch-self.elapsed))}s'
            self.inspector_text.set(f'Target: Airfield\nLaunch interval: {u.stats["shot_interval_seconds"]:g}s\n{status}')
            self.silo_toggle_button.configure(text='Engagement On' if u.enabled else 'Engagement Off',style='GamePlay.TButton' if u.enabled else 'TButton',state='normal' if u.alive else 'disabled')
            if self.see_all:self.silo_toggle_button.pack(fill='x',pady=(8,0))
        elif isinstance(self.selected,ICBMSilo):
            u=self.selected
            self.silo_instruments.update_silo(u,self.elapsed)
            self.silo_instruments.pack(fill='x',before=self.inspector_label)
            self.inspector_text.set('')
            self.silo_toggle_button.configure(text='Engagement On' if u.enabled else 'Engagement Off',style='GamePlay.TButton' if u.enabled else 'TButton',state='normal' if u.alive else 'disabled')
            if self.see_all:self.silo_toggle_button.pack(fill='x',pady=(8,0))
        elif isinstance(self.selected,Factory):
            self.airfield_health.update_health(self.selected)
            self.airfield_health.pack(fill='x',before=self.inspector_label)
            if isinstance(self.selected,EnemyRunway):
                r=self.selected
                self.inspector_text.set('Runway destroyed · Waves stopped' if not r.alive else f'Zone {r.band_number}\nWave {r.wave_number+1} in {max(0,math.ceil(r.next_wave-self.elapsed))}s\nAll runways must be destroyed to clear this zone.')
            else:self.inspector_text.set('Destroyed' if not self.selected.alive else 'Ground')
        elif isinstance(self.selected,Radar):
            if not self.selected.enemy or self.see_all:self.radar_controls.pack(fill='x')
            self.radar_toggle_button.configure(text='Radar On' if self.selected.enabled else 'Radar Off',
                style='GamePlay.TButton' if self.selected.enabled else 'TButton',state='normal' if self.selected.alive else 'disabled')
            self.refresh_ground_instruments(self.selected,'ewr' if self.selected.early_warning else 'radar')
            if self.selected.early_warning:
                r=self.selected
                self.ewr_point_text.set(f'Range: {r.range_points} points · {r.range_nm:g} NM\nWidth: {r.width_points} points · {r.radar_angle_deg:g}°')
                point_key=(id(r),r.range_points,r.width_points)
                if point_key!=getattr(self,'ewr_point_key',None):
                    self.ewr_point_key=point_key;self.ewr_points.delete('all')
                    for i in range(r.stats['configuration_points']):
                        self.ewr_points.create_rectangle(8+i*44,2,46+i*44,16,fill='#69adff' if i<r.range_points else '#59e887',outline='')
                self.ewr_range_button.configure(state='normal' if r.width_points>1 else 'disabled')
                self.ewr_width_button.configure(state='normal' if r.range_points>1 else 'disabled')
                self.ewr_rotate_button.configure(text='Stop Rotation' if r.auto_rotate else 'Rotate',style='GameUpgradeReady.TButton' if r.auto_rotate else 'TButton',state='normal' if r.alive else 'disabled')
                self.ewr_bearing_slider.configure(state='disabled' if r.auto_rotate or r.track_target is not None or not r.alive else 'normal')
                self.ewr_bearing_text.set(f'Bearing: {math.degrees(r.bearing)%360:03.0f}° → {math.degrees(r.desired_bearing)%360:03.0f}°')
                control_mode=(id(r),id(r.track_target),r.auto_rotate)
                if getattr(self,'ewr_control_mode',None)!=control_mode:
                    self.ewr_control_mode=control_mode;self.ewr_bearing_var.set(math.degrees(r.desired_bearing)%360)
                self.ewr_direction_button.configure(text='Clockwise ↻' if r.rotation_direction==1 else 'Counterclockwise ↺')
                self.ewr_track_button.configure(text='Cancel Track' if self.ewr_track_picker is r else 'Stop Tracking' if r.track_target is not None else 'Track',style='GamePlay.TButton' if r.track_target is not None or self.ewr_track_picker is r else 'TButton',state='normal' if r.alive else 'disabled')
                self.ewr_track_button.pack(fill='x',after=self.radar_toggle_button,pady=(0,4))
                self.ewr_controls.pack(fill='x',before=self.ground_instruments)
                self.radar_controls.pack(fill='x',before=self.ewr_controls)
                self.ewr_bearing_controls.pack(fill='x',after=self.ground_instruments)

            if not self.selected.early_warning:self.ewr_track_button.pack_forget()
            self.inspector_text.set('Click an enemy to track' if self.ewr_track_picker is self.selected else 'Tracking: '+self.combat.unit_name(self.selected.track_target) if self.selected.early_warning and self.selected.track_target is not None else '')
        elif isinstance(self.selected,SAMLauncher):
            self.refresh_ground_instruments(self.selected,'pac3' if isinstance(self.selected,PAC3) else 'saaw' if isinstance(self.selected,SAAW) else 'sam')
            if isinstance(self.selected,PAC3):
                p=self.selected
                self.pac3_bearing_text.set(f'Bearing: {math.degrees(p.bearing)%360:03.0f}° → {math.degrees(p.desired_bearing)%360:03.0f}° · {p.radar_angle_deg:g}° cone')
                if getattr(self,'pac3_control_unit',None) is not p:
                    self.pac3_control_unit=p;self.pac3_bearing_var.set(math.degrees(p.desired_bearing)%360)
                self.pac3_bearing_slider.configure(state='normal' if p.alive else 'disabled')
                self.pac3_engage_button.configure(text='Engagement On' if p.enabled else 'Engagement Off',style='GamePlay.TButton' if p.enabled else 'TButton',state='normal' if p.alive else 'disabled')
                self.pac3_controls.pack(fill='x',after=self.ground_instruments)
                self.pac3_ammo.update_ammo(p);self.pac3_ammo.pack(fill='x',after=self.pac3_controls)
                self.pac3_engage_button.pack(fill='x',before=self.target_buttons['Suicide Drones'],pady=(4,8))
            if not isinstance(self.selected,PAC3):self.pac3_engage_button.pack_forget()
            self.inspector_text.set(self.logistics.status(self.selected) if not self.selected.enemy else '' if isinstance(self.selected,SAAW) else 'Ready' if self.selected.ammo else 'Out of ammo')
            if self.selected.enemy and self.combat.reload_status(self.selected,self.elapsed):self.inspector_text.set('Reloading: '+self.combat.reload_status(self.selected,self.elapsed))
            if not self.selected.enemy or self.see_all:self.sam_controls.pack(fill='x')
            for kind,button in self.target_buttons.items():
                button.configure(style='GamePlay.TButton' if kind in self.selected.preferred_targets else 'TButton')
        elif self.placing_player_silo:
            self.inspector_title.set('Missile Silo')
            self.inspector_text.set(f'Cost: {dollars(STATS["ground_units"]["Missile Silo"]["price"])} · Power: {STATS['ground_units']['Missile Silo']['power']}\nSelect a location inside the building area.')
        elif self.placing_radar or self.placing_sam or self.placing_ciws:
            unit=Radar(0,0,0,long_range=self.placing_lr,early_warning=self.placing_ewr) if self.placing_radar else self.sam_preview(0,0)
            self.inspector_title.set(unit.name)
            self.inspector_text.set(f'Cost: {dollars(unit.price)}\nPower: {unit.power}\nRange: {unit.range_nm:g} NM\nSelect a location inside the building area.')
        else:self.inspector_text.set('Click a unit to inspect it.')
        if isinstance(self.selected,(SAMLauncher,CIWS)) and not self.selected.enemy and self.selected.alive:
            pending=self.logistics.requested(self.selected)
            self.resupply_button.configure(text='Resupply' if id(self.selected) in self.logistics.reloads else 'Resupply Requested' if pending else 'Resupply',state='disabled' if pending or self.selected.ammo>=self.selected.ammo_capacity or not self.airfield.alive else 'normal')
            self.resupply_button.pack(fill='x',pady=(8,0))
        if isinstance(self.selected,(Radar,SAMLauncher,CIWS)) and not self.selected.enemy and self.selected.alive:
            self.destroy_unit_button.pack(fill='x',pady=(12,4))
        self.refresh_reload_progress()
        self.refresh_build_details()
        if self.run_started and hasattr(self,'progress'):self.poll_progress()

    def set_pac3_bearing(self,value):
        if not isinstance(self.selected,PAC3):return
        self.selected.desired_bearing=math.radians(float(value)%360)
        p=self.selected
        self.pac3_bearing_text.set(f'Bearing: {math.degrees(p.bearing)%360:03.0f}° → {float(value)%360:03.0f}° · {p.radar_angle_deg:g}° cone')
        self.ground_instruments.render()

    def toggle_pac3_engagement(self):
        if not isinstance(self.selected,PAC3) or not self.selected.alive:return False
        self.selected.enabled=not self.selected.enabled
        self.refresh_inspector();self.request_draw();return True

    def sam_preview(self,x,y):
        return (PAC3 if self.placing_pac3 else SAMLauncher)(0,x,y,long_range=self.placing_lr)

    def shift_ewr_points(self,delta):
        radar=self.selected
        if not isinstance(radar,Radar) or not radar.early_warning or not radar.shift_points(delta):return False
        self.ground_instruments.scope_updated=-math.inf
        self.coverage_key=None;self.refresh_inspector();self.request_draw();return True

    def set_ewr_bearing(self,value):
        radar=self.selected
        if not isinstance(radar,Radar) or not radar.early_warning:return
        radar.desired_bearing=math.radians(float(value)%360)
        self.ewr_bearing_text.set(f'Bearing: {math.degrees(radar.bearing)%360:03.0f}° → {float(value)%360:03.0f}°')
        self.ground_instruments.render()

    def toggle_ewr_direction(self):
        radar=self.selected
        if not isinstance(radar,Radar) or not radar.early_warning:return False
        radar.rotation_direction*=-1
        self.refresh_inspector();return True

    def begin_ewr_track(self):
        radar=self.selected
        if not isinstance(radar,Radar) or not radar.early_warning or not radar.alive:return False
        if self.ewr_track_picker is radar:
            self.ewr_track_picker=None;self.canvas.configure(cursor='')
        elif radar.track_target is not None:
            radar.stop_tracking();self.ewr_bearing_var.set(math.degrees(radar.desired_bearing)%360)
        else:
            self.cancel_commands();self.selected=radar
            self.ewr_track_picker=radar;self.canvas.configure(cursor='crosshair')
        self.refresh_inspector();return True

    def choose_ewr_track(self,event):
        radar=self.ewr_track_picker
        targets=[]
        for target in self.combat.enemies:
            display=self.track_display(target)
            if target.alive and display is not None:targets.append((target,display[:2]))
        targets.extend((target,(target.x,target.y)) for target in self.combat.icbms if target.alive and self.weapon_visible(target))
        targets.extend((target,(target.x,target.y)) for target in self.visible_ground_units() if target.alive and getattr(target,'enemy',False))
        for target,point in reversed(targets):
            x,y=self.pixel(*point)
            if math.hypot(event.x-x,event.y-y)<=12 and radar.start_tracking(target):
                self.ewr_track_picker=None;self.canvas.configure(cursor='')
                self.refresh_inspector();self.request_draw();return True
        return False

    def toggle_ewr_rotation(self):
        radar=self.selected
        if not isinstance(radar,Radar) or not radar.early_warning or not radar.alive:return False
        radar.stop_tracking()
        radar.auto_rotate=not radar.auto_rotate
        radar.desired_bearing=radar.bearing
        self.ewr_bearing_var.set(math.degrees(radar.bearing)%360)
        self.refresh_inspector();self.request_draw();return True

    def refresh_ground_instruments(self,unit,mode):
        aircraft=[a for a in self.aircraft.values() if a.alive]
        if isinstance(unit,PAC3) or (unit.alive and getattr(unit,'enabled',True)):
            aircraft.extend(a for a in self.combat.enemies if a.alive and (self.see_all or self.combat.contact(a) is not None))
        if isinstance(unit,PAC3):
            aircraft.extend(u for u in self.visible_ground_units() if u.alive and u is not unit)
            aircraft.extend(h for h in self.logistics.helicopters if h.alive)
            if self.airfield.alive:aircraft.append(self.airfield)
        weapons=[m for m in [*self.combat.missiles,*self.combat.icbms] if m.alive and self.weapon_visible(m)]
        self.ground_instruments.update_unit(unit,mode,aircraft,self.elapsed,weapons)
        self.ground_instruments.pack(fill='x',before=self.inspector_label)

    def next_build_id(self,kind,units):
        if not hasattr(self,'build_ids'):self.build_ids={}
        number=max(self.build_ids.get(kind,0),max((unit.id for unit in units),default=0))+1
        self.build_ids[kind]=number
        return number

    def destroy_selected_unit(self):
        unit=self.selected
        if not isinstance(unit,(Radar,SAMLauncher,CIWS,PlayerMissileSilo)) or unit.enemy or not unit.alive:return False
        collection=self.player_silos if isinstance(unit,PlayerMissileSilo) else self.radars if isinstance(unit,Radar) else self.sams if isinstance(unit,SAMLauncher) else self.ciws
        if not any(item is unit for item in collection):return False
        if not hasattr(self,'build_ids'):self.build_ids={}
        kind='player_silo' if isinstance(unit,PlayerMissileSilo) else 'radar' if isinstance(unit,Radar) else 'sam' if isinstance(unit,SAMLauncher) else 'ciws'
        self.build_ids[kind]=max(self.build_ids.get(kind,0),unit.id,max((item.id for item in collection),default=0))
        collection[:]=[item for item in collection if item is not unit]
        unit.health=0;self.logistics.requests[:]=[item for item in self.logistics.requests if item is not unit]
        self.add_log(f'Destroyed {unit.name} #{unit.id}','status')
        self.coverage_key=None;self.sam_coverage_key=None;self.visual_coverage_key=None
        self.selected=None;self.show_left_menu('Unit List',cancel=False)
        self.refresh_resources();self.request_draw()
        return True

    def toggle_sam(self,long_range=False,pac3=False):
        if not self.unlocked('PAC-3' if pac3 else 'LR SAM' if long_range else 'SAM'):return False
        self.show_left_menu('Build',cancel=False)
        self.cancel_movement()
        if self.placing_sam and self.placing_lr==long_range and self.placing_pac3==pac3:self.cancel_placement();return
        self.cancel_placement()
        self.sam_overlay=True;self.sam_coverage_button.configure(style='GameSAMCoverage.TButton')
        self.placing_sam=True;self.placing_pac3=pac3
        self.placing_lr=long_range
        self.selected=None
        (self.pac3_button if pac3 else self.lr_sam_button if long_range else self.sam_button).configure(style='Selected.TButton')
        self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair')
        self.refresh_inspector();self.request_draw()

    def toggle_radar(self,long_range=False,early_warning=False):
        if not self.unlocked('EWR' if early_warning else 'LR Radar' if long_range else 'Radar'):return False
        self.show_left_menu('Build',cancel=False)
        self.cancel_movement()
        if self.placing_radar and self.placing_lr==long_range and self.placing_ewr==early_warning:self.cancel_placement();return
        self.cancel_placement()
        self.radar_overlay=True;self.coverage_button.configure(style='GamePlay.TButton')
        self.placing_radar=True;self.placing_lr=long_range;self.placing_ewr=early_warning;self.selected=None
        (self.ewr_button if early_warning else self.lr_radar_button if long_range else self.radar_button).configure(style='Selected.TButton')
        self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair')
        self.refresh_inspector();self.request_draw()

    def cancel_placement(self):
        self.debug_kill_mode=False
        if hasattr(self,'debug_kill_button'):self.debug_kill_button.configure(text='Kill Tool',style='TButton')
        self.ewr_track_picker=None
        self.placing_player_silo=False;self.silo_target_picker=None
        self.placing_factory=False;self.placing_enemy=False
        for name in ('enemy_interceptor_button','enemy_lr_radar_button','enemy_lr_sam_button'):
            if hasattr(self,name):getattr(self,name).configure(style='TButton')
        if hasattr(self,'enemy_button'):self.enemy_button.configure(style='TButton')
        if hasattr(self,'drone_button'):self.drone_button.configure(style='TButton')
        if hasattr(self,'enemy_bomber_button'):self.enemy_bomber_button.configure(style='TButton')
        if hasattr(self,'enemy_radar_button'):self.enemy_radar_button.configure(style='TButton')
        if hasattr(self,'enemy_ciws_button'):self.enemy_ciws_button.configure(style='TButton')
        if hasattr(self,'enemy_flak_button'):self.enemy_flak_button.configure(style='TButton')
        if hasattr(self,'enemy_saaw_button'):self.enemy_saaw_button.configure(style='TButton')
        if hasattr(self,'enemy_sam_button'):self.enemy_sam_button.configure(style='TButton')
        if hasattr(self,'enemy_drone_launcher_button'):self.enemy_drone_launcher_button.configure(style='TButton')
        if hasattr(self,'enemy_silo_button'):self.enemy_silo_button.configure(style='TButton')
        if hasattr(self,'enemy_icbm_button'):self.enemy_icbm_button.configure(style='TButton')
        if hasattr(self,'factory_button'):self.factory_button.configure(style='TButton')
        if hasattr(self,'bunker_button'):self.bunker_button.configure(style='TButton')
        self.placing_ciws=False
        self.point_defence_button.configure(style='GamePointDefence.TButton' if self.point_defence_overlay else 'TButton')
        self.ciws_button.configure(style='TButton');self.flak_button.configure(style='TButton')
        self.placing_sam=False;self.placing_radar=False;self.placing_lr=False;self.placing_ewr=False;self.placing_pac3=False;self.pointer=None
        self.sam_button.configure(style='TButton')
        self.radar_button.configure(style='TButton')
        self.lr_radar_button.configure(style='TButton')
        self.ewr_button.configure(style='TButton')
        self.lr_sam_button.configure(style='TButton')
        self.pac3_button.configure(style='TButton')
        self.player_silo_button.configure(style='TButton')
        self.cancel_button.pack_forget()
        self.canvas.configure(cursor='')
        self.refresh_inspector();self.request_draw()

    def toggle_target(self,kind):
        if not isinstance(self.selected,SAMLauncher):return
        targets=self.selected.preferred_targets
        if kind in targets:targets.remove(kind)
        else:targets.add(kind)
        self.refresh_inspector()

    def toggle_coverage(self):
        self.radar_overlay=not self.radar_overlay
        self.coverage_button.configure(style='GamePlay.TButton' if self.radar_overlay else 'TButton')
        self.request_draw()

    def toggle_sam_coverage(self):
        self.sam_overlay=not self.sam_overlay
        self.sam_coverage_button.configure(style='GameSAMCoverage.TButton' if self.sam_overlay else 'TButton')
        self.request_draw()

    def toggle_point_defence(self):
        self.point_defence_overlay=not self.point_defence_overlay
        self.point_defence_button.configure(style='GamePointDefence.TButton' if self.point_defence_overlay or self.placing_ciws else 'TButton')
        self.request_draw()

    def toggle_visual_coverage(self):
        self.visual_overlay=not self.visual_overlay
        self.visual_coverage_button.configure(style='GamePlay.TButton' if self.visual_overlay else 'TButton')
        self.request_draw()

    def update_contact_pings(self,now=None):
        now=time.monotonic() if now is None else now
        previous=self.ping_sweep_time;self.ping_sweep_time=now
        if previous is None:return
        swept=min(3.,max(0.,now-previous))*math.tau/3
        start=(previous*math.tau/3)%math.tau
        for contact in self.combat.contacts[False].values():
            a=contact.target
            if not isinstance(a,Aircraft) or not a.alive or not a.sensors_active:continue
            if self.elapsed-contact.seen>.2:continue
            bearing=math.atan2(contact.x-self.airfield.x,contact.y-self.airfield.y)%math.tau
            offset=(bearing-start)%math.tau or math.tau
            if offset<=swept:self.play_game_sound('radar_ping')

    def on_datalink(self,x,y,target=None):
        if target is not None and not (isinstance(target,Aircraft) and target.sensors_active):return False
        return (any(r.radar_detects(x,y) for r in [*self.radars,*self.ciws])
                or any(a.kind!='AWACS' and a.radar_detects(x,y) for a in self.aircraft.values()))

    def visible_track(self,x,y):
        return self.airfield.visual_detects(x,y) or any(c.visual_detects(x,y) for c in self.ciws) or self.on_datalink(x,y) or any(a.visual_detects(x,y) or (a.kind=='AWACS' and a.radar_detects(x,y)) for a in self.aircraft.values())

    def refresh_map_aircraft_buttons(self):
        now=time.monotonic()
        font=tkfont.nametofont('TkDefaultFont')
        width=round((font.measure('000')+10)*1.3)
        height=round((font.metrics('linespace')+10)*1.3)
        for slot in range(max(HANGAR_LEVELS)):
            a=self.aircraft.get(slot);alive=a is not None and a.alive
            previous=self.aircraft_button_health.get(slot)
            if a is not None:
                if previous is not None and previous[0] is a and a.health<previous[1]:self.aircraft_damage_times[slot]=(a,now)
                self.aircraft_button_health[slot]=(a,a.health)
            if slot not in self.map_aircraft_buttons:
                button=tk.Canvas(self.map_aircraft_bar,width=width,height=height+22,background=BG,highlightthickness=0,cursor='hand2')
                self.bind_aircraft_reordering(button,slot,'map')
                button.bind('<Double-Button-1>',lambda event,n=slot:self.double_click_aircraft_button(n))
                button.pack(side='left',padx=2);self.map_aircraft_buttons[slot]=button
            button=self.map_aircraft_buttons[slot];button.delete('all')
            color=a.color if alive else PANEL
            selected=alive and self.selected is a
            button.create_rectangle(4,4,width-4,height-4,fill=color,outline='#ffffff' if selected else '#405168',width=2)
            damage=self.aircraft_damage_times.get(slot)
            if alive and damage is not None and damage[0] is a:
                fraction=max(0.,1-(now-damage[1])/30)
                if fraction:
                    base='#ffffff' if selected else '#405168';red='#ef6262'
                    fade='#'+''.join(f'{round(int(base[i:i+2],16)*(1-fraction)+int(red[i:i+2],16)*fraction):02x}' for i in (1,3,5))
                    button.create_rectangle(4,4,width-4,height-4,outline=fade,width=3)
            low_fuel=alive and a.state=='airborne' and a.fuel<=rtb_alert_fuel(a)
            if low_fuel and int(now)%2==0:
                button.create_rectangle(1,1,width-1,height-1,outline='#ffe66d',width=2)
            # Offset copies give the white number a solid black outline.
            for dx,dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                button.create_text(width/2+dx,height/2+dy,text=str(slot+1),font=font,fill='#000000')
            button.create_text(width/2,height/2,text=str(slot+1),font=font,fill='#ffffff' if alive else MUTED)
            if alive:
                attacking=a.mode!='rtb' and any(t is not None and getattr(t,'alive',True) for t in (a.engage_target,a.attack_target,a.auto_attack_target))
                cx=width/2;cy=height+10
                if attacking:
                    button.create_oval(cx-5,cy-5,cx+5,cy+5,outline='#ef6262',width=2)
                    button.create_line(cx-9,cy,cx+9,cy,fill='#ef6262',width=2)
                    button.create_line(cx,cy-9,cx,cy+9,fill='#ef6262',width=2)
                if a.mode=='rtb':
                    button.create_polygon(cx-8,cy-1,cx,cy-8,cx+8,cy-1,fill='#72d693',outline='#72d693')
                    button.create_rectangle(cx-5,cy-1,cx+5,cy+7,fill='#72d693',outline='#72d693')
                    button.create_rectangle(cx-1,cy+2,cx+2,cy+7,fill=BG,outline=BG)
        self.aircraft_button_states=tuple((slot,a.alive) for slot,a in self.aircraft.items())
        self.map_aircraft_bar.place(x=8,y=8)

    def aircraft_status_tick(self):
        self.aircraft_status_job=None
        if not self.active:return
        self.refresh_map_aircraft_buttons()
        self.expire_aircraft_wrecks()
        self.expire_ground_markers()
        self.animate_missile_icons()
        self.update_contacts_hud()
        self.aircraft_status_job=self.after(100,self.aircraft_status_tick)

    def release_shortcut(self,event):
        key=event.keysym
        if key in ('equal','plus','Shift_L','Shift_R') or getattr(event,'char','')=='+' or (getattr(event,'keycode',None) is not None and event.keycode==getattr(self,'debug_shortcut_keycode',None)):
            self.debug_shortcut_down=False;self.debug_shortcut_keycode=None
        if key not in self.held_shortcuts:return
        def released():
            self.held_shortcuts.discard(key)
            self.shortcut_release_jobs.pop(key,None)
        self.shortcut_release_jobs[key]=self.after(10,released)

    def aircraft_shortcut(self,event):
        if not self.run_started or self.run_result is not None:return
        if not self.active:return
        # Aqua can report the resulting '+' without a reliable Shift mask.
        if event.keysym=='plus' or getattr(event,'char','')=='+' or (event.state&1 and event.keysym=='equal'):
            if not self.debug_shortcut_down:
                self.debug_shortcut_down=True;self.debug_shortcut_keycode=getattr(event,'keycode',None)
                self.enable_debug_menu()
            return 'break'
        if event.widget.winfo_class() in ('Entry','TEntry','Text','TCombobox','Spinbox','TSpinbox'):return
        key=event.keysym
        if key in tuple('1234567890'):
            pending=self.shortcut_release_jobs.pop(key,None)
            if pending is not None:self.after_cancel(pending)
            if key in self.held_shortcuts:return 'break'
            self.held_shortcuts.add(key)
            slot=9 if key=='0' else int(key)-1
            if slot in self.aircraft and self.aircraft[slot].alive:
                now=time.monotonic()
                follow=self.last_shortcut[0]==key and now-self.last_shortcut[1]<=.4
                self.last_shortcut=(None,0.) if follow else (key,now)
                self.follow_enabled=False
                self.select_map_aircraft(slot,follow=follow)
                return 'break'

    def select_map_aircraft(self,slot,follow=False):
        aircraft=self.aircraft_for_slot(slot)
        if aircraft is None:return
        if self.movement_mode=='attack' and not follow:
            self.finish_attack(aircraft);return
        if self.movement_mode=='form_up' and not follow:
            self.finish_form_up(aircraft);return
        self.cancel_commands()
        self.inspect_unit(aircraft)
        if follow:self.follow_enabled=True;self.update_follow()
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()

    def aircraft_number(self,plane):
        return self.combat.aircraft_label(plane) if plane.enemy else next((str(slot+1) for slot,a in self.map_aircraft() if slot>=0 and a is plane),0)

    def refresh_follow_button(self):
        if not hasattr(self,'follow_button'):return
        self.follow_button.configure(style='GamePlay.TButton' if self.follow_enabled else 'TButton',
                                     state='normal' if isinstance(self.selected,Aircraft) else 'disabled')

    def toggle_follow(self):
        if not isinstance(self.selected,Aircraft):return
        self.follow_enabled=not self.follow_enabled
        self.refresh_follow_button();self.update_follow()

    def update_follow(self):
        if self.follow_enabled and isinstance(self.selected,Aircraft):
            a=self.selected
            display=self.track_display(a)
            if display is None:
                self.follow_enabled=False;self.refresh_follow_button();return
            ax,ay=display[:2]
            if math.dist(self.center,(ax,ay))>1e-9:
                dx=(self.center[0]-ax)*self.scale();dy=(ay-self.center[1])*self.scale()
                self.center=[ax,ay]
                self.canvas.move('map_world',dx,dy)
                self.radar_sweeps={key:(item,x+dx,y+dy) for key,(item,x,y) in self.radar_sweeps.items()}
                self.sam_glyphs={key:(item,x+dx,y+dy) for key,(item,x,y) in self.sam_glyphs.items()}
                self.ciws_glyphs={key:(item,x+dx,y+dy) for key,(item,x,y) in self.ciws_glyphs.items()}
                # Refresh grid labels and newly exposed map edges at 4 Hz.
                if time.monotonic()-self.last_background_draw>=.25:self.request_draw()

    def double_click_aircraft_button(self,slot):
        self.aircraft_drag=None
        self.select_map_aircraft(slot,follow=True)
        return 'break'

    def aircraft_at(self,x,y):
        candidates=[]
        for slot,a in self.map_aircraft():
            if not a.alive:continue
            display=self.track_display(a)
            if display is None:continue
            px,py=self.pixel(*display[:2]);distance=math.hypot(x-px,y-py)
            if distance<=12:candidates.append((distance,slot))
        return min(candidates)[1] if candidates else None

    def double_click_aircraft(self,event):
        slot=self.aircraft_at(event.x,event.y)
        if slot is not None:
            self.select_map_aircraft(slot,follow=True)
            self.ignore_map_release=True;self.drag=None
        return 'break'

    def refresh_form_up_button(self):
        a=self.selected
        following=isinstance(a,Aircraft) and a.mode=='formation' and a.leader is not None
        self.form_up_button.configure(text=f'Leader: {self.aircraft_number(a.leader)} · {a.leader.kind}' if following else 'Form Up')

    def command_form_up(self):
        a=self.selected
        if not isinstance(a,Aircraft) or a.enemy or not a.alive:return
        if a.mode=='formation' and a.leader is not None:
            self.cancel_movement()
            a.fuel_rendezvous=False;a.fuel_resume=None
            a.loiter((a.x,a.y))
            self.refresh_inspector();self.request_draw()
        else:self.start_movement('form_up')

    def finish_form_up(self,leader):
        if not isinstance(self.selected,Aircraft):return
        if not self.selected.form_up(leader):
            self.movement_text.set('Select another aircraft. Formation loops are not allowed.');return
        self.cancel_movement();self.refresh_inspector();self.request_draw()

    def command_rtb(self):
        if not isinstance(self.selected,Aircraft):return
        if self.selected.state=='servicing':return
        self.cancel_movement()
        if self.selected.state=='queued':self.selected.cancel_departure()
        elif self.selected.mode=='rtb' and self.selected.state in ('airborne','rtb','approach'):self.selected.cancel_rtb()
        elif self.selected.state=='parked':
            self.selected.mode='loiter';self.selected.orbit_center=(0.,0.)
            self.selected.depart()
        else:self.selected.rtb()
        self.refresh_inspector();self.request_draw()

    def set_fence(self,engage):
        if not isinstance(self.selected,Aircraft) or engage and self.selected.mode=='rtb':return
        self.selected.fenced_in=bool(engage)
        self.refresh_inspector()

    def set_aircraft_speed(self,setting):
        if not isinstance(self.selected,Aircraft):return
        if self.selected.set_speed(setting):self.refresh_inspector();self.request_draw()

    def start_movement(self,mode):
        if not isinstance(self.selected,Aircraft):return
        if self.movement_mode==mode:self.cancel_movement();return
        self.cancel_placement();self.cancel_movement()
        self.movement_mode=mode;self.pending_path=[]
        self.canvas.configure(cursor='crosshair')
        self.movement_text.set({'direct':'Click a destination to fly directly there, then orbit at full-speed radius.',
                                'loiter':'Click for a 10 NM-radius orbit. Drag to set radius: right clockwise, left counterclockwise.',
                                'patrol':'Click waypoints, then click the first point to close the loop (3–20 points).',
                                'form_up':'Click another aircraft or its numbered button to form up.',
                                'attack':'Click an enemy aircraft or building to attack.'}[mode])
        {'direct':self.direct_button,'loiter':self.loiter_button,'patrol':self.patrol_button,'form_up':self.form_up_button,'attack':self.attack_button}[mode].configure(style='GameSpeed.Selected.TButton')
        self.movement_cancel.pack(fill='x')
        self.request_draw()

    def cancel_movement(self):
        self.movement_mode=None;self.pending_path=[]
        self.movement_text.set('')
        self.direct_button.configure(style='TButton');self.loiter_button.configure(style='TButton');self.patrol_button.configure(style='TButton');self.form_up_button.configure(style='TButton');self.attack_button.configure(style='TButton')
        self.movement_cancel.pack_forget()
        if not self.placing_sam and not self.placing_radar:self.canvas.configure(cursor='')
        self.request_draw()

    def cancel_commands(self):
        self.cancel_movement();self.cancel_placement()

    def ground_target_hit(self,target,x,y,radius):
        tx,ty=self.pixel(target.x,target.y)
        if isinstance(target,EnemyRunway):
            return abs(x-tx)<=max(7,target.runway_width*self.scale()/2) and abs(y-ty)<=max(17.5,target.runway_length*self.scale()/2)
        return math.hypot(x-tx,y-ty)<=radius

    def finish_loiter(self,event):
        if not self.drag or not isinstance(self.selected,Aircraft):return
        x,y,_=self.drag;center=self.world(x,y)
        dragged=math.hypot(event.x-x,event.y-y)>3
        radius=max(.5,math.dist(center,self.world(event.x,event.y))) if dragged else 10.
        self.selected.loiter(center,radius,event.x>=x)
        self.cancel_movement();self.refresh_inspector();self.request_draw()

    def add_patrol_point(self,event):
        point=self.world(event.x,event.y)
        if self.pending_path:
            px,py=self.pixel(*self.pending_path[0])
            if math.hypot(event.x-px,event.y-py)<=12:
                if len(self.pending_path)>=3 and self.selected.patrol(self.pending_path):
                    self.cancel_movement();self.refresh_inspector();self.request_draw()
                else:self.movement_text.set('Add at least three distinct waypoints before closing the loop.')
                return
        if len(self.pending_path)>=20:
            self.movement_text.set('20 waypoints set. Click the first point to close the loop.');return
        if self.pending_path and math.dist(self.pending_path[-1],point)<.05:return
        self.pending_path.append(point);self.request_draw()

    def tower_position(self):
        return self.airfield.x+.5,self.airfield.y+.25

    def tower_pixel(self):
        return self.pixel(*self.tower_position())

    def building_factor(self):
        return self.scale()/80

    def placement_error(self,building):
        if not self.unlocked('Missile Silo' if isinstance(building,PlayerMissileSilo) else 'PAC-3' if isinstance(building,PAC3) else 'Flak' if isinstance(building,Flak) else 'CIWS' if isinstance(building,CIWS) else 'EWR' if isinstance(building,Radar) and building.early_warning else 'LR Radar' if isinstance(building,Radar) and building.long_range else 'Radar' if isinstance(building,Radar) else 'LR SAM' if building.long_range else 'SAM'):return 'Upgrade Airfield to unlock this unit.'
        cost=building.price
        power=building.power
        if self.power_used+power>self.power_capacity:return 'Upgrade Generator to build more structures.'
        if self.money<cost:return 'Not enough money.'
        if any(math.hypot(x-self.airfield.x,y-self.airfield.y)>BUILD_RADIUS_NM+1e-9 for x,y in building.corners()):
            return f'Place buildings inside the {BUILD_RADIUS_NM:g} NM building area.'
        if abs(building.x-self.airfield.x)<(building.width+self.airfield.runway_width)/2+.02 and abs(building.y-self.airfield.y)<(building.length+self.airfield.runway_length)/2+.02:
            return 'Keep the runway clear.'
        if any(abs(building.x-px)<building.width/2+.12 and abs(building.y-py)<building.length/2+.12
               for px,py in (parking_position(slot) for slot in range(max(HANGAR_LEVELS)))):
            return 'Keep aircraft parking spots clear.'
        tx,ty=self.tower_position()
        if abs(building.x-tx)<building.width/2+.3 and abs(building.y-ty)<building.length/2+.6:
            return 'Keep the ATC tower clear.'
        hx,hy=helipad_position(self.airfield)
        if abs(building.x-hx)<building.width/2+.2 and abs(building.y-hy)<building.length/2+.2:
            return 'Keep the helipad clear.'
        if any(abs(building.x-h.x)<(building.width+h.width)/2+.02 and abs(building.y-h.y)<(building.length+h.length)/2+.02 for h in self.sams+self.radars+self.ciws+self.player_silos):
            return 'Choose a little more space between buildings.'
        return None

    def place_sam(self,x,y,long_range=None,pac3=False):
        if not all(math.isfinite(v) for v in (x,y)):return None
        sam=(PAC3 if pac3 or self.placing_pac3 else SAMLauncher)(self.next_build_id('sam',self.sams),x,y,long_range=(self.placing_sam and self.placing_lr) if long_range is None else long_range)
        error=self.placement_error(sam)
        if error:self.inspector_text.set(error);return None
        self.spend_money(sam.price,f'Build {sam.name} #{sam.id}')
        self.play_game_sound('place_unit')
        self.sams.append(sam)
        self.progress_action('build',sam.stats_key)
        self.cancel_placement();self.selected=sam
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        return sam

    def place_radar(self,x,y,long_range=None,early_warning=False):
        if not all(math.isfinite(v) for v in (x,y)):return None
        radar=Radar(self.next_build_id('radar',self.radars),x,y,long_range=(self.placing_radar and self.placing_lr) if long_range is None else long_range,early_warning=early_warning or (self.placing_radar and self.placing_ewr))
        error=self.placement_error(radar)
        if error:self.inspector_text.set(error);return None
        self.spend_money(radar.price,f'Build {radar.name} #{radar.id}')
        self.play_game_sound('place_unit')
        self.radars.append(radar)
        self.progress_action('build',radar.stats_key)
        self.cancel_placement();self.selected=radar
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        return radar

    def hover(self,event):
        if self.placing_player_silo or self.silo_target_picker is not None or self.placing_sam or self.placing_radar or self.placing_ciws or self.movement_mode:
            self.pointer=self.world(event.x,event.y)
            if self.placing_radar:
                if self.radar_preview_job is None:self.radar_preview_job=self.after(33,self.refresh_radar_placement_preview)
            else:self.request_draw()

    def leave(self,event):
        if self.pointer is not None:
            self.pointer=None
            if self.placing_radar:self.refresh_radar_placement_preview()
            else:self.request_draw()

    def view_width_nm(self):
        return self.view_width

    def select_airfield(self):
        self.cancel_commands()
        self.show_left_menu('Airfield',cancel=False)
        self.follow_enabled=False
        self.selected=self.airfield
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()

    def jump_airfield(self,event=None):
        self.select_airfield();self.home()
        return 'break' 

    def set_active(self, active):
        if not active and getattr(self,'fullscreen',None) is not None:self.fullscreen.exit()
        if self.active and self.playing:self.tick_elapsed()
        self.active=active
        if not active:self.game_audio.stop()
        self.last_tick=time.monotonic()
        self.ping_sweep_time=None
        if not active and self.job is not None:
            self.after_cancel(self.job);self.job=None
        if not active and self.aircraft_status_job is not None:
            self.after_cancel(self.aircraft_status_job);self.aircraft_status_job=None
        if active:
            if self.aircraft_status_job is None:self.aircraft_status_tick()
            self.request_draw()
            self.schedule_tick()

    def schedule_tick(self):
        if self.active and self.playing and self.job is None:self.job=self.after(50,self.tick)

    def tick(self):
        self.job=None
        if not self.active or not self.playing:return
        self.tick_elapsed()
        self.update_contact_pings()
        self.rotate_radars()
        self.rotate_sams()
        self.rotate_ciws()
        if self.left_menu=='Inspector' and isinstance(self.selected,(Radar,CIWS,PAC3)):self.ground_instruments.animate(self.elapsed)
        self.update_follow()
        if self.left_menu=='Unit List':self.refresh_unit_list()
        if self.draw_job is None:self.render_aircraft()
        if isinstance(self.selected,(Airfield,Aircraft,Factory,Radar,SAMLauncher,CIWS,Missile,Bomb,LogisticsHelicopter,RWRSignal)) and time.monotonic()-self.last_inspector_update>=.25:
            self.last_inspector_update=time.monotonic();self.refresh_inspector()
        self.schedule_tick()

    def toggle_play(self):
        if not self.run_started or self.run_result is not None:return
        if self.playing and self.active:self.tick_elapsed()
        self.playing=not self.playing
        if not self.playing:self.game_audio.stop()
        self.ping_sweep_time=None
        self.last_tick=time.monotonic()
        if not self.playing and self.job is not None:
            self.after_cancel(self.job);self.job=None
        self.play_button.configure(image=self.play_icon if self.playing else self.pause_icon,
                                   style='GamePlay.TButton' if self.playing else 'GamePause.TButton')
        self.schedule_tick()

    def tick_elapsed(self):
        now=time.monotonic()
        seconds=min(.5,max(0,now-self.last_tick))*self.play_speed
        self.combat.radars=self.radars;self.combat.sams=self.sams;self.combat.ciws=self.ciws
        self.combat.ground_targets=[self.airfield,*self.radars,*self.sams,*self.ciws,*self.player_silos]
        for radar in self.radars:radar.advance_bearing(seconds)
        for sam in self.sams:
            if isinstance(sam,PAC3):sam.advance_bearing(seconds)
        for a in self.aircraft.values():
            target=a.attack_target
            if target is not None and id(target) not in self.combat.known_ground and id(target) in self.rwr.estimates:
                _,x,y,_=self.rwr.estimates[id(target)];a.attack_point=(x,y)
        self.operations.advance(self.aircraft.values(),seconds)
        if self.aircraft_menu_open and self.aircraft_menu_state()!=getattr(self,'aircraft_menu_signature',None):self.refresh_aircraft_menu()
        health_key=tuple(unit.alive for unit in [*self.combat.ground_targets,*self.combat.enemy_radars,*self.combat.enemy_sams])+(len(self.combat.known_ground),)
        if health_key!=getattr(self,'ground_health_key',None):
            self.ground_health_key=health_key;self.request_draw()
        self.logistics.advance([*self.sams,*self.ciws],self.airfield,seconds)
        self.elapsed=self.operations.time
        self.refresh_campaign()
        self.process_game_events()
        self.refresh_auto_prompts()
        if self.rwr.update(self.aircraft.values(),[*self.combat.enemy_radars,*[s for s in self.combat.enemy_sams if getattr(s,'radar_emitting',False)]],self.elapsed):self.request_draw()
        contacts=sum(isinstance(contact.target,Aircraft) and contact.target.alive for contact in self.combat.contacts[False].values())
        self.contacts_text.set(f"Contacts: {contacts}")
        self.update_contacts_hud()
        if self.airfield.alive:self.money+=self.income_per_minute*seconds/60
        self.refresh_resources()
        if self.left_menu=='Airfield' and now-self.last_inspector_update>=.25:
            self.last_inspector_update=now;self.refresh_inspector()
        self.last_tick=now

    def set_speed(self, speed):
        if self.active and self.playing:self.tick_elapsed()
        self.play_speed=speed
        self.last_tick=time.monotonic()
        for value,button in self.speed_buttons.items():
            button.configure(style='GameSpeed.Selected.TButton' if value==speed else 'TButton')

    def destroyed(self, event):
        if event.widget is not self:return
        if getattr(self,'fullscreen',None) is not None:self.fullscreen.exit()
        self.game_audio.close()
        if self.key_binding:self.winfo_toplevel().unbind('<KeyPress>',self.key_binding)
        if self.key_release_binding:self.winfo_toplevel().unbind('<KeyRelease>',self.key_release_binding)
        for job in self.shortcut_release_jobs.values():self.after_cancel(job)
        for name in ('job','draw_job','aircraft_status_job','progress_notice_job','grid_opacity_job','radar_preview_job'):
            job=getattr(self,name)
            if job is not None:self.after_cancel(job);setattr(self,name,None)

    def request_draw(self):
        if self.draw_job is None:self.draw_job=self.after_idle(self.draw)

    def scale(self):
        return max(1,self.canvas.winfo_width())/self.view_width

    def pixel(self,x,y):
        s=self.scale()
        return (self.canvas.winfo_width()/2+(x-self.center[0])*s,
                self.canvas.winfo_height()/2-(y-self.center[1])*s)

    def world(self,x,y):
        s=self.scale()
        return (self.center[0]+(x-self.canvas.winfo_width()/2)/s,
                self.center[1]-(y-self.canvas.winfo_height()/2)/s)

    def resized(self,event):
        self.request_draw()

    def set_view_width(self,width,anchor=None):
        if anchor:before=self.world(*anchor)
        self.view_width=min(ZOOM_WIDTHS_NM,key=lambda v:abs(v-width))
        self.zoom_text.set(f'{self.view_width:g} NM')
        if anchor:
            after=self.world(*anchor)
            self.center=[self.center[i]+before[i]-after[i] for i in (0,1)]
        self.request_draw()

    def home(self):
        self.follow_enabled=False;self.refresh_follow_button()
        self.center=[self.airfield.x,self.airfield.y]
        self.request_draw()

    def full_map(self):
        self.follow_enabled=False;self.refresh_follow_button()
        self.center=[self.airfield.x,self.airfield.y]
        self.set_view_width(ZOOM_WIDTHS_NM[-1])

    def zoom(self,factor,anchor=None):
        index=ZOOM_WIDTHS_NM.index(self.view_width)
        index=max(0,min(len(ZOOM_WIDTHS_NM)-1,index+(1 if factor>1 else -1)))
        self.set_view_width(ZOOM_WIDTHS_NM[index],anchor)

    def wheel(self,event):
        if event.delta:self.zoom(.85 if event.delta>0 else 1/.85,(event.x,event.y))
        return 'break'

    def press(self,event):
        self.canvas.focus_set()
        self.drag=(event.x,event.y,self.center.copy())

    def motion(self,event):
        if not self.drag:return
        x,y,center=self.drag
        if self.movement_mode:
            self.pointer=self.world(event.x,event.y);self.request_draw();return
        if math.hypot(event.x-x,event.y-y)>3:
            self.follow_enabled=False;self.refresh_follow_button()
            self.center=[center[0]-(event.x-x)/self.scale(),
                         center[1]+(event.y-y)/self.scale()]
            self.request_draw()

    def release(self,event):
        if self.silo_target_picker is not None:
            if self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:self.finish_silo_target(event)
            self.drag=None;return
        if self.debug_kill_mode:
            if self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:self.debug_kill_at(event)
            self.drag=None;return
        if getattr(self,'ignore_map_release',False):
            self.ignore_map_release=False;self.drag=None;return
        if self.ewr_track_picker is not None:
            if self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:self.choose_ewr_track(event)
            self.drag=None;return
        if self.movement_mode and isinstance(self.selected,Aircraft):
            if self.movement_mode=='attack':
                slot=self.aircraft_at(event.x,event.y)
                if slot is not None:self.finish_attack(self.aircraft_for_slot(slot))
                else:
                    signal=None
                    for target,x,y,quality in self.rwr.estimates.values():
                        if not self.see_all and target.alive and target.radar_emitting and id(target) not in self.combat.known_ground:
                            px,py=self.pixel(x,y)
                            if math.hypot(event.x-px,event.y-py)<=14:
                                signal=(target,(x,y));break
                    if signal is not None:
                        self.finish_attack(*signal);self.drag=None;return
                    for target in [*self.combat.factories,*self.combat.enemy_radars,*self.combat.enemy_sams]:
                        if not self.see_all and not (target.id in self.combat.known if isinstance(target,Factory) else id(target) in self.combat.known_ground):continue
                        x,y=self.pixel(target.x,target.y)
                        if self.ground_target_hit(target,event.x,event.y,max(10,22*self.building_factor())):
                            self.finish_attack(target);break
            elif self.movement_mode=='form_up':
                slot=self.aircraft_at(event.x,event.y)
                if slot is not None:self.finish_form_up(self.aircraft_for_slot(slot))
            elif self.movement_mode=='direct':
                self.selected.direct_to(self.world(event.x,event.y))
                self.cancel_movement();self.refresh_inspector();self.request_draw()
            elif self.movement_mode=='loiter':self.finish_loiter(event)
            elif self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:self.add_patrol_point(event)
            self.drag=None;return
        if self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:
            if self.placing_enemy:
                if self.enemy_spawn_kind=='ICBM':
                    self.selected=self.combat.spawn_icbm(*self.world(event.x,event.y),target=self.airfield)
                elif self.enemy_spawn_kind in ('Drone Launcher','ICBM Silo','Radar','LR Radar','SAM','LR SAM','CIWS','Flak','SAAW'):
                    self.selected=self.spawn_campaign_ground(self.enemy_spawn_kind,*self.world(event.x,event.y))
                else:
                    spawn={'Fighter':self.combat.spawn_fighter,'Interceptor':self.combat.spawn_interceptor,'Bomber':self.combat.spawn_bomber,'Suicide Drone':self.combat.spawn_drone}[self.enemy_spawn_kind]
                    self.selected=spawn(*self.world(event.x,event.y))
                self.refresh_inspector();self.request_draw()
            elif self.placing_factory:
                self.selected=(self.combat.spawn_bunker if self.factory_spawn_kind=='Bunker' else self.combat.spawn_factory)(*self.world(event.x,event.y))
                self.refresh_inspector();self.request_draw()
            elif self.placing_player_silo:
                self.place_player_silo(*self.world(event.x,event.y))
            elif self.placing_ciws:
                self.place_ciws(*self.world(event.x,event.y))
            elif self.placing_radar:
                self.place_radar(*self.world(event.x,event.y))
            elif self.placing_sam:
                self.place_sam(*self.world(event.x,event.y))
            else:
                if self.select_rwr_at(event):self.drag=None;return
                px,py=self.tower_pixel();f=self.building_factor()
                for unit in reversed(self.visible_ground_units()):
                    if self.ground_dot_required(unit) and (abs(event.x-self.ground_pixel(unit)[0])<=7 and abs(event.y-self.ground_pixel(unit)[1])<=20 if isinstance(unit,(Airfield,EnemyRunway)) else math.dist((event.x,event.y),self.ground_pixel(unit))<=(12 if unit.category=='Radars' else 9)):
                        self.selected=unit;self.follow_enabled=False
                        self.show_left_menu('Inspector',cancel=False);self.refresh_inspector();self.request_draw()
                        self.drag=None;return
                self.selected=self.airfield if f>=.08 and abs(event.x-px)<=27*f and py-51*f<=event.y<=py+18*f else None
                if f>=.08:
                    for unit in reversed(self.radars+self.sams+self.ciws+self.player_silos+[r for r in [*self.combat.enemy_radars,*self.combat.enemy_sams] if self.see_all or id(r) in self.combat.known_ground]):
                        ux,uy=self.pixel(unit.x,unit.y)
                        if math.hypot(event.x-ux,event.y-uy)<=max(5,17*f*(.48 if isinstance(unit,SAMLauncher) else .25 if isinstance(unit,CIWS) else .8)):
                            self.selected=unit;break
                # The physical runway is never a selectable hit area.
                wx,wy=self.world(event.x,event.y)
                if abs(wx-self.airfield.x)<=self.airfield.runway_width/2 and abs(wy-self.airfield.y)<=self.airfield.runway_length/2:
                    self.selected=None
                for target in self.combat.factories:
                    if not self.see_all and target.id not in self.combat.known:continue
                    tx,ty=self.pixel(target.x,target.y)
                    if self.ground_target_hit(target,event.x,event.y,max(7,18*self.building_factor()*.4)):self.selected=target;break
                for slot,a in self.map_aircraft():
                    if not a.alive:continue
                    display=self.track_display(a)
                    if display is None:continue
                    ax,ay=self.pixel(*display[:2])
                    if math.hypot(event.x-ax,event.y-ay)<=10:
                        self.selected=a;break
                for weapon in [*self.combat.missiles,*self.combat.bombs,*self.combat.icbms]:
                    if not self.weapon_visible(weapon):continue
                    wx,wy=self.pixel(*weapon.position(self.elapsed))
                    if math.hypot(event.x-wx,event.y-wy)<=9:self.selected=weapon;break
                for h in self.logistics.helicopters:
                    hx,hy=self.pixel(h.x,h.y)
                    if h.state!='parked' and math.hypot(event.x-hx,event.y-hy)<=10:self.selected=h;break
                if self.selected is not None:self.show_left_menu('Inspector',cancel=False)
                if not isinstance(self.selected,Aircraft):self.follow_enabled=False
                self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()
        self.drag=None

    def draw_parking(self):
        if self.view_width>=50:return
        for slot in range(self.aircraft_capacity):
            x,y=self.pixel(*parking_position(slot));w=.1*self.scale();h=.12*self.scale()
            self.canvas.create_rectangle(x-w,y-h,x+w,y+h,outline='#526279',width=1,tags=('parking','airfield_icons'))
            if w>=8:self.canvas.create_text(x,y+h+7,text=str(slot+1),fill=MUTED,font=('Helvetica',8),tags=('parking','airfield_icons'))

    def draw_formation_spots(self):
        if not isinstance(self.selected,Aircraft) or self.selected.enemy:return
        leader=self.selected.leader if self.selected.mode=='formation' and self.selected.leader is not None else self.selected
        if leader.enemy:return
        occupants={a.formation_slot:a for a in leader.followers if not a.enemy}
        count=max(2,max(occupants,default=-1)+3)
        for slot in range(count):
            x,y=self.pixel(*formation_position(leader,slot))
            occupant=occupants.get(slot)
            self.canvas.create_oval(x-3,y-3,x+3,y+3,outline=occupant.color if occupant else MUTED,
                                    width=1,tags='game_aircraft')

    def draw_aircraft_unit(self,a,x,y,heading,filled,size):
        size*=1.3
        co,si=math.cos(heading),math.sin(heading)
        points=[coord for px,py in self.aircraft_vertices
                for coord in (x+(px*co+py*si)*size,y-(-px*si+py*co)*size)]
        self.canvas.create_polygon(*points,fill=a.color if filled else '',outline=a.color,width=1,tags='game_aircraft')

    def render_aircraft(self):
        states=tuple((slot,a.alive) for slot,a in self.aircraft.items())
        if states!=getattr(self,'aircraft_button_states',None):self.refresh_map_aircraft_buttons()
        if isinstance(self.selected,Aircraft) and not self.selected.alive:
            self.follow_enabled=False;self.refresh_follow_button()
        c=self.canvas;c.delete('game_aircraft')
        self.draw_radar_coverage()
        self.draw_sam_coverage()
        self.draw_point_defence()
        self.draw_visual_coverage()
        self.draw_selected_friendly_coverage()
        self.draw_formation_spots()
        fade=min(60,max(0,2*getattr(getattr(self.app,'settings',None),'replay_trail_fade_sec',0)))
        width,height=c.winfo_width(),c.winfo_height()
        scale=width/self.view_width;cx,cy=self.center
        def pixel(x,y):return width/2+(x-cx)*scale,height/2-(y-cy)*scale
        if isinstance(self.selected,Aircraft) and self.selected.alive and not self.selected.enemy and self.selected.kind in ('Fighter','Interceptor','Bomber'):
            display=self.track_display(self.selected)
            if display is not None:
                x,y=pixel(*display[:2]);r=self.selected.engagement_range*scale
                c.create_oval(x-r,y-r,x+r,y+r,outline='#ef6262',dash=(6,4),width=1.3,tags='game_aircraft')
        size=AIRCRAFT_SIZE*c.winfo_fpixels('1i')/72
        bg=tuple(int(BG[i:i+2],16) for i in (1,3,5))
        for slot,a in self.map_aircraft():
            if isinstance(a,ICBM):continue
            display=self.track_display(a)
            if display is None:continue
            ax,ay,heading,filled,history=display
            rgb=tuple(int(a.color[i:i+2],16) for i in (1,3,5))
            if a.color not in self.trail_palette:
                self.trail_palette[a.color]=['#'+''.join(f'{round(b+(v-b)*((band+.5)/16 if band<16 else 1)):02x}'
                    for b,v in zip(bg,rgb)) for band in range(17)]
            run=[];last_band=None
            def flush():
                if len(run)>1:
                    color=self.trail_palette[a.color][last_band]
                    c.create_line(*[coord for point in run for coord in pixel(*point)],fill=color,
                                  width=AIRCRAFT_TRAIL_WIDTH,tags='game_aircraft')
            for t,x,y,speed in history:
                age=self.elapsed-t
                if age>60 or speed<1:continue
                alpha=min(1,max(0,(60-age)/fade)) if fade else 1
                band=min(16,int(alpha*16))
                if last_band is not None and band!=last_band:
                    last=run[-1] if run else None;flush();run=[last] if last else []
                last_band=band;run.append((x,y))
            if history and a.speed>=1:run.append((ax,ay))
            flush()
            if a.refueling_from is not None:
                tx,ty=pixel(a.refueling_from.x,a.refueling_from.y);rx,ry=pixel(a.x,a.y)
                c.create_line(tx,ty,rx,ry,fill='#75e5ba',width=1.3,tags='game_aircraft')
                length=math.hypot(rx-tx,ry-ty)
                if length>2:
                    ux,uy=(rx-tx)/length,(ry-ty)/length
                    for i in range(3):
                        fraction=(self.elapsed/2+i/3)%1
                        px,py=tx+(rx-tx)*fraction,ty+(ry-ty)*fraction
                        c.create_line(px-ux*6,py-uy*6,px,py,fill='#75e5ba',width=1.5,
                                      arrow='last',arrowshape=(4,5,2),tags='game_aircraft')
            x,y=pixel(ax,ay)
            if not a.alive:continue
            if not -15<x<width+15 or not -15<y<height+15:continue
            self.draw_aircraft_unit(a,x,y,heading,filled,size)
            if a.state=='servicing':
                c.create_rectangle(x-16,y+13,x+16,y+18,fill=PANEL,outline=MUTED,tags='game_aircraft')
                if a.service_progress>0:c.create_rectangle(x-15,y+14,x-15+30*a.service_progress,y+17,fill='#72d693' if a.crew_active else '#ffc05a',outline='',tags='game_aircraft')
            if self.selected is a:c.create_oval(x-10,y-10,x+10,y+10,outline='#ffffff',tags='game_aircraft')
            c.create_text(x+9,y-9,text=self.combat.aircraft_label(a,slot+1 if slot>=0 else None),fill=a.color,font=('Helvetica',9,'bold'),anchor='w',tags='game_aircraft')
        self.render_combat()
        self.render_logistics()
        self.render_rwr()
        c.addtag_withtag('map_world','game_aircraft')
        self.refresh_movement_overlay()
        self.apply_map_layers()
        self.contacts_hud.lift()

    def visible_ground_units(self):
        units=[self.airfield,*self.radars,*self.sams,*self.ciws,*self.player_silos]
        units.extend(t for t in self.combat.factories if self.see_all or t.id in self.combat.known)
        units.extend(t for t in [*self.combat.enemy_radars,*self.combat.enemy_sams] if self.see_all or id(t) in self.combat.known_ground)
        return [u for u in units if self.ground_marker_visible(u)]

    def ground_marker_visible(self,unit):
        if unit.alive:return True
        if getattr(unit,'death_wall_time',None) is None:unit.death_wall_time=time.monotonic()
        return self.view_width<50 or time.monotonic()-unit.death_wall_time<60

    def expire_ground_markers(self):
        units=[self.airfield,*self.radars,*self.sams,*self.ciws,*self.player_silos,
               *self.combat.factories,*self.combat.enemy_radars,*self.combat.enemy_sams]
        for unit in units:
            if not self.ground_marker_visible(unit):self.canvas.delete(f'ground_marker_{id(unit)}')

    def ground_dot_required(self,unit):
        x,y=self.pixel(unit.x,unit.y)
        return self.view_width>=50 or not (6<=x<=self.canvas.winfo_width()-6 and 6<=y<=self.canvas.winfo_height()-6)

    def ground_pixel(self,unit):
        x,y=self.pixel(unit.x,unit.y)
        margin=20 if isinstance(unit,(Airfield,EnemyRunway)) else 12 if unit.category=='Radars' else 6
        return max(6,min(self.canvas.winfo_width()-6,x)),max(margin,min(self.canvas.winfo_height()-margin,y))

    def weapon_visible(self,weapon):
        if not weapon.owner.enemy or self.see_all or getattr(weapon,'player_spotted',False):return True
        owner=weapon.owner
        if isinstance(weapon,ICBM) and self.combat.contact(weapon) is not None:weapon.player_spotted=True
        spotted=(self.combat.contact(owner) is not None if isinstance(owner,Aircraft) else owner.id in self.combat.known if isinstance(owner,Factory) else id(owner) in self.combat.known_ground)
        if spotted:
            weapon.player_spotted=True;return True
        point=weapon.position(self.elapsed) if hasattr(weapon,'position') else (weapon.x,weapon.y)
        visual=(self.airfield.visual_detects(*point) or any(a.visual_detects(*point) for a in self.aircraft.values())
                or any(c.radar_detects(*point) for c in self.ciws)
                or any(c.alive and math.dist((c.x,c.y),point)<=c.visual_range_nm for c in self.ciws))
        if spotted or visual:weapon.player_spotted=True
        return getattr(weapon,'player_spotted',False)

    def refresh_auto_prompts(self):
        pending=[(slot,a) for slot,a in self.aircraft.items() if a.alive and a.pending_auto and a.mode!='rtb' and a.state=='airborne']
        signature=tuple((slot,a.pending_auto['action'],a.pending_auto['reason'],id(a.pending_auto['target'])) for slot,a in pending)
        if signature==self.auto_prompt_signature:return
        self.auto_prompt_signature=signature
        for child in self.auto_prompt_panel.winfo_children():child.destroy()
        if not pending:self.auto_prompt_panel.place_forget();return
        for slot,a in pending:
            request=a.pending_auto;target=request['target']
            action=f'Fuel from KC-49 #{self.aircraft_number(target)}' if request['action']=='fuel' and target is not None else 'RTB — Return to airfield'
            reason='Low fuel' if request['reason']=='fuel' else 'Winchester — out of ammo'
            color='#ef6262' if request['reason']=='fuel' else '#ffe66d'
            card=tk.Frame(self.auto_prompt_panel,background=PANEL,highlightthickness=2,highlightbackground=color,padx=5,pady=5);card.pack(fill='x',pady=3)
            ttk.Label(card,text=f'{slot+1} · {a.kind}',font=('Helvetica',10,'bold')).pack(anchor='w')
            ttk.Label(card,text=f'{reason}\n{action}',wraplength=220,justify='left',foreground=TEXT).pack(anchor='w',pady=3)
            row=ttk.Frame(card);row.pack(fill='x')
            ttk.Button(row,text='Refuel' if request['action']=='fuel' else 'RTB',command=lambda n=slot:self.answer_auto_prompt(n,True)).pack(side='left',fill='x',expand=True)
            ttk.Button(row,text='Ignore',command=lambda n=slot:self.answer_auto_prompt(n,False)).pack(side='left',fill='x',expand=True,padx=(4,0))
        self.auto_prompt_panel.place(relx=1,x=-12,y=86,anchor='ne');self.auto_prompt_panel.lift()

    def answer_auto_prompt(self,slot,confirm,redeploy=False):
        a=self.aircraft.get(slot)
        if a is None or not a.alive or not a.pending_auto:return False
        request=a.pending_auto;a.pending_auto=None
        if not confirm:a.ignored_auto.add(request['reason'])
        elif redeploy:a.rtb(redeploy=True)
        elif request['action']=='rtb':a.rtb()
        else:self.operations.seek_fuel(a)
        self.refresh_auto_prompts();self.refresh_inspector();self.request_draw()
        return True

    def add_log(self,message,tag='status',now=None,cost_text=None):
        now=self.elapsed if now is None else now
        seconds=int(now);stamp=f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'
        entry=f'{stamp} · {message}\n'
        self.log_entries.append((entry,tag))
        self.log_text.configure(state='normal')
        if cost_text is None:
            self.log_text.insert('end',entry,tag)
        else:
            self.log_text.insert('end',entry[:-len(cost_text)-1],tag)
            self.log_text.insert('end',cost_text,'cost')
            self.log_text.insert('end','\n',tag)
        self.log_text.configure(state='disabled');self.log_text.see('end')

    def debug_add_money(self):
        self.money+=5000
        self.add_log('Debug · +$5,000','reward')
        self.refresh_resources();self.refresh_inspector()
        if self.aircraft_menu_open:self.refresh_aircraft_menu()
        self.request_draw()

    def spend_money(self,amount,description,tag='purchase'):
        self.money-=amount
        if self.money<500 and getattr(self,'run_started',False) and hasattr(self,'progress'):self.progress.unlock('paycheck')
        cost_text=f'−{dollars(amount)}'
        self.add_log(f'{description} · {cost_text}',tag,cost_text=cost_text)

    def process_game_events(self):
        for now,message,reward,kind in self.combat.events:
            self.money+=reward
            if reward>0 and kind=='kill':self.play_game_sound('kill_reward',volume_multiplier=kill_reward_gain(reward,STATS['audio']['kill_reward_scaling']))
            if kind in ('enemy_reload','enemy_wave') and not self.debug_enabled:continue
            self.add_log(message+(f' · +{dollars(reward)}' if reward else ''),'reward' if reward else kind,now)
        self.combat.events.clear()
        self.poll_progress()

    def visible_rwr_estimates(self):
        for radar,x,y,quality in self.rwr.estimates.values():
            identified=id(radar) in (self.combat.identified_ground if isinstance(radar,SAAW) else self.combat.known_ground)
            if radar.radar_emitting and not self.see_all and not identified:yield radar,x,y,quality

    def refresh_selected_rwr(self):
        selected=self.selected
        if not isinstance(selected,RWRSignal):return
        estimate=next((estimate for estimate in self.visible_rwr_estimates() if estimate[0] is selected.emitter),None)
        if estimate is None:self.selected=None
        else:_,selected.x,selected.y,selected.quality=estimate

    def select_rwr_at(self,event):
        candidates=[]
        for radar,x,y,quality in self.visible_rwr_estimates():
            px,py=self.pixel(x,y)
            distance=math.hypot(event.x-px,event.y-py)
            if distance<=14:candidates.append((distance,radar,x,y,quality))
        if not candidates:return False
        _,radar,x,y,quality=min(candidates,key=lambda candidate:candidate[0])
        self.selected=RWRSignal(radar,x,y,quality);self.follow_enabled=False
        self.show_left_menu('Inspector',cancel=False)
        self.refresh_inspector();self.request_draw()
        return True

    def render_rwr(self):
        c=self.canvas
        for radar,x,y,quality in self.visible_rwr_estimates():
            px,py=self.pixel(x,y)
            if not -15<px<c.winfo_width()+15 or not -15<py<c.winfo_height()+15:continue
            c.create_text(px,py,text='?',fill='#ef6262',font=('Helvetica',14,'bold'),tags='game_aircraft')
            signal='CIWS' if isinstance(radar,CIWS) else 'SAAW' if isinstance(radar,SAAW) else 'EWR' if radar.early_warning else 'LR Radar' if radar.long_range else 'Radar'
            c.create_text(px,py+15,text=signal,anchor='n',fill='#ef6262',font=('Helvetica',9,'bold'),tags='game_aircraft')
            if isinstance(self.selected,RWRSignal) and self.selected.emitter is radar:
                c.create_oval(px-11,py-11,px+11,py+11,outline='#ffffff',tags='game_aircraft')

    def request_resupply(self):
        unit=self.selected
        if not isinstance(unit,(SAMLauncher,CIWS)):return False
        if not self.logistics.request(unit,self.airfield):return False
        self.logistics.advance([*self.sams,*self.ciws],self.airfield,0.)
        self.refresh_resources();self.refresh_inspector();self.request_draw()
        return True

    def draw_support_icons(self,canvas,kind,capacity,busy):
        canvas.delete('all')
        canvas.configure(width=capacity*21+4)
        for slot in range(capacity):
            x=12+slot*21;y=12
            color='#586070' if slot>=capacity-busy else '#dfe9f5' if kind=='crew' else '#56deef'
            if kind=='crew':
                # Hollow head and shoulders, ending at the waist.
                canvas.create_oval(x-3.5,y-10,x+3.5,y-3,fill='',outline=color,width=1.5)
                canvas.create_line(x-2,y-3,x-2,y-1,x-6,y+1,x-8,y+4,x-8,y+10,
                                   x+8,y+10,x+8,y+4,x+6,y+1,x+2,y-1,x+2,y-3,
                                   fill=color,width=1.5,joinstyle='round')
                canvas.create_line(x-5,y+4,x-5,y+10,fill=color,width=1)
                canvas.create_line(x+5,y+4,x+5,y+10,fill=color,width=1)
            else:
                canvas.create_oval(x-5,y-2,x+5,y+5,outline=color,width=1.5)
                canvas.create_line(x,y-2,x,y-6,fill=color,width=1.5)
                canvas.create_line(x-9,y-6,x+9,y-6,fill=color,width=1.5)
                canvas.create_line(x+5,y+1,x+9,y-3,x+9,y+1,fill=color,width=1.5)
                canvas.create_line(x-6,y+8,x+6,y+8,fill=color,width=1.5)
                canvas.create_line(x-3,y+5,x-3,y+8,x+3,y+8,x+3,y+5,fill=color,width=1)

    def power_image(self,count):
        """Raster bolts keep their yellow color under every button theme."""
        image=tk.PhotoImage(master=self,width=count*14,height=22)
        spans=((8,9),(7,9),(7,8),(6,8),(5,8),(5,7),(4,7),(3,7),
               (3,10),(2,10),(1,9),(5,9),(5,8),(4,8),(4,7),(3,7),
               (3,6),(2,6),(2,5),(1,4))
        for n in range(count):
            for y,(left,right) in enumerate(spans,1):
                image.put('#ffe66d',to=(n*14+left,y,n*14+right+1,y+1))
        return image

    def draw_flak(self,unit,ghost=False):
        if not ghost and self.ground_dot_required(unit):return
        x,y=self.pixel(unit.x,unit.y);f=self.building_factor()*.4;c=self.canvas
        color='#ffb347' if not unit.enemy else '#ef6262'
        if not unit.alive:color='#586070'
        if ghost and self.placement_error(unit):color='#ff7777'
        if unit.enemy:
            c.create_rectangle(x-12*f,y-9*f,x+12*f,y+9*f,fill=PANEL,outline=color,width=2,tags='ciws_icon')
            for side in (-1,1):c.create_line(x-14*f,y+side*12*f,x+14*f,y+side*12*f,fill=color,width=3,tags='ciws_icon')
        c.create_oval(x-14*f,y-14*f,x+14*f,y+14*f,fill=PANEL,outline=color,width=2,tags='ciws_icon')
        circles=[]
        for side in (-1,1):
            cx=x+side*math.cos(unit.heading)*5*f;cy=y+side*math.sin(unit.heading)*5*f
            circles.append(c.create_oval(cx-5*f,cy-5*f,cx+5*f,cy+5*f,fill=PANEL,outline=color,width=2,tags='ciws_icon'))
        points=self.ciws_barrel_points(unit,x,y)
        barrels=[c.create_line(*points[i:i+4],fill=color,width=2,tags='ciws_icon') for i in (0,4)]
        if not ghost:self.ciws_glyphs[id(unit)]=(tuple([*circles,*barrels]),x,y)
        if self.selected is unit:c.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',tags='ciws_icon')

    def ciws_barrel_points(self,unit,x,y):
        f=self.building_factor()*(.4 if isinstance(unit,Flak) else .25);ux=math.sin(unit.heading);uy=-math.cos(unit.heading)
        if isinstance(unit,Flak):
            sx,sy=math.cos(unit.heading)*5*f,math.sin(unit.heading)*5*f
            return (x-sx+ux*4*f,y-sy+uy*4*f,x-sx+ux*19*f,y-sy+uy*19*f,x+sx+ux*4*f,y+sy+uy*4*f,x+sx+ux*19*f,y+sy+uy*19*f)
        return (x+ux*5*f,y+uy*5*f,x+ux*18*f,y+uy*18*f)

    def rotate_ciws(self):
        dt=max(0,self.elapsed-getattr(self,'ciws_last_elapsed',self.elapsed))
        self.ciws_last_elapsed=self.elapsed
        for unit in [*self.ciws,*[u for u in self.combat.enemy_sams if isinstance(u,CIWS)]]:
            if not unit.alive:continue
            target=unit.attack_target
            if target is not None and target.alive:
                tx,ty=target.position(self.elapsed) if isinstance(target,(Missile,Bomb)) else (target.x,target.y)
                unit.target_heading=math.atan2(tx-unit.x,ty-unit.y)
            elif self.elapsed>=unit.next_look:
                unit.target_heading=self.random.uniform(-math.pi,math.pi)
                unit.next_look=self.elapsed+self.random.uniform(2,5)
            delta=(unit.target_heading-unit.heading+math.pi)%math.tau-math.pi
            unit.heading+=max(-dt*.9,min(dt*.9,delta))
            if id(unit) in self.ciws_glyphs:
                item,x,y=self.ciws_glyphs[id(unit)]
                if isinstance(unit,Flak):
                    f=self.building_factor()*.4
                    for side,circle in zip((-1,1),item[:2]):
                        cx=x+side*math.cos(unit.heading)*5*f;cy=y+side*math.sin(unit.heading)*5*f
                        self.canvas.coords(circle,cx-5*f,cy-5*f,cx+5*f,cy+5*f)
                    points=self.ciws_barrel_points(unit,x,y)
                    for barrel,offset in zip(item[2:],(0,4)):self.canvas.coords(barrel,*points[offset:offset+4])
                else:self.canvas.coords(item,*self.ciws_barrel_points(unit,x,y))

    def draw_ciws(self,unit,ghost=False):
        if isinstance(unit,Flak):self.draw_flak(unit,ghost);return
        if not ghost and self.ground_dot_required(unit):return
        x,y=self.pixel(unit.x,unit.y);f=self.building_factor()*.25
        color='#586070' if not unit.alive else '#ef6262' if unit.enemy else CIWS_COLOR
        if ghost and self.placement_error(unit):color='#ff7777'
        self.canvas.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,tags='ciws_icon')
        self.canvas.create_oval(x-6*f,y-6*f,x+6*f,y+6*f,fill=PANEL,outline=color,width=2,tags='ciws_icon')
        item=self.canvas.create_line(*self.ciws_barrel_points(unit,x,y),fill=color,width=max(1,3*f),capstyle='round',tags='ciws_icon')
        if not ghost:self.ciws_glyphs[id(unit)]=(item,x,y)
        if self.selected is unit:self.canvas.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',tags='ciws_icon')

    def render_logistics(self):
        c=self.canvas
        f=1.2
        for h in self.logistics.helicopters:
            if h.state=='parked':continue
            x,y=self.pixel(h.x,h.y);ux=math.sin(h.heading);uy=-math.cos(h.heading)
            c.create_line(x-ux*9*f,y-uy*9*f,x+ux*5*f,y+uy*5*f,fill=h.color,width=2*f,tags='game_aircraft')
            c.create_oval(x-3*f,y-3*f,x+3*f,y+3*f,fill=PANEL,outline=h.color,tags='game_aircraft')
            angle=self.elapsed*math.tau*1.7+h.id*.6
            for phase in (0,math.pi/2):
                rx=8*f*math.cos(angle+phase);ry=8*f*math.sin(angle+phase)
                c.create_line(x-rx,y-ry,x+rx,y+ry,fill=h.color,tags='game_aircraft')
            if self.selected is h:c.create_oval(x-11*f,y-11*f,x+11*f,y+11*f,outline='#ffffff',tags='game_aircraft')

    def draw_missile_attack_line(self):
        missile=self.selected
        if not isinstance(missile,(Missile,ICBM)) or not missile.alive or not self.weapon_visible(missile) or getattr(missile,'terminal',False):return False
        target=missile.guidance_target if isinstance(missile,Missile) else missile.target
        if not target.alive:return False
        point=None
        if target is getattr(missile,'decoy',None):
            if not target.owner.enemy or self.see_all or self.combat.contact(target.owner) is not None:point=(target.x,target.y)
        elif not getattr(target,'enemy',False) or self.see_all:point=(target.x,target.y)
        elif isinstance(target,ICBM):
            if self.weapon_visible(target):point=(target.x,target.y)
        elif isinstance(target,Aircraft):
            contact=self.combat.contact(target)
            if contact is not None:point=(contact.x,contact.y)
        elif (target.id in self.combat.known if isinstance(target,Factory) else id(target) in self.combat.known_ground):point=(target.x,target.y)
        elif id(target) in self.rwr.estimates:
            _,x,y,_=self.rwr.estimates[id(target)];point=(x,y)
        if point is None:return False
        color='#69adff' if isinstance(missile,Missile) and missile.kind=='AIM-120' and missile.pitbull else '#ef6262'
        self.canvas.create_line(*self.pixel(missile.x,missile.y),*self.pixel(*point),fill=color,dash=(6,4),width=1.5,arrow='last',tags='game_combat')
        return True

    def aircraft_wreck_visible(self,aircraft):
        if aircraft.alive:return False
        if getattr(aircraft,'death_wall_time',None) is None:aircraft.death_wall_time=time.monotonic()
        return time.monotonic()-aircraft.death_wall_time<STATS['world']['aircraft_wreck_lifetime_seconds']

    def expire_aircraft_wrecks(self):
        for a in [*self.aircraft.values(),*self.combat.enemies]:
            if not a.alive and not self.aircraft_wreck_visible(a):self.canvas.delete(f'aircraft_wreck_{id(a)}')

    def draw_enemy_structure(self,target,show_label=True):
        c=self.canvas;f=self.building_factor()*.4
        x,y=self.pixel(target.x,target.y)
        color='#ef6262' if target.alive else '#586070'
        if isinstance(target,EnemyRunway):
            half_width=max(4,target.runway_width*self.scale()/2);half_length=target.runway_length*self.scale()/2
            c.create_rectangle(x-half_width,y-half_length,x+half_width,y+half_length,fill=PANEL,outline=color,width=2,tags=('game_combat','ground_markers','airfield_icons'))
            c.create_line(x,y-half_length+3,x,y+half_length-3,fill=color,dash=(5,4),tags=('game_combat','ground_markers','airfield_icons'))
            if show_label:c.create_text(x,y+half_length+14,text=target.name,fill=color,tags=('game_combat','ground_markers','airfield_icons'))
            if self.selected is target:c.create_rectangle(x-half_width-4,y-half_length-4,x+half_width+4,y+half_length+4,outline='#ffffff',tags=('game_combat','ground_markers','airfield_icons'))
            return
        if isinstance(target,DroneLauncher):
            c.create_rectangle(x-20*f,y-15*f,x+20*f,y+15*f,fill=PANEL,outline=color,width=2,tags=('game_combat','ground_markers'))
            for offset in (-12,0,12):
                dx=x+offset*f
                c.create_line(dx,y-10*f,dx,y+8*f,fill=color,width=2,tags=('game_combat','ground_markers'))
                c.create_line(dx-4*f,y,dx,y-5*f,dx+4*f,y,fill=color,width=2,tags=('game_combat','ground_markers'))
            if show_label:c.create_text(x,y+28*f,text='Drone Launcher',fill=color,tags=('game_combat','ground_markers'))
            if self.selected is target:c.create_rectangle(x-24*f,y-19*f,x+24*f,y+19*f,outline='#ffffff',tags=('game_combat','ground_markers'))
            return
        if isinstance(target,ICBMSilo):
            c.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,fill=PANEL,outline=color,width=2,tags=('game_combat','ground_markers'))
            c.create_line(x-14*f,y-14*f,x+14*f,y+14*f,fill=color,width=2,tags=('game_combat','ground_markers'))
            c.create_line(x+14*f,y-14*f,x-14*f,y+14*f,fill=color,width=2,tags=('game_combat','ground_markers'))
            if show_label:c.create_text(x,y+28*f,text='ICBM Silo',fill=color,tags=('game_combat','ground_markers'))
            if self.selected is target:c.create_oval(x-24*f,y-24*f,x+24*f,y+24*f,outline='#ffffff',tags=('game_combat','ground_markers'))
            return
        if isinstance(target,Bunker):
            c.create_arc(x-20*f,y-20*f,x+20*f,y+16*f,start=0,extent=180,style='arc',outline=color,width=2,tags=('game_combat','ground_markers'))
            c.create_line(x-20*f,y-2*f,x-20*f,y+12*f,x+20*f,y+12*f,x+20*f,y-2*f,fill=color,width=2,tags=('game_combat','ground_markers'))
            c.create_rectangle(x-5*f,y+3*f,x+5*f,y+12*f,outline=color,tags=('game_combat','ground_markers'))
            if self.selected is target:c.create_rectangle(x-23*f,y-23*f,x+23*f,y+16*f,outline='#ffffff',tags=('game_combat','ground_markers'))
            return
        c.create_rectangle(x-18*f,y-9*f,x+18*f,y+12*f,fill=PANEL,outline=color,width=1.5,tags=('game_combat','ground_markers'))
        c.create_line(x-18*f,y-9*f,x-6*f,y-16*f,x-6*f,y-9*f,x+6*f,y-16*f,x+6*f,y-9*f,x+18*f,y-9*f,
                      fill=color,width=1.5,tags=('game_combat','ground_markers'))
        c.create_rectangle(x+10*f,y-24*f,x+15*f,y-9*f,fill=PANEL,outline=color,tags=('game_combat','ground_markers'))
        if self.selected is target:c.create_rectangle(x-22*f,y-28*f,x+22*f,y+16*f,outline='#ffffff',tags=('game_combat','ground_markers'))

    def draw_icbm_unit(self,m,show_label=True):
        if isinstance(m,PlayerStrike):
            self.draw_player_strike(m,show_label);return
        c=self.canvas
        x,y=self.pixel(m.x,m.y)
        color='#ffe66d' if int(time.monotonic()*2)%2 else '#ef6262'
        parts=[]
        if not hasattr(self,'icbm_icon_items'):self.icbm_icon_items={}
        self.icbm_icon_items[id(m)]=(m,parts)
        def remember(item,outline=False):parts.append((item,outline))
        if self.view_width>=75:
            remember(c.create_oval(x-7,y-7,x+7,y+7,fill=color,outline='',tags='game_combat'))
            if self.selected is m:c.create_oval(x-11,y-11,x+11,y+11,outline='#ffffff',tags='game_combat')
            return
        ux=math.sin(m.heading);uy=-math.cos(m.heading)
        def body_point(forward,side):return x+ux*forward-uy*side,y+uy*forward+ux*side
        outline=[body_point(-14,-2.3),body_point(10,-2.3),body_point(16,0),body_point(10,2.3),body_point(-14,2.3)]
        remember(c.create_polygon(*[v for point in outline for v in point],fill=color,outline=color,tags='game_combat'),True)
        for side in (-1,1):
            fin=[body_point(-13,side*2),body_point(-15,side*5),body_point(-7,side*2)]
            remember(c.create_polygon(*[v for point in fin for v in point],fill=color,tags='game_combat'))
        remember(c.create_line(*body_point(-11,-.7),*body_point(7,-.7),fill=color,width=1,tags='game_combat'))
        remember(c.create_line(*body_point(6,-2.3),*body_point(6,2.3),fill=color,tags='game_combat'))
        if show_label:c.create_text(x,y+25,text=m.name,fill=m.color,tags='game_combat')
        if self.selected is m:c.create_oval(x-19,y-19,x+19,y+19,outline='#ffffff',tags='game_combat')

    def render_combat(self):
        c=self.canvas;c.delete('game_combat')
        self.missile_icon_items={};self.icbm_icon_items={}
        for a in [*self.aircraft.values(),*self.combat.enemies]:
            if not self.aircraft_wreck_visible(a):continue
            if a.alive or not (not a.enemy or self.see_all or self.combat.contact(a) is not None or id(a) in getattr(self.combat,'known_wrecks',set())):continue
            x,y=self.pixel(a.x,a.y)
            c.create_oval(x-3.5,y-3.5,x+3.5,y+3.5,fill='#586070',outline='',tags=('game_combat',f'aircraft_wreck_{id(a)}'))
        for unit in self.visible_ground_units():
            if not self.ground_dot_required(unit):continue
            marker_tag=f'ground_marker_{id(unit)}'
            x,y=self.ground_pixel(unit)
            color='#586070' if not unit.alive else '#69adff' if isinstance(unit,PlayerMissileSilo) else '#ef6262' if isinstance(unit,Factory) or getattr(unit,'enemy',False) else SAM_COLOR if isinstance(unit,SAMLauncher) else '#6cd9af' if isinstance(unit,Radar) else '#ffb347' if isinstance(unit,Flak) else CIWS_COLOR if isinstance(unit,CIWS) else '#dfe9f5'
            if isinstance(unit,Radar) and not unit.enabled:color=self.muted_map_color(color,.75)
            if isinstance(unit,(Airfield,EnemyRunway)):
                c.create_rectangle(x-3.5,y-17.5,x+3.5,y+17.5,fill=color,outline='',tags=('game_combat','ground_dot',marker_tag,'ground_markers','airfield_icons'))
            elif type(unit) is Factory or isinstance(unit,Bunker):
                c.create_rectangle(x-3.5,y-3.5,x+3.5,y+3.5,fill=color,outline='',tags=('game_combat','ground_dot',marker_tag,'ground_markers'))
            else:
                c.create_oval(x-3.5,y-3.5,x+3.5,y+3.5,fill=color,outline='',tags=('game_combat','ground_dot',marker_tag,'ground_markers'))
                if unit.category=='Radars':
                    c.create_line(x-6,y-10,x-4,y-6,x+4,y-6,x+6,y-10,fill=color,width=1.5,tags=('game_combat','ground_dot',marker_tag,'ground_markers'))
            if self.selected is unit:
                if isinstance(unit,(Airfield,EnemyRunway)):c.create_rectangle(x-6,y-20,x+6,y+20,outline='#ffffff',tags=('game_combat',marker_tag,'ground_markers','airfield_icons'))
                elif unit.category=='Radars':c.create_rectangle(x-8,y-12,x+8,y+6,outline='#ffffff',tags=('game_combat',marker_tag,'ground_markers'))
                elif type(unit) is Factory or isinstance(unit,Bunker):c.create_rectangle(x-6,y-6,x+6,y+6,outline='#ffffff',tags=('game_combat',marker_tag,'ground_markers'))
                else:c.create_oval(x-6,y-6,x+6,y+6,outline='#ffffff',tags=('game_combat',marker_tag,'ground_markers'))
        for silo in self.player_silos:self.draw_player_silo(silo)
        if self.placing_player_silo and self.pointer:self.draw_player_silo(PlayerMissileSilo(0,*self.pointer),ghost=True)
        self.draw_silo_target_preview()
        self.draw_strike_blasts()
        f=self.building_factor()*.4
        for target in self.combat.factories:
            if not self.see_all and target.id not in self.combat.known:continue
            if self.ground_dot_required(target):continue
            if f<.08:continue
            self.draw_enemy_structure(target)
        attackers=[*self.aircraft.values(),*self.combat.enemies,*self.sams,*self.combat.enemy_sams]
        for a in attackers:
            if not a.alive or not self.see_all and self.selected is not a:continue
            point=None
            manual=getattr(a,'attack_target',None)
            active=getattr(a,'auto_attack_target',None)
            if active is None and isinstance(a,SAMLauncher):active=next((m.target for m in self.combat.missiles if m.owner is a),None)
            if manual is not None and manual.alive and getattr(a,'attack_point',None) is not None:
                point=a.attack_point
            elif active is not None and active.alive:
                target=active
                if isinstance(target,Aircraft):
                    contact=self.combat.contact(target,a.enemy)
                    if contact is not None:point=(contact.x,contact.y)
                elif a.enemy and self.see_all or isinstance(target,Factory) and target.id in self.combat.known:
                    point=(target.x,target.y)
                elif isinstance(target,(Radar,SAMLauncher)) and id(target) in self.combat.known_ground:point=(target.x,target.y)
            if point is not None:
                c.create_line(*self.pixel(a.x,a.y),*self.pixel(*point),fill='#ef6262',dash=(6,4),width=1.5,tags='game_combat')
        for m in self.combat.icbms:
            if not self.weapon_visible(m):continue
            self.draw_missile_trail(m,60.)
            self.draw_icbm_unit(m)
        for shell in self.combat.flak_shells:
            if not self.weapon_visible(shell):continue
            x,y=self.pixel(*shell.position(self.elapsed));c.create_oval(x-2,y-2,x+2,y+2,fill='#ffb347',outline='',tags='game_combat')
        for piece in self.combat.shrapnel:
            if not self.weapon_visible(piece):continue
            x,y=self.pixel(piece.x,piece.y);c.create_line(x-math.sin(piece.heading)*3,y+math.cos(piece.heading)*3,x,y,fill='#ffcf70',tags='game_combat')
        for bullet in self.combat.bullets:
            if not self.weapon_visible(bullet):continue
            x,y=self.pixel(bullet.x,bullet.y)
            c.create_line(x-math.sin(bullet.heading)*4,y+math.cos(bullet.heading)*4,x,y,fill="#fff1ad",width=1,tags="game_combat")
        for bomb in self.combat.bombs:
            if not self.weapon_visible(bomb):continue
            self.draw_bomb_unit(bomb)
        for missile in self.combat.missiles:
            if not self.weapon_visible(missile):continue
            self.draw_missile_trail(missile,24.)
            self.draw_missile_marker(missile)
        for flare in self.combat.flares:
            if flare.owner.enemy and not self.see_all and self.combat.contact(flare.owner) is None:continue
            x,y=self.pixel(flare.x,flare.y)
            age=self.elapsed-flare.spawned
            color='#ffe9a0' if age<3 else '#b48640'
            c.create_oval(x-1.5,y-1.5,x+1.5,y+1.5,fill=color,outline='',tags='game_combat')
        for t,x,y,color in self.combat.explosions:
            age=self.elapsed-t;x,y=self.pixel(x,y);radius=5+20*age
            c.create_oval(x-radius,y-radius,x+radius,y+radius,outline=color,width=max(1,3*(1-age)),tags='game_combat')
        if isinstance(self.selected,(Missile,Bomb)) and self.selected.alive and self.selected in [*self.combat.missiles,*self.combat.bombs] and self.weapon_visible(self.selected):
            x,y=self.pixel(*self.selected.position(self.elapsed))
            radius=max(8,self.bomb_marker_radius(self.selected)*1.2+3) if isinstance(self.selected,Bomb) else 8
            c.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#ffffff',tags='game_combat')
        self.draw_missile_attack_line()
        self.draw_buildable_reload_bars()
        c.addtag_withtag('map_world','game_combat')
        c.tag_raise('game_bombs')

    def bomb_marker_radius(self,bomb):
        return max(2.5,min(8.,2.5*math.sqrt(bomb.weight/250.)))

    def draw_bomb_unit(self,bomb):
        color=bomb.owner.color
        start=max(bomb.launched,self.elapsed-24.)
        if bomb.owner.enemy and not self.see_all:
            if not hasattr(bomb,'player_spotted_at'):bomb.player_spotted_at=self.elapsed
            start=max(start,bomb.player_spotted_at)
        # Bombs follow a known straight ballistic path; no history storage is needed.
        if self.elapsed>start:
            for i in range(8):
                t0=start+(self.elapsed-start)*i/8;t1=start+(self.elapsed-start)*(i+1)/8
                a=bomb.position(t0);b=bomb.position(t1)
                opacity=max(0.,min(1.,1.-(self.elapsed-(t0+t1)/2)/24.))
                self.canvas.create_line(*self.pixel(*a),*self.pixel(*b),fill=self.muted_map_color(color,opacity),dash=(3,3),width=1,tags='game_combat')
        x,y=self.pixel(*bomb.position(self.elapsed));r=self.bomb_marker_radius(bomb)
        ux,uy=math.sin(bomb.heading),-math.cos(bomb.heading);sx,sy=math.cos(bomb.heading),math.sin(bomb.heading)
        points=[]
        for i in range(24):
            angle=math.tau*i/24;forward=r*1.2*math.cos(angle);side=r*.65*math.sin(angle)
            points.extend((x+ux*forward+sx*side,y+uy*forward+sy*side))
        self.canvas.create_polygon(*points,fill=color,outline='',smooth=True,tags=('game_combat','game_bombs'))

    def draw_missile_marker(self,missile,item=None,now=None):
        c=self.canvas;x,y=self.pixel(missile.x,missile.y)
        now=time.monotonic() if now is None else now
        # The shape stays identifiable; pulse/rotation/flash use real time only.
        r=4.*(1.+.15*math.sin(now*3.))
        color=('#ffe66d' if int(now*2)%2 else '#ef6262') if missile.owner.enemy else missile.color
        if missile.kind=='AIM-9':
            shape='oval';points=(x-r,y-r,x+r,y+r)
        elif missile.kind in ('MIM-23','MIM-104'):
            shape='rectangle';points=(x-r,y-r,x+r,y+r)
        else:
            shape='polygon';sides=5 if missile.kind=='PAC-3 MSE' else 4
            angle=-math.pi/2 if missile.kind in ('AIM-120','Sidearm','AGM-88','PAC-3 MSE') else now*3.
            points=[v for i in range(sides) for v in (x+r*math.cos(angle+i*math.tau/sides),y+r*math.sin(angle+i*math.tau/sides))]
        if item is None:
            item=getattr(c,'create_'+shape)(*points,fill=color,outline='',tags='game_combat')
            if not hasattr(self,'missile_icon_items'):self.missile_icon_items={}
            self.missile_icon_items[id(missile)]=(missile,item)
        else:
            c.coords(item,*points);c.itemconfigure(item,fill=color)
        return item

    def animate_missile_icons(self):
        # The existing 100-ms UI timer runs while paused; update icon items only.
        now=time.monotonic()
        for missile,item in list(getattr(self,'missile_icon_items',{}).values()):
            if missile.alive:self.draw_missile_marker(missile,item=item,now=now)
        color='#ffe66d' if int(now*2)%2 else '#ef6262'
        for missile,parts in list(getattr(self,'icbm_icon_items',{}).values()):
            if not missile.alive:continue
            for item,outline in parts:
                self.canvas.itemconfigure(item,**({'fill':color,'outline':color} if outline else {'fill':color}))

    def draw_missile_trail(self,missile,lifetime):
        enemy=missile.owner.enemy
        if enemy and not self.see_all:
            if not hasattr(missile,'player_spotted_at'):missile.player_spotted_at=self.elapsed
            visible_since=missile.player_spotted_at
        else:visible_since=-math.inf
        history=[p for p in missile.history if p[0]>=visible_since and 0<=self.elapsed-p[0]<=lifetime]
        if not history:return
        color='#b85b22' if enemy else missile.color
        # Eight cached shades bound canvas work even when trail history doubles.
        if not hasattr(self,'trail_palette'):self.trail_palette={}
        key=('missile',color)
        if key not in self.trail_palette:
            self.trail_palette[key]=[self.muted_map_color(color,(i+.5)/8) for i in range(8)]
        palette=self.trail_palette[key];run=[];last_band=None
        def flush():
            if len(run)>1:
                self.canvas.create_line(*[v for point in run for v in self.pixel(*point)],fill=palette[last_band],dash=(3,3),width=1,tags='game_combat')
        for point in history:
            t,x,y=point[:3];band=min(7,int(max(0.,1.-(self.elapsed-t)/lifetime)*8))
            if last_band is not None and band!=last_band:
                last=run[-1];flush();run=[last]
            last_band=band;run.append((x,y))
        run.append((missile.x,missile.y));flush()

    def muted_map_color(self,color,opacity):
        return '#'+''.join(f'{round(int(BG[i:i+2],16)*(1-opacity)+int(color[i:i+2],16)*opacity):02x}' for i in (1,3,5))

    def draw_travel_arrow(self,start,end,color):
        x1,y1=self.pixel(*start);x2,y2=self.pixel(*end)
        length=math.hypot(x2-x1,y2-y1)
        if length<10:return
        ux,uy=(x2-x1)/length,(y2-y1)/length
        x,y=(x1+x2)/2,(y1+y2)/2
        self.canvas.create_line(x-ux*7,y-uy*7,x+ux*7,y+uy*7,fill=color,width=1.5,
                                arrow='last',arrowshape=(5,7,3),tags='movement')

    def route_measurement_text(self,distance,aircraft):
        speed=aircraft.spec['speed_knots']*STATS['speed_modes']['Mil']['speed_multiplier']
        if speed<=0:return f'{distance:.1f} NM ETA unavailable'
        minutes=max(0,math.ceil(distance/speed*60-1e-9))
        hours,minutes=divmod(minutes,60)
        duration=f'{hours}h {minutes}min' if hours else f'{minutes}min'
        return f'{distance:.1f} NM {duration}'

    def draw_route_text(self,x,y,text,color,anchor='center'):
        item=self.canvas.create_text(x,y,text=text,anchor=anchor,fill=color,font=('Helvetica',9,'bold'),tags='movement')
        bounds=self.canvas.bbox(item)
        if bounds:
            x1,y1,x2,y2=bounds
            background=self.canvas.create_rectangle(x1-3,y1-2,x2+3,y2+2,fill=BG,outline='',tags='movement')
            self.canvas.tag_lower(background,item)

    def draw_cursor_route_details(self,distance,aircraft,color):
        if self.pointer is None:return
        x,y=self.pixel(*self.pointer)
        self.draw_route_text(x+14,y+16,self.route_measurement_text(distance,aircraft),color,anchor='nw')

    def refresh_movement_overlay(self):
        now=time.monotonic()
        if self.canvas.find_withtag('movement') and now-getattr(self,'last_movement_draw',-math.inf)<.25:return
        self.last_movement_draw=now
        self.canvas.delete('movement');self.draw_movement()
        self.canvas.addtag_withtag('map_world','movement')
        if self.canvas.find_withtag('game_aircraft'):self.canvas.tag_lower('movement','game_aircraft')

    def draw_movement(self):
        c=self.canvas
        if isinstance(self.selected,Aircraft):
            a=self.selected
            color=self.muted_map_color('#ffffff',.4)
            if a.mode=='direct':
                start=(a.x,a.y);end=a.orbit_center
                c.create_line(*self.pixel(*start),*self.pixel(*end),fill=color,dash=(5,4),tags='movement')
                x,y=self.pixel(*end);c.create_oval(x-5,y-5,x+5,y+5,outline=color,tags='movement')
                self.draw_travel_arrow(start,end,color)
            elif a.mode=='patrol' and a.path:
                points=a.path+[a.path[0]]
                c.create_line(*[n for p in points for n in self.pixel(*p)],fill=color,dash=(5,4),tags='movement')
                for start,end in zip(points,points[1:]):
                    self.draw_travel_arrow(start,end,color)
            elif a.mode=='loiter':
                x,y=self.pixel(*a.orbit_center);r=a.orbit_radius*self.scale()
                c.create_oval(x-r,y-r,x+r,y+r,outline=color,dash=(5,4),tags='movement')
                direction=-1 if a.clockwise else 1
                for i in range(4):
                    angle=i*math.pi/2;delta=direction*.06
                    start=(a.orbit_center[0]+a.orbit_radius*math.cos(angle-delta),a.orbit_center[1]+a.orbit_radius*math.sin(angle-delta))
                    end=(a.orbit_center[0]+a.orbit_radius*math.cos(angle+delta),a.orbit_center[1]+a.orbit_radius*math.sin(angle+delta))
                    self.draw_travel_arrow(start,end,color)
        if self.movement_mode=='patrol' and self.pending_path:
            points=self.pending_path+([self.pointer] if self.pointer else [])
            if len(points)>1:
                color=self.muted_map_color('#ffffff',.4)
                c.create_line(*[n for p in points for n in self.pixel(*p)],fill=color,dash=(4,3),tags='movement')
                for start,end in zip(points,points[1:]):
                    self.draw_travel_arrow(start,end,color)
                if isinstance(self.selected,Aircraft):
                    distance=sum(math.dist(start,end) for start,end in zip(points,points[1:]))
                    self.draw_cursor_route_details(distance,self.selected,color)
            for i,p in enumerate(self.pending_path):
                x,y=self.pixel(*p);r=6 if i==0 else 3
                c.create_oval(x-r,y-r,x+r,y+r,outline='#ffffff',tags='movement')
        elif self.movement_mode=='direct' and self.pointer and isinstance(self.selected,Aircraft):
            start=(self.selected.x,self.selected.y);end=self.pointer
            color=self.muted_map_color('#ffffff',.4)
            c.create_line(*self.pixel(*start),*self.pixel(*end),fill=color,dash=(4,3),tags='movement')
            self.draw_travel_arrow(start,end,color)
            self.draw_cursor_route_details(math.dist(start,end),self.selected,color)
        elif self.movement_mode=='loiter' and self.pointer and isinstance(self.selected,Aircraft):
            color=self.muted_map_color('#ffffff',.4)
            center=self.world(self.drag[0],self.drag[1]) if self.drag else self.pointer
            cx,cy=self.pixel(*center);px,py=self.pixel(*self.pointer)
            dragged=self.drag is not None and math.hypot(px-self.drag[0],py-self.drag[1])>3
            radius=max(.5,math.dist(center,self.pointer)) if dragged else 10.
            r=radius*self.scale()
            c.create_oval(cx-r,cy-r,cx+r,cy+r,outline=color,dash=(4,3),tags='movement')
            dx,dy=px-cx,py-cy;length=math.hypot(dx,dy)
            ux,uy=(dx/length,dy/length) if length>1e-9 else (1.,0.)
            ex,ey=cx+ux*r,cy+uy*r
            c.create_line(cx,cy,ex,ey,fill=color,tags='movement')
            self.draw_route_text((cx+ex)/2,(cy+ey)/2,f'{radius:.1f} NM',color)
            self.draw_cursor_route_details(math.tau*radius,self.selected,color)

    def radar_d_points(self,x,y,angle=None):
        if angle is None:angle=self.elapsed*math.tau/6
        points=[]
        for i in range(25):
            a=angle-math.pi/2+i*math.pi/24
            points.extend((x+10*self.building_factor()*.8*math.cos(a),y-10*self.building_factor()*.8*math.sin(a)))
        return points

    def ewr_dish_points(self,radar,x,y):
        # Open the V toward the cone: tips ahead, apex behind the centre.
        f=self.building_factor()*.8
        bearing=radar.bearing
        ux,uy=math.sin(bearing),-math.cos(bearing)
        sx,sy=math.cos(bearing),math.sin(bearing)
        return [v for lateral,forward in ((-8,8),(0,-4),(8,8))
                for v in (x+f*(lateral*sx+forward*ux),y+f*(lateral*sy+forward*uy))]

    def draw_base_legs(self,x,y,f,color,tag):
        for sx,sy in ((-1,-1),(-1,1),(1,-1),(1,1)):
            self.canvas.create_line(x+sx*11*f,y+sy*11*f,x+sx*22*f,y+sy*22*f,
                                    fill=color,width=2,tags=tag)

    def draw_radar(self,radar,ghost=False):
        if not ghost and self.ground_dot_required(radar):return
        x,y=self.pixel(radar.x,radar.y);c=self.canvas;f=self.building_factor()*.8
        if f<.08:return
        color=('#6cd9af' if not self.placement_error(radar) else '#ff7777') if ghost else '#ef6262' if radar.enemy else '#6cd9af'
        if not radar.alive:color='#586070'
        if not ghost and not radar.enabled:color=self.muted_map_color(color,.75)
        icon_tag='radar_preview' if ghost else 'radar_icon'
        sweep_tag='radar_preview' if ghost else 'radar_sweep'
        if radar.long_range:self.draw_base_legs(x,y,f,color,icon_tag)
        c.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,dash=(4,3) if ghost else (),tags=icon_tag)
        if radar.early_warning:
            item=c.create_line(*self.ewr_dish_points(radar,x,y),fill=color,width=2,tags=sweep_tag)
        else:item=c.create_polygon(self.radar_d_points(x,y,None if ghost else radar.sweep_angle),fill='',outline=color,width=2,tags=sweep_tag)
        if not ghost:self.radar_sweeps[id(radar)]=(item,x,y)
        if self.selected is radar:c.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',dash=(4,3))

    def rotate_radars(self):
        # Only the small D glyphs animate; keep the map and coverage background cached.
        dt=max(0,self.elapsed-getattr(self,'radar_last_elapsed',self.elapsed))
        self.radar_last_elapsed=self.elapsed
        for radar in [*self.radars,*self.combat.enemy_radars]:
            if radar.radar_emitting:radar.sweep_angle=(math.pi/2-radar.bearing) if radar.early_warning else (radar.sweep_angle+dt*math.tau/6)%math.tau
            entry=self.radar_sweeps.get(id(radar))
            if entry is not None:
                item,x,y=entry
                self.canvas.coords(item,*(self.ewr_dish_points(radar,x,y) if radar.early_warning else self.radar_d_points(x,y,radar.sweep_angle)))

    def sam_e_points(self,sam,x,y):
        f=self.building_factor()*.48;angle=sam.heading
        points=[]
        # One connected stroke forms the E, including its central arm.
        for px,py in ((7,10),(-7,10),(-7,10/3),(7,10/3),(-7,10/3),(-7,-10/3),(7,-10/3),(-7,-10/3),(-7,-10),(7,-10)):
            points.extend((x+f*(px*math.cos(angle)-py*math.sin(angle)),
                           y-f*(px*math.sin(angle)+py*math.cos(angle))))
        return points

    def saaw_barrel_points(self,unit,x,y):
        f=self.building_factor()*.48
        return (x,y,x+15*f*math.cos(unit.heading),y-15*f*math.sin(unit.heading))

    def draw_saaw(self,unit):
        if self.ground_dot_required(unit):return
        x,y=self.pixel(unit.x,unit.y);f=self.building_factor()*.48
        if f<.08:return
        color='#ef6262' if unit.alive else '#586070';c=self.canvas
        c.create_rectangle(x-10*f,y-8*f,x+10*f,y+8*f,fill=PANEL,outline=color,width=2,tags='sam_icon')
        for side in (-1,1):c.create_rectangle(x-12*f,y+side*7*f,x+12*f,y+side*11*f,outline=color,tags='sam_icon')
        c.create_oval(x-5*f,y-5*f,x+5*f,y+5*f,fill=PANEL,outline=color,tags='sam_icon')
        item=c.create_line(*self.saaw_barrel_points(unit,x,y),fill=color,width=2,tags='sam_glyph')
        self.sam_glyphs[id(unit)]=(item,x,y)
        if self.selected is unit:c.create_oval(x-18*f,y-18*f,x+18*f,y+18*f,outline='#69b7ff',tags='sam_icon')

    def pac3_turret_points(self,sam,x,y):
        f=self.building_factor()*.48
        ux,uy=math.sin(sam.bearing),-math.cos(sam.bearing)
        sx,sy=math.cos(sam.bearing),math.sin(sam.bearing)
        return [[v for lateral,forward in ((offset-2,-5),(offset+2,-5),(offset+2,14),(offset-2,14))
                 for v in (x+f*(lateral*sx+forward*ux),y+f*(lateral*sy+forward*uy))]
                for offset in (-6,0,6)]

    def draw_pac3(self,sam,ghost=False):
        if not ghost and self.ground_dot_required(sam):return
        f=self.building_factor()*.48
        if f<.08:return
        x,y=self.pixel(sam.x,sam.y)
        color=('#ff7777' if self.placement_error(sam) else SAM_COLOR) if ghost else SAM_COLOR if sam.alive else '#586070'
        self.draw_base_legs(x,y,f,color,'sam_icon')
        self.canvas.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,fill=PANEL,outline=color,width=2,tags='sam_icon')
        items=[self.canvas.create_polygon(*points,fill=PANEL,outline=color,width=2,tags='sam_glyph') for points in self.pac3_turret_points(sam,x,y)]
        if not ghost:self.sam_glyphs[id(sam)]=(items,x,y)
        if self.selected is sam:self.canvas.create_oval(x-24*f,y-24*f,x+24*f,y+24*f,outline='#69b7ff',dash=(4,3),tags='sam_icon')

    def draw_sam(self,sam,ghost=False):
        if isinstance(sam,PAC3):self.draw_pac3(sam,ghost);return
        if isinstance(sam,Flak):self.draw_flak(sam,ghost);return
        if isinstance(sam,CIWS):self.draw_ciws(sam,ghost);return
        if isinstance(sam,SAAW):
            if self.see_all or id(sam) in self.combat.identified_ground:self.draw_saaw(sam)
            return
        if not ghost and self.ground_dot_required(sam):return
        f=self.building_factor()*.48
        if f<.08:return
        x,y=self.pixel(sam.x,sam.y)
        color=(SAM_COLOR if not self.placement_error(sam) else '#ff7777') if ghost else '#ef6262' if sam.enemy else SAM_COLOR
        if not sam.alive:color='#586070'
        if sam.long_range:self.draw_base_legs(x,y,f,color,'sam_icon')
        self.canvas.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,tags='sam_icon')
        item=self.canvas.create_line(*self.sam_e_points(sam,x,y),fill=color,width=2,tags='sam_glyph')
        if not ghost:self.sam_glyphs[id(sam)]=(item,x,y)
        if self.selected is sam:self.canvas.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',dash=(4,3))

    def rotate_sams(self):
        dt=max(0,self.elapsed-getattr(self,'sam_last_elapsed',self.elapsed))
        self.sam_last_elapsed=self.elapsed
        for sam in [*self.sams,*self.combat.enemy_sams]:
            if isinstance(sam,PAC3):
                if id(sam) in self.sam_glyphs:
                    items,x,y=self.sam_glyphs[id(sam)]
                    for item,points in zip(items,self.pac3_turret_points(sam,x,y)):self.canvas.coords(item,*points)
                continue
            if isinstance(sam,CIWS):continue
            target=next((m.target for m in self.combat.missiles if m.owner is sam and m.target.alive),None)
            if target is None and isinstance(sam,SAAW):target=sam.attack_target
            if target is not None and target.alive:
                tx,ty=target.position(self.elapsed) if isinstance(target,(Missile,Bomb)) else (target.x,target.y)
                sam.target_heading=math.atan2(ty-sam.y,tx-sam.x)
            elif self.elapsed>=sam.next_look:
                sam.target_heading=self.random.uniform(-math.pi,math.pi)
                sam.next_look=self.elapsed+self.random.uniform(2,5)
            delta=(sam.target_heading-sam.heading+math.pi)%math.tau-math.pi
            sam.heading+=max(-dt*.9,min(dt*.9,delta))
            if id(sam) in self.sam_glyphs:
                item,x,y=self.sam_glyphs[id(sam)]
                self.canvas.coords(item,*(self.saaw_barrel_points(sam,x,y) if isinstance(sam,SAAW) else self.sam_e_points(sam,x,y)))

    def coverage_in_view(self,spec):
        # A source whose bounding circle misses the viewport cannot alter a
        # visible union edge; keep all intersecting sources for correct merging.
        x,y,r=spec[:3]
        half_width=self.view_width/2
        half_height=half_width*max(1,self.canvas.winfo_height())/max(1,self.canvas.winfo_width())
        return (x+r>=self.center[0]-half_width and x-r<=self.center[0]+half_width
                and y+r>=self.center[1]-half_height and y-r<=self.center[1]+half_height)

    def radar_footprints(self):
        # The airfield and visual detection areas are not radar sources.
        sources=[(r,(r.x,r.y,r.range_nm,r.bearing if r.early_warning else 0.,r.radar_angle_deg)) for r in self.radars if r.radar_emitting]
        sources.extend((g,(g.x,g.y,g.radar_range_nm,0.,360.)) for g in self.ciws if g.radar_emitting)
        sources.extend((a,(a.x,a.y,a.radar_range_nm,a.heading,a.radar_angle_deg))
                       for a in self.aircraft.values() if a.sensors_active and a.radar_range_nm and a.kind!='AWACS')
        return sources

    def refresh_radar_placement_preview(self):
        job=self.radar_preview_job
        if job is not None:self.after_cancel(job);self.radar_preview_job=None
        c=self.canvas;c.delete('radar_preview')
        paths=[]
        if self.placing_radar and self.pointer:
            radar=Radar(0,*self.pointer,long_range=self.placing_lr,early_warning=self.placing_ewr)
            self.draw_radar(radar,ghost=True)
            c.addtag_withtag('map_world','radar_preview')
            paths=range_paths(radar.x,radar.y,radar.range_nm,radar.bearing,radar.radar_angle_deg,radar.min_engagement_range_nm)
        self.update_coverage_items(self.placement_radar_items,paths,'#6cd9af',(6,5),'placement_radar_coverage')
        self.apply_map_layers()

    def update_coverage_items(self,items,paths,color,dash,tag='radar_coverage'):
        c=self.canvas
        scale=self.scale();cx,cy=self.center
        ox,oy=c.winfo_width()/2-cx*scale,c.winfo_height()/2+cy*scale
        while len(items)>len(paths):c.delete(items.pop())
        for i,path in enumerate(paths):
            coords=[v for x,y in path for v in (ox+x*scale,oy-y*scale)]
            if i>=len(items):
                items.append(c.create_line(*coords,fill=color,dash=dash,width=1.3,
                                           tags=(tag,'map_world')))
            else:c.coords(items[i],*coords)
            if dash:c.tag_lower(items[i])
            else:c.tag_raise(items[i])

    def draw_selected_range_path(self,polygon,color,dash=(),dotted=False):
        c=self.canvas;points=[*polygon,polygon[0]]
        shapes=getattr(self,'selected_range_shapes',None)
        def emit(kind,coords):
            if shapes is not None:shapes.append((kind,tuple(coords),color,dash))
            elif kind=='line':c.create_line(*coords,fill=color,dash=dash,width=1.3,tags=('selected_unit_coverage','map_world'))
            else:c.create_oval(*coords,fill=color,outline='',tags=('selected_unit_coverage','map_world'))
        if not dotted:
            emit('line',[v for point in points for v in self.pixel(*point)])
            return
        spacing=c.winfo_fpixels('1i')*.1875;travelled=0.
        width,height=c.winfo_width(),c.winfo_height()
        for start,end in zip(points,points[1:]):
            x,y=self.pixel(*start);ex,ey=self.pixel(*end)
            dx,dy=ex-x,ey-y;length=math.hypot(dx,dy)
            offset=travelled;travelled+=length
            if length<1e-9:continue
            # Clip before sampling, retaining the original circumference phase.
            lo,hi=0.,1.
            for p,q in ((-dx,x+2),(dx,width+2-x),(-dy,y+2),(dy,height+2-y)):
                if abs(p)<1e-12:
                    if q<0:hi=-1;break
                elif p<0:lo=max(lo,q/p)
                else:hi=min(hi,q/p)
            if hi<lo:continue
            for n in range(math.ceil((offset+lo*length)/spacing),math.ceil((offset+hi*length)/spacing)):
                f=(n*spacing-offset)/length;px=x+dx*f;py=y+dy*f
                emit('oval',(px-1.35,py-1.35,px+1.35,py+1.35))

    def draw_selected_friendly_coverage(self):
        c=self.canvas
        unit=self.selected
        if not isinstance(unit,(Airfield,Aircraft,Radar,SAMLauncher,CIWS)) or not unit.alive or unit.enemy:
            if any(getattr(self,'selected_range_items',{}).values()):c.delete('selected_unit_coverage')
            self.selected_range_items={'line':[],'oval':[]};self.selected_range_key=None
            return
        # Draw this unit's complete boundary independently of merged overlays.
        circles=[];radar=None
        if isinstance(unit,Airfield):circles.append((unit.visual_range_nm,'#6cd9af',(),True))
        elif isinstance(unit,Aircraft):
            circles.append((unit.visual_range_nm,'#6cd9af',(),True))
            if unit.radar_range_nm and unit.kind!='AWACS':radar=(unit.radar_range_nm,unit.heading,unit.radar_angle_deg)
            if unit.kind in ('Fighter','Interceptor','Bomber'):circles.append((unit.engagement_range,'#ef6262',(6,4),False))
        elif isinstance(unit,Radar):radar=(unit.range_nm,unit.bearing if unit.early_warning else 0.,unit.radar_angle_deg)
        elif isinstance(unit,PAC3):radar=(unit.range_nm,unit.bearing,unit.radar_angle_deg)
        elif isinstance(unit,SAMLauncher):
            circles.append((unit.range_nm,SAM_COLOR,(),False))
            if unit.min_engagement_range_nm:circles.append((unit.min_engagement_range_nm,SAM_COLOR,(),False))
        elif isinstance(unit,CIWS):
            circles.extend(((unit.visual_range_nm,'#6cd9af',(),True),(unit.range_nm,'#ffe66d',(),False)))
            if unit.radar_emitting:radar=(unit.radar_range_nm,0.,360.)
            if unit.min_engagement_range_nm:circles.append((unit.min_engagement_range_nm,'#ffe66d',(),False))
        key=(id(unit),unit.x,unit.y,tuple(circles),radar,
             c.winfo_width(),c.winfo_height(),c.winfo_fpixels('1i'),self.view_width,tuple(self.center))
        if key==getattr(self,'selected_range_key',None):
            c.tag_raise('selected_unit_coverage');return
        self.selected_range_shapes=[]
        for radius,color,dash,dotted in circles:
            if radius:self.draw_selected_range_path(footprint(unit.x,unit.y,radius),color,dash,dotted)
        if radar:
            radius,bearing,angle=radar
            for path in range_paths(unit.x,unit.y,radius,bearing,angle,unit.min_engagement_range_nm if isinstance(unit,(PAC3,Radar)) else 0.):
                self.draw_selected_range_path(path[:-1],SAM_COLOR if isinstance(unit,PAC3) else '#6cd9af',() if isinstance(unit,PAC3) else (6,5))
        pools=getattr(self,'selected_range_items',{'line':[],'oval':[]})
        counts={'line':0,'oval':0}
        for kind,coords,color,dash in self.selected_range_shapes:
            index=counts[kind];counts[kind]+=1;pool=pools[kind]
            options={'fill':color,'dash':dash,'width':1.3} if kind=='line' else {'fill':color,'outline':''}
            if index==len(pool):
                item=getattr(c,'create_'+kind)(*coords,**options,tags=('selected_unit_coverage','map_world'))
                pool.append((item,coords,color,dash))
            else:
                item,old_coords,old_color,old_dash=pool[index]
                if coords!=old_coords:c.coords(item,*coords)
                if color!=old_color or dash!=old_dash:c.itemconfigure(item,**options)
                pool[index]=(item,coords,color,dash)
        for kind,pool in pools.items():
            while len(pool)>counts[kind]:c.delete(pool.pop()[0])
        self.selected_range_items=pools;self.selected_range_key=key;self.selected_range_shapes=None
        c.tag_raise('selected_unit_coverage')

    def draw_radar_coverage(self,force=False):
        sources=self.radar_footprints() if self.radar_overlay else []
        enemy_sources=[]
        if self.radar_overlay and self.see_all:
            enemy_sources=[(r,(r.x,r.y,r.range_nm,r.bearing if r.early_warning else 0.,r.radar_angle_deg)) for r in self.combat.enemy_radars if r.radar_emitting]
            enemy_sources.extend((g,(g.x,g.y,g.radar_range_nm,0.,360.)) for g in self.combat.enemy_sams if getattr(g,'radar_emitting',False))
            enemy_sources.extend((a,(a.x,a.y,a.radar_range_nm,a.heading,a.radar_angle_deg)) for a in self.combat.enemies if a.sensors_active and a.radar_range_nm and a.kind!='AWACS')
        sources=[(source,spec) for source,spec in sources if self.coverage_in_view(spec)]
        enemy_sources=[(source,spec) for source,spec in enemy_sources if self.coverage_in_view(spec)]
        key=(tuple(spec for source,spec in sources),tuple(spec for source,spec in enemy_sources))
        source_ids=(tuple(id(source) for source,spec in sources),tuple(id(source) for source,spec in enemy_sources))
        now=time.monotonic()
        if key!=self.coverage_key and (self.coverage_key is None or force or not self.playing
            or source_ids!=getattr(self,'radar_source_ids',None)
            or now-self.coverage_updated>=STATS['world']['coverage_refresh_seconds']):
            self.coverage_paths=coverage_outline([(*spec,source.min_engagement_range_nm if isinstance(source,Radar) else 0.) for source,spec in sources])
            self.enemy_radar_coverage_paths=coverage_outline([(*spec,source.min_engagement_range_nm if isinstance(source,Radar) else 0.) for source,spec in enemy_sources])
            self.coverage_key=key;self.radar_enemy_specs=key[1];self.coverage_updated=now
            self.radar_source_ids=source_ids
        self.update_coverage_items(self.coverage_items,self.coverage_paths if sources else [],'#6cd9af',(6,5))
        self.update_coverage_items(self.enemy_radar_coverage_items,getattr(self,'enemy_radar_coverage_paths',[]) if enemy_sources else [],'#ef6262',(6,5),'enemy_radar_coverage')
        selected=[path for source,spec in [*sources,*enemy_sources] if source is self.selected and source is not None and getattr(source,'enemy',False) for path in range_paths(*spec,source.min_engagement_range_nm if isinstance(source,Radar) else 0.)]
        enemy_selected=bool(getattr(self.selected,'enemy',False))
        self.update_coverage_items(self.selected_coverage_items,selected,'#ef6262' if enemy_selected else '#6cd9af',(6,5))

    def draw_visual_coverage(self):
        c=self.canvas
        if not self.visual_overlay:
            c.delete('visual_coverage');self.visual_coverage_items=[];return
        friendly=tuple((a.x,a.y,a.visual_range_nm) for a in self.aircraft.values() if a.alive and a.sensors_active)+tuple((c.x,c.y,c.visual_range_nm) for c in self.ciws if c.alive and c.visual_range_nm>0)
        if self.airfield.alive:friendly+=((self.airfield.x,self.airfield.y,self.airfield.visual_range_nm),)
        enemy=tuple((a.x,a.y,a.visual_range_nm) for a in self.combat.enemies if a.alive and a.sensors_active) if self.see_all else ()
        if self.see_all:enemy+=tuple((g.x,g.y,g.visual_range_nm) for g in self.combat.enemy_sams if isinstance(g,CIWS) and g.alive and g.visual_range_nm>0)
        friendly=tuple(spec for spec in friendly if self.coverage_in_view(spec))
        enemy=tuple(spec for spec in enemy if self.coverage_in_view(spec))
        key=(friendly,enemy,self.see_all);now=time.monotonic()
        if key!=self.visual_coverage_key and (not self.playing or self.visual_coverage_key is None
            or self.see_all!=self.visual_coverage_key[2] or now-self.visual_coverage_updated>=STATS['world']['coverage_refresh_seconds']):
            self.visual_coverage_paths=[]
            for circles,color in ((friendly,'#6cd9af'),(enemy,'#ef6262')):
                paths=union_outline([footprint(x,y,r,0.,360.) for x,y,r in circles])
                self.visual_coverage_paths.extend((path,color) for path in paths)
            self.visual_coverage_key=key;self.visual_coverage_updated=now
        # Real round dots distinguish visual coverage from radar's dashed lines.
        # Clip edges before sampling, so huge off-screen circles are inexpensive.
        width,height=c.winfo_width(),c.winfo_height();dots=[]
        spacing=c.winfo_fpixels('1i')*.1875
        for path,color in self.visual_coverage_paths:
            travelled=0.
            for start,end in zip(path,path[1:]):
                x,y=self.pixel(*start);ex,ey=self.pixel(*end);dx,dy=ex-x,ey-y
                length=math.hypot(dx,dy);offset=travelled;travelled+=length
                lo,hi=0.,1.
                for p,q in ((-dx,x+2),(dx,width+2-x),(-dy,y+2),(dy,height+2-y)):
                    if abs(p)<1e-12:
                        if q<0:hi=-1;break
                    elif p<0:lo=max(lo,q/p)
                    else:hi=min(hi,q/p)
                if hi<lo:continue
                if length<1e-9:continue
                first=math.ceil((offset+lo*length)/spacing)
                for j in range(first,math.ceil((offset+hi*length)/spacing)):
                    t=(j*spacing-offset)/length;dots.append((x+dx*t,y+dy*t,color))
        while len(self.visual_coverage_items)>len(dots):c.delete(self.visual_coverage_items.pop())
        for i,(x,y,color) in enumerate(dots):
            coords=(x-1.35,y-1.35,x+1.35,y+1.35)
            if i>=len(self.visual_coverage_items):
                self.visual_coverage_items.append(c.create_oval(*coords,fill=color,outline='',tags=('visual_coverage','map_world')))
            else:
                item=self.visual_coverage_items[i];c.coords(item,*coords);c.itemconfigure(item,fill=color)

    def draw_point_defence(self):
        active=self.point_defence_overlay or self.placing_ciws
        friendly=tuple((u.x,u.y,u.range_nm,0.,360.,u.min_engagement_range_nm) for u in self.ciws if u.alive) if active else ()
        enemy=tuple((u.x,u.y,u.gun_range_nm if isinstance(u,SAAW) else u.range_nm,0.,360.,u.min_engagement_range_nm) for u in self.combat.enemy_sams if isinstance(u,(CIWS,SAAW)) and u.alive) if active and self.see_all else ()
        preview_paths=[]
        if self.placing_ciws and self.pointer:
            preview=(Flak if self.placing_gun_kind=='Flak' else CIWS)(0,*self.pointer)
            preview_paths=range_paths(preview.x,preview.y,preview.range_nm,0.,360.,preview.min_engagement_range_nm)
        friendly=tuple(spec for spec in friendly if self.coverage_in_view(spec))
        enemy=tuple(spec for spec in enemy if self.coverage_in_view(spec))
        key=(friendly,enemy)
        if key!=self.point_defence_key:
            self.point_defence_key=key
            self.point_defence_paths=coverage_outline(friendly)
            self.enemy_point_defence_paths=coverage_outline(enemy)
        self.update_coverage_items(self.point_defence_items,self.point_defence_paths,'#ffe66d',(),'point_defence')
        self.update_coverage_items(self.enemy_point_defence_items,self.enemy_point_defence_paths,'#ef6262',(),'enemy_point_defence')
        selected=[];unit=self.selected
        if isinstance(unit,(CIWS,SAAW)) and unit.alive and unit.enemy:
            radius=unit.gun_range_nm if isinstance(unit,SAAW) else unit.range_nm
            for r in (radius,unit.min_engagement_range_nm):
                if r and r<=radius:
                    poly=footprint(unit.x,unit.y,r);selected.append(list(poly)+[poly[0]])
        self.update_coverage_items(self.selected_point_defence_items,selected,'#ef6262' if getattr(unit,'enemy',False) else '#ffe66d',(),'selected_point_defence')
        # A placement preview must stay complete even inside another site's coverage.
        self.update_coverage_items(self.placement_point_defence_items,preview_paths,'#ffe66d',(),'placement_point_defence')

    def draw_sam_coverage(self):
        def spec(s):
            return (s.x,s.y,s.range_nm,s.bearing if isinstance(s,PAC3) else 0.,s.radar_angle_deg if isinstance(s,PAC3) else 360.,s.min_engagement_range_nm)
        friendly=tuple(spec(s) for s in self.sams if s.alive) if self.sam_overlay else ()
        enemy=tuple(spec(s) for s in self.combat.enemy_sams if isinstance(s,SAMLauncher) and s.alive) if self.sam_overlay and self.see_all else ()
        if self.placing_sam and self.pointer:friendly+=(spec(self.sam_preview(*self.pointer)),)
        friendly=tuple(spec for spec in friendly if self.coverage_in_view(spec))
        enemy=tuple(spec for spec in enemy if self.coverage_in_view(spec))
        key=(friendly,enemy)
        if key!=self.sam_coverage_key:
            self.sam_coverage_key=key
            self.sam_coverage_paths=coverage_outline(friendly)
            self.enemy_sam_coverage_paths=coverage_outline(enemy)
        self.update_coverage_items(self.sam_coverage_items,self.sam_coverage_paths,SAM_COLOR,(),'sam_coverage')
        self.update_coverage_items(self.enemy_sam_coverage_items,self.enemy_sam_coverage_paths,'#ef6262',(),'enemy_sam_coverage')
        selected=[];unit=self.selected
        if isinstance(unit,SAMLauncher) and unit.alive and unit.enemy:
            selected=range_paths(*spec(unit))
        self.update_coverage_items(self.selected_sam_coverage_items,selected,'#ef6262' if getattr(unit,'enemy',False) else SAM_COLOR,(),'selected_sam_coverage')

    def set_grid_opacity(self,value):
        opacity=round(max(0.,min(100.,float(value))))/100.
        if opacity==self.grid_opacity:return
        self.grid_opacity=opacity
        self.grid_opacity_text.set(f'{round(opacity*100)}%')
        if self.grid_opacity_job is None:
            self.grid_opacity_job=self.after(40,self.update_grid_opacity)

    def update_grid_opacity(self):
        self.grid_opacity_job=None
        self.draw_map_grid()

    def draw_map_grid(self):
        c=self.canvas;width=max(1,c.winfo_width());height=max(1,c.winfo_height())
        key=(width,height,tuple(self.center),self.view_width,self.grid_opacity)
        if key!=self.grid_photo_key:
            image,self.grid_labels=grid_image(width,height,self.center,self.view_width,self.grid_opacity,BG,MUTED)
            self.grid_photo=ImageTk.PhotoImage(image,master=c)
            self.grid_photo_key=key
        tags=('map_grid','map_grid_image','map_background','map_world')
        if c.find_withtag('map_grid_image'):
            c.itemconfigure('map_grid_image',image=self.grid_photo)
            c.coords('map_grid_image',0,0)
        else:c.create_image(0,0,image=self.grid_photo,anchor='nw',tags=tags)
        c.delete('map_grid_labels')
        color=self.muted_map_color(MUTED,self.grid_opacity*.75)
        for x,y,value in self.grid_labels:
            c.create_text(x,y,text=f'{value:g}',anchor='w',fill=color,font=('Helvetica',8),
                          tags=('map_grid','map_grid_labels','map_background','map_world'))
        c.tag_lower('map_grid')

    def draw(self):
        self.draw_job=None
        c=self.canvas;c.delete('all')
        self.last_background_draw=time.monotonic()
        self.coverage_items=[];self.selected_coverage_items=[];self.enemy_radar_coverage_items=[]
        self.sam_coverage_items=[];self.selected_sam_coverage_items=[];self.enemy_sam_coverage_items=[]
        self.point_defence_items=[];self.enemy_point_defence_items=[];self.selected_point_defence_items=[];self.placement_point_defence_items=[]
        self.visual_coverage_items=[]
        self.placement_radar_items=[]
        self.selected_range_items={'line':[],'oval':[]};self.selected_range_key=None
        self.radar_sweeps={};self.sam_glyphs={};self.ciws_glyphs={}
        width,height=c.winfo_width(),c.winfo_height()
        self.draw_map_grid()
        self.draw_bands()
        if self.placing_player_silo or self.placing_radar or self.placing_sam or self.placing_ciws:
            cx,cy=self.pixel(self.airfield.x,self.airfield.y);radius=BUILD_RADIUS_NM*self.scale()
            c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill=self.muted_map_color('#ffe65c',.03),outline='#ffe65c',dash=(7,5),width=1,tags='building_area')
        c.addtag_withtag('map_background','all')
        # The polygon is the real 1.5-NM by 400-ft footprint, in map coordinates.
        corners=[n for point in self.airfield.runway_corners() for n in self.pixel(*point)]
        c.create_polygon(corners,fill='#65758a',outline=TEXT,width=1,tags=('runway','airfield_icons'))
        px,py=self.pixel(self.airfield.x,self.airfield.y)
        runway_pixels=self.airfield.runway_length*self.scale()
        if runway_pixels>=12:
            a=self.pixel(self.airfield.x,self.airfield.y-self.airfield.runway_length*.45)
            b=self.pixel(self.airfield.x,self.airfield.y+self.airfield.runway_length*.45)
            c.create_line(*a,*b,fill=TEXT,dash=(5,4),width=1,tags=('runway','airfield_icons'))
        else:
            # A small symbol keeps the airfield visible at the full-map scale.
            c.create_line(px,py-5,px,py+5,fill=TEXT,width=3,tags=('runway','airfield_icons'))
        tx,ty=self.tower_pixel();f=self.building_factor()
        tower_before=set(c.find_all())
        # World-sized warehouse-and-tower symbol shrinks with the map.
        c.create_rectangle(tx-24,ty-9,tx+24,ty+14,fill='#425872',outline=TEXT,tags=('atc_tower','airfield_icons'))
        c.create_line(tx-24,ty-9,tx,ty-16,tx+24,ty-9,fill=TEXT,tags=('atc_tower','airfield_icons'))
        c.create_rectangle(tx-17,ty+2,tx-3,ty+14,fill=PANEL,outline='#91a4bd',tags=('atc_tower','airfield_icons'))
        c.create_rectangle(tx+7,ty-3,tx+15,ty+11,fill='#526b87',outline=TEXT,tags=('atc_tower','airfield_icons'))
        c.create_rectangle(tx+8,ty-30,tx+14,ty+2,fill='#526b87',outline=TEXT,tags=('atc_tower','airfield_icons'))
        c.create_polygon(tx+1,ty-30,tx+1,ty-41,tx+21,ty-41,tx+21,ty-30,
                         fill='#69b7ff',outline=TEXT,tags=('atc_tower','airfield_icons'))
        c.create_line(tx+3,ty-35,tx+19,ty-35,fill=PANEL,width=1,tags=('atc_tower','airfield_icons'))
        c.create_line(tx+11,ty-41,tx+11,ty-48,fill=TEXT,tags=('atc_tower','airfield_icons'))
        if self.selected is self.airfield:
            c.create_rectangle(tx-28,ty-51,tx+28,ty+18,outline='#69b7ff',dash=(4,3),tags=('atc_tower','airfield_icons'))
        for item in set(c.find_all())-tower_before:
            if f<.08 or self.ground_dot_required(self.airfield):c.delete(item)
            else:c.scale(item,tx,ty,f,f)
        self.draw_parking()
        if self.view_width<50:
            hx,hy=self.pixel(*helipad_position(self.airfield));r=.18*self.scale()
            c.create_oval(hx-r,hy-r,hx+r,hy+r,fill=PANEL,outline='#56deef',width=1.5,tags=('helipad','airfield_icons'))
            if r>=5:
                c.create_line(hx-r*.35,hy-r*.5,hx-r*.35,hy+r*.5,fill=TEXT,width=1.5,tags=('helipad','airfield_icons'))
                c.create_line(hx+r*.35,hy-r*.5,hx+r*.35,hy+r*.5,fill=TEXT,width=1.5,tags=('helipad','airfield_icons'))
                c.create_line(hx-r*.35,hy,hx+r*.35,hy,fill=TEXT,width=1.5,tags=('helipad','airfield_icons'))
        for unit in self.ciws:self.draw_ciws(unit)
        if self.placing_ciws and self.pointer:self.draw_ciws((Flak if self.placing_gun_kind=='Flak' else CIWS)(0,*self.pointer),ghost=True)
        for sam in self.sams:self.draw_sam(sam)
        for radar in self.radars:self.draw_radar(radar)
        for radar in self.combat.enemy_radars:
            if self.see_all or id(radar) in self.combat.known_ground:self.draw_radar(radar)
        for sam in self.combat.enemy_sams:
            if self.see_all or id(sam) in self.combat.known_ground:self.draw_sam(sam)
        self.refresh_radar_placement_preview()
        if self.placing_sam and self.pointer:self.draw_sam(self.sam_preview(*self.pointer),ghost=True)
        if not self.ground_dot_required(self.airfield):
            c.create_text(px+12,py-runway_pixels/2-12,text=self.airfield.name,anchor='w',fill=TEXT,font=('Helvetica',10,'bold'),tags='airfield_icons')
        else:c.delete('runway')
        self.update_contacts_hud()
        c.create_text(width-8,height-12,text='NM',anchor='e',fill=MUTED,font=('Helvetica',9),tags='map_hud')
        c.addtag_withtag('map_world','all');c.dtag('map_hud','map_world')
        self.draw_radar_coverage()
        self.render_aircraft()
        self.map_aircraft_bar.lift()
        self.refresh_auto_prompts()
        self.auto_prompt_panel.lift()
        self.map_controls.lift()
        self.refresh_objective_popup()
