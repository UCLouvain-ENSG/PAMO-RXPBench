#!/bin/bash
# Define a list of directories to ignore
ignore_dirs=(".git" "data" "doca") # Replace dir1, dir2, dir3 with your directories

# Construct the find command to exclude the ignored directories
find_cmd="find ."
for dir in "${ignore_dirs[@]}"; do
    find_cmd="$find_cmd -path ./$dir -prune -o"
done
find_cmd="$find_cmd -type f \( -iname \*.c -o -iname \*.h -o -iname \*.cpp -o -iname \*.hh -o -iname \*.cxx -o -iname \*.hxx \) -exec clang-format -i {} +"

# Execute the constructed find command
eval $find_cmd