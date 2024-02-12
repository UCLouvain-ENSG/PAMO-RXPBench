import itertools

# Function to check if a string is in alphabetical order
def is_alphabetical(s):
    return list(s) == sorted(s)

# Initialize SID
sid = 1

desired_rules_count = 1000000

# Define output file
output_file = "prefixes_8b_1M.rules"

# Set to track unique combinations
unique_combinations = set()

# Open the output file for writing
with open(output_file, "w") as f:
    # Generate all possible 4-letter combinations
    for combination in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=8):
        combination_str = ''.join(combination)
        
        # Check if the combination is not in alphabetical order and is unique
        if not is_alphabetical(combination_str) and combination_str not in unique_combinations:
            # Add to the set of unique combinations
            unique_combinations.add(combination_str)
            
            # Write the rule to the file
            f.write(f"alert tcp any any -> any any (content:\"{combination_str}\"; sid:{sid};)\n")
            sid += 1
            
            # Stop when we have generated the desired number of rules
            if len(unique_combinations) >= desired_rules_count:
                break

print(f"Generated {desired_rules_count} rules in {output_file}")
