"""
OSRS location database for the Discord bot.
Maps common location names/aliases to coordinates.
"""
from typing import Optional, Dict, List, Tuple
import re

# Location database: name -> (x, y, plane, aliases)
# Coordinates are walkable tiles, not centers of areas
LOCATIONS: Dict[str, Dict] = {
    # Lumbridge
    "lumbridge": {"x": 3222, "y": 3218, "plane": 0, "aliases": ["lumb", "lumby"]},
    "lumbridge_castle": {"x": 3222, "y": 3218, "plane": 0, "aliases": ["lumbridge castle", "lumb castle"]},
    "lumbridge_swamp": {"x": 3197, "y": 3169, "plane": 0, "aliases": ["lumb swamp", "swamp"]},
    "lumbridge_cows": {"x": 3253, "y": 3270, "plane": 0, "aliases": ["cows", "cow field", "lumbridge cows"]},
    "lumbridge_goblins": {"x": 3244, "y": 3245, "plane": 0, "aliases": ["goblins"]},
    "lumbridge_chickens": {"x": 3180, "y": 3288, "plane": 0, "aliases": ["chickens", "chicken coop"]},
    "lumbridge_bank": {"x": 3208, "y": 3220, "plane": 2, "aliases": ["lumb bank"]},
    "lumbridge_furnace": {"x": 3226, "y": 3256, "plane": 0, "aliases": []},

    # Draynor
    "draynor": {"x": 3093, "y": 3244, "plane": 0, "aliases": ["draynor village"]},
    "draynor_bank": {"x": 3092, "y": 3245, "plane": 0, "aliases": []},
    "draynor_fishing": {"x": 3087, "y": 3228, "plane": 0, "aliases": ["draynor fish", "shrimp spot", "net fishing"]},
    "draynor_willows": {"x": 3087, "y": 3235, "plane": 0, "aliases": ["willows", "willow trees"]},
    "draynor_manor": {"x": 3109, "y": 3350, "plane": 0, "aliases": ["manor"]},

    # Varrock
    "varrock": {"x": 3213, "y": 3428, "plane": 0, "aliases": ["varrock center", "varrock square"]},
    "varrock_bank_west": {"x": 3185, "y": 3436, "plane": 0, "aliases": ["varrock west bank", "vwest bank"]},
    "varrock_bank_east": {"x": 3253, "y": 3420, "plane": 0, "aliases": ["varrock east bank", "veast bank", "varrock bank"]},
    "varrock_ge": {"x": 3165, "y": 3487, "plane": 0, "aliases": ["ge", "grand exchange"]},
    "varrock_anvil": {"x": 3188, "y": 3425, "plane": 0, "aliases": ["anvil", "varrock smithing"]},
    "varrock_sewers": {"x": 3237, "y": 3459, "plane": 0, "aliases": ["sewers"]},
    "barbarian_village": {"x": 3082, "y": 3420, "plane": 0, "aliases": ["barb village", "barbarians"]},

    # Falador
    "falador": {"x": 2965, "y": 3380, "plane": 0, "aliases": ["fally"]},
    "falador_bank_east": {"x": 3013, "y": 3355, "plane": 0, "aliases": ["falador bank", "fally bank"]},
    "falador_bank_west": {"x": 2946, "y": 3368, "plane": 0, "aliases": ["fally west bank"]},
    "falador_mine": {"x": 3045, "y": 3348, "plane": 0, "aliases": ["mining guild entrance"]},
    "falador_park": {"x": 2994, "y": 3376, "plane": 0, "aliases": ["fally park"]},

    # Al Kharid
    "al_kharid": {"x": 3293, "y": 3174, "plane": 0, "aliases": ["alkharid", "al-kharid", "kharid"]},
    "al_kharid_bank": {"x": 3269, "y": 3167, "plane": 0, "aliases": ["alkharid bank"]},
    "al_kharid_mine": {"x": 3300, "y": 3314, "plane": 0, "aliases": ["scorpion mine"]},
    "al_kharid_furnace": {"x": 3275, "y": 3186, "plane": 0, "aliases": ["alkharid furnace"]},

    # Edgeville
    "edgeville": {"x": 3094, "y": 3491, "plane": 0, "aliases": ["edge", "edgy"]},
    "edgeville_bank": {"x": 3094, "y": 3491, "plane": 0, "aliases": ["edge bank"]},
    "edgeville_furnace": {"x": 3109, "y": 3499, "plane": 0, "aliases": ["edge furnace"]},
    "edgeville_dungeon": {"x": 3097, "y": 3468, "plane": 0, "aliases": ["edge dungeon"]},

    # Port Sarim
    "port_sarim": {"x": 3023, "y": 3208, "plane": 0, "aliases": ["sarim"]},
    "port_sarim_docks": {"x": 3041, "y": 3193, "plane": 0, "aliases": ["docks", "boat"]},
    "port_sarim_jail": {"x": 3012, "y": 3179, "plane": 0, "aliases": ["jail"]},

    # Rimmington
    "rimmington": {"x": 2957, "y": 3214, "plane": 0, "aliases": ["rimmy"]},
    "rimmington_mine": {"x": 2977, "y": 3239, "plane": 0, "aliases": ["rimmy mine"]},

    # Wilderness (low level)
    "wilderness_ditch": {"x": 3087, "y": 3520, "plane": 0, "aliases": ["wildy ditch", "wild ditch"]},
    "chaos_temple": {"x": 3236, "y": 3635, "plane": 0, "aliases": ["wildy altar"]},

    # Skilling areas
    "fishing_guild": {"x": 2611, "y": 3393, "plane": 0, "aliases": ["fish guild"]},
    "mining_guild": {"x": 3046, "y": 9756, "plane": 0, "aliases": ["mine guild"]},
    "crafting_guild": {"x": 2933, "y": 3285, "plane": 0, "aliases": ["craft guild"]},
    "cooking_guild": {"x": 3143, "y": 3443, "plane": 0, "aliases": ["cook guild"]},

    # Combat areas
    "giant_frogs": {"x": 3197, "y": 3169, "plane": 0, "aliases": ["frogs", "frog area", "big frogs"]},
    "hill_giants": {"x": 3117, "y": 9856, "plane": 0, "aliases": ["hillies", "hill giant"]},
    "moss_giants": {"x": 3155, "y": 9904, "plane": 0, "aliases": ["mossy", "moss giant"]},
    "fire_giants": {"x": 2570, "y": 9893, "plane": 0, "aliases": ["fire giant"]},
    "lesser_demons": {"x": 2839, "y": 9558, "plane": 0, "aliases": ["lessers", "lesser demon"]},
    "rock_crabs": {"x": 2707, "y": 3713, "plane": 0, "aliases": ["crabs", "rock crab"]},
    "sand_crabs": {"x": 1750, "y": 3470, "plane": 0, "aliases": ["sandies", "sand crab"]},
    "ammonite_crabs": {"x": 3706, "y": 3880, "plane": 0, "aliases": ["ammys", "ammonite"]},

    # === NEW LOCATIONS FROM locations.json ===
    "abandoned_mine": {"x": 3441, "y": 3236, "plane": 0, "aliases": ['abandoned mine']},
    "agility_arena": {"x": 2809, "y": 3191, "plane": 0, "aliases": ['agility arena']},
    "agility_pyramid": {"x": 3364, "y": 2840, "plane": 0, "aliases": ['agility pyramid']},
    "agility_training_area": {"x": 2481, "y": 3424, "plane": 0, "aliases": ['agility training area']},
    "agility_training_area_2": {"x": 2533, "y": 3538, "plane": 0, "aliases": ['agility training area']},
    "agility_training_area_3": {"x": 2998, "y": 3952, "plane": 0, "aliases": ['agility training area']},
    "ah_za_rhoon": {"x": 2908, "y": 9336, "plane": 0, "aliases": ['ah za rhoon']},
    "ancient_cavern": {"x": 1762, "y": 5346, "plane": 0, "aliases": ['ancient cavern']},
    "ape_atoll": {"x": 2747, "y": 2751, "plane": 0, "aliases": ['ape atoll']},
    "arandar": {"x": 2342, "y": 3294, "plane": 0, "aliases": []},
    "arceuus": {"x": 1688, "y": 3745, "plane": 0, "aliases": []},
    "ardougne_sewers": {"x": 2567, "y": 9682, "plane": 0, "aliases": ['ardougne sewers']},
    "ardougne_sewers_mine": {"x": 2655, "y": 9677, "plane": 0, "aliases": ['ardougne sewers mine']},
    "ardougne_zoo": {"x": 2612, "y": 3275, "plane": 0, "aliases": ['ardougne zoo', 'zoo']},
    "asgarnian_ice_dungeon": {"x": 3038, "y": 9580, "plane": 0, "aliases": ['asgarnian ice dungeon']},
    "avatar_of_creation": {"x": 2126, "y": 2891, "plane": 0, "aliases": ['avatar of creation']},
    "avatar_of_destruction": {"x": 2286, "y": 2931, "plane": 0, "aliases": ['avatar of destruction']},
    "bandit_camp": {"x": 3037, "y": 3699, "plane": 0, "aliases": ['bandit camp']},
    "bandit_camp_2": {"x": 3171, "y": 2979, "plane": 0, "aliases": ['bandit camp']},
    "barbarian_assault": {"x": 2523, "y": 3574, "plane": 0, "aliases": ['barbarian assault']},
    "barbarian_outpost": {"x": 2552, "y": 3561, "plane": 0, "aliases": ['barb outpost', 'barbarian outpost']},
    "barrows": {"x": 3564, "y": 3288, "plane": 0, "aliases": []},
    "barrows_crypt": {"x": 3551, "y": 9695, "plane": 0, "aliases": ['barrows crypt']},
    "battlefield": {"x": 2520, "y": 3232, "plane": 0, "aliases": []},
    "battlefront": {"x": 1368, "y": 3716, "plane": 0, "aliases": []},
    "baxtorian_falls": {"x": 2513, "y": 3461, "plane": 0, "aliases": ['baxtorian falls']},
    "bear": {"x": 3285, "y": 3838, "plane": 0, "aliases": []},
    "bedabin_camp": {"x": 3169, "y": 3036, "plane": 0, "aliases": ['bedabin camp']},
    "beehives": {"x": 2759, "y": 3442, "plane": 0, "aliases": []},
    "black_knights_fortress": {"x": 3025, "y": 3514, "plane": 0, "aliases": ["black knights' fortress"]},
    "blast_mine": {"x": 1493, "y": 3848, "plane": 0, "aliases": ['blast mine']},
    "blue_base": {"x": 2125, "y": 2914, "plane": 0, "aliases": ['blue base']},
    "bone_yard": {"x": 3236, "y": 3746, "plane": 0, "aliases": ['bone yard']},
    "brimhaven": {"x": 2773, "y": 3176, "plane": 0, "aliases": ['brim']},
    "brimhaven_dungeon": {"x": 2668, "y": 9520, "plane": 0, "aliases": ['brimhaven dungeon']},
    "brine_rat_cavern": {"x": 2718, "y": 10143, "plane": 0, "aliases": ['brine rat cavern']},
    "burgh_de_rott": {"x": 3495, "y": 3218, "plane": 0, "aliases": ['burgh de rott']},
    "burthorpe": {"x": 2893, "y": 3541, "plane": 0, "aliases": ['burth']},
    "cairn_island_dungeon": {"x": 2764, "y": 9376, "plane": 0, "aliases": ['cairn island dungeon']},
    "cairn_isle": {"x": 2765, "y": 2976, "plane": 0, "aliases": ['cairn isle']},
    "camelot_castle": {"x": 2758, "y": 3507, "plane": 0, "aliases": ['camelot castle']},
    "canifis": {"x": 3495, "y": 3487, "plane": 0, "aliases": ['canafis']},
    "castle_drakan": {"x": 3554, "y": 3357, "plane": 0, "aliases": ['castle drakan']},
    "castle_wars": {"x": 2430, "y": 3104, "plane": 0, "aliases": ['castle wars', 'cw', 'cwars']},
    "catacombs_of_kourend": {"x": 1664, "y": 10046, "plane": 0, "aliases": ['catacombs', 'catacombs of kourend', 'kourend catacombs']},
    "catherby": {"x": 2821, "y": 3433, "plane": 0, "aliases": []},
    "champions_guild": {"x": 3191, "y": 3360, "plane": 0, "aliases": ["champions' guild"]},
    "chaos_druid_tower_dungeon": {"x": 2580, "y": 9743, "plane": 0, "aliases": ['chaos druid tower dungeon']},
    "chapel": {"x": 1497, "y": 3566, "plane": 0, "aliases": []},
    "charcoal_burners": {"x": 1738, "y": 3468, "plane": 0, "aliases": ['charcoal burners']},
    "chasm_of_fire": {"x": 1438, "y": 3677, "plane": 0, "aliases": ['chasm of fire']},
    "clan_wars": {"x": 3371, "y": 3162, "plane": 0, "aliases": ['clan wars']},
    "clan_wars_2": {"x": 3422, "y": 4735, "plane": 0, "aliases": ['clan wars']},
    "clocktower": {"x": 2571, "y": 3240, "plane": 0, "aliases": []},
    "clocktower_dungeon": {"x": 2590, "y": 9630, "plane": 0, "aliases": ['clocktower dungeon']},
    "coal_trucks": {"x": 2598, "y": 3489, "plane": 0, "aliases": ['coal trucks']},
    "combat_ring": {"x": 1543, "y": 3623, "plane": 0, "aliases": ['combat ring']},
    "combat_training_camp": {"x": 2515, "y": 3369, "plane": 0, "aliases": ['combat training camp']},
    "cooks_guild": {"x": 3143, "y": 3447, "plane": 0, "aliases": ["cooks' guild"]},
    "corsair_cove": {"x": 2567, "y": 2856, "plane": 0, "aliases": ['corsair cove']},
    "cosmic_entitys_plane": {"x": 2079, "y": 4828, "plane": 0, "aliases": ["cosmic entity's plane"]},
    "crabclaw_caves": {"x": 1674, "y": 9824, "plane": 0, "aliases": ['crabclaw caves']},
    "crabclaw_isle": {"x": 1759, "y": 3421, "plane": 0, "aliases": ['crabclaw isle']},
    "crandor": {"x": 2836, "y": 3271, "plane": 0, "aliases": []},
    "crandor_dungeon": {"x": 2849, "y": 9636, "plane": 0, "aliases": ['crandor dungeon']},
    "crash_island": {"x": 2914, "y": 2720, "plane": 0, "aliases": ['crash island']},
    "creature_creation": {"x": 3038, "y": 4384, "plane": 0, "aliases": ['creature creation']},
    "crombwick_manor": {"x": 3725, "y": 3358, "plane": 0, "aliases": ['crombwick manor']},
    "dark_altar": {"x": 1689, "y": 3877, "plane": 0, "aliases": ['dark altar']},
    "dark_warriors_fortress": {"x": 3029, "y": 3630, "plane": 0, "aliases": ["dark warriors' fortress"]},
    "dark_wizards_tower": {"x": 2908, "y": 3334, "plane": 0, "aliases": ["dark wizards' tower"]},
    "darkmeyer": {"x": 3624, "y": 3363, "plane": 0, "aliases": ['darky']},
    "death_plateau": {"x": 2863, "y": 3590, "plane": 0, "aliases": ['death plat', 'death plateau']},
    "deep_wilderness_dungeon": {"x": 3040, "y": 10336, "plane": 0, "aliases": ['deep wilderness dungeon']},
    "demonic_ruins": {"x": 3289, "y": 3885, "plane": 0, "aliases": ['demonic ruins']},
    "desert_mining_camp": {"x": 3288, "y": 3021, "plane": 0, "aliases": ['desert mining camp']},
    "deserted_keep": {"x": 3153, "y": 3931, "plane": 0, "aliases": ['deserted keep']},
    "digsite": {"x": 3362, "y": 3417, "plane": 0, "aliases": []},
    "distilleries": {"x": 3787, "y": 2997, "plane": 0, "aliases": []},
    "doors_of_dinh": {"x": 1630, "y": 3964, "plane": 0, "aliases": ['doors of dinh']},
    "dorgesh_kaan": {"x": 2717, "y": 5319, "plane": 0, "aliases": []},
    "dragontooth_island": {"x": 3806, "y": 3554, "plane": 0, "aliases": ['dragontooth island']},
    "draynor_sewers": {"x": 3107, "y": 9672, "plane": 0, "aliases": ['draynor sewers']},
    "draynor_village": {"x": 3105, "y": 3258, "plane": 0, "aliases": ['draynor village']},
    "druids_circle": {"x": 2925, "y": 3482, "plane": 0, "aliases": ["druids' circle"]},
    "duel_arena": {"x": 3361, "y": 3232, "plane": 0, "aliases": ['da', 'duel', 'duel arena']},
    "dwarven_mine": {"x": 3015, "y": 3445, "plane": 0, "aliases": ['dwarven mine']},
    "dwarven_mine_dungeon": {"x": 3024, "y": 9791, "plane": 0, "aliases": ['dwarven mine dungeon']},
    "eagles_peak": {"x": 2332, "y": 3486, "plane": 0, "aliases": ["eagles' peak"]},
    "east_ardougne": {"x": 2598, "y": 3295, "plane": 0, "aliases": ['ardougne', 'ardy', 'east ardougne']},
    "eastern_graveyard": {"x": 2251, "y": 2924, "plane": 0, "aliases": ['eastern graveyard']},
    "ectofuntus": {"x": 3659, "y": 3519, "plane": 0, "aliases": []},
    "elemental_workshop": {"x": 1963, "y": 5149, "plane": 0, "aliases": ['elemental workshop']},
    "elf_camp": {"x": 2196, "y": 3251, "plane": 0, "aliases": ['elf camp']},
    "enakhras_temple_bottom_floor": {"x": 3104, "y": 9312, "plane": 0, "aliases": ["enakhra's temple bottom floor"]},
    "entrana": {"x": 2843, "y": 3378, "plane": 0, "aliases": []},
    "etceteria": {"x": 2609, "y": 3874, "plane": 0, "aliases": []},
    "exam_centre": {"x": 3363, "y": 3339, "plane": 0, "aliases": ['exam centre']},
    "falador_mole_lair": {"x": 1760, "y": 5190, "plane": 0, "aliases": ['falador mole lair']},
    "falconer": {"x": 2374, "y": 3604, "plane": 0, "aliases": []},
    "farming_guild": {"x": 1248, "y": 3731, "plane": 0, "aliases": ['farming guild']},
    "feldip_hills": {"x": 2556, "y": 2982, "plane": 0, "aliases": ['feldip hills']},
    "fenkenstrains_castle": {"x": 3548, "y": 3554, "plane": 0, "aliases": ["fenkenstrain's castle"]},
    "fenkenstrains_dungeon": {"x": 3519, "y": 9952, "plane": 0, "aliases": ["fenkenstrain's dungeon"]},
    "ferox_enclave": {"x": 3141, "y": 3629, "plane": 0, "aliases": ['ferox', 'ferox enclave']},
    "fight_arena": {"x": 2592, "y": 3161, "plane": 0, "aliases": ['fight arena']},
    "fishing_hamlet": {"x": 1693, "y": 3933, "plane": 0, "aliases": ['fishing hamlet']},
    "fishing_platform": {"x": 2772, "y": 3283, "plane": 0, "aliases": ['fishing platform']},
    "flax": {"x": 2744, "y": 3443, "plane": 0, "aliases": []},
    "foodhall": {"x": 1842, "y": 3746, "plane": 0, "aliases": []},
    "forthos_dungeon": {"x": 1819, "y": 9951, "plane": 0, "aliases": ['forthos dungeon']},
    "forthos_ruin": {"x": 1674, "y": 3574, "plane": 0, "aliases": ['forthos ruin']},
    "fossil_island": {"x": 3718, "y": 3774, "plane": 0, "aliases": ['fossil', 'fossil island', 'fossils']},
    "fountain_of_rune": {"x": 3378, "y": 3891, "plane": 0, "aliases": ['fountain of rune']},
    "fremennik_isles": {"x": 2349, "y": 3880, "plane": 0, "aliases": ['fremennik isles']},
    "fremennik_province": {"x": 2666, "y": 3632, "plane": 0, "aliases": ['fremennik province']},
    "fremennik_slayer_dungeon": {"x": 2805, "y": 10001, "plane": 0, "aliases": ['fremennik slayer dungeon']},
    "frozen_waste_plateau": {"x": 2962, "y": 3917, "plane": 0, "aliases": ['frozen waste plateau']},
    "glarials_tomb": {"x": 2543, "y": 9827, "plane": 0, "aliases": ["glarial's tomb"]},
    "gnome_ball_field": {"x": 2395, "y": 3486, "plane": 0, "aliases": ['gnome ball field']},
    "goblin_cave": {"x": 2587, "y": 9830, "plane": 0, "aliases": ['goblin cave']},
    "goblin_village": {"x": 2956, "y": 3505, "plane": 0, "aliases": ['goblin village']},
    "god_wars_dungeon": {"x": 2916, "y": 3751, "plane": 0, "aliases": ['god wars', 'god wars dungeon', 'godwars', 'gwd']},
    "golden_apple_tree": {"x": 2766, "y": 3607, "plane": 0, "aliases": ['golden apple tree']},
    "grand_exchange": {"x": 3164, "y": 3481, "plane": 0, "aliases": ['grand exchange']},
    "grand_tree": {"x": 2464, "y": 3501, "plane": 0, "aliases": ['grand tree']},
    "grand_tree_tunnels": {"x": 2463, "y": 9887, "plane": 0, "aliases": ['grand tree tunnels']},
    "graveyard": {"x": 3569, "y": 3404, "plane": 0, "aliases": []},
    "graveyard_of_heroes": {"x": 1481, "y": 3558, "plane": 0, "aliases": ['graveyard of heroes']},
    "graveyard_of_shadows": {"x": 3164, "y": 3672, "plane": 0, "aliases": ['graveyard of shadows']},
    "gutanoth": {"x": 2521, "y": 3043, "plane": 0, "aliases": ["gu'tanoth"]},
    "harmony": {"x": 3801, "y": 2858, "plane": 0, "aliases": []},
    "haunted_woods": {"x": 3564, "y": 3490, "plane": 0, "aliases": ['haunted woods']},
    "hemenster": {"x": 2634, "y": 3437, "plane": 0, "aliases": []},
    "here_be_penguins": {"x": 2615, "y": 3958, "plane": 0, "aliases": ['here be penguins']},
    "heroes_guild": {"x": 2896, "y": 3510, "plane": 0, "aliases": ['heroes', 'heroes guild', "heroes' guild"]},
    "hosidius": {"x": 1746, "y": 3597, "plane": 0, "aliases": []},
    "house_on_the_hill": {"x": 3779, "y": 3873, "plane": 0, "aliases": ['house on the hill']},
    "ibans_lair_lower_level": {"x": 2335, "y": 9855, "plane": 0, "aliases": ["iban's lair lower level"]},
    "ice_mountain": {"x": 3007, "y": 3481, "plane": 0, "aliases": ['ice mountain']},
    "ice_path": {"x": 2854, "y": 3808, "plane": 0, "aliases": ['ice path']},
    "ice_queens_lair": {"x": 2865, "y": 9954, "plane": 0, "aliases": ["ice queen's lair"]},
    "iceberg": {"x": 2676, "y": 4034, "plane": 0, "aliases": []},
    "infirmary": {"x": 1519, "y": 3619, "plane": 0, "aliases": []},
    "isafdar": {"x": 2244, "y": 3180, "plane": 0, "aliases": []},
    "isle_of_souls": {"x": 2209, "y": 2875, "plane": 0, "aliases": ['isle of souls']},
    "jail": {"x": 3125, "y": 3242, "plane": 0, "aliases": []},
    "jatizso": {"x": 2391, "y": 3814, "plane": 0, "aliases": []},
    "jiggig": {"x": 2465, "y": 3045, "plane": 0, "aliases": []},
    "jiggig_dungeon_bottom_level": {"x": 2465, "y": 9441, "plane": 0, "aliases": ['jiggig dungeon (bottom level)']},
    "jiggig_dungeon_middle_level": {"x": 2465, "y": 9441, "plane": 2, "aliases": ['jiggig dungeon (middle level)']},
    "kalphite_lair": {"x": 3226, "y": 3106, "plane": 0, "aliases": ['kalphite lair']},
    "karamja": {"x": 2859, "y": 3043, "plane": 0, "aliases": ['karam']},
    "karamja_dungeon": {"x": 2840, "y": 9571, "plane": 0, "aliases": ['karamja dungeon']},
    "kebos_lowlands": {"x": 1258, "y": 3645, "plane": 0, "aliases": ['kebos lowlands']},
    "kebos_swamp": {"x": 1254, "y": 3619, "plane": 0, "aliases": ['kebos swamp']},
    "keep_le_faye": {"x": 2769, "y": 3399, "plane": 0, "aliases": ['keep le faye']},
    "keldagrim": {"x": 2855, "y": 10175, "plane": 0, "aliases": []},
    "keldagrim_entrance": {"x": 2725, "y": 3712, "plane": 0, "aliases": ['keldagrim entrance']},
    "kharazi_jungle": {"x": 2833, "y": 2922, "plane": 0, "aliases": ['kharazi jungle']},
    "kharidian_desert": {"x": 3264, "y": 2960, "plane": 0, "aliases": ['kharidian desert']},
    "kingdom_of_asgarnia": {"x": 2991, "y": 3405, "plane": 0, "aliases": ['kingdom of asgarnia']},
    "kingdom_of_great_kourend": {"x": 1604, "y": 3692, "plane": 0, "aliases": ['kingdom of great kourend']},
    "kingdom_of_kandarin": {"x": 2572, "y": 3445, "plane": 0, "aliases": ['kingdom of kandarin']},
    "kingdom_of_misthalin": {"x": 3215, "y": 3318, "plane": 0, "aliases": ['kingdom of misthalin']},
    "kourend_castle": {"x": 1624, "y": 3672, "plane": 0, "aliases": ['kourend castle']},
    "kourend_woodland": {"x": 1543, "y": 3466, "plane": 0, "aliases": ['kourend woodland']},
    "lacerta_falls": {"x": 1383, "y": 3473, "plane": 0, "aliases": ['lacerta falls']},
    "lake_molch": {"x": 1369, "y": 3650, "plane": 0, "aliases": ['lake molch']},
    "lands_end": {"x": 1509, "y": 3428, "plane": 0, "aliases": ["land's end"]},
    "last_man_standing": {"x": 3456, "y": 5824, "plane": 0, "aliases": ['last man standing']},
    "lava_dragon_isle": {"x": 3197, "y": 3825, "plane": 0, "aliases": ['lava dragon isle']},
    "lava_maze": {"x": 3075, "y": 3845, "plane": 0, "aliases": ['lava maze']},
    "lava_maze_dungeon": {"x": 3040, "y": 10272, "plane": 0, "aliases": ['lava maze dungeon']},
    "legends_guild": {"x": 2730, "y": 3377, "plane": 0, "aliases": ['legends', 'legends guild', "legends' guild"]},
    "legends_guild_dungeon": {"x": 2720, "y": 9754, "plane": 0, "aliases": ["legends' guild dungeon"]},
    "library": {"x": 1619, "y": 3821, "plane": 0, "aliases": []},
    "lighthouse": {"x": 2510, "y": 3626, "plane": 0, "aliases": []},
    "lighthouse_dungeon": {"x": 2518, "y": 10021, "plane": 0, "aliases": ['lighthouse dungeon']},
    "lithkren": {"x": 3565, "y": 4000, "plane": 0, "aliases": []},
    "lizardman_canyon": {"x": 1518, "y": 3693, "plane": 0, "aliases": ['lizardman canyon']},
    "lizardman_settlement": {"x": 1309, "y": 3540, "plane": 0, "aliases": ['lizardman settlement']},
    "lizardman_temple": {"x": 1312, "y": 10078, "plane": 0, "aliases": ['lizardman temple']},
    "lizards": {"x": 3421, "y": 3041, "plane": 0, "aliases": []},
    "lletya": {"x": 2346, "y": 3177, "plane": 0, "aliases": []},
    "lovakengj": {"x": 1503, "y": 3800, "plane": 0, "aliases": []},
    "lovakengj_assembly": {"x": 1483, "y": 3751, "plane": 0, "aliases": ['lovakengj assembly']},
    "lovakite_mine": {"x": 1426, "y": 3833, "plane": 0, "aliases": ['lovakite mine']},
    "lumber_yard": {"x": 3305, "y": 3505, "plane": 0, "aliases": ['lumber yard']},
    "lumbridge_basement": {"x": 3213, "y": 9620, "plane": 0, "aliases": ['lumbridge basement']},
    "lumbridge_swamp_caves": {"x": 3169, "y": 9571, "plane": 0, "aliases": ['lumbridge swamp caves']},
    "lunar_isle": {"x": 2130, "y": 3873, "plane": 0, "aliases": ['lunar isle']},
    "mage_arena": {"x": 3105, "y": 3932, "plane": 0, "aliases": ['mage arena']},
    "mage_training_arena": {"x": 3363, "y": 3304, "plane": 0, "aliases": ['mage training arena']},
    "mage_training_arena_rooms": {"x": 3357, "y": 9666, "plane": 0, "aliases": ['mage training arena rooms']},
    "marim": {"x": 2760, "y": 2783, "plane": 0, "aliases": []},
    "market": {"x": 3082, "y": 3246, "plane": 0, "aliases": []},
    "mausoleum": {"x": 3503, "y": 3572, "plane": 0, "aliases": []},
    "mcgrubors_wood": {"x": 2641, "y": 3480, "plane": 0, "aliases": ["mcgrubor's wood"]},
    "meiyerditch": {"x": 3618, "y": 3259, "plane": 0, "aliases": []},
    "melzars_maze": {"x": 2933, "y": 3248, "plane": 0, "aliases": ["melzar's maze"]},
    "menaphos": {"x": 3233, "y": 2780, "plane": 0, "aliases": ['menaphos']},
    "mess": {"x": 1641, "y": 3617, "plane": 0, "aliases": []},
    "miscellania": {"x": 2537, "y": 3875, "plane": 0, "aliases": []},
    "miscellania_and_etceteria_dungeon": {"x": 2558, "y": 10276, "plane": 0, "aliases": ['miscellania and etceteria dungeon']},
    "mogre_camp": {"x": 2974, "y": 9496, "plane": 1, "aliases": ['mogre camp']},
    "molch": {"x": 1313, "y": 3669, "plane": 0, "aliases": []},
    "monastery": {"x": 2602, "y": 3215, "plane": 0, "aliases": []},
    "monastery_2": {"x": 3052, "y": 3487, "plane": 0, "aliases": []},
    "mor_ul_rek": {"x": 2494, "y": 5124, "plane": 0, "aliases": ['mor ul rek']},
    "mort_myre_swamp": {"x": 3440, "y": 3380, "plane": 0, "aliases": ['mort myre swamp']},
    "mortton": {"x": 3487, "y": 3283, "plane": 0, "aliases": ["mort'ton"]},
    "morytania": {"x": 3467, "y": 3441, "plane": 0, "aliases": ['mory']},
    "mos_leharmless": {"x": 3709, "y": 3029, "plane": 0, "aliases": ['mos le', "mos le'harmless", 'pirate island']},
    "motherlode_mine": {"x": 3745, "y": 5665, "plane": 0, "aliases": ['mlm', 'motherlode', 'motherlode mine']},
    "mount_karuulm": {"x": 1311, "y": 3807, "plane": 0, "aliases": ['mount karuulm']},
    "mount_quidamortem": {"x": 1244, "y": 3558, "plane": 0, "aliases": ['mount quidamortem']},
    "mountain_camp": {"x": 2801, "y": 3670, "plane": 0, "aliases": ['mountain camp']},
    "mouse_hole": {"x": 2280, "y": 5535, "plane": 0, "aliases": ['mouse hole']},
    "mudskipper_point": {"x": 2992, "y": 3116, "plane": 0, "aliases": ['mudskipper point']},
    "musa_point": {"x": 2897, "y": 3161, "plane": 0, "aliases": ['musa point']},
    "museum_camp": {"x": 3730, "y": 3819, "plane": 0, "aliases": ['museum camp']},
    "mushroom_forest": {"x": 3688, "y": 3860, "plane": 0, "aliases": ['mushroom forest']},
    "myths_guild": {"x": 2457, "y": 2843, "plane": 0, "aliases": ["myth's guild"]},
    "myths_guild_basement": {"x": 1977, "y": 9021, "plane": 1, "aliases": ["myth's guild basement"]},
    "nardah": {"x": 3427, "y": 2903, "plane": 0, "aliases": ['nar']},
    "necromancer": {"x": 2669, "y": 3241, "plane": 0, "aliases": []},
    "necropolis": {"x": 3334, "y": 2732, "plane": 0, "aliases": []},
    "neitiznot": {"x": 2317, "y": 3818, "plane": 0, "aliases": []},
    "nightmare_zone": {"x": 2603, "y": 3115, "plane": 0, "aliases": ['nightmare zone', 'nmz']},
    "observatory": {"x": 2441, "y": 3157, "plane": 0, "aliases": []},
    "observatory_dungeon": {"x": 2334, "y": 9375, "plane": 0, "aliases": ['observatory dungeon']},
    "ogre_enclave": {"x": 2592, "y": 9444, "plane": 0, "aliases": ['ogre enclave']},
    "ottos_grotto": {"x": 2502, "y": 3488, "plane": 0, "aliases": ["otto's grotto"]},
    "ourania_cave": {"x": 3036, "y": 5610, "plane": 0, "aliases": ['ourania cave']},
    "outpost": {"x": 2441, "y": 3345, "plane": 0, "aliases": []},
    "palace": {"x": 3212, "y": 3479, "plane": 0, "aliases": []},
    "pest_control": {"x": 2656, "y": 2593, "plane": 0, "aliases": ['pc', 'pest control']},
    "pirates_cove": {"x": 2205, "y": 3817, "plane": 0, "aliases": ["pirate's cove"]},
    "pirates_hideout": {"x": 3041, "y": 3950, "plane": 0, "aliases": ["pirates' hideout"]},
    "piscatoris_fishing_colony": {"x": 2343, "y": 3690, "plane": 0, "aliases": ['piscatoris fishing colony']},
    "poision_waste": {"x": 2232, "y": 3096, "plane": 0, "aliases": ['poision waste']},
    "pollnivneach": {"x": 3352, "y": 2977, "plane": 0, "aliases": ['pollniv', 'polly']},
    "port_khazard": {"x": 2655, "y": 3185, "plane": 0, "aliases": ['port khazard']},
    "port_phasmatys": {"x": 3674, "y": 3486, "plane": 0, "aliases": ['port phasmatys']},
    "port_piscarilius": {"x": 1825, "y": 3700, "plane": 0, "aliases": ['port piscarilius']},
    "port_tyras": {"x": 2150, "y": 3122, "plane": 0, "aliases": ['port tyras']},
    "pothole_dungeon": {"x": 2845, "y": 9505, "plane": 0, "aliases": ['pothole dungeon']},
    "prifddinas": {"x": 3263, "y": 6082, "plane": 0, "aliases": ['elf city', 'prif']},
    "puro_puro": {"x": 2592, "y": 4319, "plane": 0, "aliases": []},
    "pyramid": {"x": 3233, "y": 2896, "plane": 0, "aliases": []},
    "quarry": {"x": 3172, "y": 2908, "plane": 0, "aliases": []},
    "raids": {"x": 3312, "y": 5295, "plane": 0, "aliases": ['chambers of xeric', 'cox']},
    "ranging_guild": {"x": 2666, "y": 3429, "plane": 0, "aliases": ['range guild', 'ranging guild']},
    "ratcatchers_mansion": {"x": 2847, "y": 5086, "plane": 0, "aliases": ['ratcatchers mansion']},
    "red_base": {"x": 2287, "y": 2907, "plane": 0, "aliases": ['red base']},
    "rellekka": {"x": 2668, "y": 3676, "plane": 0, "aliases": ['fremmy', 'rell']},
    "resource_area": {"x": 3185, "y": 3934, "plane": 0, "aliases": ['resource area']},
    "revenant_caves": {"x": 3211, "y": 10150, "plane": 0, "aliases": ['revenant caves']},
    "river_elid": {"x": 3372, "y": 3074, "plane": 0, "aliases": ['river elid']},
    "river_lum": {"x": 3167, "y": 3346, "plane": 0, "aliases": ['river lum']},
    "river_molch": {"x": 1255, "y": 3671, "plane": 0, "aliases": ['river molch']},
    "river_salve": {"x": 3403, "y": 3442, "plane": 0, "aliases": ['river salve']},
    "rogues_castle": {"x": 3286, "y": 3931, "plane": 0, "aliases": ["rogues' castle"]},
    "rogues_den": {"x": 3047, "y": 4976, "plane": 1, "aliases": ["rogue's den"]},
    "ruins": {"x": 2967, "y": 3695, "plane": 0, "aliases": []},
    "ruins_2": {"x": 3164, "y": 3734, "plane": 0, "aliases": []},
    "ruins_of_camdozaal": {"x": 2973, "y": 5799, "plane": 0, "aliases": ['ruins of camdozaal']},
    "ruins_of_morra": {"x": 1447, "y": 3510, "plane": 0, "aliases": ['ruins of morra']},
    "ruins_of_ullek": {"x": 3408, "y": 2830, "plane": 0, "aliases": ['ruins of ullek']},
    "ruins_of_unkah": {"x": 3171, "y": 2842, "plane": 0, "aliases": ['ruins of unkah']},
    "ruins_of_uzer": {"x": 3479, "y": 3098, "plane": 0, "aliases": ['ruins of uzer']},
    "saltpetre": {"x": 1713, "y": 3517, "plane": 0, "aliases": []},
    "scorpion_pit": {"x": 3232, "y": 3942, "plane": 0, "aliases": ['scorpion pit']},
    "sea_spirit_dock": {"x": 3131, "y": 2839, "plane": 0, "aliases": ['sea spirit dock']},
    "secret_hangar": {"x": 2391, "y": 9890, "plane": 0, "aliases": ['secret hangar']},
    "seers_village": {"x": 2701, "y": 3483, "plane": 0, "aliases": ['seers', 'seers village', "seers' village"]},
    "settlement_ruins": {"x": 1558, "y": 3891, "plane": 0, "aliases": ['settlement ruins']},
    "shadow_dungeon": {"x": 2687, "y": 5088, "plane": 0, "aliases": ['shadow dungeon']},
    "shamans": {"x": 1433, "y": 3708, "plane": 0, "aliases": []},
    "shantay_pass": {"x": 3304, "y": 3122, "plane": 0, "aliases": ['shantay pass']},
    "shayzien": {"x": 1524, "y": 3562, "plane": 0, "aliases": []},
    "shayzien_prison": {"x": 1439, "y": 9959, "plane": 0, "aliases": ['shayzien prison']},
    "shayziens_wall": {"x": 1403, "y": 3535, "plane": 0, "aliases": ["shayzien's wall"]},
    "shilo_village": {"x": 2844, "y": 2982, "plane": 0, "aliases": ['shilo', 'shilo village']},
    "ship_yard": {"x": 2987, "y": 3055, "plane": 0, "aliases": ['ship yard']},
    "sinclair_mansion": {"x": 2742, "y": 3549, "plane": 0, "aliases": ['sinclair mansion']},
    "slayer_tower": {"x": 3428, "y": 3554, "plane": 0, "aliases": ['morytania slayer', 'slayer', 'slayer tower']},
    "slepe": {"x": 3719, "y": 3328, "plane": 0, "aliases": ['slepe']},
    "smoke_dungeon": {"x": 3265, "y": 9373, "plane": 0, "aliases": ['smoke dungeon']},
    "sophanem": {"x": 3296, "y": 2780, "plane": 0, "aliases": ['soph']},
    "sophanem_slayer_dungeon_1": {"x": 3262, "y": 9245, "plane": 0, "aliases": ['sophanem slayer dungeon (1)']},
    "sophanem_slayer_dungeon_2": {"x": 3294, "y": 9246, "plane": 2, "aliases": ['sophanem slayer dungeon (2)']},
    "sorcerers_tower": {"x": 2702, "y": 3404, "plane": 0, "aliases": ["sorcerer's tower"]},
    "sorceresss_garden": {"x": 2909, "y": 5472, "plane": 0, "aliases": ["sorceress's garden"]},
    "soul_obelisk": {"x": 2206, "y": 2910, "plane": 0, "aliases": ['soul obelisk']},
    "soul_wars_arena": {"x": 2204, "y": 2934, "plane": 0, "aliases": ['soul wars arena']},
    "soul_wars_lobby": {"x": 2209, "y": 2846, "plane": 0, "aliases": ['soul wars lobby']},
    "spider": {"x": 3320, "y": 3756, "plane": 0, "aliases": []},
    "stronghold_of_security_catacomb_of_famine": {"x": 2016, "y": 5215, "plane": 0, "aliases": ['stronghold of security - catacomb of famine']},
    "stronghold_of_security_pit_of_pestilence": {"x": 2144, "y": 5280, "plane": 0, "aliases": ['stronghold of security - pit of pestilence']},
    "stronghold_of_security_sepulchre_of_death": {"x": 2333, "y": 5219, "plane": 0, "aliases": ['stronghold of security - sepulchre of death']},
    "stronghold_of_security_vault_of_war": {"x": 1884, "y": 5218, "plane": 0, "aliases": ['stronghold of security - vault of war']},
    "stronghold_slayer_cave": {"x": 2435, "y": 9806, "plane": 0, "aliases": ['stronghold slayer cave']},
    "sulphur_mine": {"x": 1447, "y": 3879, "plane": 0, "aliases": ['sulphur mine']},
    "swamp": {"x": 2418, "y": 3511, "plane": 0, "aliases": []},
    "tai_bwo_wannai": {"x": 2789, "y": 3063, "plane": 0, "aliases": ['tai bwo wannai']},
    "tar_swamp": {"x": 3679, "y": 3778, "plane": 0, "aliases": ['tar swamp']},
    "taverley": {"x": 2896, "y": 3455, "plane": 0, "aliases": ['tav']},
    "taverley_dungeon": {"x": 2886, "y": 9811, "plane": 0, "aliases": ['tav dungeon', 'taverley dungeon']},
    "temple": {"x": 3414, "y": 3487, "plane": 0, "aliases": []},
    "temple_of_ikov": {"x": 2649, "y": 9854, "plane": 0, "aliases": ['temple of ikov']},
    "temple_of_marimbo_dungeon": {"x": 2784, "y": 9184, "plane": 0, "aliases": ['temple of marimbo dungeon']},
    "the_forgotten_cemetery": {"x": 2976, "y": 3750, "plane": 0, "aliases": ['the forgotten cemetery']},
    "the_forsaken_tower": {"x": 1382, "y": 3823, "plane": 0, "aliases": ['the forsaken tower']},
    "the_hollows": {"x": 3498, "y": 3381, "plane": 0, "aliases": ['the hollows']},
    "the_inferno": {"x": 2272, "y": 5343, "plane": 0, "aliases": ['the inferno']},
    "the_node": {"x": 3105, "y": 3027, "plane": 0, "aliases": ['the node']},
    "the_warrens": {"x": 1776, "y": 10143, "plane": 0, "aliases": ['the warrens']},
    "tirannwn": {"x": 2240, "y": 3263, "plane": 0, "aliases": []},
    "tithe_farm": {"x": 1806, "y": 3507, "plane": 0, "aliases": ['tithe farm']},
    "toll_gate": {"x": 3271, "y": 3226, "plane": 0, "aliases": ['toll gate']},
    "tower_of_life": {"x": 2648, "y": 3215, "plane": 0, "aliases": ['tower of life']},
    "tower_of_magic": {"x": 1579, "y": 3818, "plane": 0, "aliases": ['tower of magic']},
    "trawler": {"x": 2683, "y": 3166, "plane": 0, "aliases": []},
    "tree_gnome_stronghold": {"x": 2430, "y": 3447, "plane": 0, "aliases": ['gnome stronghold', 'stronghold', 'tree gnome stronghold']},
    "tree_gnome_village": {"x": 2527, "y": 3166, "plane": 0, "aliases": ['gnome village', 'tree gnome village']},
    "troll_stronghold": {"x": 2832, "y": 3682, "plane": 0, "aliases": ['troll stronghold']},
    "trollheim": {"x": 2891, "y": 3676, "plane": 0, "aliases": []},
    "trollweiss_mountain": {"x": 2782, "y": 3862, "plane": 0, "aliases": ['trollweiss mountain']},
    "tutorial_island": {"x": 3101, "y": 3094, "plane": 0, "aliases": ['tutorial island']},
    "tyras_camp": {"x": 2186, "y": 3146, "plane": 0, "aliases": ['tyras camp']},
    "tzhaar_city": {"x": 2451, "y": 5146, "plane": 0, "aliases": ['tzhaar city']},
    "underground_pass": {"x": 2449, "y": 3312, "plane": 0, "aliases": ['underground pass']},
    "underground_pass_area_1": {"x": 2464, "y": 9700, "plane": 0, "aliases": ['underground pass area 1']},
    "underground_pass_area_2": {"x": 2399, "y": 9637, "plane": 0, "aliases": ['underground pass area 2']},
    "underground_pass_area_3": {"x": 2398, "y": 9710, "plane": 0, "aliases": ['underground pass area 3']},
    "ungael": {"x": 2271, "y": 4065, "plane": 0, "aliases": []},
    "unmarked_grave": {"x": 1576, "y": 3938, "plane": 0, "aliases": ['unmarked grave']},
    "ver_sinhaza": {"x": 3662, "y": 3218, "plane": 0, "aliases": ['ver sinhaza']},
    "vinery": {"x": 1814, "y": 3544, "plane": 0, "aliases": []},
    "viyeldi_caves": {"x": 2398, "y": 4717, "plane": 0, "aliases": ['viyeldi caves']},
    "viyeldi_caves_2": {"x": 2782, "y": 9315, "plane": 0, "aliases": ['viyeldi caves (2)']},
    "void_knights_outpost": {"x": 2639, "y": 2674, "plane": 0, "aliases": ["void knights' outpost"]},
    "volcano": {"x": 3778, "y": 3778, "plane": 0, "aliases": []},
    "vultures": {"x": 3337, "y": 2868, "plane": 0, "aliases": []},
    "war_tent": {"x": 1484, "y": 3636, "plane": 0, "aliases": ['war tent']},
    "warriors_guild": {"x": 2855, "y": 3543, "plane": 0, "aliases": ['warrior guild', 'warriors guild', "warriors' guild"]},
    "warriors_guild_basement": {"x": 2920, "y": 9964, "plane": 0, "aliases": ["warriors' guild basement"]},
    "waterbirth_dungeon_1": {"x": 2495, "y": 10144, "plane": 0, "aliases": ['waterbirth dungeon (1)']},
    "waterbirth_dungeon_2": {"x": 1895, "y": 4367, "plane": 0, "aliases": ['waterbirth dungeon (2)']},
    "waterbirth_dungeon_3": {"x": 1895, "y": 4367, "plane": 1, "aliases": ['waterbirth dungeon (3)']},
    "waterbirth_dungeon_4": {"x": 1895, "y": 4367, "plane": 2, "aliases": ['waterbirth dungeon (4)']},
    "waterbirth_dungeon_5": {"x": 1895, "y": 4367, "plane": 3, "aliases": ['waterbirth dungeon (5)']},
    "waterbirth_dungeon_6": {"x": 2912, "y": 4448, "plane": 0, "aliases": ['waterbirth dungeon (6)']},
    "waterbirth_island": {"x": 2521, "y": 3757, "plane": 0, "aliases": ['waterbirth island']},
    "waterfall_dungeon": {"x": 2577, "y": 9890, "plane": 0, "aliases": ['waterfall dungeon']},
    "west_ardougne": {"x": 2524, "y": 3305, "plane": 0, "aliases": ['west ardougne', 'west ardy']},
    "western_graveyard": {"x": 2161, "y": 2898, "plane": 0, "aliases": ['western graveyard']},
    "white_knights_castle": {"x": 2969, "y": 3341, "plane": 0, "aliases": ["white knights' castle"]},
    "white_wolf_mountain": {"x": 2847, "y": 3494, "plane": 0, "aliases": ['white wolf', 'white wolf mountain', 'wwm']},
    "wilderness": {"x": 3144, "y": 3775, "plane": 0, "aliases": []},
    "wilderness_slayer_cave": {"x": 3392, "y": 10102, "plane": 0, "aliases": ['wilderness slayer cave']},
    "wintertodt": {"x": 1630, "y": 4004, "plane": 0, "aliases": ['todt', 'wt']},
    "witchaven": {"x": 2709, "y": 3289, "plane": 0, "aliases": []},
    "witchaven_dungeon": {"x": 2722, "y": 9689, "plane": 0, "aliases": ['witchaven dungeon']},
    "witchaven_dungeon_2": {"x": 2329, "y": 5097, "plane": 0, "aliases": ['witchaven dungeon (2)']},
    "wizards_guild": {"x": 2583, "y": 3078, "plane": 0, "aliases": ["wizards' guild"]},
    "wizards_tower": {"x": 3110, "y": 3157, "plane": 0, "aliases": ["wizards' tower"]},
    "woodcutting_guild": {"x": 1612, "y": 3492, "plane": 0, "aliases": ['woodcutting guild']},
    "xerics_look_out": {"x": 1590, "y": 3530, "plane": 0, "aliases": ["xeric's look out"]},
    "xerics_shrine": {"x": 1310, "y": 3619, "plane": 0, "aliases": ["xeric's shrine"]},
    "yanille": {"x": 2554, "y": 3089, "plane": 0, "aliases": ['yan']},
    "yanille_agility_dungeon": {"x": 2581, "y": 9499, "plane": 0, "aliases": ['yanille agility dungeon']},
    "yanille_agility_dungeon_2": {"x": 2580, "y": 9577, "plane": 0, "aliases": ['yanille agility dungeon (2)']},
    "zanaris": {"x": 2415, "y": 4455, "plane": 0, "aliases": []},
    "zul_andra": {"x": 2204, "y": 3064, "plane": 0, "aliases": []},
    "zulrahs_shrine": {"x": 2267, "y": 3074, "plane": 0, "aliases": ["zulrah's shrine"]},
}


def find_location(query: str) -> Optional[Dict]:
    """Find a location by name or alias.

    Returns dict with x, y, plane, name or None if not found.
    """
    query_lower = query.lower().strip()
    query_normalized = query_lower.replace("-", "_").replace(" ", "_")

    # Direct match on normalized name
    if query_normalized in LOCATIONS:
        loc = LOCATIONS[query_normalized]
        return {"name": query_normalized, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]}

    # Exact alias match (highest priority)
    for name, loc in LOCATIONS.items():
        for alias in loc["aliases"]:
            if query_lower == alias.lower():
                return {"name": name, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]}

    # Match query with spaces against name with underscores
    for name, loc in LOCATIONS.items():
        name_spaced = name.replace("_", " ")
        if query_lower == name_spaced:
            return {"name": name, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]}

    # Partial match - query contains location name or vice versa (but be careful)
    # Only match if it's a significant portion
    for name, loc in LOCATIONS.items():
        name_spaced = name.replace("_", " ")
        # Query contains the full location name
        if name_spaced in query_lower and len(name_spaced) >= 4:
            return {"name": name, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]}

    return None


def find_locations_in_text(text: str) -> List[Dict]:
    """Find all location references in a text string.

    Returns list of matched locations with their coordinates.
    Uses word boundary matching to avoid false positives.
    """
    text_lower = text.lower()
    found = []
    seen_names = set()

    def word_match(pattern: str, text: str) -> bool:
        """Check if pattern exists as a word/phrase in text."""
        # Use word boundaries to avoid partial matches
        pattern_escaped = re.escape(pattern.lower())
        return bool(re.search(r'\b' + pattern_escaped + r'\b', text))

    # Check each location and its aliases
    for name, loc in LOCATIONS.items():
        if name in seen_names:
            continue

        # Check main name (with underscores as spaces)
        name_spaced = name.replace("_", " ")
        if word_match(name_spaced, text_lower):
            found.append({"name": name, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]})
            seen_names.add(name)
            continue

        # Check aliases (must be exact word match)
        for alias in loc["aliases"]:
            if word_match(alias, text_lower):
                found.append({"name": name, "x": loc["x"], "y": loc["y"], "plane": loc["plane"]})
                seen_names.add(name)
                break

    return found


def get_goto_command(location_name: str) -> Optional[str]:
    """Get a GOTO command for a location.

    Returns command string like "GOTO 3200 3200 0" or None.
    """
    loc = find_location(location_name)
    if loc:
        return f"GOTO {loc['x']} {loc['y']} {loc['plane']}"
    return None


def list_locations(category: Optional[str] = None) -> List[str]:
    """List all known locations, optionally filtered by category prefix."""
    if category:
        return [name for name in LOCATIONS.keys() if name.startswith(category)]
    return list(LOCATIONS.keys())
