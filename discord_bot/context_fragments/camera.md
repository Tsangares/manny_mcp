## Camera Context

### Camera Commands

```
CAMERA_RESET              - Reset camera to default position
CAMERA_PITCH <value>      - Set camera pitch (vertical angle)
CAMERA_YAW <value>        - Set camera rotation (horizontal angle)
CAMERA_POINT_AT <x> <y>   - Point camera at coordinates
CAMERA_STABILIZE          - Reset to stable zoom and pitch (MCP tool)
```

### When to Use Camera Commands

1. **Before NPC interactions** - Ensure NPC is visible
2. **After zooming in** - NPCs can zoom camera; reset it
3. **In dungeons/buildings** - Top-down view helps navigation
4. **Before fishing/combat** - Ensure spots/monsters visible

### Camera Pitch Values

| Value | Description |
|-------|-------------|
| 128 | Level (looking straight ahead) |
| 256 | Slight top-down |
| 400 | Default top-down (good for most) |
| 512 | Maximum top-down (best for dungeons) |

### Stabilize Camera (Recommended)

```python
# Use MCP tool for reliable reset
stabilize_camera()  # Default: pitch=400, zoom=8

# Custom settings
stabilize_camera(pitch=512)  # Max top-down for caves
stabilize_camera(pitch=300, zoom_in_scrolls=10)  # Custom
```

### Common Patterns

**Before interacting with NPCs:**
```yaml
- action: CAMERA_STABILIZE
  description: "Reset camera before NPC interaction"
  delay_after_ms: 1000
- action: INTERACT_NPC
  args: "Banker Bank"
```

**In dungeons:**
```python
send_command("CAMERA_PITCH 512")  # Max top-down
```

### Camera Issues

| Problem | Solution |
|---------|----------|
| NPC not visible after fight | `CAMERA_STABILIZE` |
| Can't click fishing spot | `CAMERA_RESET` |
| Zoomed in too close | `stabilize_camera()` |
| Can't see door in building | `CAMERA_PITCH 512` |

### Routine Pattern

Many routines include camera stabilization before key interactions:
```yaml
steps:
  - id: 1
    action: CAMERA_STABILIZE
    description: "Ensure stable camera before starting"

  - id: 2
    action: FISH
    args: "lobster"
```

### Manual Camera Control

Camera can also be controlled with arrow keys, but commands are more reliable for automation.
