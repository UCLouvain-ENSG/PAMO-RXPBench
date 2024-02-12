#!/bin/bash

set -xe

rm -rf /tmp/regex-test/
mkdir -p /tmp/regex-test/
rxpc -V bf2 -f ./regex.rules -p 0.01 -o /tmp/regex-test/rules
