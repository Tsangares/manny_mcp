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
    "lumbridge_chickens": {"x": 3235, "y": 3295, "plane": 0, "aliases": ["chickens", "chicken coop"]},
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
