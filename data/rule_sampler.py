#!/usr/bin/python3
import argparse
from random import seed, sample
from time import time
def write_to_file_or_print(output, message):
    """Write message to a file if output is specified, otherwise print."""
    if output:
        with open(output, 'w') as file:
            file.write(message + "\n")
    else:
        print(message)

def count_lines(file_path):
    """Count the number of lines in a file."""
    with open(file_path, 'r') as file:
        return sum(1 for _ in file)
    
def clean_commented(file_path):
    with open(file_path, 'r') as f:
        return [l.strip() for l in f.readlines() if not l.strip().startswith("#") and not l.strip() == "\n" and not len(l.strip()) == 0]
        
def preview_file(file_path, num_lines=5):
    """Print the first few lines of a file."""
    with open(file_path, 'r') as file:
        for _ in range(num_lines):
            line = file.readline()
            if not line:
                break
            print(line.strip())

def sample100(file_path):
    seed(time())
    with open(file_path, "r") as f:
        lines = [l for l in f.readlines()]
    return sample(lines, 100)

def main():
    parser = argparse.ArgumentParser(description="Process a file.")
    parser.add_argument("input_file", type=str, help="The file to process")
    parser.add_argument("--action", type=str, choices=["count", "preview", "clean", "sample100", "sample1000"], required=True,
                        help="The action to perform on the file ('count' or 'preview')")
    parser.add_argument("--output_file", type=str, help="Optional output file")
    
    args = parser.parse_args()

    if args.action == "count":
        line_count = count_lines(args.input_file)
        write_to_file_or_print(args.output_file, f"Total lines: {line_count}")
    elif args.action == "preview":
        message = "Previewing the file..."
        write_to_file_or_print(args.output_file, message)
        preview_lines = preview_file(args.input_file)
        for line in preview_lines:
            write_to_file_or_print(args.output_file, line)
    elif args.action == "clean":
        write_to_file_or_print(args.output_file, "\n".join(clean_commented(args.input_file)))
    elif args.action == "sample100":
        write_to_file_or_print(args.output_file, "\n".join(sample100(args.input_file)))


if __name__ == "__main__":
    main()