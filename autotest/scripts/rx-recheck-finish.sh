#!/bin/bash

sudo pkill regex-test
while pgrep -x regex-test > /dev/null; do sleep 1; done

echo "regex-test is really not runnig anymore"