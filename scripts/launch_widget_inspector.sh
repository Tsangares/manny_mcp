#!/bin/bash
#
# Launch External Widget Inspector
#
# Runs on display :0 (main laptop) to inspect widgets from RuneLite on :2
#
# Prerequisites:
# 1. Build the manny plugin first: cd /home/wil/Desktop/manny && mvn compile
# 2. RuneLite should be running on :2 with the manny plugin loaded
# 3. Trigger a widget scan: send_command("SCAN_WIDGETS --tree")
#

set -e

# Run on main laptop display
export DISPLAY=:0

# Find gson jar (needed for JSON parsing)
GSON_JAR=$(find ~/.m2/repository/com/google/code/gson/gson -name "gson-*.jar" | head -1)

if [ -z "$GSON_JAR" ]; then
    echo "Error: Could not find Gson JAR in Maven repository"
    echo "Try: mvn dependency:resolve"
    exit 1
fi

# Manny plugin classes are built as part of RuneLite
MANNY_CLASSES="/home/wil/Desktop/runelite/runelite-client/target/classes"

if [ ! -d "$MANNY_CLASSES" ]; then
    echo "Error: RuneLite not compiled"
    echo "Run the MCP build_plugin tool or: cd /home/wil/Desktop/runelite && mvn compile -pl runelite-client -am"
    exit 1
fi

# Check if widget file exists
if [ ! -f "/tmp/manny_widgets.json" ]; then
    echo "Warning: /tmp/manny_widgets.json not found"
    echo "The inspector will start but you'll need to trigger a scan:"
    echo "  send_command('SCAN_WIDGETS --tree')"
    echo ""
fi

echo "Starting External Widget Inspector on display :0"
echo "Classpath: $MANNY_CLASSES:$GSON_JAR"
echo ""

# Run the inspector
java -cp "$MANNY_CLASSES:$GSON_JAR" \
    net.runelite.client.plugins.manny.tools.ExternalWidgetInspector

