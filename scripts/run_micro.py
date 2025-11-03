from sc2.ids.unit_typeid import UnitTypeId

from avocados import create_avocados
from game_runner import GameRunner


if __name__ == "__main__":
    #micro_scenario = {UnitTypeId.MARINE: 8}
    #micro_scenario = ({UnitTypeId.MARINE: 3}, {UnitTypeId.SIEGETANKSIEGED: 1})
    micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.SIEGETANKSIEGED: 1})
    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZEALOT: 4})
    #micro_scenario = ({UnitTypeId.MARINE: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4})
    #micro_scenario = {UnitTypeId.REAPER: 8}
    #micro_scenario = {UnitTypeId.REAPER: 1}
    #micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.MARINE: 12}
    #micro_scenario = {UnitTypeId.REAPER: 8}, {UnitTypeId.ZERGLING: 8, UnitTypeId.BANELING: 4}
    runner = GameRunner(
        bot=create_avocados(micro_scenario=micro_scenario, build=None),
        map_='micro-training-4x4',
    )
    runner.run()
