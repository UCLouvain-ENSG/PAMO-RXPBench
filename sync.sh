#!/bin/bash

# Define the local directory to monitor and the remote directory to sync with
LOCAL_DIR="../surexcata"
REMOTE_DIR="dormeur:~/"



# Function to execute rsync
sync_directories() {
    echo "Formatting step"
    ./format.sh
    echo "Changes detected, starting rsyhnc..."
    rsync -vzr --progress --exclude .git "$LOCAL_DIR" "$REMOTE_DIR"
    echo "Synchronization complete."
}
sync_directories
# Monitor the local directory for changes using gio
echo "Monitoring $LOCAL_DIR for changes. Press [CTRL+C] to stop..."
while true; do
    inotifywait -e modify,create,delete,move -r "$LOCAL_DIR"
    # Call the sync function on any detected change

    sync_directories
done




