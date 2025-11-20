import random
from typing import TYPE_CHECKING

from sc2.data import Race

from avocados.core.manager import BotManager

if TYPE_CHECKING:
    from avocados.bot.avocados import AvocaDOS


cheese_taunts = [
    "Fresh cheese, delivered to your door.",
    "Extra cheddar, no refunds.",
    "Warning: lactose intolerant players may leave early.",
    "Cheese drop inbound.",
    "Would you like some salt with that cheese?",
    "100% organic proxy goodness.",
    "From my rax to your ramp.",
    "Made with love... and no scouting.",
    "I age my cheese in hidden corners of the map.",
    "Say cheese!",
    "Cheese so strong, even observers cry.",
    "I'm not proxying — I'm delivering flavor.",
    "Handcrafted at 3 a.m. in the ladder mines.",
    "Your base, my kitchen.",
    "Fermenting victory since game start.",
    "Don't worry, it's only mildly toxic.",
    "Cheese fast, win faster.",
    "Straight from the Terran Dairy.",
    "This batch has extra rinds.",
    "Hope you brought detection for the smell.",
    "Hot cheese, straight off the proxy line.",
    "Welcome to the dairy of despair.",
    "No scouting? No problem.",
    "Some call it cheese, I call it efficiency.",
    "Cheese: the breakfast of grandmasters.",
    "Ladder ladder, who ordered cheddar?",
    "Proxy power, maximum flavor.",
    "This map pairs nicely with brie.",
    "My rax are closer than they appear.",
    "Aged in enemy territory for extra tang.",
    "Say goodbye to your natural, say hello to dairy.",
    "I'm not all-in, I'm all-dairy.",
    "Your ramp looks like a good place to age some cheese.",
    "From farm to front line in under a minute.",
    "Prepared fresh every match.",
    "Warning: contents may melt your MMR.",
    "This cheese doesn't expire, it executes.",
    "Skill issue? No, milk issue.",
    "I bring the cheese, you bring the tears.",
    "Proxy approved, ladder tested."
]

race_cheese_taunts = {
    Race.Terran: [
        "Mirror match? More like mirror dairy.",
        "Real Terrans proxy harder.",
        "My rax are closer than family.",
        "I brought the cheese, you brought the salt.",
        "SCVs love the smell of cheese in the morning.",
        "Your wall is cute. Mine is forward.",
        "Factory tech is for lactose-free players.",
        "No tanks, just thanks.",
        "You build reapers, I build believers.",
        "Cheese: the true Terran tradition.",
        "Two rax? I raise you four.",
        "Your orbital can't scan out this aroma.",
        "No medivacs needed when victory is this fresh.",
        "Who needs upgrades when you have cheddar?",
        "I learned this recipe from Tychus himself.",
        "Proxying since before it was meta.",
        "We both build rax, but mine have flavor.",
        "Early aggression, extra seasoning.",
        "Terran on Terran, dairy on dairy.",
        "May the best cheeser win.",
    ],
    Race.Zerg: [
        "Zerg detected. Preparing pest control cheese.",
        "Hope your creep can handle dairy.",
        "This cheese spreads faster than your creep.",
        "No spores? No problem.",
        "Banelings pop nicely with cheddar.",
        "Extra rinds for extra lings.",
        "My marines love roasted overlord.",
        "Cheese so strong it melts through carapace.",
        "You bring zerglings, I bring lactose.",
        "Creep tumors won't save you from this aroma.",
        "The only infestation here is my barracks.",
        "Spawning pool smells like defeat.",
        "Queens can't transfuse flavor.",
        "One hatch, one batch of cheese.",
        "Sorry, lair tech can't neutralize dairy.",
        "You spread creep, I spread cheese.",
        "Zerg evolution: lactose intolerance unlocked.",
        "Hot and ready before your spire.",
        "Hope your overlords packed snacks.",
        "Fresh cheese, now with anti-zerg enzymes.",
    ],
    Race.Protoss: [
        "Ah, Protoss — the fine wine to my cheese.",
        "Chrono boost won't age this faster.",
        "Photon cannons fear dairy.",
        "Warp gates? More like snack gates.",
        "Even pylons can't power through this smell.",
        "Your wall looks tasty.",
        "I deliver cheese faster than your warp-ins.",
        "Stalkers? Meet marines with flavor.",
        "This proxy is built to melt shields.",
        "Protoss tears pair well with cheddar.",
        "Your probes look hungry for lactose.",
        "Force fields won't stop the flavor flood.",
        "You may have psionics, I have parmesan.",
        "No observer can un-smell this cheese.",
        "Cheese so potent it bypasses shields.",
        "Recall won't save your taste buds.",
        "You can warp, but you can't hide from dairy.",
        "Made fresh while your core spins.",
        "Your nexus is my serving plate.",
        "GG stands for Grilled Gouda.",
    ]
}


class TauntManager(BotManager):
    used_taunts: set[str]
    queued: set[str]
    max_taunts: int

    def __init__(self, bot: 'AvocaDOS', *, max_taunts: int = 1) -> None:
        super().__init__(bot)
        self.used_taunts = set()
        self.queued = set()
        self.max_taunts = max_taunts

    @property
    def taunts_left(self) -> int:
        return self.max_taunts - len(self.used_taunts) - len(self.queued)

    async def on_step(self, step: int) -> None:
        while self.queued:
            taunt = self.queued.pop()
            self.logger.info("Sending taunt: {}", taunt)
            await self.api.client.chat_send(taunt, False)
            self.used_taunts.add(taunt)

    def taunt(self) -> bool:
        if self.taunts_left <= 0:
            return False
        if self.api.enemy_race == Race.Random or random.random() < 0.66:
            taunts = cheese_taunts
        else:
            taunts = race_cheese_taunts[self.api.enemy_race]
        taunt = random.choice(taunts)
        self.queued.add(taunt)
        return True
