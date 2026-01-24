## Navigation Context

### GOTO Command
```
GOTO <x> <y> <plane>

Examples:
  GOTO 3200 3200 0    # Walk to Lumbridge area
  GOTO 3087 3227 0    # Draynor fishing spot
```

### Location Lookup
Always use lookup_location before GOTO to get correct coordinates:
```
Step 1: lookup_location(location="draynor fishing")
Result: {"x": 3087, "y": 3227, "plane": 0, "goto_command": "GOTO 3087 3227 0"}

Step 2: send_command(command="GOTO 3087 3227 0")
```

### Coordinate System
- **South** = Y decreases (3200 -> 3180)
- **North** = Y increases (3200 -> 3220)
- **East** = X increases (3200 -> 3220)
- **West** = X decreases (3200 -> 3180)

### Directional Movement
When user says "go south/north/etc." without coordinates:
| Request | Distance | Example |
|---------|----------|---------|
| "Go south" | 15-25 tiles | Y -= 20 |
| "Go south a bit" | 5-10 tiles | Y -= 8 |
| "Go far south" | 40-60 tiles | Y -= 50 |

### Indoor Navigation
Buildings have doors that must be opened:
1. **Scan**: get_transitions() to find doors with open/closed state
2. **Open**: INTERACT_OBJECT Large_door Open
3. **Walk**: GOTO to destination

### Common Locations
| Name | Coordinates |
|------|-------------|
| Lumbridge Castle | 3222, 3218 |
| Draynor Bank | 3093, 3244 |
| Draynor Fishing | 3087, 3227 |
| Grand Exchange | 3165, 3487 |
| Giant Frogs | 3197, 3169 |
