#!/usr/bin/env python3
import argparse
import csv
import sys
import os

def parse_key_value(item):
    """Parse a string in the form key=value and return a tuple (key, value)."""
    if "=" not in item:
        raise argparse.ArgumentTypeError(f"Expected key=value format, got '{item}'")
    key, value = item.split("=", 1)
    return key.strip(), value.strip()

def load_csv(filename):
    """Load a CSV file and return (rows, fieldnames)."""
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
        return rows, reader.fieldnames

def save_csv(filename, fieldnames, rows):
    """Write CSV data (list of dict rows) to filename."""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def row_matches(row, conditions):
    """
    Return True if row matches all key/value conditions.
    The comparison is done as a string equality.
    """
    for key, value in conditions.items():
        if key not in row or row[key].strip() != value:
            return False
    return True

def update_rows(rows, conditions, updates):
    """
    Update rows that match the conditions with the updates.
    Returns the count of rows updated.
    """
    count = 0
    for row in rows:
        if row_matches(row, conditions):
            for key, value in updates.items():
                if key not in row:
                    print(f"Warning: Field '{key}' not found in the row; skipping update for that field.", file=sys.stderr)
                else:
                    row[key] = value
            count += 1
    return count

def print_csv(rows, fieldnames):
    """
    Print rows as CSV to stdout.
    """
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

def main():
    parser = argparse.ArgumentParser(
        description="Edit a CSV file by applying updates to rows matching query conditions. "
                    "If no --set arguments are given, the script only prints the matching rows."
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input CSV file path.")
    parser.add_argument("--output", "-o",
                        help="Output CSV file path. If not specified, input file is overwritten in update mode.")
    parser.add_argument("--query", "-q", action="append", type=parse_key_value, required=True,
                        help="Query condition in the form key=value. Can be specified multiple times.")
    parser.add_argument("--set", "-s", action="append", type=parse_key_value, required=False,
                        help="Update assignment in the form field=value. Can be specified multiple times. "
                             "If omitted, the script will only print the matching rows.")
    
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output if args.output else args.input

    # Convert list of key=value tuples into dictionaries.
    conditions = dict(args.query)
    updates = dict(args.set) if args.set else {}

    # Load CSV data.
    try:
        rows, fieldnames = load_csv(input_file)
    except Exception as e:
        print(f"Error loading CSV file '{input_file}': {e}", file=sys.stderr)
        sys.exit(1)

    # Find matching rows.
    matching_rows = [row for row in rows if row_matches(row, conditions)]
    if not matching_rows:
        print("No rows found matching the conditions:", conditions)
        sys.exit(0)

    if not updates:
        # Query-only mode: print matching rows as CSV.
        print("Matching rows:")
        print_csv(matching_rows, fieldnames)
    else:
        # Update mode: update matching rows.
        num_updated = update_rows(rows, conditions, updates)
        print(f"Updated {num_updated} matching row{'s' if num_updated != 1 else ''}.")
        print("Changed rows:")
        print_csv([row for row in rows if row_matches(row, conditions)], fieldnames)

        # Save the entire CSV file with the updated rows.
        try:
            save_csv(output_file, fieldnames, rows)
        except Exception as e:
            print(f"Error writing CSV file '{output_file}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"CSV file saved to '{output_file}'.")

if __name__ == "__main__":
    main()
