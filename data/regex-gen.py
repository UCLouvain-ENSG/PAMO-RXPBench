import random
import string

def generate_regex_segment(config, require_non_empty=False):
    base_chars = string.ascii_lowercase + string.digits
    quantifiers = []
    char_sets = []

    if config['use_unbound_quants']:
        unbounded_quantifiers = ['+', '*'] if not require_non_empty else ['+']
    else:
        unbounded_quantifiers = []

    if config['use_bound_quants']:
        bounded_quantifiers = ['{' + str(random.randint(1, 15)) + '}', '{' + str(random.randint(1, 10)) + ',' + str(random.randint(11, 50)) + '}']
    else:
        bounded_quantifiers = []

    quantifiers.extend(unbounded_quantifiers + bounded_quantifiers)

    if config['use_sets']:
        char_sets = ['[aeiou]', '[1-3]', '[a-z]', '[A-Z]', '[0-9]', '[^0-9]', '[m-n]']

    # Choose either a base character or a character set
    ch = [base_chars] + char_sets
    segment_choice = random.choice(ch)
    segment = random.choice(segment_choice) if segment_choice == base_chars else segment_choice

    # Optionally add a quantifier, ensuring at least one non-empty match if required
    if quantifiers and (not require_non_empty or random.choice([True, False])):
        segment += random.choice(quantifiers)

    return segment

def random_valid_regex(config):
    segments = []

    # Generate the first segment that requires a non-empty match
    segments.append(generate_regex_segment(config, require_non_empty=True))

    # Define the total number of segments to generate
    num_segments = random.randint(3, 10)

    # Generate remaining segments
    for _ in range(1, num_segments):
        segments.append(generate_regex_segment(config))

    # Optionally add a group by combining two segments into one group
    if config['use_groups'] and len(segments) > 1:
        start_index = random.randint(0, len(segments) - 2)
        segments[start_index] = '(' + segments[start_index] + segments.pop(start_index + 1) + ')'

    # Construct the regex pattern
    regex = ''.join(segments)
    return regex

def generate_and_write_patterns(num_patterns, filename, config, suri_format = True):
    with open(filename, 'w') as file:
        for rule_id in range(num_patterns):
            pattern = random_valid_regex(config)
            if (suri_format):
                file.write(f"alert ip any any -> any any (msg:\"Regex sample rule {rule_id + 1}\"; content:\"{pattern}\"; sid:{rule_id + 1}; rev:1;)\n")
            else:
                file.write(pattern + '\n')

# Main function to set configurations and initiate pattern generation
def main():
    num_patterns = 1000000
    filename = 'fixed_string_patterns.rules'
    config = {
        'use_bound_quants': False,
        'use_unbound_quants': False,
        'use_sets': False,
        'use_groups': False,
    }

    # Generate and write patterns with specific features to a file
    generate_and_write_patterns(num_patterns, filename, config)

    print(f'{num_patterns} valid regex patterns have been written to {filename}')

# Execute the main function
if __name__ == "__main__":
    main()
