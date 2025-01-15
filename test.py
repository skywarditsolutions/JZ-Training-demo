import re


raw_pattern = "\$\d+(?:\.\d{2})?"
text_to_search = "The items cost $12.99, $25, and $8.50. Some items are priced at $100.00."

print(f"regex_pattern: {raw_pattern}, text_to_search: {text_to_search}")
pattern = re.compile(raw_pattern)
matches = pattern.findall(text_to_search)
print(f"matches: {matches}")

if matches:
    print(f"Found {len(matches)} matches:")
    for i, match in enumerate(matches, 1):
        print(f"Match {i}: {match}")
else:
    print("No matches found")