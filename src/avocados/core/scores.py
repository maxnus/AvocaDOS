from enum import StrEnum


class ScoreEntry(StrEnum):
    SCORE_TYPE                        = "score_type"
    SCORE                             = "score"
    IDLE_PRODUCTION_TIME              = "idle_production_time"
    IDLE_WORKER_TIME                  = "idle_worker_time"
    TOTAL_VALUE_UNITS                 = "total_value_units"
    TOTAL_VALUE_STRUCTURES            = "total_value_structures"
    KILLED_VALUE_UNITS                = "killed_value_units"
    KILLED_VALUE_STRUCTURES           = "killed_value_structures"
    COLLECTED_MINERALS                = "collected_minerals"
    COLLECTED_VESPENE                 = "collected_vespene"
    COLLECTION_RATE_MINERALS          = "collection_rate_minerals"
    COLLECTION_RATE_VESPENE           = "collection_rate_vespene"
    SPENT_MINERALS                    = "spent_minerals"
    SPENT_VESPENE                     = "spent_vespene"
    FOOD_USED_NONE                    = "food_used_none"
    FOOD_USED_ARMY                    = "food_used_army"
    FOOD_USED_ECONOMY                 = "food_used_economy"
    FOOD_USED_TECHNOLOGY              = "food_used_technology"
    FOOD_USED_UPGRADE                 = "food_used_upgrade"
    KILLED_MINERALS_NONE              = "killed_minerals_none"
    KILLED_MINERALS_ARMY              = "killed_minerals_army"
    KILLED_MINERALS_ECONOMY           = "killed_minerals_economy"
    KILLED_MINERALS_TECHNOLOGY        = "killed_minerals_technology"
    KILLED_MINERALS_UPGRADE           = "killed_minerals_upgrade"
    KILLED_VESPENE_NONE               = "killed_vespene_none"
    KILLED_VESPENE_ARMY               = "killed_vespene_army"
    KILLED_VESPENE_ECONOMY            = "killed_vespene_economy"
    KILLED_VESPENE_TECHNOLOGY         = "killed_vespene_technology"
    KILLED_VESPENE_UPGRADE            = "killed_vespene_upgrade"
    LOST_MINERALS_NONE                = "lost_minerals_none"
    LOST_MINERALS_ARMY                = "lost_minerals_army"
    LOST_MINERALS_ECONOMY             = "lost_minerals_economy"
    LOST_MINERALS_TECHNOLOGY          = "lost_minerals_technology"
    LOST_MINERALS_UPGRADE             = "lost_minerals_upgrade"
    LOST_VESPENE_NONE                 = "lost_vespene_none"
    LOST_VESPENE_ARMY                 = "lost_vespene_army"
    LOST_VESPENE_ECONOMY              = "lost_vespene_economy"
    LOST_VESPENE_TECHNOLOGY           = "lost_vespene_technology"
    LOST_VESPENE_UPGRADE              = "lost_vespene_upgrade"
    FRIENDLY_FIRE_MINERALS_NONE       = "friendly_fire_minerals_none"
    FRIENDLY_FIRE_MINERALS_ARMY       = "friendly_fire_minerals_army"
    FRIENDLY_FIRE_MINERALS_ECONOMY    = "friendly_fire_minerals_economy"
    FRIENDLY_FIRE_MINERALS_TECHNOLOGY = "friendly_fire_minerals_technology"
    FRIENDLY_FIRE_MINERALS_UPGRADE    = "friendly_fire_minerals_upgrade"
    FRIENDLY_FIRE_VESPENE_NONE        = "friendly_fire_vespene_none"
    FRIENDLY_FIRE_VESPENE_ARMY        = "friendly_fire_vespene_army"
    FRIENDLY_FIRE_VESPENE_ECONOMY     = "friendly_fire_vespene_economy"
    FRIENDLY_FIRE_VESPENE_TECHNOLOGY  = "friendly_fire_vespene_technology"
    FRIENDLY_FIRE_VESPENE_UPGRADE     = "friendly_fire_vespene_upgrade"
    USED_MINERALS_NONE                = "used_minerals_none"
    USED_MINERALS_ARMY                = "used_minerals_army"
    USED_MINERALS_ECONOMY             = "used_minerals_economy"
    USED_MINERALS_TECHNOLOGY          = "used_minerals_technology"
    USED_MINERALS_UPGRADE             = "used_minerals_upgrade"
    USED_VESPENE_NONE                 = "used_vespene_none"
    USED_VESPENE_ARMY                 = "used_vespene_army"
    USED_VESPENE_ECONOMY              = "used_vespene_economy"
    USED_VESPENE_TECHNOLOGY           = "used_vespene_technology"
    USED_VESPENE_UPGRADE              = "used_vespene_upgrade"
    TOTAL_USED_MINERALS_NONE          = "total_used_minerals_none"
    TOTAL_USED_MINERALS_ARMY          = "total_used_minerals_army"
    TOTAL_USED_MINERALS_ECONOMY       = "total_used_minerals_economy"
    TOTAL_USED_MINERALS_TECHNOLOGY    = "total_used_minerals_technology"
    TOTAL_USED_MINERALS_UPGRADE       = "total_used_minerals_upgrade"
    TOTAL_USED_VESPENE_NONE           = "total_used_vespene_none"
    TOTAL_USED_VESPENE_ARMY           = "total_used_vespene_army"
    TOTAL_USED_VESPENE_ECONOMY        = "total_used_vespene_economy"
    TOTAL_USED_VESPENE_TECHNOLOGY     = "total_used_vespene_technology"
    TOTAL_USED_VESPENE_UPGRADE        = "total_used_vespene_upgrade"
    TOTAL_DAMAGE_DEALT_LIFE           = "total_damage_dealt_life"
    TOTAL_DAMAGE_DEALT_SHIELDS        = "total_damage_dealt_shields"
    TOTAL_DAMAGE_DEALT_ENERGY         = "total_damage_dealt_energy"
    TOTAL_DAMAGE_TAKEN_LIFE           = "total_damage_taken_life"
    TOTAL_DAMAGE_TAKEN_SHIELDS        = "total_damage_taken_shields"
    TOTAL_DAMAGE_TAKEN_ENERGY         = "total_damage_taken_energy"
    TOTAL_HEALED_LIFE                 = "total_healed_life"
    TOTAL_HEALED_SHIELDS              = "total_healed_shields"
    TOTAL_HEALED_ENERGY               = "total_healed_energy"
    CURRENT_APM                       = "current_apm"
    CURRENT_EFFECTIVE_APM             = "current_effective_apm"


killed_mineral_scores = {
    ScoreEntry.KILLED_MINERALS_NONE,
    ScoreEntry.KILLED_MINERALS_ARMY,
    ScoreEntry.KILLED_MINERALS_ECONOMY,
    ScoreEntry.KILLED_MINERALS_TECHNOLOGY,
    ScoreEntry.KILLED_MINERALS_UPGRADE,
}


killed_vespene_scores = {
    ScoreEntry.KILLED_VESPENE_NONE,
    ScoreEntry.KILLED_VESPENE_ARMY,
    ScoreEntry.KILLED_VESPENE_ECONOMY,
    ScoreEntry.KILLED_VESPENE_TECHNOLOGY,
    ScoreEntry.KILLED_VESPENE_UPGRADE,
}


lost_mineral_scores = {
    ScoreEntry.LOST_MINERALS_NONE,
    ScoreEntry.LOST_MINERALS_ARMY,
    ScoreEntry.LOST_MINERALS_ECONOMY,
    ScoreEntry.LOST_MINERALS_TECHNOLOGY,
    ScoreEntry.LOST_MINERALS_UPGRADE,
}


lost_vespene_scores = {
    ScoreEntry.LOST_VESPENE_NONE,
    ScoreEntry.LOST_VESPENE_ARMY,
    ScoreEntry.LOST_VESPENE_ECONOMY,
    ScoreEntry.LOST_VESPENE_TECHNOLOGY,
    ScoreEntry.LOST_VESPENE_UPGRADE,
}
