"""
Activity classifier for smart context injection.

Fast keyword-based classification to determine which context fragment
to inject into the system prompt. This allows the LLM to have domain-specific
knowledge without loading everything into every request.

The classification is intentionally simple and fast (<1ms). The goal is to
give the LLM relevant context, not to perfectly categorize every request.
"""

import re
from typing import Optional, List
from pathlib import Path


# Activity domains with keywords that trigger them
# Order matters - more specific matches should come first within each domain
ACTIVITY_DOMAINS = {
    "skilling": [
        "fish", "fishing", "shrimp", "lobster", "net",
        "mine", "mining", "ore", "rock", "pickaxe",
        "chop", "woodcut", "tree", "log", "axe",
        "fletch", "fletching", "bow", "arrow",
        "train fishing", "train mining", "train woodcutting",
        "start fishing", "start mining", "start woodcutting",
    ],
    "combat": [
        "kill", "attack", "fight", "grind", "train combat",
        "combat style", "switch style", "aggressive", "accurate", "defensive",
        "monster", "npc", "mob",
        "giant frog", "cow", "chicken", "goblin",
        "hill giant", "moss giant", "lesser demon",
        "train attack", "train strength", "train defence",
    ],
    "navigation": [
        "go to", "walk to", "travel to", "run to",
        "teleport", "home teleport",
        "go north", "go south", "go east", "go west",
        "where is", "how do i get to", "location of",
        "draynor", "lumbridge", "varrock", "falador", "al kharid",
        # Note: "ge" and "grand exchange" are in grand_exchange domain
        # Use "go to ge" for navigation
    ],
    "banking": [
        "bank", "deposit", "withdraw",
        "store", "save my items",
        "empty inventory", "clear inventory",
        "get from bank", "put in bank",
    ],
    "interaction": [
        "pick up", "take", "grab",
        "talk to", "speak to", "chat with",
        "open door", "close door", "use door",
        "climb", "ladder", "stairs",
        "use item", "use on",
    ],
    "quests": [
        "quest", "dialogue", "talk through", "quest guide",
        "cook's assistant", "sheep shearer", "romeo", "juliet",
        "restless ghost", "imp catcher", "vampire slayer",
        "start quest", "finish quest", "complete quest",
    ],
    "inventory": [
        "drop", "drop all", "drop item",
        "equip", "wear", "wield",
        "inventory full", "make space",
        "use item on",
    ],
    "magic": [
        "cast", "spell", "magic", "rune", "runes",
        "teleport", "telegrab", "alch", "alchemy",
        "wind strike", "fire strike", "earth strike", "water strike",
    ],
    "cooking": [
        "cook", "cooking", "raw food", "burnt",
        "range", "fire", "cook all",
    ],
    "prayer": [
        "pray", "prayer", "bury", "bones",
        "altar", "prayer points",
    ],
    "smithing": [
        "smith", "smithing", "smelt", "smelting",
        "furnace", "anvil", "bar", "ore",
        "bronze bar", "iron bar", "steel bar",
    ],
    "grand_exchange": [
        "ge", "grand exchange", "buy ge", "sell ge",
        "trade", "market", "price check",
    ],
    "shops": [
        "shop", "store", "buy from", "sell to",
        "shopkeeper", "general store",
    ],
    "camera": [
        "camera", "zoom", "rotate", "pitch",
        "can't see", "reset view", "top down",
    ],
}

# Multi-word keywords need special handling
MULTI_WORD_KEYWORDS = {
    "skilling": ["train fishing", "train mining", "start fishing", "start mining"],
    "combat": ["train combat", "combat style", "switch style", "giant frog", "hill giant", "train attack", "train strength"],
    "navigation": ["go to", "walk to", "travel to", "run to", "go north", "go south", "go east", "go west", "home teleport"],
    "banking": ["empty inventory", "clear inventory", "get from bank", "put in bank", "save my items"],
    "interaction": ["pick up", "talk to", "speak to", "open door", "use item", "use on"],
    "quests": ["start quest", "finish quest", "complete quest", "quest guide", "cook's assistant", "sheep shearer", "restless ghost"],
    "inventory": ["drop all", "drop item", "use item on", "inventory full", "make space"],
    "magic": ["wind strike", "fire strike", "earth strike", "water strike", "home teleport"],
    "cooking": ["raw food", "cook all"],
    "prayer": ["prayer points"],
    "smithing": ["bronze bar", "iron bar", "steel bar"],
    "grand_exchange": ["grand exchange", "buy ge", "sell ge", "price check"],
    "shops": ["buy from", "sell to", "general store"],
    "camera": ["reset view", "top down", "can't see"],
}


def classify_activity(message: str) -> Optional[str]:
    """
    Classify a user message into an activity domain.

    Returns the domain name (skilling, combat, navigation, banking, interaction)
    or None if no clear domain is detected.

    This is intentionally fast and simple - it's keyword matching, not NLP.
    The goal is to inject relevant context, not perfect classification.
    """
    message_lower = message.lower()

    # Check multi-word keywords first (they're more specific)
    for domain, keywords in MULTI_WORD_KEYWORDS.items():
        for kw in keywords:
            if kw in message_lower:
                return domain

    # Check single-word keywords
    for domain, keywords in ACTIVITY_DOMAINS.items():
        for kw in keywords:
            # Skip multi-word keywords (already checked)
            if " " in kw:
                continue
            # Use word boundary matching for single words
            if re.search(rf'\b{re.escape(kw)}\b', message_lower):
                return domain

    return None


def get_context_fragment(domain: str) -> Optional[str]:
    """
    Load the context fragment for a domain.

    Returns the markdown content or None if not found.
    """
    fragment_path = Path(__file__).parent / "context_fragments" / f"{domain}.md"

    if fragment_path.exists():
        return fragment_path.read_text()

    return None


def get_smart_context(message: str) -> Optional[str]:
    """
    Get the appropriate context fragment for a message.

    Combines classification and fragment loading into one call.
    Returns None if no domain matches or fragment not found.
    """
    domain = classify_activity(message)
    if domain:
        return get_context_fragment(domain)
    return None


def get_all_domains() -> List[str]:
    """Get list of all activity domains."""
    return list(ACTIVITY_DOMAINS.keys())


# For testing
if __name__ == "__main__":
    test_messages = [
        "Start fishing raw shrimps",
        "Kill 100 giant frogs",
        "Go to Draynor bank",
        "Deposit all my items",
        "Pick up the fishing net",
        "What's my status?",  # Should return None
        "Help me",  # Should return None
        "Switch combat style to aggressive",
        "Train strength at giant frogs",
    ]

    print("Activity Classification Tests:")
    print("=" * 50)
    for msg in test_messages:
        domain = classify_activity(msg)
        print(f"  '{msg[:40]:<40}' -> {domain or 'None'}")
