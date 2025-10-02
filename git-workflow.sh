#!/bin/bash

# Git Workflow Helper Script

echo "=== Git Workflow Helper ==="

# Function to work on test branch
work_on_test() {
    echo "Switching to test branch..."
    git checkout test
    echo "Ready to work on test branch!"
}

# Function to sync test with main
sync_test() {
    echo "Syncing test branch with main..."
    git checkout main
    git pull origin main
    git checkout test
    git merge main
    echo "Test branch synced with main!"
}

# Function to push changes to main after testing
push_to_main() {
    echo "Pushing tested changes to main..."
    git checkout main
    git merge test
    git push origin main
    echo "Changes pushed to main!"
}

# Function to push test branch
push_test() {
    echo "Pushing test branch..."
    git push origin test
    echo "Test branch pushed!"
}

# Menu
case "$1" in
    "test")
        work_on_test
        ;;
    "sync")
        sync_test
        ;;
    "main")
        push_to_main
        ;;
    "push-test")
        push_test
        ;;
    *)
        echo "Usage: $0 {test|sync|main|push-test}"
        echo "  test      - Switch to test branch"
        echo "  sync      - Sync test branch with main"
        echo "  main      - Push tested changes to main"
        echo "  push-test - Push test branch to origin"
        ;;
esac
