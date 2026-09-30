#!/usr/bin/env bash
# Convert CRLF to LF in every tracked or new (non-ignored) text file.
git ls-files -co --exclude-standard | while IFS= read -r f; do
  [ -f "$f" ] && grep -Iq $'\r' "$f" 2>/dev/null && sed -i 's/\r$//' "$f" && echo "normalized $f"
done
exit 0
