input_file = '/tmp/10k.hs'  # Name of your input file
output_file = '/tmp/10k.rxpc'  # Name of your output file

with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
    for i, line in enumerate(infile, start=1):
        # Strip newline characters from the end of the line read from file
        line = line.rstrip('\n')
        # Write formatted line to output file
        outfile.write(f"{i},/{line}/\n")

