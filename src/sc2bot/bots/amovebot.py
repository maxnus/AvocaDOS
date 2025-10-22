from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId


class AMoveBot(BotAI):

    async def on_step(self, iteration):
        for unit in self.units:
            if unit.type_id == UnitTypeId.MARINE:
                unit.attack(self.enemy_start_locations[0])
