#!/bin/bash

# # Step 1: Setup
# REPO_DIR="twitch-clone"
# cd "$REPO_DIR" || exit

# Remove any existing Git history
rm -rf .git
git init
git config user.name "Prakash-sa"
git config user.email "sainiprakash525@gmail.com"

# Get non-ignored files (respects .gitignore)
FILES=($(git ls-files --others --exclude-standard))

# Start date
START_DATE="2024-04-01"
TOTAL_DAYS=30
file_count=${#FILES[@]}
files_per_day=2
commit_index=0

for ((day=0; day<TOTAL_DAYS; day++)); do
  # Calculate date string
  COMMIT_DATE=$(date -u -j -v+"$day"d -f "%Y-%m-%d" "$START_DATE" "+%Y-%m-%dT12:00:00Z" 2>/dev/null || date -d "$START_DATE +$day days" "+%Y-%m-%dT12:00:00Z")

  # Stage 1–2 files per day
  for ((i=0; i<files_per_day && commit_index<file_count; i++)); do
    FILE=${FILES[$commit_index]}
    git add "$FILE"
    GIT_AUTHOR_DATE="$COMMIT_DATE" GIT_COMMITTER_DATE="$COMMIT_DATE" git commit -m "Add $(basename "$FILE")"
    ((commit_index++))
  done

  # Break if all files are committed
  if [ $commit_index -ge $file_count ]; then
    break
  fi
done

echo "✅ Fake commit history created across $day days."