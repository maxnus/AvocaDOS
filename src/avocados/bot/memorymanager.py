from pathlib import Path
from time import perf_counter
from typing import Optional

import numpy
from sc2.unit import Unit

from avocados import api
from avocados.combat.util import get_strength
from avocados.core.manager import BotManager
from avocados.core.scores import (ScoreEntry, killed_mineral_scores, killed_vespene_scores, lost_mineral_scores,
                                  lost_vespene_scores)
from avocados.core.timeseries import Timeseries


INITIAL_TIMESERIES_SIZE = 8192


class MemoryManager(BotManager):
    units_last_seen: dict[int, tuple[int, Unit]]
    #enemy_units: dict[int, tuple[int, Unit]]
    max_length: int
    #
    minerals: Timeseries[int]
    vespene: Timeseries[int]
    supply: Timeseries[int]
    supply_cap: Timeseries[int]
    supply_workers: Timeseries[int]
    army_strength: Timeseries[float]
    scores: dict[ScoreEntry, Timeseries[float]]
    killed_minerals: Timeseries[float]
    killed_vespene: Timeseries[float]
    lost_minerals: Timeseries[float]
    lost_vespene: Timeseries[float]
    damage_dealt: Timeseries[float]
    damage_taken: Timeseries[float]

    def __init__(self, max_length: int = 1000) -> None:
        super().__init__()
        self.max_length = max_length
        self.units_last_seen = {}
        #self.enemy_units = {}
        self.minerals = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.vespene = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply_cap = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.supply_workers = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.army_strength = Timeseries.empty(float, initial_size=INITIAL_TIMESERIES_SIZE)
        # Score
        self.scores = {score_entry: Timeseries.empty(float, initial_size=INITIAL_TIMESERIES_SIZE)
                       for score_entry in ScoreEntry}
        self.killed_minerals = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.killed_vespene = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.lost_minerals = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.lost_vespene = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.damage_taken = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)
        self.damage_dealt = Timeseries.empty(int, initial_size=INITIAL_TIMESERIES_SIZE)

    async def on_step_start(self, step: int) -> None:
        t0 = perf_counter()

        # Observations
        self.minerals.append(step, api.minerals)
        self.vespene.append(step, api.vespene)
        self.supply.append(step, int(api.supply_used))
        self.supply_cap.append(step, int(api.supply_cap))
        self.supply_workers.append(step, int(api.supply_workers))
        self.army_strength.append(step, get_strength(api.army))
        # Score
        for score_entry, series in self.scores.items():
            series.append(step, getattr(api.state.score, score_entry))
        self.killed_minerals.append(step, sum(getattr(api.state.score, score) for score in killed_mineral_scores))
        self.killed_vespene.append(step, sum(getattr(api.state.score, score) for score in killed_vespene_scores))
        self.lost_minerals.append(step, sum(getattr(api.state.score, score) for score in lost_mineral_scores))
        self.lost_vespene.append(step, sum(getattr(api.state.score, score) for score in lost_vespene_scores))
        self.damage_taken.append(step, api.state.score.total_damage_taken_life
                                 + api.state.score.total_damage_taken_shields)
        self.damage_dealt.append(step, api.state.score.total_damage_dealt_life
                                 + api.state.score.total_damage_dealt_shields)

        # Own
        for unit in api.units:
            self.units_last_seen[unit.tag] = (api.state.game_loop, unit)

        # Enemies
        # TODO: Move to botapi?
        for unit in api.enemy_units:
            prev_entry = self.units_last_seen.get(unit.tag)
            self.units_last_seen[unit.tag] = (api.state.game_loop, unit)
            if prev_entry is not None:
                assert prev_entry[0] < api.state.game_loop
                change = unit.health + unit.shield - prev_entry[1].health - prev_entry[1].shield
                if change < 0:
                    await api.on_unit_took_damage(unit, -change)
        self.timings['step'].add(t0)

    def get_last_seen(self, unit: int | Unit) -> Optional[Unit]:
        tag = unit.tag if isinstance(unit, Unit) else unit
        last_seen = self.units_last_seen.get(tag)
        return last_seen[1] if last_seen is not None else None

    def plot(self, path: Path | str) -> None:
        from matplotlib import pyplot as plt
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        plt.figure()
        time = numpy.arange(0, api.step) / 22.4
        plt.plot(time, self.supply, label='Supply')
        plt.plot(time, self.supply_cap, label='Supply Cap')
        plt.plot(time, self.supply_workers, label='Workers')
        plt.savefig(path / 'supply.png')
        plt.figure()
        plt.plot(time, self.minerals, label='Minerals')
        plt.plot(time, self.vespene, label='Vespene')
        plt.savefig(path / 'resources.png')

    def plot_score(self, path: Path | str) -> None:
        from matplotlib import pyplot as plt
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        plt.figure()
        time = numpy.arange(0, api.step + 1) / 22.4
        #        plt.plot(time, self.lost_minerals, label='Lost Minerals')
        #        plt.plot(time, self.lost_vespene, label='Lost Vespene')
        plt.plot(time, self.scores[ScoreEntry.KILLED_MINERALS_NONE], label='Killed Minerals None')
        plt.plot(time, self.scores[ScoreEntry.KILLED_MINERALS_ARMY], label='Killed Minerals Army')
        plt.plot(time, self.scores[ScoreEntry.KILLED_MINERALS_ECONOMY], label='Killed Minerals Economy')
        plt.plot(time, self.scores[ScoreEntry.KILLED_MINERALS_TECHNOLOGY], label='Killed Minerals Technology')
        plt.plot(time, self.scores[ScoreEntry.KILLED_MINERALS_UPGRADE], label='Killed Minerals Upgrade')
        #        plt.plot(time, self.killed_vespene, label='Killed Vespene')
        plt.legend()
        plt.savefig(path / 'score.png')
