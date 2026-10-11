"""Standalone game-map foundation; independent of replay files and scoring."""
from dataclasses import dataclass, field
import math
import random
import time
import tkinter as tk
from tkinter import ttk
from plots import BG, PANEL, TEXT, MUTED
from game_radar import footprint, union_outline
from game_world import RWR, scatter_world
from game_logistics import LogisticsFleet, LogisticsHelicopter, LOGISTICS_LEVELS, LOGISTICS_UPGRADE_COSTS
from game_combat import CombatWorld, Factory, Bunker, Missile, Bomb, TARGET_TYPES, ENGAGEMENT_RANGES
from game_aircraft import Aircraft, AIRCRAFT_TYPES, AirOperations, parking_position, formation_position, REFUEL_RADIUS_NM
from replay_style import AIRCRAFT_SIZE, AIRCRAFT_TRAIL_WIDTH, aircraft_marker
from matplotlib.markers import MarkerStyle

ZOOM_WIDTHS_NM = (5,10,15,25,50,75,100,150,250,400,500,750,1500,2500,5000,10000,20000)
FEET_PER_NM = 6076.115485564304
BUILD_RADIUS_NM = 25.
SAM_COST = 100
HANGAR_LEVELS = (2,4,6,8,10)
HANGAR_UPGRADE_COSTS = (10000,20000,35000,50000)
RADAR_COST = 100
RADAR_RANGE_NM = 75.
POWER_LEVELS = (4,8,12,18,30)
FACTORY_INCOME = (100,250,500,750,1000)
FACTORY_UPGRADE_COSTS = (1000,2500,5000,10000)
BUILD_BUTTON_ICON_DATA = {'SAM Launcher': 'iVBORw0KGgoAAAANSUhEUgAAAJ0AAAAYCAYAAADgW/+9AAAFk0lEQVR4nO2Ze4hVRRzHP7utmU32IHNUlBqU0pulZRFYRhiVFdUWlGjRlgapcS1Pjz+koExyMbuKp4zeK0qxVFSk0hOiJ4XUWno0EUez1p2SUnLSzfT2x8zN4+3u7jl3LXucDxx2z/nNb85vzvnOb+Z3LmRkZGRkZGRkZPwTKbbmi0nb1v6VgWT8P0gjOMhEl3EIyESX0S3SZjnIRHcA2tg2bezwQx3Hf506AG3s2cDDwJnANuAFYI6SYme8sTb2PWAE0E9J0R67vhrIAYOVFDp2/SNgNHCGkqKl/Ober1FJsfTgDuvfSxCFjUBjIZffXnb9VeAqf/pEIZefErP1Bp4CrgC2A7MLufzjSe3VUk2WA6jVxvYElgPvAoOA84EdwDXxhtrYk4BzAANcWaGvtcBNsfanAH2B9gptM8oIonBUEIUfAwHwRRCF04IorCnZC7l8fSGXrwEeq+BeACQwGLgemBtE4ZgU9tRUElyxNV8sPyr51gEKOAGY67PXDmBuhbY3Am8CnwINwItl9sXAVG3s/UqKIjAJaALuq2ZQ2tiVwCicaFcBU5UUn3vbb8BAJUWbP18A7FRS3OvP24B5wM24ibQCaFBStGtjBwDzgbF+rHcoKZbFbj1OG9tc7uf7lUAIXAjsBBYoKebH7vmIfzb9lBR9Ug55KfAM8AmwBJgM9AdaO3MKorAHMAG4rJDLtwFtQRQ2+zg+6MqeMsZU1AzYP2ni1AKbcdlrjjb2FG1sxYY40TX74xL/AuJs9H2N1cYehptRi6sNWElxlpKiBjgOJ95m329SLgPGAUOB04AbtLG1wGs4wQwHLsYJqFM/AP9cXsE9qyHAJbhJdnnM92rg8ioEBzAAeBXYA2wq5PL5Qi7fqeA8JwECaIldawFOTWhPTbXLaolaJcUu4AKgH07527SxT2pjjy810saeh3soryspNvqgJ1bo7zlcdrkUWK2k+LY7wQEoKXYpKR4HDsO97KTMUlJsUVK04l7mcNx+9GRgmpLCKCk2KilmJPADOB0YhsuMPykp1gELgGvLfDd3FJA29g1t7OwOzPNwE/pcYHQQhYcnHOdR/u/PsWs7gN4J7WnjTERHWQ589aqkWKekmKik6Ivbtw3BpfoSDcDyWGFRSs/lvARcBNwOPNudoLWxU7Wx67Wx7drYIm4b0D9FF9ti/+8CeuGWzC3xIiihH8CJwLFAuzZ2rzZ2H25/NSjW/rsU8R1AIZd/EBgP/IhbVVYHUTg0gWvpncRFdAz7RdaVPRVJslxnggNfvcZRUmzQxi4CHgXQxvYCrgOO9i//D7SxI5QUq2K+Vhu7DKjHLWNV4YuQh3BL2JdKit3aWB2LdzdwRMylD/sfbmdsAQZpY3t2IbyOfFtxe8mOHnynL0RJMa4zeyGX3xBE4VqgEbgbmAZM7yKuTcAvwEjgfX9tJLAmoT1VnJUElXa5rdPGDgNmAgt9IP2BqcBK36Yet5nvqaT4teSojX0LNyPvLAt4Mm4T3B0EsBdX3tdpY+/C7U1KfAVM0sY2AmNwlXYhQb8twHpgkTZ2JnAkML3CEluJVcA3wCP+vvtwVXwvJUWlijIV/pPILKAHMBA3rhVd+RVy+T1BFL4APBBE4QTcXnQ8bm/apb27lAuuqywHbnn9Gje4hcAPwIfAVuAW36YBaIoLzvMEcL029k/ZMiVLtLHF2NHkq9Qm4DOcSAZz4MycjhPaVmAK8HKSG/kMVY9bJiNcNf5OQt993rcvTvRrcN8gm5P4J+BpYBGQB97295hfMgZRODuIwiJwG3BrEIVF/00PYAbwPa6Yex64p5DLxyvTruwHhSSCy/gHEkRhYxCFxx7qOJLS2fe4jsh+Bsuomu5+OsnISE01WS4jo1tU/dvrwQ4k4/9BluEy/nYy0WX8q/gdSq5V9zJgMtcAAAAASUVORK5CYII=', 'Radar': 'iVBORw0KGgoAAAANSUhEUgAAAHkAAAAYCAYAAADeUlK2AAADzUlEQVR4nO2YTYgcRRTHf+smXtr4hdBxTSCNoqH1EEwOoojelKi44iEoRA+CGmMLFomePERXGXBtDyUufmEkQdmDuOIlQfBgEPGTaDYdCCG1El22NEj8KDWEZTxUjemdzM70dHp7wNTv0nS9etWv+t/vVVWDx+PxeDyeXjRnk+ZS+51X5gGeaqhDYPAinxN4kQdEXVkMSyCy0mZcadOoelxPeZYBKG2mgWtd23HgE+DxKAx+GVRg/SIy2QAaaZycaGufAu52t6+lcfJozrYCeAO4CzgBjKVxMlHUXpY6sxicyI7NURjsVtqsBiaBBvBQmUHrRGRyPSCBDcAmkckXgYk0ti8kjZNR1+8VFs4XIAVC4EpgLfCRyOR0Gif7Ctr7ppNQndqGRuRQFX5w5qSJwuCY0uZD4N5Wm9Lma2A9cBL4DtgShcG3zhYDb2NfwmfYSjBb0HcOeAl4EFgZhcFl7fEUYDfwFvA5sAv7YV6ej6ETIpPLgfuAjWmczAFzIpOTLpZ9vewl4ixMJ6HOxu+MNVlpswoYBb5qtUVhsCEKgyHgEmAnMKm0GVbaDAMfAHuB1diXfX9+vMV8c13uAe4oKTDACDAFnAJm0jhJ0jjpKrBjDRAA+3Nt+zm9bPWy903dZbpFXuRdSpsmcAybddvaO0dh8HcUBhPAMHAVNkMvBXZEYfB7FAbvA3s6PaiDb4tnozD4YbEAlTZ7lDZjXeYwjl1ebgJuFJk8v0vfPBe46x+5tt+AFQXt/cZZiKqzGBaKvNnd3wBcB9zSMihttihtDittTroPIcKWxBHgxygM5nPjzOQf0MW3xU9lJtUijZPngE3Ar8ADwLTI5NoCrn+6a160izgtai97XxTJxk5ClfXLs2BNjsKgCXyhtHkeGFfa7AWuBl4AbgO+j8LgH6WNcr6zwBVKm+Gc0GuAaQClzTVdfP+bR7cAozC4vdck0zg5IjJ5CLtZ3A48BjzRw20G+AtYB3zq2tYBBwva+4qzSgGr+uP1Ojbb7sSuS/PYI8Qypc02rJAA32BL2DNKmwuVNqNAfrLdfCtBZHJKZPJ6YDmwCriZHpsugDROTgHvATtEJleKTN6KrQjvFLGfLe1CFS3TZfw6ihyFgQFeBZ52O+GdwJfAYexx4qDrN4/dOG3EruUPA+/mxlnUt0LedLEmwMfAAeDlllFkckxksglsBR4RmWy6MzXAk8DPwFEX91Ntx6Ne9kpYinX4f4nIZENk8uJBx1GU5mzSLLNrLuPn/10PgEEdpTw1UmcWewZE3Znsy3XN+FJ9DuBF9iwJ/wLFQe096aBD1gAAAABJRU5ErkJggg==', 'LR Radar': 'iVBORw0KGgoAAAANSUhEUgAAAKgAAAAYCAYAAABugbbBAAAEHElEQVR4nO2ZT2gdRRzHPzGpl7H+o7A1ttBF0bJ6KG0PoojelKoY8VAUqgdBrXUFl/rn4qEa5YFxPawY/IeRBCUHMeKlRfBgEfEvtaYrlNKJ1IaMitQ/o5YSnoedR5e4eW/evoTspvOB8Hjz+30nv935vpnZWXA4HA6Hw+FwVJnmbNhcbbrzyvwDR/Wossl60TmDOiqNM+gqoOqzYC+6ShtUKj0ilW6sdB2OlWMAQCo9DTR8T0wsTDCxa8zXX4FPgEd9T/xS1GG3+VUkSpMG0IiD8NSC9ingTvP1tTgIH87F1gJvAHcAp4DhOAhHbeNlqcMs2ItuwDJvl++JCan0RmASaAAPLGF+JYjSZBuQANuBnVGavAiMxkF2c+MgHDJ5r/D/excDHnAFsBn4KEqT6TgID1rGu6Zo0Iva+gaTvjrqwN6gAPieOCGV/hC4u2y+VPprYBtwGvgO2O174lsTC4C3yQbwM7IZeNZSOwe8BNwPrPc9sa6bazNMAG8BnwPjZD+qy/I1FBGlyRrgHmBHHIRzwFyUJpOmloOd4iXqtKZo0Ouk62oPKpXeAAwBX5XN9z2x3fdEH3AJMAZMSqX7pdL9wAfAAWAjmVHuzfe3mDaXchdwW0lzAgwCU8AZYCYOwjAOwrbmNGwCBHAo13aIs1udTvGuqcsSXVbXwtag41LpJnCCbPba22u+74l/fE+MAv3AlWQz46XAPt8Tf/ieeB/YX9R5gbbFs74nflysKKn0fqn0cJu6R8i2JDcA10dpcn67i8xxgfn8M9f2O7DWMt5tnVZUZRbsRWdr0F0m9zrgWuCmsvlS6d1S6aNS6dPGxD7ZMjoI/OR7Yj7Xz0y+0zbaFictr6eQOAifA3YCvwH3AdNRmmy2kP5lPvOGu4izhuwU7wqbWalo0Ouiy2O9B/U90QS+kEo/D4xIpQ+YNut84CrgBeAW4LDviX+l0tLUMQtcLpXuz5l0EzANIJW+uo22Rdsb4nvi1k7XGQfhsShNfiB7sHsCeAR4rINsBvgb2AJ8atq2AEcs413VWQUTLacuT5lz0NfJZq3bS+QLYJ7smGVAKr2XzIQA35Ate89IpS+USg8B+YFqp10SojSZitJkK7AG2ADcSIcHJIA4CM8A7wH7ojRZH6XJzWQz8Ts28V5ZOOi2S20ddHmDjkulm7m/sSKB7wkNvAo8ZVNUPt88cY8BXwJHyY5cjpi8ebKHnB1ke9cHgXdz/SyqXULeNLWGwMfA98DLrWCUJsNRmjSBPcBDUZo0zZkpwOPAz8BxU/eTC46QOsWXhCrtH5dD5yA7qI/S5OKVrsOW5mzYLPO0XAddpV91OjpTl2Oj5X6TdE4RB+HTK11Dt9RliXZL+zlGXWbCsjq3xNeYupis17dJjppSF6M5gzpWLf8BowiXXjQSLSkAAAAASUVORK5CYII=', 'LR SAM': 'iVBORw0KGgoAAAANSUhEUgAAAIMAAAAYCAYAAADZPE7mAAAEP0lEQVR4nO2Zf4gVVRTHP1uaxM0KJK+KgRcDdSq0IgrLiiD6QT+2/ihU2q0MKmuKpl8QQVQbLptM4JSh/dpNSYQIxZQsCskKoqCNtrFAvIaydVPCpW5h/vH6Y+a5l9fsvpnX27cbzQcey7vne+47O+fMOffNg5KSkpKSkpL/OpVBvzLWfic08gElraUVhQBlMZQ4lMUwwWlVV4CyGEocJgFoYweAbiXFxlpBajs7fXsY+Bh4QElxKGtDbeyFwAvA+al+E7BKSfF7jW4XsBCYoaQ4WvN5HjBXSaGd9c+AxcB5Sor+Rv5ZgCCOuoHu0POP1KxvAW5K364LPf9exzYVeBW4ATgCdIWe/0pee6O0sitA/s5wu5KijSTBZwLdWSJt7BRgO/BRqrsMGAJuqdHNAS4CDHBjxlZ7gDsc/TxgOnA0Q5uLII4uCOLocyAAvg7iaGUQR21Ve+j57aHntwEvZ7iHgATmAsuBniCOlhSwFyYroZVBv1L7apYfFBwTSooDwFbg3JEkwBlAj5JiSElxUEnRo6R4q0bXAewE+oDOjH36gA5tbDVZdwG9RWLNYCPwLhABNwMLgJn1nII4mgwsBZ4OPf/n0PN3AZurcdezjyVts4aLuRl+hYpBGzsbaAe+HEHyI8ndvkobO89JZi0dJBdsM3C1NlbW2Pele12pjT2R5G7rKxJrBrOALcAxYH/o+X7o+YM5/OYAAuh31voZHp317IVp9XiokrcYNmhjK8ABklb9aJZISfEncAUwA9gNHNbGrtfGTqtqtLGXkiRmm5JiH8mFW5ax3ZvAncC1wICS4uBoAWpj39fGdo0iWU1SfJcAi4M4Omm0/RxOSf/+5qwNAVNz2ovGmYtmdwUocGZItRcD5wCXjyRUUnyvpFimpJhOci44C3jdkXQC250D5Ugt9R3gKuAh4I2ccY5I6PnPAbcBv5J0poEgjubncK3G6Sb3NIaTX89eiDx3d1ZCG/VzmVRvgypKigrwhTb2eWC1NnZnujaaz15t7FrgJQBt7MnArcCpaac5jjZ2oZLiG8fXamPfIxlLW3PEd009Tej5e4M42kNyAH4MWAk8WMdtP/AHsAj4JF1bBHyX014ozmYmuujYyF0MDuuBp4DrgW2uQRu7AHgSWENyMWYC9wFfpZJ2kjEzRUnxl+P3Acnd+oi7n5JiBbCigRj/QfrV8VlgMjAbWALsqOcXev6xII42Ac8EcbQUmE/SYa7LY/+31CY073hoxM8dExu0sRXn1ZvloKSwwFrgiQzzDyQXeA1wCPgU+Am4O7V3Ar1uIaSsA5ZrYxspzry8RhK3D3wIfAu8WDUGcdQVxFEFuB+4J4ijSvpMAuBh4BeSg+3bwOOh5+929q5nbwpjcU74XxPEUXcQR6ePdxx5Ge25QLP9ysfRE5jx+opZMgFpZVcomeBM1N8mSlpMOSJKjlMWQ8m48jcBFAgJzuKGlQAAAABJRU5ErkJggg==', 'CIWS': 'iVBORw0KGgoAAAANSUhEUgAAAGcAAAAYCAYAAADnNePtAAAD70lEQVR4nO3YXawccxjH8c+pIjIapNFpGxKDRC2Rhgjpi4graSKEhCDhAkWZCyMEqQtUWtWsxHiJl/aGeIkLbogEkZ6iEYREDdIydXMYSlqMhkaOi9nV7WbPObtbrZL5JpPdfZ55dn7/+c0z+8xSU1NTU1MzPONj8Xi/+07bl0Jq9mQQY6jNOaCpzdlPDNo11OYc0Exvv8mL8hLchtOwA+9geRQGX+ZFuQmrojB4Ni/KO7E4CoMlHbWbsblH7O4oDF7Ii/JMPIjTsQ3PY2UUBr8OKzzJ0lVY1WzE27vir+DC1scnmo34ho7cDDyFC7AdK5qN+PF+88MyTNfQ6py8KJdiHZ5EpDLoOdzco2YUC/OiPKhVOxsH4/Su2IkYzYvyULyKt3AszlGZf/EwgpMsPSPJ0veQ4OMkS5clWTrSzjcb8UXNRjyCR3uUNxHiBFyJ1UmWLh4gPzC9jBkfi8e7t1610/OiPAwP4NYoDNZ15F5ubd18oDJjPj5Sney3cXxX7KsoDMbyopyHo7E6CoPfVcasHmqlFc9iLTbiGVyDORibrCjJ0oNxOZY0G/F3+C7J0hdxNTZMld8LvVMyMnf3xdXJNJyBI/FiP18UhcEfeF9lgNbrBtVtsDM22nr/DQqszIvypLwoewoZgLl4BbuwtdmI42YjntSYFschwCcdsU9wSp/5gRn2dtZmGmaijMLglwHq1tttxGKVORu6YushCoOdOBezW/tsy4vyybwoZ/b64rwoX8+LcsUkx16jupAWYkGSpYf0qfnw1mvnOndgRp/5QXX2xURdQ2XOjwjyouwpYgJGsSgvyqNwdBQGm/EeFrRip9rdOaIw+CIKgyuiMJiFs1S/R2sHXwrNRnwfLsNPuAqbkiyd10dpe/joXOcRdpsxVX4g+umayYyhMucj1WRy6QDH3qgSvhTvQhQGP6vu+0sxFoVB3qswCoMteAxnT5A/PwqD5ZMdvNmIt+Bz3ICXsKwPzVvxm+p3sc18fNZnfiCdI3PTke6tD417MD0Kg515Ud6BNXlR/qmarGARzovCIO4hbGdelB+qJqb7O1LvtGJvtgN5UZ6Mu/CwaqFzcCM+HFQsf4/K96qGkmNUt9DXpqprNuJdSZY+j3uSLL0c81QduKSf/N7S3Un9mDUNojB4AtepTto3+FQ1uTwySe16zFIZ0mZDKzbaEftSdfIexg+t/b/FtVOJm4CnVZ0X442W1ofaySRLVyRZOo6bcH2SpeOtZyK4Bd/ja9Wjwu3NRtw5iU2V/0cYpov+UyRZuirJ0iP/bR39MtnzzETUf9/sB/Z2pK7ZhwzTNTX7ib36b61m31F3zAFMbc7/lL8AoyWgQuQOg0wAAAAASUVORK5CYII='}
UPGRADE_ICON_DATA = {'Factory': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAABn0lEQVR4nO3VvWsVQRQF8F8kNhamUhTUWASERRQk2IggFnamUVsRRay2cLAU/A8WcSsFbWytFIlFtNDCQhsFBxGLFH484UUsREKEPIvdB2HdXTNgCsEDU8zce8+Ze+fODP/xNxFi+THEcpgSsylRYyLRf+MFegNCLLfgPE5iH/bUMQO8xUs8wrMiy1faOCZ7yKexgJkW8456HMMVXMb1Np6+Et3pIE9Cq0CI5XYcX7P0HPvxCUvYhsO4hHksdwl0lWhnY363yPI3IZYjKLJ8iCFe4FZfBl0CXxrzEGI5wOY+sjZ0dlGI5VMcbTGN8FrVQfO4X2T5zy6evkM+i9ixqYO4gHt4F2I520Xyp3swiVM4jSN+P5sxPmOmyPIfSQItgh+wFVdxUdVZY8wVWf6gGZP6VMBKkeU3VCVci91tzq1dFGJ5ALfxEI+xqCrD2D6FM42wpXULqDKbrce1em1VVdIJfGv4f1c9K+sW6BJtwzLOFVmelMErHMIJ1V3Yi12Yqu1f8R5PcLPI8sWEjXYjxHKw0T/aaqJ/ssAoVeDfxy9JrWawkl1U4wAAAABJRU5ErkJggg==', 'Hangars': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAuUlEQVR4nM2U2w2AMAhFxThTd+sE7tal6pdJgxe4aKryZeVxKFCWZbJIxnhvvZ/ftQjlu2YzykoawGaeBozlQefHgLsyHUDL1BJZwRjI9z2Isoz0LsB7uePZg5gAZi0wEAjI7JwIcgFYwb0x9ezWyGlvvXtjeuosyIYcaxFhH9IYEPm5PahFhOnBeFutN2/A5X710ZANGT0RHeN/qyK7Vc2S6JFFgfR/VGLYZARDzswohwCv8d54viYHLiCX67h8LbYAAAAASUVORK5CYII=', 'Logistics': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAlElEQVR4nO1Uyw3AIAiFpgu4gkN1SIdyBUewJxPSAGILSQ++kxJ4/AHY2PgKpJ+rtu5FXHJCAIDDi9AFV219NcszIojxLjmhuUTUUMqEk5kcSGV5OuV0kBNyJGMqZo5LTkht1Aw0ck7O6bk1mZJLAbHQRtMytiZPGsks2vBNXuoBjda60eEZiPV7c1m5fvzrmm6E4AYRi1BR37oFQAAAAABJRU5ErkJggg==', 'Ground Crew': 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAaCAYAAACtv5zzAAAAo0lEQVR4nO1UMQ6AIAwsxo0HMPP/RzHzAGacSCpQKAUSSbwJbbnjjirA6VAjzc6HiJ+t0d39l5SceicSwETWaIVP3hNhO0jktfUyAQmGBHAcnPwBBqaIIuxFNRXR0jEdIcW4ew2trFOtJUoW8tmX9lUj4pLn9Zrb5h1w8271FQLc+aaQ7ycdWKMVV8z5ECkX3/pV/AJbUNz87JgCvL+L7Q7OxwMGE0vnbtHpjQAAAABJRU5ErkJggg=='}
UPGRADE_ATTRIBUTES = {"Power":"power_level", "Hangars":"hangar_level", "Factory":"factory_level", "Logistics":"logistics_level", "Ground Crew":"ground_crew_level"}
SAM_COLOR = '#b18aff'
CIWS_COLOR = '#ffd52a'
SAM_RANGE_NM = 30.
LR_RANGE_MULTIPLIER = 2.25
AIRCRAFT_COLORS = (
    ('Blue','#438cff'),('Sky Blue','#87caff'),('Cyan','#56deef'),
    ('Teal','#42bdb3'),('Green','#72d693'),('Lime','#b4e46b'),
    ('Orange','#ff9a48'),('Amber','#ffc05a'),('Lemon','#ffe66d'),
    ('Red','#ef6262'),('Coral','#ff9689'),('Violet','#aa8aff'),
    ('Rose','#ee8aca'),('Pink','#ffc1dc'),('White','#dfe9f5'),
)
HARDPOINT_LOADOUTS = ('Empty','2× AIM-9','1× AIM-120C','1× HARM')
BAY_LOADOUTS = ('Empty','4× 250 lb Bomb','2× 500 lb Bomb','1× 1,000 lb Bomb')
DEFAULT_LOADOUTS={
    'Fighter':(['1× AIM-120C','1× AIM-120C','2× AIM-9','2× AIM-9'],['Empty']),
    'Interceptor':(['1× AIM-120C','1× AIM-120C','2× AIM-9','2× AIM-9'],[]),
    'Bomber':(['1× AIM-120C','1× AIM-120C'],['4× 250 lb Bomb','4× 250 lb Bomb','2× 500 lb Bomb','2× 500 lb Bomb']),
}
AIRCRAFT_DESCRIPTIONS={
    'Fighter':'A versatile aircraft for air combat and ground strikes. Carries missiles and one bomb bay.',
    'Bomber':'Carries the largest bomb load for attacking ground targets. Slower than fighters, with two missile hardpoints for defense.',
    'Interceptor':'The fastest aircraft, built to catch and engage airborne threats. Carries missiles with a shorter fuel endurance.',
    'AWACS':'Provides long-range visual air contacts in every direction. Unarmed and designed to support the rest of your force.',
    'KC-49':'An airborne tanker that refuels nearby compatible aircraft. Form up on it to replenish fuel.',
    'RQ-9B':'A slow, unarmed scout with 100 NM visual coverage. Finds air and ground targets while using very little fuel.',
}


@dataclass
class Airfield:
    name: str = 'Airfield'
    x: float = 0.
    y: float = 0.
    runway_length: float = 1.5
    runway_width_ft: float = 400.
    power_level: int = 1
    hangar_level: int = 1
    factory_level: int = 1
    logistics_level: int = 1
    ground_crew_level: int = 1
    health: float = 500.
    category: str = 'Ground'

    @property
    def alive(self):return self.health>0

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
    health: float = 100.
    category: str = 'Ground'

    @property
    def alive(self):return self.health>0

    def corners(self):
        return [(self.x+dx*self.width/2,self.y+dy*self.length/2)
                for dx,dy in ((-1,-1),(1,-1),(1,1),(-1,1))]


@dataclass
class Radar(Building):
    long_range: bool = False
    enemy: bool = False
    enabled: bool = True
    sweep_angle: float = 0.

    @property
    def radar_emitting(self):return self.alive and self.enabled

    @property
    def range_nm(self):
        return RADAR_RANGE_NM*(LR_RANGE_MULTIPLIER if self.long_range else 1)

    @property
    def power(self):
        return 4 if self.long_range else 2

    @property
    def name(self):
        return ('Enemy ' if self.enemy else '')+('LR Radar' if self.long_range else 'Radar')


@dataclass
class SAMLauncher(Building):
    ammo: int = 8
    ammo_capacity: int = 8
    width: float = .32
    length: float = .32
    enemy: bool = False
    preferred_targets: set = field(default_factory=lambda: {"Drones", "Bombers", "Fighters"})
    heading: float = 0.
    target_heading: float = 0.
    next_look: float = 0.
    long_range: bool = False

    @property
    def range_nm(self):
        return SAM_RANGE_NM*(LR_RANGE_MULTIPLIER if self.long_range else 1)

    @property
    def power(self):
        return 2 if self.long_range else 1

    @property
    def name(self):
        return ('Enemy ' if self.enemy else '')+('LR SAM' if self.long_range else 'SAM Launcher')


    def accepts_target(self, kind, x, y, *, on_datalink):
        return (on_datalink and kind in self.preferred_targets
                and math.hypot(x-self.x,y-self.y)<=self.range_nm)


def dollars(value):
    return f'${value:,.0f}' if value==int(value) else f'${value:,.2f}'


def upgrade_cost(level):
    return 100*1.5**(level-1)


@dataclass
class CIWS(Building):
    enemy: bool = False
    preferred_targets: set = field(default_factory=lambda: {'Fighters','Bombers','Drones','Missiles','Bombs'})
    shot_timer: float = 0.
    attack_target: object = None
    range_nm: float = 3.5
    power: int = 1
    ammo: int = 300
    ammo_capacity: int = 300
    name: str = 'CIWS'
    heading: float = 0.
    target_heading: float = 0.
    next_look: float = 0.


class GameMapPage(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app = app
        self.airfield = Airfield()
        self.logistics=LogisticsFleet();self.logistics.sync(1,self.airfield)
        self.center = [self.airfield.x,self.airfield.y]
        self.view_width = 10.
        self.playing = False
        self.play_speed = 1
        self.elapsed = 0.
        self.active = False
        self.job = None
        self.draw_job = None
        self.last_tick = time.monotonic()
        self.drag = None
        self.selected = self.airfield
        self.money = 100000
        self.aircraft = {}
        self.operations=AirOperations()
        self.combat=CombatWorld();self.operations.combat=self.combat
        self.combat.ground_targets=[self.airfield]
        self.rwr=RWR();self.log_entries=[]
        scatter_world(self.combat,Radar,SAMLauncher)
        self.factory_spawn_kind="Factory"
        self.placing_factory=False
        self.placing_enemy=False
        self.enemy_spawn_kind='Fighter'
        self.left_menu="Build"
        self.movement_mode=None
        self.pending_path=[]
        self.map_aircraft_buttons={}
        self.last_inspector_update=0.
        self.follow_enabled=False
        self.radar_overlay=True
        self.sam_overlay=True
        self.sam_coverage_key=None;self.sam_coverage_paths=[];self.sam_coverage_items=[];self.selected_sam_coverage_items=[]
        self.visual_overlay=True;self.visual_coverage_items=[]
        self.visual_coverage_key=None;self.visual_coverage_paths=[];self.visual_coverage_updated=-1.
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
        self.ciws=[];self.placing_ciws=False
        self.radars = []
        self.radar_sweeps = {}
        self.coverage_key = None
        self.coverage_paths = []
        self.coverage_updated = -1.
        self.coverage_items=[]
        self.selected_coverage_items=[]
        self.last_background_draw=0.
        marker=MarkerStyle(aircraft_marker(0,1))
        self.aircraft_vertices=marker.get_path().transformed(marker.get_transform()).vertices[:-1]
        self.trail_palette={} 
        self.placing_radar = False
        self.placing_sam = False
        self.pointer = None
        self.placing_lr = False

        body=ttk.Panedwindow(self,orient='horizontal')
        body.pack(fill='both',expand=True,pady=(4,0))
        left=ttk.Frame(body,width=310)
        menu_row=ttk.Frame(left);menu_row.pack(fill='x',pady=(0,5))
        self.left_menu_buttons={}
        for i,name in enumerate(('Build','Airfield','Hangar','Unit List','Debug','Log')):
            button=ttk.Button(menu_row,text=name,width=7,command=lambda n=name:self.show_left_menu(n))
            button.grid(row=i//3,column=i%3,sticky='ew',padx=1,pady=1);self.left_menu_buttons[name]=button
        for column in range(3):menu_row.columnconfigure(column,weight=1)
        self.sidebar=ttk.Panedwindow(left,orient='vertical',width=310)
        self.sidebar.pack(fill='both',expand=True)
        right=ttk.Frame(body,padding=(10,0,0,0))
        self.right_panel=right
        body.add(left,weight=0);body.add(right,weight=1)
        self.menu_host=ttk.Frame(self.sidebar)
        build=ttk.Frame(self.menu_host,padding=10)
        self.build_panel=build
        build.pack(fill='both',expand=True)
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
        self.cash_text=tk.StringVar(value='$100,000')
        self.build_power_images={n:self.power_image(n) for n in (1,2,4)}
        self.build_button_images={name:tk.PhotoImage(master=self,data=data) for name,data in BUILD_BUTTON_ICON_DATA.items()}
        self.upgrade_icons={kind:tk.PhotoImage(master=self,data=data) for kind,data in UPGRADE_ICON_DATA.items()}
        self.upgrade_icons["Power"]=self.build_power_images[1]
        self.sam_button=ttk.Button(build,text='',image=self.build_button_images['SAM Launcher'],compound='center',command=self.toggle_sam)
        self.sam_button.pack(fill='x')
        self.radar_button=ttk.Button(build,text='',image=self.build_button_images['Radar'],compound='center',command=self.toggle_radar)
        self.radar_button.pack(fill='x',pady=(6,0))
        self.lr_radar_button=ttk.Button(build,text='',image=self.build_button_images['LR Radar'],compound='center',command=lambda:self.toggle_radar(True))
        self.lr_radar_button.pack(fill='x',pady=(6,0))
        self.lr_sam_button=ttk.Button(build,text='',image=self.build_button_images['LR SAM'],compound='center',command=lambda:self.toggle_sam(True))
        self.lr_sam_button.pack(fill='x',pady=(6,0))
        self.ciws_button=ttk.Button(build,text='',image=self.build_button_images['CIWS'],compound='center',command=self.toggle_ciws)
        self.ciws_button.pack(fill='x',pady=(6,0))
        self.cancel_button=ttk.Button(build,text='Cancel Placement',command=self.cancel_placement)
        self.airfield_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.airfield_panel,text='AIRFIELD',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        self.airfield_menu_text=tk.StringVar()
        income_row=ttk.Frame(self.airfield_panel);income_row.pack(anchor='w',pady=(0,5))
        ttk.Label(income_row,text='Income: ').pack(side='left')
        ttk.Label(income_row,textvariable=self.airfield_menu_text,foreground='#72d693').pack(side='left')
        ttk.Label(income_row,text='/m').pack(side='left')
        self.logistics_text=tk.StringVar()
        ttk.Label(self.airfield_panel,textvariable=self.logistics_text).pack(anchor='w')
        self.airfield_logistics=tk.Canvas(self.airfield_panel,background=BG,highlightthickness=0,height=25,width=105)
        self.airfield_logistics.pack(anchor='w',pady=(0,5))
        self.crew_text=tk.StringVar()
        ttk.Label(self.airfield_panel,textvariable=self.crew_text,justify='left').pack(anchor='w')
        self.airfield_crew=tk.Canvas(self.airfield_panel,background=BG,highlightthickness=0,height=25,width=105)
        self.airfield_crew.pack(anchor='w',pady=(0,5))
        self.airfield_resources=tk.Canvas(self.airfield_panel,background=BG,highlightthickness=0,height=76)
        self.airfield_resources.pack(fill='x',pady=(0,10))
        self.airfield_upgrade_buttons={}
        for kind in ('Power','Hangars','Factory','Logistics','Ground Crew'):
            button=ttk.Button(self.airfield_panel,image=self.upgrade_icons[kind],compound='left',command=lambda k=kind:self.upgrade(k))
            button.pack(fill='x',pady=3);self.airfield_upgrade_buttons[kind]=button
        ttk.Button(self.airfield_panel,text='Hangar',command=self.open_aircraft_menu).pack(fill='x',pady=(10,0))
        self.debug_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.debug_panel,text='DEBUG',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        self.factory_button=ttk.Button(self.debug_panel,text='Spawn Factory · 50 HP',command=self.toggle_factory)
        self.factory_button.pack(fill='x')
        self.bunker_button=ttk.Button(self.debug_panel,text='Spawn Bunker · 500 HP',command=lambda:self.toggle_factory('Bunker'))
        self.bunker_button.pack(fill='x',pady=(6,0))
        self.enemy_button=ttk.Button(self.debug_panel,text='Spawn Enemy Fighter',command=self.toggle_enemy)
        self.enemy_button.pack(fill='x',pady=(6,0))
        self.drone_button=ttk.Button(self.debug_panel,text='Spawn Enemy Drone',command=lambda:self.toggle_enemy('Drone'))
        self.drone_button.pack(fill='x',pady=(6,0))
        self.enemy_radar_button=ttk.Button(self.debug_panel,text='Spawn Enemy Radar',command=lambda:self.toggle_enemy('Radar'))
        self.enemy_radar_button.pack(fill='x',pady=(6,0))
        self.enemy_sam_button=ttk.Button(self.debug_panel,text='Spawn Enemy SAM',command=lambda:self.toggle_enemy('SAM'))
        self.enemy_sam_button.pack(fill='x',pady=(6,0))
        self.see_all_button=ttk.Button(self.debug_panel,text='See All',command=self.toggle_see_all)
        self.see_all_button.pack(fill='x',pady=(10,0))
        ttk.Button(self.debug_panel,text='Cancel',command=self.cancel_placement).pack(fill='x',pady=(5,0))
        self.log_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.log_panel,text='LOG',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        log_scroll=ttk.Scrollbar(self.log_panel);log_scroll.pack(side='right',fill='y')
        self.log_text=tk.Text(self.log_panel,background=BG,foreground=TEXT,wrap='word',width=30,height=12,relief='flat',state='disabled',yscrollcommand=log_scroll.set)
        self.log_text.pack(fill='both',expand=True);log_scroll.configure(command=self.log_text.yview)
        self.log_text.tag_configure('cost',foreground='#ef6262')
        self.log_text.tag_configure('reward',foreground='#72d693')
        self.unit_list_panel=ttk.Frame(self.menu_host,padding=10)
        ttk.Label(self.unit_list_panel,text='UNIT LIST',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        self.unit_tree=ttk.Treeview(self.unit_list_panel,show='tree',selectmode='browse',height=8)
        unit_scroll=ttk.Scrollbar(self.unit_list_panel,orient='vertical',command=self.unit_tree.yview)
        unit_scroll.pack(side='right',fill='y');self.unit_tree.pack(fill='both',expand=True)
        self.unit_tree.configure(yscrollcommand=unit_scroll.set)
        for key,label in (('friendly','Friendly Units'),('datalink','Enemy · Data Link'),('visual','Enemy · Visual')):
            self.unit_tree.insert('', 'end',iid=key,text=label,open=True)
        self.unit_list_signature=None;self.unit_list_units={}
        self.unit_tree.bind('<<TreeviewSelect>>',self.select_list_unit)
        ttk.Label(inspector,text='INSPECTOR' ,font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,10))
        self.inspector_text=tk.StringVar()
        ttk.Label(inspector,textvariable=self.inspector_text,justify='left',wraplength=270).pack(anchor='w',fill='x')

        self.upgrade_panel=ttk.Frame(inspector)
        self.upgrade_buttons={}
        for kind in ('Power','Hangars','Factory','Logistics','Ground Crew'):
            button=ttk.Button(self.upgrade_panel,image=self.upgrade_icons[kind],compound='left',command=lambda k=kind:self.upgrade(k))
            button.pack(fill='x',pady=3);self.upgrade_buttons[kind]=button

        self.aircraft_button=ttk.Button(self.upgrade_panel,text='Aircraft',command=self.open_aircraft_menu)
        self.aircraft_button.pack(fill='x',pady=(10,3))
        self.aircraft_controls=ttk.Frame(inspector)
        self.movement_text=tk.StringVar()
        row=ttk.Frame(self.aircraft_controls);row.pack(fill='x',pady=(8,4))
        self.rtb_button=ttk.Button(row,text='RTB',width=6,command=self.command_rtb)
        self.rtb_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.fence_out_button=ttk.Button(row,text='Fence Out',width=9,command=lambda:self.set_fence(False))
        self.fence_out_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.fence_in_button=ttk.Button(row,text='Fence In',width=9,command=lambda:self.set_fence(True))
        self.fence_in_button.pack(side='left',fill='x',expand=True)
        row=ttk.Frame(self.aircraft_controls);row.pack(fill='x')
        self.loiter_button=ttk.Button(row,text='Loiter',command=lambda:self.start_movement('loiter'))
        self.loiter_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.patrol_button=ttk.Button(row,text='Patrol',command=lambda:self.start_movement('patrol'))
        self.patrol_button.pack(side='left',fill='x',expand=True)
        self.form_up_button=ttk.Button(self.aircraft_controls,text='Form Up',command=lambda:self.start_movement('form_up'))
        self.form_up_button.pack(fill='x',pady=(5,0))
        self.attack_button=ttk.Button(self.aircraft_controls,text='Attack',command=self.attack_command)
        self.attack_button.pack(fill='x',pady=(5,0))
        self.ab_button=ttk.Button(self.aircraft_controls,text='AB',command=self.toggle_ab)
        self.ab_button.pack(fill='x',pady=(5,0))
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
        self.resupply_button=ttk.Button(inspector,text='Resupply',command=self.request_resupply)
        self.sam_controls=ttk.Frame(inspector)
        ttk.Label(self.sam_controls,text='Preferred Targets').pack(anchor='w',pady=(10,4))
        self.target_buttons={}
        for kind in ('Drones','Bombers','Fighters'):
            button=ttk.Button(self.sam_controls,text=kind,command=lambda k=kind:self.toggle_target(k))
            button.pack(fill='x',pady=2);self.target_buttons[kind]=button
        self.ciws_controls=ttk.Frame(inspector)
        self.ciws_target_buttons={}
        for kind in ('Fighters','Bombers','Drones','Missiles','Bombs'):
            b=ttk.Button(self.ciws_controls,text=kind,command=lambda k=kind:self.toggle_ciws_target(k))
            b.pack(fill='x',pady=2);self.ciws_target_buttons[kind]=b
        self.create_aircraft_menu()
        def inspector_widgets(widget):
            yield widget
            for child in widget.winfo_children():yield from inspector_widgets(child)
        for widget in inspector_widgets(inspector):
            widget.bind('<MouseWheel>',scroll_inspector)
            widget.bind('<Button-4>',lambda e:inspector_canvas.yview_scroll(-1,'units'))
            widget.bind('<Button-5>',lambda e:inspector_canvas.yview_scroll(1,'units'))

        controls=ttk.Frame(right);controls.pack(fill='x',pady=(0,6))
        style=ttk.Style(self)
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
        self.visual_coverage_button=ttk.Button(controls,text='Visual',style='GamePlay.TButton',command=self.toggle_visual_coverage)
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
        ttk.Label(right,textvariable=self.contacts_text).pack(anchor='w',pady=(0,4))
        self.canvas=tk.Canvas(right,background=BG,highlightthickness=1,highlightbackground='#344258')
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',self.resized)
        self.canvas.bind('<Button-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Double-Button-1>',self.double_click_aircraft)
        self.canvas.bind('<Motion>',self.hover)
        self.canvas.bind('<Leave>',self.leave)
        self.canvas.bind('<Escape>',lambda event:self.cancel_commands())
        self.map_aircraft_bar=ttk.Frame(self.canvas)
        self.key_binding=self.winfo_toplevel().bind('<KeyPress>',self.aircraft_shortcut,add='+')
        self.key_release_binding=self.winfo_toplevel().bind('<KeyRelease>',self.release_shortcut,add='+')
        self.refresh_map_aircraft_buttons()
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda e:self.zoom(.85,(e.x,e.y)))
        self.canvas.bind('<Button-5>',lambda e:self.zoom(1/.85,(e.x,e.y)))
        self.bind('<Destroy>',self.destroyed,add='+')
        self.refresh_inspector()
        self.show_left_menu("Build",cancel=False)
        self.request_draw()

    @property
    def aircraft_capacity(self):
        return HANGAR_LEVELS[self.airfield.hangar_level-1]

    def create_aircraft_menu(self):
        self.aircraft_panel=ttk.Frame(self.menu_host,padding=10)
        header=ttk.Frame(self.aircraft_panel);header.pack(fill='x')
        ttk.Label(header,text='AIRCRAFT',font=('Helvetica',11,'bold')).pack(side='left',padx=(5,0))
        slots=ttk.Frame(self.aircraft_panel);slots.pack(fill='x',pady=(10,6))
        self.slot_buttons=[]
        for slot in range(10):
            button=ttk.Button(slots,text=str(slot+1),width=3,
                              style=f'GameAircraftSlot{slot}.TButton',
                              command=lambda n=slot:self.select_aircraft_slot(n))
            button.grid(row=slot//5,column=slot%5,padx=2,pady=2,sticky='nsew')
            self.slot_buttons.append(button)
        for col in range(5):slots.columnconfigure(col,weight=1,uniform='slots')
        scroll=ttk.Frame(self.aircraft_panel);scroll.pack(fill='both',expand=True)
        self.aircraft_canvas=tk.Canvas(scroll,background=BG,highlightthickness=0,width=270)
        bar=ttk.Scrollbar(scroll,orient='vertical',command=self.aircraft_canvas.yview)
        bar.pack(side='right',fill='y');self.aircraft_canvas.pack(side='left',fill='both',expand=True)
        self.aircraft_canvas.configure(yscrollcommand=bar.set)
        self.aircraft_content=ttk.Frame(self.aircraft_canvas)
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
        if cancel:self.cancel_commands()
        self.aircraft_menu_open=False;self.aircraft_panel.pack_forget()
        for panel in (self.build_panel,self.airfield_panel,self.debug_panel,self.unit_list_panel,self.log_panel):panel.pack_forget()
        self.left_menu=name
        for key,button in self.left_menu_buttons.items():
            button.configure(style='GameSpeed.Selected.TButton' if key==name else 'TButton')
        if name in ('Build','Unit List'):
            (self.build_panel if name=='Build' else self.unit_list_panel).pack(fill='both',expand=True)
            if name=='Unit List':self.refresh_unit_list()
            if str(self.inspector_host) not in self.sidebar.panes():
                self.sidebar.add(self.inspector_host,weight=1)
                if self.inspector_sash is not None:self.after_idle(self.restore_inspector_sash)
        else:
            if str(self.inspector_host) in self.sidebar.panes():
                self.inspector_sash=self.sidebar.sashpos(0);self.sidebar.forget(self.inspector_host)
            if name=='Hangar':
                self.aircraft_menu_open=True;self.aircraft_panel.pack(fill='both',expand=True)
                self.refresh_aircraft_menu()
            else:(self.airfield_panel if name=='Airfield' else self.log_panel if name=='Log' else self.debug_panel).pack(fill='both',expand=True)
        self.refresh_inspector();self.request_draw()

    def open_aircraft_menu(self):
        self.show_left_menu('Hangar')

    def close_aircraft_menu(self):
        if self.aircraft_menu_open:self.show_left_menu('Airfield',cancel=False)

    def refresh_unit_list(self):
        rows=[('friendly','airfield',self.airfield.name,self.airfield)]
        rows.extend(('friendly',f'plane{slot}',f'{slot+1} · {a.kind} · {a.state.title()}',a)
                    for slot,a in self.aircraft.items() if a.alive)
        rows.extend(('friendly',f'heli{h.id}',f'{h.name} · {h.state.title()}',h) for h in self.logistics.helicopters)
        rows.extend(('friendly',f'ciws{c.id}',f'CIWS #{c.id}',c) for c in self.ciws if c.alive)
        rows.extend(('friendly',f'radar{r.id}',f'{r.name} #{r.id}',r) for r in self.radars if r.alive)
        rows.extend(('friendly',f'sam{s.id}',f'{s.name} #{s.id}',s) for s in self.sams if s.alive)
        for i,a in enumerate(self.combat.enemies):
            contact=self.combat.contact(a)
            if a.alive and contact is not None:
                rows.append((contact.kind,f'enemy{i}',f'E{i+1} · {a.kind}',a))
        rows.extend(('visual',f'factory{f.id}',f'{f.name} #{f.id}',f)
                    for f in self.combat.factories if f.alive and f.id in self.combat.known)
        rows.extend(('visual',f'enemyradar{radar.id}',f'{radar.name} #{radar.id}',radar)
                    for radar in self.combat.enemy_radars if radar.alive and (self.see_all or id(radar) in self.combat.known_ground))
        rows.extend(('visual',f'enemysam{sam.id}',f'Enemy SAM #{sam.id}',sam)
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
        keys=self.unit_tree.selection()
        unit=self.unit_list_units.get(keys[0]) if keys else None
        if unit is None:return
        self.cancel_commands();self.selected=unit
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()

    def toggle_factory(self,kind="Factory"):
        was=self.placing_factory and self.factory_spawn_kind==kind
        self.cancel_commands()
        self.placing_factory=not was;self.factory_spawn_kind=kind
        (self.bunker_button if kind=='Bunker' else self.factory_button).configure(style='GameSpeed.Selected.TButton' if self.placing_factory else 'TButton')
        self.canvas.configure(cursor='crosshair' if self.placing_factory else '')
        self.request_draw()

    def toggle_enemy(self,kind='Fighter'):
        was=self.placing_enemy and self.enemy_spawn_kind==kind
        self.cancel_commands();self.placing_enemy=not was;self.enemy_spawn_kind=kind
        {'Drone':self.drone_button,'Radar':self.enemy_radar_button,'SAM':self.enemy_sam_button,'Fighter':self.enemy_button}[kind].configure(style='GameSpeed.Selected.TButton' if self.placing_enemy else 'TButton')
        self.canvas.configure(cursor='crosshair' if self.placing_enemy else '')
        self.request_draw()

    def toggle_see_all(self):
        self.see_all=not self.see_all
        self.see_all_button.configure(style='GamePlay.TButton' if self.see_all else 'TButton')
        self.request_draw()

    def track_display(self,a):
        if not a.enemy:return a.x,a.y,a.heading,True,a.history
        contact=self.combat.contact(a)
        if contact is None and not self.see_all:return None
        filled=contact is not None and contact.kind=='datalink'
        if self.see_all:return a.x,a.y,a.heading,filled,a.history
        return contact.x,contact.y,contact.heading,filled,contact.history

    def attack_command(self):
        if not isinstance(self.selected,Aircraft) or self.selected.enemy:return
        if self.selected.attack_target is not None:
            self.selected.attack_target=None;self.selected.attack_point=None
            self.selected.bomb_run_target=None;self.selected.bomb_run_phase='attack'
            self.cancel_movement();self.refresh_inspector();return
        self.start_movement('attack')

    def finish_attack(self,target):
        a=self.selected
        if not isinstance(a,Aircraft) or a.enemy or target is None or not target.alive:return
        if not isinstance(target,Factory) and (not isinstance(target,(Aircraft,Radar,SAMLauncher)) or target.enemy==a.enemy):return
        a.attack_target=target;a.attack_point=(target.x,target.y);a.fenced_in=True
        a.bomb_run_target=None;a.bomb_run_phase='attack';a.bomb_run_heading=None
        self.cancel_movement();self.refresh_inspector();self.request_draw()

    def aircraft_for_slot(self,slot):
        if slot>=0:return self.aircraft.get(slot)
        index=-slot-1
        return self.combat.enemies[index] if index<len(self.combat.enemies) else None

    def map_aircraft(self):
        yield from self.aircraft.items()
        yield from ((-i-1,a) for i,a in enumerate(self.combat.enemies))

    def toggle_aircraft_target(self,kind):
        if not isinstance(self.selected,Aircraft):return
        targets=self.selected.target_types
        if kind in targets:targets.remove(kind)
        else:targets.add(kind)
        self.refresh_inspector()

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
            color=aircraft.color if aircraft else '#286fc3' if slot==self.aircraft_slot else PANEL
            rgb=[int(color[i:i+2],16) for i in (1,3,5)]
            foreground='#182436' if sum(c*w for c,w in zip(rgb,(.2126,.7152,.0722)))>155 else '#ffffff'
            style=ttk.Style(self);name=f'GameAircraftSlot{slot}.TButton'
            style.configure(name,background=color,foreground=foreground,padding=3,
                            borderwidth=2,relief='solid',
                            bordercolor='#ffffff' if slot==self.aircraft_slot else BG)
            style.map(name,background=[('disabled',PANEL),('active',color)],
                      foreground=[('disabled',MUTED),('active',foreground)])
            button.configure(state='normal' if available else 'disabled')

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

    def select_aircraft_slot(self,slot):
        if not 0<=slot<self.aircraft_capacity:return
        self.aircraft_slot=slot
        self.refresh_aircraft_menu()

    def buy_aircraft(self,kind):
        slot=self.aircraft_slot
        if kind not in AIRCRAFT_TYPES or not 0<=slot<self.aircraft_capacity or slot in self.aircraft:return False
        spec=AIRCRAFT_TYPES[kind]
        hardpoints,bays=DEFAULT_LOADOUTS.get(kind,(['Empty']*spec['hardpoints'],['Empty']*spec['bays']))
        self.aircraft[slot]=Aircraft(kind,list(hardpoints),list(bays),parking_slot=slot,state='parked')
        self.refresh_aircraft_menu();self.refresh_inspector()
        self.refresh_map_aircraft_buttons();self.request_draw()
        return True

    def set_aircraft_loadout(self,slot,group,index,value):
        aircraft=self.aircraft.get(slot)
        options=HARDPOINT_LOADOUTS if group=='hardpoints' else BAY_LOADOUTS if group=='bays' else ()
        if aircraft is None or value not in options:return False
        stations=getattr(aircraft,group)
        if not 0<=index<len(stations):return False
        changed=aircraft.change_loadout(group,index,value,self.airfield.ground_crew_level)
        if changed:self.refresh_inspector();self.request_draw()
        return changed

    def refresh_aircraft_menu(self):
        self.refresh_slot_colors()
        self.color_buttons={}
        for widget in self.aircraft_content.winfo_children():widget.destroy()
        content=self.aircraft_content
        slot=self.aircraft_slot
        aircraft=self.aircraft.get(slot)
        ttk.Label(content,text=f'Slot {slot+1} · {aircraft.kind if aircraft else "Empty"}',
                  font=('Helvetica',11,'bold')).pack(anchor='w',pady=(6,8))
        if aircraft is None:
            for kind,spec in AIRCRAFT_TYPES.items():
                if kind=='Drone':continue
                card=ttk.Frame(content);card.pack(fill='x',pady=(0,12))
                ttk.Label(card,text=kind,font=('Helvetica',10,'bold')).pack(anchor='w')
                ttk.Label(card,text=AIRCRAFT_DESCRIPTIONS[kind],wraplength=260,justify='left').pack(anchor='w',fill='x',pady=(3,0))
                ttk.Label(card,text=f"{spec['speed']} knots · {spec['fuel']:,} Fuel Units\n"
                          f"{spec['hardpoints']} Hardpoints · {spec['bays']} Bomb Bays\n{spec['cms']} Countermeasures",justify='left').pack(anchor='w',pady=3)
                ttk.Button(card,text=f'Buy {kind}',command=lambda k=kind:self.buy_aircraft(k)).pack(fill='x')
        else:
            spec=AIRCRAFT_TYPES[aircraft.kind]
            ttk.Label(content,text=f"Top Speed: {spec['speed']} knots\nFuel: {spec['fuel']:,} Units\nCountermeasures: {spec['cms']}",justify='left').pack(anchor='w',pady=(0,10))
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
            for group,title,options in (('hardpoints','Hardpoint',HARDPOINT_LOADOUTS),('bays','Bomb Bay',BAY_LOADOUTS)):
                for index,value in enumerate(getattr(aircraft,group)):
                    ttk.Label(content,text=f'{title} {index+1}').pack(anchor='w',pady=(5,2))
                    combo=ttk.Combobox(content,values=options,state='readonly',width=20)
                    combo.set(value);combo.pack(fill='x',pady=(0,3))
                    combo.bind('<<ComboboxSelected>>',lambda e,n=slot,g=group,i=index,c=combo:
                               self.set_aircraft_loadout(n,g,i,c.get()))
        # Wheel scrolling stays local to this panel and never zooms the map.
        def bind_wheel(widget):
            if not isinstance(widget,ttk.Combobox):
                widget.bind('<MouseWheel>',self.scroll_aircraft_menu)
                widget.bind('<Button-4>',lambda e:self.aircraft_canvas.yview_scroll(-1,'units'))
                widget.bind('<Button-5>',lambda e:self.aircraft_canvas.yview_scroll(1,'units'))
            for child in widget.winfo_children():bind_wheel(child)
        bind_wheel(content)
        self.aircraft_canvas.yview_moveto(0)

    @property
    def power_capacity(self):
        return POWER_LEVELS[self.airfield.power_level-1]

    @property
    def power_used(self):
        return sum(unit.power for unit in self.radars+self.sams+self.ciws if unit.alive)

    @property
    def income_per_minute(self):
        return FACTORY_INCOME[self.airfield.factory_level-1] if self.airfield.alive else 0

    def upgrade_price(self,kind,level):
        if kind=='Hangars':return HANGAR_UPGRADE_COSTS[min(level-1,3)]
        if kind=='Factory':return FACTORY_UPGRADE_COSTS[min(level-1,3)]
        if kind in ('Logistics','Ground Crew'):return LOGISTICS_UPGRADE_COSTS[min(level-1,3)]
        return upgrade_cost(level)

    def unit_color(self,unit):
        if not unit.alive:return '#586070'
        if isinstance(unit,(Aircraft,LogisticsHelicopter)):return unit.color
        if isinstance(unit,Factory) or getattr(unit,'enemy',False):return '#ef6262'
        if isinstance(unit,SAMLauncher):return SAM_COLOR
        if isinstance(unit,Radar):
            return '#6cd9af' if unit.enabled else self.muted_map_color('#6cd9af',.75)
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
        self.cash_text.set(f'${self.money:,.0f}')
        crew_level=self.airfield.ground_crew_level
        working=sum(a.crew_active for a in self.aircraft.values() if a.state=='servicing')
        self.crew_text.set(f'Ground Crew: {working}/{crew_level} busy\n{6-crew_level}s/HP · {10-(crew_level-1)*1.25:g}s/weapon')
        deployed=sum(h.state!='parked' for h in self.logistics.helicopters)
        self.logistics_text.set(f'Logistics: {deployed}/{self.airfield.logistics_level} helicopters deployed')
        support_key=(crew_level,working,self.airfield.logistics_level,deployed)
        if support_key!=getattr(self,'support_signature',None):
            self.support_signature=support_key
            for canvas in (self.hud_crew,self.airfield_crew):self.draw_support_icons(canvas,'crew',crew_level,working)
            for canvas in (self.hud_logistics,self.airfield_logistics):self.draw_support_icons(canvas,'logistics',self.airfield.logistics_level,deployed)
        used=sum(a.alive for a in self.aircraft.values())
        key=(self.power_capacity,self.power_used,self.airfield.factory_level,
             self.income_per_minute,self.aircraft_capacity,used)
        if key==getattr(self,'resource_signature',None):return
        self.resource_signature=key
        self.hud_power.configure(width=self.power_capacity*14+4)
        self.hud_power.delete('all');self.draw_power_icons(self.hud_power,used_from_right=True)
        self.airfield_menu_text.set(dollars(self.income_per_minute))
        c=self.airfield_resources;c.delete('all')
        c.create_text(0,12,text='Power:',anchor='w',fill=TEXT)
        self.draw_power_icons(c,12,55,15)
        c.create_text(0,62,text='Aircraft:',anchor='w',fill=TEXT)
        # Fighter silhouette: nose, swept wings, fuselage, and tail fins.
        vertices=((0,-11),(2,-3),(8,3),(8,6),(2,3),(2,8),(5,10),
                  (5,12),(0,10),(-5,12),(-5,10),(-2,8),(-2,3),
                  (-8,6),(-8,3),(-2,-3))
        for slot in range(self.aircraft_capacity):
            points=[v for x,y in vertices for v in (65+slot*20+x,60+y)]
            c.create_polygon(*points,outline='#87caff',fill='#87caff' if slot<used else '',width=1)

    def upgrade(self,kind):
        attr=UPGRADE_ATTRIBUTES[kind]
        level=getattr(self.airfield,attr)
        if level>=5:return False
        cost=self.upgrade_price(kind,level)
        if self.money<cost:return False
        self.spend_money(cost,f'{kind} upgrade L{level+1}')
        setattr(self.airfield,attr,level+1)
        self.logistics.sync(self.airfield.logistics_level,self.airfield)
        self.operations.ground_crew_level=self.airfield.ground_crew_level
        if kind=='Ground Crew':
            for a in self.aircraft.values():
                if a.state!='servicing':continue
                progress=a.service_progress
                a.service_total=max(0,a.max_health-a.health)*(6-self.airfield.ground_crew_level)+a.missing_weapons*(10-(self.airfield.ground_crew_level-1)*1.25)
                a.service_remaining=a.service_total*(1-progress)
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        if self.aircraft_menu_open:self.refresh_aircraft_menu()
        return True

    def toggle_radar_power(self):
        if not isinstance(self.selected,Radar) or not self.selected.alive:return
        self.selected.enabled=not self.selected.enabled
        self.coverage_key=None
        self.refresh_inspector();self.request_draw()

    def toggle_ciws_target(self,kind):
        if isinstance(self.selected,CIWS):
            if kind in self.selected.preferred_targets:self.selected.preferred_targets.remove(kind)
            else:self.selected.preferred_targets.add(kind)
            self.refresh_inspector()

    def toggle_ciws(self):
        was=self.placing_ciws
        self.show_left_menu('Build',cancel=False);self.cancel_commands()
        if was:return
        self.placing_ciws=True;self.selected=None
        self.ciws_button.configure(style='Selected.TButton');self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair');self.refresh_inspector();self.request_draw()

    def place_ciws(self,x,y):
        unit=CIWS(len(self.ciws)+1,x,y)
        error=self.placement_error(unit)
        if error:self.inspector_text.set(error);return
        self.spend_money(100,f'Build CIWS #{unit.id}');self.ciws.append(unit);self.cancel_placement();self.selected=unit
        self.cash_text.set(dollars(self.money));self.refresh_inspector();self.request_draw()
        return unit

    def refresh_inspector(self):
        self.resupply_button.pack_forget()
        self.upgrade_panel.pack_forget()
        self.aircraft_controls.pack_forget()
        self.sam_controls.pack_forget()
        self.radar_controls.pack_forget()
        self.ciws_controls.pack_forget()
        self.refresh_follow_button()
        self.refresh_resources()
        for kind,button in self.airfield_upgrade_buttons.items():
            level=getattr(self.airfield,UPGRADE_ATTRIBUTES[kind])
            cost=self.upgrade_price(kind,level)
            button.configure(text=f'{kind} L{level+1} · {dollars(cost)}'+(f' · {dollars(FACTORY_INCOME[level])}/min' if kind=='Factory' else f' · {level+1} Helis' if kind=='Logistics' else f' · {level+1} crews' if kind=='Ground Crew' else '') if level<5 else f'{kind} · Max Level',
                             state='normal' if level<5 and self.money>=cost else 'disabled')
        if self.selected is self.airfield:
            self.inspector_text.set(f'{self.airfield.name}\n\n'
                f'Position: {self.airfield.x:g}, {self.airfield.y:g} NM\n'
                f'Runway: {self.airfield.runway_length:g} NM × {self.airfield.runway_width_ft:g} ft\n\n'
                f'Power Level {self.airfield.power_level}: {self.power_used}/{self.power_capacity} Used\n'
                f'Hangars Level {self.airfield.hangar_level}: {len(self.aircraft)}/{self.aircraft_capacity} Aircraft\n'
                f'Factory Level {self.airfield.factory_level}: {dollars(self.income_per_minute)}/min\n'
                f'Logistics Level {self.airfield.logistics_level}: {self.airfield.logistics_level} Helicopters\n'
                f'Ground Crew L{self.airfield.ground_crew_level}: {6-self.airfield.ground_crew_level}s/HP, {10-(self.airfield.ground_crew_level-1)*1.25:g}s/weapon')
            self.upgrade_panel.pack(fill='x',pady=(12,0))
            for kind,button in self.upgrade_buttons.items():
                level=getattr(self.airfield,UPGRADE_ATTRIBUTES[kind])
                value={'Power':POWER_LEVELS,'Hangars':HANGAR_LEVELS,'Factory':FACTORY_INCOME,'Logistics':LOGISTICS_LEVELS,'Ground Crew':LOGISTICS_LEVELS}[kind][level] if level<5 else None
                units={'Power':'⚡','Hangars':'Aircraft','Factory':'$/min','Logistics':'Helicopters','Ground Crew':'Crews'}[kind]
                cost=self.upgrade_price(kind,level)
                button.configure(text=f'{kind} L{level+1}: {value} {units} · {dollars(cost)}' if level<5 else f'{kind} · Max Level',
                                 state='normal' if level<5 and self.money>=cost else 'disabled')
        elif isinstance(self.selected,Aircraft):
            a=self.selected
            slot=self.aircraft_number(a)
            self.inspector_text.set(f'{slot} · {a.kind}\n\n'
                f'{a.state.upper() if a.state=="rtb" else a.state.title()} · {a.mode.upper() if a.mode=="rtb" else a.mode.title()}\n'
                f'Health: {a.health:g}/{a.max_health}\n'
                f'Speed: {a.speed:.0f} knots · Limit: {a.max_ab_speed if a.mode=="formation" else a.cruise_speed:.0f}\n'
                f'Fuel: {a.fuel:,.0f}/{a.spec["fuel"]:,} Units\nBurn: {a.actual_fuel_burn:g} Units/sec\n'
                f'CMS: {a.cms}/{a.cms_capacity} · 80% Decoy Chance\nBombs: {a.bombs_available}\n'
                f'AIM-120: {a.missile_inventory.get("AIM-120",0)} · AIM-9: {a.missile_inventory.get("AIM-9",0)} · HARM: {a.missile_inventory.get("HARM",0)}\n'
                f'{"Fence In" if a.fenced_in else "Fence Out"}'
                +(f'\nGround Crew: {"Working" if a.crew_active else "Waiting"} · {a.service_progress:.0%}' if a.state=='servicing' else '')
                +(f'\nLeader: {self.aircraft_number(a.leader)} · {a.leader.kind}' if a.mode=='formation' and a.leader is not None else '')
                +(f'\nRefueling: KC-49 #{self.aircraft_number(a.refueling_from)}' if a.refueling_from is not None else '')
                +(f'\nRefuel Radius: {REFUEL_RADIUS_NM:g} NM' if a.kind=='KC-49' else ''))
            if not a.enemy and a.alive:self.aircraft_controls.pack(fill='x',pady=(6,0))
            self.rtb_button.configure(text='Deploy' if a.state in ('parked','servicing','queued') else 'RTB',
                                      style='GamePlay.TButton' if a.mode=='rtb' and a.state in ('rtb','approach','rollout') else 'TButton',
                                      state='disabled' if a.state=='servicing' or (a.state in ('parked','queued') and a.needs_service) else 'normal')
            combat_aircraft=a.kind in ('Fighter','Interceptor','Bomber')
            self.engagement_controls.pack_forget();self.attack_button.pack_forget()
            if combat_aircraft:
                self.attack_button.pack(fill='x',pady=(5,0),before=self.ab_button)
                self.engagement_controls.pack(fill='x',after=self.ab_button)
            self.attack_button.configure(text='Cancel Attack' if a.attack_target is not None else 'Attack',
                                         state='normal' if a.kind in ('Fighter','Interceptor','Bomber') else 'disabled')
            for kind,button in self.aircraft_target_buttons.items():
                button.configure(style='GamePlay.TButton' if kind in a.target_types else 'TButton')
            self.engagement_button.configure(text=f'Engagement Range: {a.engagement_range} NM')
            self.air_salvo_button.configure(text=f'Weapons per Target · Air: {a.air_weapons_per_target}')
            self.ground_salvo_button.configure(text=f'Weapons per Target · Ground: {a.ground_weapons_per_target}')
            self.ab_button.configure(text='AB · Auto' if a.auto_afterburner and not a.afterburner else 'AB',
                                     style='GameAB.TButton' if a.afterburner or a.auto_afterburner else 'TButton')
            self.fence_out_button.configure(style='GamePlay.TButton' if not a.fenced_in else 'TButton')
            self.fence_in_button.configure(style='GameFenceIn.TButton' if a.fenced_in else 'TButton',
                                          state='disabled' if a.mode=='rtb' else 'normal')
        elif isinstance(self.selected,(Missile,Bomb)):
            unit=self.selected
            speed=unit.speed if isinstance(unit,Missile) else unit.speed_at(self.elapsed)
            self.inspector_text.set(f'{unit.name}\n\nHealth: {unit.health:g}\nSpeed: {speed:.0f} knots')
        elif isinstance(self.selected,CIWS):
            self.inspector_text.set(f'CIWS #{self.selected.id}\n\nVisual Range: 8 NM\nEngagement Range: 3.5 NM\nPower: 1\nAmmo: {self.selected.ammo}/{self.selected.ammo_capacity} rounds\n{self.logistics.status(self.selected)}')
            self.ciws_controls.pack(fill='x')
            for kind,b in self.ciws_target_buttons.items():b.configure(style='GamePlay.TButton' if kind in self.selected.preferred_targets else 'TButton')
        elif isinstance(self.selected,LogisticsHelicopter):
            h=self.selected
            destination=f'{h.target.name} #{h.target.id}' if h.target is not None else 'Airfield'
            self.inspector_text.set(f'{h.name}\n\n{h.state.title()}\nSpeed: 175 knots\nDestination: {destination}')
        elif isinstance(self.selected,Factory):
            self.inspector_text.set(f'Enemy {self.selected.name} #{self.selected.id}\n\nHealth: {self.selected.health:g}/{500 if isinstance(self.selected,Bunker) else 50}\n{"Destroyed" if not self.selected.alive else "Ground"}')
        elif isinstance(self.selected,Radar):
            self.radar_controls.pack(fill='x')
            self.radar_toggle_button.configure(text='Radar On' if self.selected.enabled else 'Radar Off',
                style='GamePlay.TButton' if self.selected.enabled else 'TButton',state='normal' if self.selected.alive else 'disabled')
            self.inspector_text.set(f'{self.selected.name} #{self.selected.id}\n\n'
                f'Position: {self.selected.x:.2f}, {self.selected.y:.2f} NM\n'
                f'Range: {self.selected.range_nm:g} NM\nPower: {self.selected.power}\nCost: {dollars(RADAR_COST)}')
        elif isinstance(self.selected,SAMLauncher):
            self.inspector_text.set(f'{self.selected.name} #{self.selected.id}\n\n'
                f'Position: {self.selected.x:.2f}, {self.selected.y:.2f} NM\n'
                f'Range: {self.selected.range_nm:g} NM\nPower: {self.selected.power}\nCost: {dollars(SAM_COST)}\n'
                f'Ammo: {self.selected.ammo}/{self.selected.ammo_capacity} missiles\n'
                f'{self.logistics.status(self.selected) if not self.selected.enemy else "Out of ammo" if self.selected.ammo<=0 else "Ready"}\n'
                f'Missile: {"In Flight" if any(m.owner is self.selected for m in self.combat.missiles) else "Out of Ammo" if self.selected.ammo<=0 else "Ready"}')
            self.sam_controls.pack(fill='x')
            for kind,button in self.target_buttons.items():
                button.configure(style='GamePlay.TButton' if kind in self.selected.preferred_targets else 'TButton')
        elif self.placing_radar or self.placing_sam or self.placing_ciws:
            unit=Radar(0,0,0,long_range=self.placing_lr) if self.placing_radar else SAMLauncher(0,0,0,long_range=self.placing_lr)
            self.inspector_text.set(f'{unit.name}\n\nCost: $100\nPower: {unit.power}\nRange: {unit.range_nm:g} NM\nSelect a location inside the building area.')
        else:self.inspector_text.set('Click a unit to inspect it.')
        if isinstance(self.selected,(SAMLauncher,CIWS)) and not self.selected.enemy and self.selected.alive:
            pending=self.logistics.requested(self.selected)
            self.resupply_button.configure(text='Resupply Requested' if pending else 'Resupply',state='disabled' if pending or self.selected.ammo>=self.selected.ammo_capacity or not self.airfield.alive else 'normal')
            self.resupply_button.pack(fill='x',pady=(8,0))
        if isinstance(self.selected,(Airfield,Building)):
            self.inspector_text.set(self.inspector_text.get()+f'\nHealth: {self.selected.health:g}/{500 if isinstance(self.selected,Airfield) else 100}')

    def toggle_sam(self,long_range=False):
        self.show_left_menu('Build',cancel=False)
        self.cancel_movement()
        if self.placing_sam and self.placing_lr==long_range:self.cancel_placement();return
        self.cancel_placement()
        self.sam_overlay=True;self.sam_coverage_button.configure(style='GameSAMCoverage.TButton')
        self.placing_sam=True
        self.placing_lr=long_range
        self.selected=None
        (self.lr_sam_button if long_range else self.sam_button).configure(style='Selected.TButton')
        self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair')
        self.refresh_inspector();self.request_draw()

    def toggle_radar(self,long_range=False):
        self.show_left_menu('Build',cancel=False)
        self.cancel_movement()
        if self.placing_radar and self.placing_lr==long_range:self.cancel_placement();return
        self.cancel_placement()
        self.radar_overlay=True;self.coverage_button.configure(style='GamePlay.TButton')
        self.placing_radar=True;self.placing_lr=long_range;self.selected=None
        (self.lr_radar_button if long_range else self.radar_button).configure(style='Selected.TButton')
        self.cancel_button.pack(fill='x',pady=(6,0))
        self.canvas.configure(cursor='crosshair')
        self.refresh_inspector();self.request_draw()

    def cancel_placement(self):
        self.placing_factory=False;self.placing_enemy=False
        if hasattr(self,'enemy_button'):self.enemy_button.configure(style='TButton')
        if hasattr(self,'drone_button'):self.drone_button.configure(style='TButton')
        if hasattr(self,'enemy_radar_button'):self.enemy_radar_button.configure(style='TButton')
        if hasattr(self,'enemy_sam_button'):self.enemy_sam_button.configure(style='TButton')
        if hasattr(self,'factory_button'):self.factory_button.configure(style='TButton')
        if hasattr(self,'bunker_button'):self.bunker_button.configure(style='TButton')
        self.placing_ciws=False;self.ciws_button.configure(style='TButton')
        self.placing_sam=False;self.placing_radar=False;self.placing_lr=False;self.pointer=None
        self.sam_button.configure(style='TButton')
        self.radar_button.configure(style='TButton')
        self.lr_radar_button.configure(style='TButton')
        self.lr_sam_button.configure(style='TButton')
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
            if offset<=swept:self.app.sounds.play('sound9')

    def on_datalink(self,x,y,target=None):
        if target is not None and not (isinstance(target,Aircraft) and target.sensors_active):return False
        return (any(r.radar_emitting and math.hypot(x-r.x,y-r.y)<=r.range_nm for r in self.radars)
                or any(a.kind!='AWACS' and a.radar_detects(x,y) for a in self.aircraft.values()))

    def visible_track(self,x,y):
        return self.on_datalink(x,y) or any(a.visual_detects(x,y) or (a.kind=='AWACS' and a.radar_detects(x,y)) for a in self.aircraft.values())

    def refresh_map_aircraft_buttons(self):
        style=ttk.Style(self)
        for slot in range(10):
            a=self.aircraft.get(slot);color=a.color if a else PANEL
            name=f'GameMapAircraft{slot}.TButton'
            rgb=[int(color[i:i+2],16) for i in (1,3,5)]
            foreground='#182436' if sum(c*w for c,w in zip(rgb,(.2126,.7152,.0722)))>155 else '#ffffff'
            style.configure(name,background=color,foreground=foreground,borderwidth=2,relief='solid',padding=3,
                            bordercolor='#ffffff' if a is not None and self.selected is a else BG)
            style.map(name,background=[('disabled',PANEL),('active',color)],
                      foreground=[('disabled',MUTED),('active',foreground)])
            if slot not in self.map_aircraft_buttons:
                button=ttk.Button(self.map_aircraft_bar,text=str(slot+1),width=3,style=name,
                                  command=lambda n=slot:self.select_map_aircraft(n))
                button.bind('<Double-Button-1>',lambda event,n=slot:self.double_click_aircraft_button(n))
                button.pack(side='left',padx=2);self.map_aircraft_buttons[slot]=button
            self.map_aircraft_buttons[slot].configure(state='normal' if a is not None and a.alive else 'disabled')
        self.aircraft_button_states=tuple((slot,a.alive) for slot,a in self.aircraft.items())
        self.map_aircraft_bar.place(x=8,y=8)

    def release_shortcut(self,event):
        key=event.keysym
        if key not in self.held_shortcuts:return
        def released():
            self.held_shortcuts.discard(key)
            self.shortcut_release_jobs.pop(key,None)
        self.shortcut_release_jobs[key]=self.after(10,released)

    def aircraft_shortcut(self,event):
        if not self.active:return
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
        self.show_left_menu('Build',cancel=False)
        self.selected=aircraft
        if follow:self.follow_enabled=True;self.update_follow()
        self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()

    def aircraft_number(self,plane):
        return next((str(slot+1) if slot>=0 else f'E{-slot}' for slot,a in self.map_aircraft() if a is plane),0)

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

    def finish_form_up(self,leader):
        if not isinstance(self.selected,Aircraft):return
        if not self.selected.form_up(leader):
            self.movement_text.set('Select another aircraft. Formation loops are not allowed.');return
        self.cancel_movement();self.refresh_inspector();self.request_draw()

    def command_rtb(self):
        if not isinstance(self.selected,Aircraft):return
        if self.selected.state=='servicing':return
        self.cancel_movement()
        if self.selected.state in ('parked','queued'):
            self.selected.mode='loiter';self.selected.orbit_center=(0.,0.)
            self.selected.depart()
        else:self.selected.rtb()
        self.refresh_inspector();self.request_draw()

    def set_fence(self,engage):
        if not isinstance(self.selected,Aircraft) or engage and self.selected.mode=='rtb':return
        self.selected.fenced_in=bool(engage)
        self.refresh_inspector()

    def toggle_ab(self):
        if not isinstance(self.selected,Aircraft):return
        self.selected.afterburner=not self.selected.afterburner
        self.refresh_inspector()

    def start_movement(self,mode):
        if not isinstance(self.selected,Aircraft):return
        if self.movement_mode==mode:self.cancel_movement();return
        self.cancel_placement();self.cancel_movement()
        self.movement_mode=mode;self.pending_path=[]
        self.canvas.configure(cursor='crosshair')
        self.movement_text.set({'loiter':'Click for a 10 NM-radius orbit. Drag to set diameter: right clockwise, left counterclockwise.',
                                'patrol':'Click waypoints, then click the first point to close the loop (3–20 points).',
                                'form_up':'Click another aircraft or its numbered button to form up.',
                                'attack':'Click an enemy aircraft or building to attack.'}[mode])
        {'loiter':self.loiter_button,'patrol':self.patrol_button,'form_up':self.form_up_button,'attack':self.attack_button}[mode].configure(style='GameSpeed.Selected.TButton')
        self.movement_cancel.pack(fill='x')
        self.request_draw()

    def cancel_movement(self):
        self.movement_mode=None;self.pending_path=[]
        self.movement_text.set('')
        self.loiter_button.configure(style='TButton');self.patrol_button.configure(style='TButton');self.form_up_button.configure(style='TButton');self.attack_button.configure(style='TButton')
        self.movement_cancel.pack_forget()
        if not self.placing_sam and not self.placing_radar:self.canvas.configure(cursor='')
        self.request_draw()

    def cancel_commands(self):
        self.cancel_movement();self.cancel_placement()

    def finish_loiter(self,event):
        if not self.drag or not isinstance(self.selected,Aircraft):return
        x,y,_=self.drag;center=self.world(x,y)
        dragged=math.hypot(event.x-x,event.y-y)>3
        radius=max(.5,math.dist(center,self.world(event.x,event.y))/2) if dragged else 10.
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
        cost=RADAR_COST if isinstance(building,Radar) else SAM_COST
        power=building.power
        if self.power_used+power>self.power_capacity:return 'Upgrade Power to build more structures.'
        if self.money<cost:return 'Not enough money.'
        if any(math.hypot(x-self.airfield.x,y-self.airfield.y)>BUILD_RADIUS_NM+1e-9 for x,y in building.corners()):
            return 'Place buildings inside the 75 NM building area.'
        if abs(building.x-self.airfield.x)<(building.width+self.airfield.runway_width)/2+.02 and abs(building.y-self.airfield.y)<(building.length+self.airfield.runway_length)/2+.02:
            return 'Keep the runway clear.'
        if any(abs(building.x-px)<building.width/2+.12 and abs(building.y-py)<building.length/2+.12
               for px,py in (parking_position(slot) for slot in range(10))):
            return 'Keep aircraft parking spots clear.'
        tx,ty=self.tower_position()
        if abs(building.x-tx)<building.width/2+.3 and abs(building.y-ty)<building.length/2+.6:
            return 'Keep the ATC tower clear.'
        if any(abs(building.x-h.x)<(building.width+h.width)/2+.02 and abs(building.y-h.y)<(building.length+h.length)/2+.02 for h in self.sams+self.radars+self.ciws):
            return 'Choose a little more space between buildings.'
        return None

    def place_sam(self,x,y,long_range=None):
        if not all(math.isfinite(v) for v in (x,y)):return None
        sam=SAMLauncher(len(self.sams)+1,x,y,long_range=(self.placing_sam and self.placing_lr) if long_range is None else long_range)
        error=self.placement_error(sam)
        if error:self.inspector_text.set(error);return None
        self.spend_money(SAM_COST,f'Build {sam.name} #{sam.id}')
        self.sams.append(sam)
        self.cancel_placement();self.selected=sam
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        return sam

    def place_radar(self,x,y,long_range=None):
        if not all(math.isfinite(v) for v in (x,y)):return None
        radar=Radar(len(self.radars)+1,x,y,long_range=(self.placing_radar and self.placing_lr) if long_range is None else long_range)
        error=self.placement_error(radar)
        if error:self.inspector_text.set(error);return None
        self.spend_money(RADAR_COST,f'Build {radar.name} #{radar.id}')
        self.radars.append(radar)
        self.cancel_placement();self.selected=radar
        self.cash_text.set(dollars(self.money))
        self.refresh_inspector();self.request_draw()
        return radar

    def hover(self,event):
        if self.placing_sam or self.placing_radar or self.placing_ciws or self.movement_mode:
            self.pointer=self.world(event.x,event.y);self.request_draw()

    def leave(self,event):
        if self.pointer is not None:self.pointer=None;self.request_draw()

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
        if self.active and self.playing:self.tick_elapsed()
        self.active=active
        self.last_tick=time.monotonic()
        self.ping_sweep_time=None
        if not active and self.job is not None:
            self.after_cancel(self.job);self.job=None
        if active:
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
        self.update_follow()
        if self.left_menu=='Unit List':self.refresh_unit_list()
        if self.draw_job is None:self.render_aircraft()
        if isinstance(self.selected,(Aircraft,Factory,SAMLauncher,CIWS,Missile,Bomb,LogisticsHelicopter)) and time.monotonic()-self.last_inspector_update>=.25:
            self.last_inspector_update=time.monotonic();self.refresh_inspector()
        self.schedule_tick()

    def toggle_play(self):
        if self.playing and self.active:self.tick_elapsed()
        self.playing=not self.playing
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
        self.combat.ground_targets=[self.airfield,*self.radars,*self.sams,*self.ciws]
        self.operations.advance(self.aircraft.values(),seconds)
        health_key=tuple(unit.alive for unit in [*self.combat.ground_targets,*self.combat.enemy_radars,*self.combat.enemy_sams])+(len(self.combat.known_ground),)
        if health_key!=getattr(self,'ground_health_key',None):
            self.ground_health_key=health_key;self.request_draw()
        self.logistics.advance([*self.sams,*self.ciws],self.airfield,seconds)
        self.elapsed=self.operations.time
        self.process_game_events()
        if self.rwr.update(self.aircraft.values(),self.combat.enemy_radars,self.elapsed):self.request_draw()
        contacts=len(self.combat.contacts[False])+len(self.combat.visible_ground_contacts)
        self.contacts_text.set(f"Contacts: {contacts}")
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
        if self.key_binding:self.winfo_toplevel().unbind('<KeyPress>',self.key_binding)
        if self.key_release_binding:self.winfo_toplevel().unbind('<KeyRelease>',self.key_release_binding)
        for job in self.shortcut_release_jobs.values():self.after_cancel(job)
        for name in ('job','draw_job'):
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
        self.set_view_width(20000)

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
        if getattr(self,'ignore_map_release',False):
            self.ignore_map_release=False;self.drag=None;return
        if self.movement_mode and isinstance(self.selected,Aircraft):
            if self.movement_mode=='attack':
                slot=self.aircraft_at(event.x,event.y)
                if slot is not None:self.finish_attack(self.aircraft_for_slot(slot))
                else:
                    for target in [*self.combat.factories,*self.combat.enemy_radars,*self.combat.enemy_sams]:
                        if not self.see_all and not (target.id in self.combat.known if isinstance(target,Factory) else id(target) in self.combat.known_ground):continue
                        x,y=self.pixel(target.x,target.y)
                        if math.hypot(event.x-x,event.y-y)<=max(10,22*self.building_factor()):
                            self.finish_attack(target);break
            elif self.movement_mode=='form_up':
                slot=self.aircraft_at(event.x,event.y)
                if slot is not None:self.finish_form_up(self.aircraft_for_slot(slot))
            elif self.movement_mode=='loiter':self.finish_loiter(event)
            elif self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:self.add_patrol_point(event)
            self.drag=None;return
        if self.drag and math.hypot(event.x-self.drag[0],event.y-self.drag[1])<=3:
            if self.placing_enemy:
                if self.enemy_spawn_kind=='Radar':
                    self.selected=Radar(len(self.combat.enemy_radars)+1,*self.world(event.x,event.y),enemy=True)
                    self.combat.enemy_radars.append(self.selected)
                elif self.enemy_spawn_kind=='SAM':
                    self.selected=SAMLauncher(len(self.combat.enemy_sams)+1,*self.world(event.x,event.y),enemy=True)
                    self.combat.enemy_sams.append(self.selected)
                else:
                    spawn=self.combat.spawn_drone if self.enemy_spawn_kind=='Drone' else self.combat.spawn_fighter
                    self.selected=spawn(*self.world(event.x,event.y))
                self.refresh_inspector();self.request_draw()
            elif self.placing_factory:
                self.selected=(self.combat.spawn_bunker if self.factory_spawn_kind=='Bunker' else self.combat.spawn_factory)(*self.world(event.x,event.y))
                self.refresh_inspector();self.request_draw()
            elif self.placing_ciws:
                self.place_ciws(*self.world(event.x,event.y))
            elif self.placing_radar:
                self.place_radar(*self.world(event.x,event.y))
            elif self.placing_sam:
                self.place_sam(*self.world(event.x,event.y))
            else:
                px,py=self.tower_pixel();f=self.building_factor()
                for unit in reversed(self.visible_ground_units()):
                    if self.ground_dot_required(unit) and math.dist((event.x,event.y),self.ground_pixel(unit))<=9:
                        self.selected=unit;self.follow_enabled=False
                        self.show_left_menu('Build',cancel=False);self.refresh_inspector();self.request_draw()
                        self.drag=None;return
                self.selected=self.airfield if f>=.08 and abs(event.x-px)<=27*f and py-51*f<=event.y<=py+18*f else None
                if f>=.08:
                    for unit in reversed(self.radars+self.sams+self.ciws+[r for r in [*self.combat.enemy_radars,*self.combat.enemy_sams] if self.see_all or id(r) in self.combat.known_ground]):
                        ux,uy=self.pixel(unit.x,unit.y)
                        if math.hypot(event.x-ux,event.y-uy)<=17*f*(.8 if isinstance(unit,SAMLauncher) else 1):
                            self.selected=unit;break
                # The physical runway is never a selectable hit area.
                wx,wy=self.world(event.x,event.y)
                if abs(wx-self.airfield.x)<=self.airfield.runway_width/2 and abs(wy-self.airfield.y)<=self.airfield.runway_length/2:
                    self.selected=None
                for target in self.combat.factories:
                    if not self.see_all and target.id not in self.combat.known:continue
                    tx,ty=self.pixel(target.x,target.y)
                    if math.hypot(event.x-tx,event.y-ty)<=max(7,18*self.building_factor()*.4):self.selected=target;break
                for slot,a in self.map_aircraft():
                    if not a.alive:continue
                    display=self.track_display(a)
                    if display is None:continue
                    ax,ay=self.pixel(*display[:2])
                    if math.hypot(event.x-ax,event.y-ay)<=10:
                        self.selected=a;break
                for weapon in [*self.combat.missiles,*self.combat.bombs]:
                    if not self.weapon_visible(weapon):continue
                    wx,wy=self.pixel(*weapon.position(self.elapsed))
                    if math.hypot(event.x-wx,event.y-wy)<=9:self.selected=weapon;break
                for h in self.logistics.helicopters:
                    hx,hy=self.pixel(h.x,h.y)
                    if h.state!='parked' and math.hypot(event.x-hx,event.y-hy)<=10:self.selected=h;break
                if self.selected is not None:self.show_left_menu('Airfield' if self.selected is self.airfield else 'Build',cancel=False)
                if not isinstance(self.selected,Aircraft):self.follow_enabled=False
                self.refresh_map_aircraft_buttons();self.refresh_inspector();self.request_draw()
        self.drag=None

    def draw_parking(self):
        if self.view_width>=50:return
        for slot in range(self.aircraft_capacity):
            x,y=self.pixel(*parking_position(slot));w=.1*self.scale();h=.12*self.scale()
            self.canvas.create_rectangle(x-w,y-h,x+w,y+h,outline='#526279',width=1,tags='parking')
            if w>=8:self.canvas.create_text(x,y+h+7,text=str(slot+1),fill=MUTED,font=('Helvetica',8),tags='parking')

    def draw_formation_spots(self):
        if not isinstance(self.selected,Aircraft):return
        leader=self.selected.leader if self.selected.mode=='formation' and self.selected.leader is not None else self.selected
        occupants={a.formation_slot:a for a in leader.followers}
        count=max(2,max(occupants,default=-1)+3)
        for slot in range(count):
            x,y=self.pixel(*formation_position(leader,slot))
            occupant=occupants.get(slot)
            self.canvas.create_oval(x-3,y-3,x+3,y+3,outline=occupant.color if occupant else MUTED,
                                    width=1,tags='game_aircraft')

    def render_aircraft(self):
        states=tuple((slot,a.alive) for slot,a in self.aircraft.items())
        if states!=getattr(self,'aircraft_button_states',None):self.refresh_map_aircraft_buttons()
        if isinstance(self.selected,Aircraft) and not self.selected.alive:
            self.follow_enabled=False;self.refresh_follow_button()
        c=self.canvas;c.delete('game_aircraft')
        self.draw_radar_coverage()
        self.draw_sam_coverage()
        self.draw_visual_coverage()
        self.draw_selected_friendly_coverage()
        self.draw_formation_spots()
        fade=min(30,max(0,getattr(getattr(self.app,'settings',None),'replay_trail_fade_sec',0)))
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
                if age>30 or speed<1:continue
                alpha=min(1,max(0,(30-age)/fade)) if fade else 1
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
            co,si=math.cos(heading),math.sin(heading)
            points=[coord for px,py in self.aircraft_vertices
                    for coord in (x+(px*co+py*si)*size,y-(-px*si+py*co)*size)]
            c.create_polygon(*points,fill=a.color if filled else '',outline=a.color,width=1,tags='game_aircraft')
            if a.state=='servicing':
                c.create_rectangle(x-16,y+13,x+16,y+18,fill=PANEL,outline=MUTED,tags='game_aircraft')
                if a.service_progress>0:c.create_rectangle(x-15,y+14,x-15+30*a.service_progress,y+17,fill='#72d693' if a.crew_active else '#ffc05a',outline='',tags='game_aircraft')
            if self.selected is a:c.create_oval(x-10,y-10,x+10,y+10,outline='#ffffff',tags='game_aircraft')
            c.create_text(x+9,y-9,text=str(slot+1) if slot>=0 else f'E{-slot}',fill=a.color,font=('Helvetica',9,'bold'),anchor='w',tags='game_aircraft')
        self.render_combat()
        self.render_logistics()
        self.render_rwr()
        c.addtag_withtag('map_world','game_aircraft')

    def visible_ground_units(self):
        units=[self.airfield,*self.radars,*self.sams,*self.ciws]
        units.extend(t for t in self.combat.factories if self.see_all or t.id in self.combat.known)
        units.extend(t for t in [*self.combat.enemy_radars,*self.combat.enemy_sams] if self.see_all or id(t) in self.combat.known_ground)
        return units

    def ground_dot_required(self,unit):
        x,y=self.pixel(unit.x,unit.y)
        return self.view_width>=75 or not (6<=x<=self.canvas.winfo_width()-6 and 6<=y<=self.canvas.winfo_height()-6)

    def ground_pixel(self,unit):
        x,y=self.pixel(unit.x,unit.y)
        return max(6,min(self.canvas.winfo_width()-6,x)),max(6,min(self.canvas.winfo_height()-6,y))

    def weapon_visible(self,weapon):
        return (not weapon.owner.enemy or self.see_all or (self.combat.contact(weapon.owner) is not None if isinstance(weapon.owner,Aircraft) else id(weapon.owner) in self.combat.known_ground)
                or any(c.alive and math.dist((c.x,c.y),weapon.position(self.elapsed))<=8. for c in self.ciws))

    def add_log(self,message,tag='status',now=None):
        now=self.elapsed if now is None else now
        seconds=int(now);stamp=f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'
        entry=f'{stamp} · {message}\n'
        self.log_entries.append((entry,tag))
        self.log_text.configure(state='normal')
        self.log_text.insert('end',entry,tag)
        self.log_text.configure(state='disabled');self.log_text.see('end')

    def spend_money(self,amount,description):
        self.money-=amount
        self.add_log(f'{description} · −{dollars(amount)}','cost')

    def process_game_events(self):
        for now,message,reward,kind in self.combat.events:
            self.money+=reward
            self.add_log(message+(f' · +{dollars(reward)}' if reward else ''),'reward' if reward else kind,now)
        self.combat.events.clear()

    def render_rwr(self):
        c=self.canvas
        for radar,x,y,quality in self.rwr.estimates.values():
            if not radar.radar_emitting or self.see_all or id(radar) in self.combat.known_ground:continue
            px,py=self.pixel(x,y)
            if not -15<px<c.winfo_width()+15 or not -15<py<c.winfo_height()+15:continue
            if isinstance(self.selected,Aircraft) and not self.selected.enemy and self.selected.sensors_active and math.dist((self.selected.x,self.selected.y),(radar.x,radar.y))<=200:
                c.create_line(*self.pixel(self.selected.x,self.selected.y),px,py,fill='#ef6262',dash=(2,6),tags='game_aircraft')
            c.create_text(px,py,text='?',fill='#ef6262',font=('Helvetica',14,'bold'),tags='game_aircraft')

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

    def ciws_barrel_points(self,unit,x,y):
        f=self.building_factor();ux=math.sin(unit.heading);uy=-math.cos(unit.heading)
        return (x+ux*5*f,y+uy*5*f,x+ux*18*f,y+uy*18*f)

    def rotate_ciws(self):
        dt=max(0,self.elapsed-getattr(self,'ciws_last_elapsed',self.elapsed))
        self.ciws_last_elapsed=self.elapsed
        for unit in self.ciws:
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
                self.canvas.coords(item,*self.ciws_barrel_points(unit,x,y))

    def draw_ciws(self,unit,ghost=False):
        if not ghost and self.ground_dot_required(unit):return
        x,y=self.pixel(unit.x,unit.y);f=self.building_factor()
        color='#586070' if not unit.alive else CIWS_COLOR
        if ghost and self.placement_error(unit):color='#ff7777'
        self.canvas.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,tags='ciws_icon')
        self.canvas.create_oval(x-6*f,y-6*f,x+6*f,y+6*f,fill=PANEL,outline=color,width=2,tags='ciws_icon')
        item=self.canvas.create_line(*self.ciws_barrel_points(unit,x,y),fill=color,width=max(1,3*f),capstyle='round',tags='ciws_icon')
        if not ghost:self.ciws_glyphs[id(unit)]=(item,x,y)
        if self.selected is unit:self.canvas.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',tags='ciws_icon')

    def render_logistics(self):
        c=self.canvas
        for h in self.logistics.helicopters:
            if h.state=='parked':continue
            x,y=self.pixel(h.x,h.y);ux=math.sin(h.heading);uy=-math.cos(h.heading)
            c.create_line(x-ux*9,y-uy*9,x+ux*5,y+uy*5,fill=h.color,width=2,tags='game_aircraft')
            c.create_oval(x-3,y-3,x+3,y+3,fill=PANEL,outline=h.color,tags='game_aircraft')
            angle=self.elapsed*math.tau*1.7+h.id*.6
            for phase in (0,math.pi/2):
                rx=8*math.cos(angle+phase);ry=8*math.sin(angle+phase)
                c.create_line(x-rx,y-ry,x+rx,y+ry,fill=h.color,tags='game_aircraft')
            if self.selected is h:c.create_oval(x-11,y-11,x+11,y+11,outline='#ffffff',tags='game_aircraft')

    def render_combat(self):
        c=self.canvas;c.delete('game_combat')
        for a in self.combat.enemies:
            if a.alive or not (self.see_all or self.combat.contact(a) is not None or id(a) in getattr(self.combat,'known_wrecks',set())):continue
            x,y=self.pixel(a.x,a.y)
            c.create_oval(x-3.5,y-3.5,x+3.5,y+3.5,fill='#586070',outline='',tags='game_combat')
        for unit in self.visible_ground_units():
            if not self.ground_dot_required(unit):continue
            x,y=self.ground_pixel(unit)
            color='#586070' if not unit.alive else '#ef6262' if isinstance(unit,Factory) or getattr(unit,'enemy',False) else SAM_COLOR if isinstance(unit,SAMLauncher) else '#6cd9af' if isinstance(unit,Radar) else CIWS_COLOR if isinstance(unit,CIWS) else '#dfe9f5'
            if isinstance(unit,Radar) and not unit.enabled:color=self.muted_map_color(color,.75)
            c.create_oval(x-3.5,y-3.5,x+3.5,y+3.5,fill=color,outline='',tags=('game_combat','ground_dot'))
            if self.selected is unit:c.create_oval(x-6,y-6,x+6,y+6,outline='#ffffff',tags='game_combat')
        f=self.building_factor()*.4
        for target in self.combat.factories:
            if not self.see_all and target.id not in self.combat.known:continue
            if self.ground_dot_required(target):continue
            if f<.08:continue
            x,y=self.pixel(target.x,target.y)
            color='#ef6262' if target.alive else '#586070'
            if isinstance(target,Bunker):
                c.create_arc(x-20*f,y-20*f,x+20*f,y+16*f,start=0,extent=180,style='arc',outline=color,width=2,tags='game_combat')
                c.create_line(x-20*f,y-2*f,x-20*f,y+12*f,x+20*f,y+12*f,x+20*f,y-2*f,fill=color,width=2,tags='game_combat')
                c.create_rectangle(x-5*f,y+3*f,x+5*f,y+12*f,outline=color,tags='game_combat')
                if self.selected is target:c.create_rectangle(x-23*f,y-23*f,x+23*f,y+16*f,outline='#ffffff',tags='game_combat')
                continue
            c.create_rectangle(x-18*f,y-9*f,x+18*f,y+12*f,fill=PANEL,outline=color,width=1.5,tags='game_combat')
            c.create_line(x-18*f,y-9*f,x-6*f,y-16*f,x-6*f,y-9*f,x+6*f,y-16*f,x+6*f,y-9*f,x+18*f,y-9*f,
                          fill=color,width=1.5,tags='game_combat')
            c.create_rectangle(x+10*f,y-24*f,x+15*f,y-9*f,fill=PANEL,outline=color,tags='game_combat')
            if self.selected is target:c.create_rectangle(x-22*f,y-28*f,x+22*f,y+16*f,outline='#ffffff',tags='game_combat')
        attackers=[*self.aircraft.values(),*self.combat.enemies,*self.sams,*self.combat.enemy_sams]
        for a in attackers:
            if not a.alive or not self.see_all and self.selected is not a:continue
            point=None
            manual=getattr(a,'attack_target',None)
            active=getattr(a,'auto_attack_target',None)
            if active is None and isinstance(a,SAMLauncher):active=next((m.target for m in self.combat.missiles if m.owner is a),None)
            if manual is not None and manual.alive and a.attack_point is not None:
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
        for bullet in self.combat.bullets:
            x,y=self.pixel(bullet.x,bullet.y)
            c.create_line(x-math.sin(bullet.heading)*4,y+math.cos(bullet.heading)*4,x,y,fill="#fff1ad",width=1,tags="game_combat")
        for bomb in self.combat.bombs:
            if not self.weapon_visible(bomb):continue
            x,y=self.pixel(*bomb.position(self.elapsed));r=3
            c.create_polygon(x,y-r,x+r,y,x,y+r,x-r,y,fill='#87caff',outline='',tags=('game_combat','game_bombs'))
        for missile in self.combat.missiles:
            if not self.weapon_visible(missile):continue
            history=missile.history
            if len(history)>1:
                c.create_line(*[v for t,x,y in history for v in self.pixel(x,y)],fill=missile.color,
                              dash=(3,3),width=1,tags='game_combat')
            x,y=self.pixel(missile.x,missile.y);r=4
            angle=self.elapsed*3
            points=[v for i in range(4) for v in (x+r*math.cos(angle+i*math.pi/2),y+r*math.sin(angle+i*math.pi/2))]
            c.create_polygon(*points,fill=missile.color,outline='',tags='game_combat')
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
            c.create_oval(x-8,y-8,x+8,y+8,outline='#ffffff',tags='game_combat')
        c.addtag_withtag('map_world','game_combat')
        c.tag_raise('game_bombs')

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

    def draw_movement(self):
        c=self.canvas
        if isinstance(self.selected,Aircraft):
            a=self.selected
            color=self.muted_map_color('#ffffff',.4)
            if a.mode=='patrol' and a.path:
                points=a.path+[a.path[0]]
                c.create_line(*[n for p in points for n in self.pixel(*p)],fill=color,dash=(5,4),tags='movement')
                for start,end in zip(points,points[1:]):self.draw_travel_arrow(start,end,color)
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
                for start,end in zip(points,points[1:]):self.draw_travel_arrow(start,end,color)
            for i,p in enumerate(self.pending_path):
                x,y=self.pixel(*p);r=6 if i==0 else 3
                c.create_oval(x-r,y-r,x+r,y+r,outline='#ffffff',tags='movement')
        elif self.movement_mode=='loiter' and self.drag and self.pointer:
            center=self.world(self.drag[0],self.drag[1]);x,y=self.pixel(*center)
            r=math.dist(center,self.pointer)*self.scale()/2
            c.create_oval(x-r,y-r,x+r,y+r,outline=self.muted_map_color('#ffffff',.4),dash=(4,3),tags='movement')

    def radar_d_points(self,x,y,angle=None):
        if angle is None:angle=self.elapsed*math.tau/6
        points=[]
        for i in range(25):
            a=angle-math.pi/2+i*math.pi/24
            points.extend((x+10*self.building_factor()*math.cos(a),y-10*self.building_factor()*math.sin(a)))
        return points

    def draw_radar(self,radar,ghost=False):
        if not ghost and self.ground_dot_required(radar):return
        x,y=self.pixel(radar.x,radar.y);c=self.canvas;f=self.building_factor()
        if f<.08:return
        color=('#6cd9af' if not self.placement_error(radar) else '#ff7777') if ghost else '#ef6262' if radar.enemy else '#6cd9af'
        if not radar.alive:color='#586070'
        if not ghost and not radar.enabled:color=self.muted_map_color(color,.75)
        c.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,dash=(4,3) if ghost else (),tags='radar_icon')
        item=c.create_polygon(self.radar_d_points(x,y,None if ghost else radar.sweep_angle),fill='',outline=color,width=2,tags='radar_sweep')
        if not ghost:self.radar_sweeps[id(radar)]=(item,x,y)
        if self.selected is radar:c.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',dash=(4,3))

    def rotate_radars(self):
        # Only the small D glyphs animate; keep the map and coverage background cached.
        dt=max(0,self.elapsed-getattr(self,'radar_last_elapsed',self.elapsed))
        self.radar_last_elapsed=self.elapsed
        for radar in [*self.radars,*self.combat.enemy_radars]:
            if radar.radar_emitting:radar.sweep_angle=(radar.sweep_angle+dt*math.tau/6)%math.tau
            entry=self.radar_sweeps.get(id(radar))
            if entry is not None:
                item,x,y=entry
                self.canvas.coords(item,*self.radar_d_points(x,y,radar.sweep_angle))

    def sam_e_points(self,sam,x,y):
        f=self.building_factor()*.8;angle=sam.heading
        points=[]
        # One connected stroke forms the E, including its central arm.
        for px,py in ((7,10),(-7,10),(-7,10/3),(7,10/3),(-7,10/3),(-7,-10/3),(7,-10/3),(-7,-10/3),(-7,-10),(7,-10)):
            points.extend((x+f*(px*math.cos(angle)-py*math.sin(angle)),
                           y-f*(px*math.sin(angle)+py*math.cos(angle))))
        return points

    def draw_sam(self,sam,ghost=False):
        if not ghost and self.ground_dot_required(sam):return
        f=self.building_factor()*.8
        if f<.08:return
        x,y=self.pixel(sam.x,sam.y)
        color=(SAM_COLOR if not self.placement_error(sam) else '#ff7777') if ghost else '#ef6262' if sam.enemy else SAM_COLOR
        if not sam.alive:color='#586070'
        self.canvas.create_oval(x-15*f,y-15*f,x+15*f,y+15*f,outline=color,width=2,tags='sam_icon')
        item=self.canvas.create_line(*self.sam_e_points(sam,x,y),fill=color,width=2,tags='sam_glyph')
        if not ghost:self.sam_glyphs[id(sam)]=(item,x,y)
        if self.selected is sam:self.canvas.create_oval(x-20*f,y-20*f,x+20*f,y+20*f,outline='#69b7ff',dash=(4,3))

    def rotate_sams(self):
        dt=max(0,self.elapsed-getattr(self,'sam_last_elapsed',self.elapsed))
        self.sam_last_elapsed=self.elapsed
        for sam in [*self.sams,*self.combat.enemy_sams]:
            target=next((m.target for m in self.combat.missiles if m.owner is sam and m.target.alive),None)
            if target is not None:sam.target_heading=math.atan2(target.y-sam.y,target.x-sam.x)
            elif self.elapsed>=sam.next_look:
                sam.target_heading=self.random.uniform(-math.pi,math.pi)
                sam.next_look=self.elapsed+self.random.uniform(2,5)
            delta=(sam.target_heading-sam.heading+math.pi)%math.tau-math.pi
            sam.heading+=max(-dt*.9,min(dt*.9,delta))
            if id(sam) in self.sam_glyphs:
                item,x,y=self.sam_glyphs[id(sam)]
                self.canvas.coords(item,*self.sam_e_points(sam,x,y))

    def radar_footprints(self):
        # The airfield and visual detection areas are not radar sources.
        sources=[(r,(r.x,r.y,r.range_nm,0.,360.)) for r in self.radars if r.radar_emitting]
        sources.extend((a,(a.x,a.y,a.radar_range_nm,a.heading,a.radar_angle_deg))
                       for a in self.aircraft.values() if a.sensors_active and a.radar_range_nm and a.kind!='AWACS')
        if self.placing_radar and self.pointer:
            sources.append((None,(*self.pointer,Radar(0,0,0,long_range=self.placing_lr).range_nm,0.,360.)))
        return sources

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

    def draw_selected_friendly_coverage(self):
        c=self.canvas;c.delete('selected_unit_coverage')
        unit=self.selected
        if unit is None or not getattr(unit,'alive',False) or getattr(unit,'enemy',False):return
        circles=[];radar=None
        if isinstance(unit,Aircraft):
            if unit.kind=='AWACS':return
            circles.append((unit.visual_range_nm,'#6cd9af',(2,5)))
            if unit.radar_range_nm:radar=(unit.radar_range_nm,unit.heading,unit.radar_angle_deg)
            if unit.kind in ('Fighter','Interceptor','Bomber'):circles.append((unit.engagement_range,'#ef6262',(6,4)))
        elif isinstance(unit,Radar):radar=(unit.range_nm,0.,360.)
        elif isinstance(unit,SAMLauncher):circles.append((unit.range_nm,SAM_COLOR,()))
        elif isinstance(unit,CIWS):circles.extend(((8.,'#6cd9af',(2,5)),(unit.range_nm,CIWS_COLOR,())))
        for radius,color,dash in circles:
            x,y=self.pixel(unit.x,unit.y);r=radius*self.scale()
            c.create_oval(x-r,y-r,x+r,y+r,outline=color,dash=dash,width=1.3,tags=('selected_unit_coverage','map_world'))
        if radar:
            polygon=footprint(unit.x,unit.y,*radar)
            points=[v for point in [*polygon,polygon[0]] for v in self.pixel(*point)]
            c.create_line(*points,fill='#69b7ff',width=1.3,tags=('selected_unit_coverage','map_world'))
        c.tag_lower('selected_unit_coverage')

    def draw_radar_coverage(self,force=False):
        if not self.radar_overlay:
            self.canvas.delete('radar_coverage');self.coverage_items=[];self.selected_coverage_items=[]
            return
        sources=self.radar_footprints()
        key=tuple(spec for source,spec in sources)
        now=time.monotonic()
        # Coverage union runs at 5 Hz; aircraft, trails, and selected footprint
        # continue at 20 Hz. Reuse Canvas items instead of allocating every tick.
        if key!=self.coverage_key and (force or now-self.coverage_updated>=.2):
            self.coverage_paths=union_outline([footprint(*spec) for source,spec in sources])
            self.coverage_key=key;self.coverage_updated=now
        self.update_coverage_items(self.coverage_items,self.coverage_paths,'#6cd9af',(6,5))
        selected=[footprint(*spec) for source,spec in sources if source is self.selected and source is not None and not (isinstance(source,Aircraft) and source.kind=='AWACS')]
        enemy_selected=isinstance(self.selected,(Aircraft,Radar)) and self.selected.enemy
        if isinstance(self.selected,Aircraft) and self.selected.sensors_active and self.selected.radar_range_nm and ((self.selected.enemy and self.see_all)):
            a=self.selected;display=self.track_display(a)
            if display is not None:selected=[footprint(*display[:2],a.radar_range_nm,display[2],a.radar_angle_deg)]
        if isinstance(self.selected,Radar) and self.selected.enemy and self.selected.radar_emitting and self.see_all:
            a=self.selected;selected=[footprint(a.x,a.y,a.range_nm,0.,360.)]
        self.update_coverage_items(self.selected_coverage_items,[list(p)+[p[0]] for p in selected],
                                   '#ef6262' if enemy_selected else '#c6d0dc' if isinstance(self.selected,Aircraft) and self.selected.kind=='AWACS' else '#69b7ff',
                                   (6,5) if enemy_selected else ())

    def draw_visual_coverage(self):
        c=self.canvas
        if not self.visual_overlay:
            c.delete('visual_coverage');self.visual_coverage_items=[];return
        friendly=tuple((a.x,a.y,a.visual_range_nm) for a in self.aircraft.values() if a.alive and a.sensors_active)+tuple((c.x,c.y,8.) for c in self.ciws if c.alive)
        enemy=tuple((a.x,a.y,a.visual_range_nm) for a in self.combat.enemies if a.alive and a.sensors_active) if self.see_all else ()
        key=(friendly,enemy,self.see_all);now=time.monotonic()
        if key!=self.visual_coverage_key and (not self.playing or self.visual_coverage_key is None
            or self.see_all!=self.visual_coverage_key[2] or now-self.visual_coverage_updated>=.2):
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

    def draw_sam_coverage(self):
        enemy_selected=isinstance(self.selected,SAMLauncher) and self.selected.enemy and self.selected.alive
        if not self.sam_overlay and not enemy_selected:
            self.canvas.delete('sam_coverage');self.sam_coverage_items=[];self.selected_sam_coverage_items=[];return
        key=tuple((s.x,s.y,s.range_nm) for s in self.sams if s.alive) if self.sam_overlay else ()
        if self.placing_sam and self.pointer:key+=((*self.pointer,SAMLauncher(0,0,0,long_range=self.placing_lr).range_nm),)
        if key!=self.sam_coverage_key:
            self.sam_coverage_key=key
            self.sam_coverage_paths=union_outline([footprint(x,y,r,0.,360.) for x,y,r in key])
        self.update_coverage_items(self.sam_coverage_items,self.sam_coverage_paths,SAM_COLOR,(6,5),'sam_coverage')
        selected=[]
        if isinstance(self.selected,SAMLauncher) and self.selected.alive:
            s=self.selected;polygon=footprint(s.x,s.y,s.range_nm,0.,360.)
            selected=[list(polygon)+[polygon[0]]]
        self.update_coverage_items(self.selected_sam_coverage_items,selected,'#ef6262' if enemy_selected else SAM_COLOR,(6,4) if enemy_selected else (),'sam_coverage')

    def draw(self):
        self.draw_job=None
        c=self.canvas;c.delete('all')
        self.last_background_draw=time.monotonic()
        self.coverage_items=[];self.selected_coverage_items=[]
        self.sam_coverage_items=[];self.selected_sam_coverage_items=[]
        self.visual_coverage_items=[]
        self.radar_sweeps={};self.sam_glyphs={};self.ciws_glyphs={}
        width,height=c.winfo_width(),c.winfo_height()
        step=100 if self.view_width>400 else 50 if self.view_width>150 else 25 if self.view_width>50 else 5 if self.view_width>15 else 1
        low=self.world(0,height);high=self.world(width,0)
        for axis in (0,1):
            lo=low[axis];hi=high[axis]
            for i in range(math.ceil(lo/step),math.floor(hi/step)+1):
                v=i*step
                if axis==0:
                    px,_=self.pixel(v,0)
                    c.create_line(px,0,px,height,fill='#2c3c51')
                    c.create_text(px+3,height-10,text=f'{v:g}',anchor='w',fill=MUTED,font=('Helvetica',8))
                else:
                    _,py=self.pixel(0,v)
                    c.create_line(0,py,width,py,fill='#2c3c51')
                    c.create_text(7,py-5,text=f'{v:g}',anchor='w',fill=MUTED,font=('Helvetica',8))
        if self.placing_radar or self.placing_sam or self.placing_ciws:
            cx,cy=self.pixel(self.airfield.x,self.airfield.y);radius=BUILD_RADIUS_NM*self.scale()
            c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill=self.muted_map_color('#ffe65c',.03),outline='#ffe65c',dash=(7,5),width=1,tags='building_area')
        # The polygon is the real 1.5-NM by 400-ft footprint, in map coordinates.
        corners=[n for point in self.airfield.runway_corners() for n in self.pixel(*point)]
        c.create_polygon(corners,fill='#65758a',outline=TEXT,width=1,tags='runway')
        px,py=self.pixel(self.airfield.x,self.airfield.y)
        runway_pixels=self.airfield.runway_length*self.scale()
        if runway_pixels>=12:
            a=self.pixel(self.airfield.x,self.airfield.y-self.airfield.runway_length*.45)
            b=self.pixel(self.airfield.x,self.airfield.y+self.airfield.runway_length*.45)
            c.create_line(*a,*b,fill=TEXT,dash=(5,4),width=1,tags='runway')
        else:
            # A small symbol keeps the airfield visible at the full-map scale.
            c.create_line(px,py-5,px,py+5,fill=TEXT,width=3,tags='runway')
        tx,ty=self.tower_pixel();f=self.building_factor()
        tower_before=set(c.find_all())
        # World-sized warehouse-and-tower symbol shrinks with the map.
        c.create_rectangle(tx-24,ty-9,tx+24,ty+14,fill='#425872',outline=TEXT,tags='atc_tower')
        c.create_line(tx-24,ty-9,tx,ty-16,tx+24,ty-9,fill=TEXT,tags='atc_tower')
        c.create_rectangle(tx-17,ty+2,tx-3,ty+14,fill=PANEL,outline='#91a4bd',tags='atc_tower')
        c.create_rectangle(tx+7,ty-3,tx+15,ty+11,fill='#526b87',outline=TEXT,tags='atc_tower')
        c.create_rectangle(tx+8,ty-30,tx+14,ty+2,fill='#526b87',outline=TEXT,tags='atc_tower')
        c.create_polygon(tx+1,ty-30,tx+1,ty-41,tx+21,ty-41,tx+21,ty-30,
                         fill='#69b7ff',outline=TEXT,tags='atc_tower')
        c.create_line(tx+3,ty-35,tx+19,ty-35,fill=PANEL,width=1,tags='atc_tower')
        c.create_line(tx+11,ty-41,tx+11,ty-48,fill=TEXT,tags='atc_tower')
        if self.selected is self.airfield:
            c.create_rectangle(tx-28,ty-51,tx+28,ty+18,outline='#69b7ff',dash=(4,3),tags='atc_tower')
        for item in set(c.find_all())-tower_before:
            if f<.08 or self.ground_dot_required(self.airfield):c.delete(item)
            else:c.scale(item,tx,ty,f,f)
        self.draw_parking()
        for unit in self.ciws:self.draw_ciws(unit)
        if self.placing_ciws and self.pointer:self.draw_ciws(CIWS(0,*self.pointer),ghost=True)
        for sam in self.sams:self.draw_sam(sam)
        for radar in self.radars:self.draw_radar(radar)
        for radar in self.combat.enemy_radars:
            if self.see_all or id(radar) in self.combat.known_ground:self.draw_radar(radar)
        for sam in self.combat.enemy_sams:
            if self.see_all or id(sam) in self.combat.known_ground:self.draw_sam(sam)
        if self.placing_radar and self.pointer:self.draw_radar(Radar(0,*self.pointer,long_range=self.placing_lr),ghost=True)
        if self.placing_sam and self.pointer:self.draw_sam(SAMLauncher(0,*self.pointer,long_range=self.placing_lr),ghost=True)
        if not self.ground_dot_required(self.airfield):
            c.create_text(px+12,py-runway_pixels/2-12,text=self.airfield.name,anchor='w',fill=TEXT,font=('Helvetica',10,'bold'))
        else:c.delete('runway')
        c.create_text(width-25,16,text='N',fill='#ff5555',font=('Helvetica',10,'bold'),tags='map_hud')
        c.create_line(width-25,42,width-25,25,fill='#ff5555',width=2,arrow='last',tags='map_hud')
        c.create_text(width-8,height-12,text='NM',anchor='e',fill=MUTED,font=('Helvetica',9),tags='map_hud')
        c.addtag_withtag('map_world','all');c.dtag('map_hud','map_world')
        self.draw_radar_coverage(force=True)
        self.draw_movement();c.addtag_withtag('map_world','movement');self.render_aircraft()
        self.map_aircraft_bar.lift()
