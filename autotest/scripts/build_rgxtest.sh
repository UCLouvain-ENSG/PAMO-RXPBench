#!/bin/bash
{% if platform == "host" and dpdk == "mellanox" %}
if test ! -d /opt/mellanox/dpdk; then
    echo "EXPRUN-FAILED: Could not find mellanox DPDK !"
    exit
fi
{% endif %}
kill_running_instances() {
    # Check if the application is running
    if pgrep -f regex-test > /dev/null; then
        echo "Killing running instances of the application..."
        # Forcefully terminate all instances
        sudo pkill -9 -f regex-test
        sleep 2  # Wait a bit to ensure processes are terminated
    fi
}

# Function to encapsulate the startup procedure
startup_procedure() {
    cd $EXPATH
    cp $RENDIR/meson.build $EXPATH
    cp $RENDIR/*.c $EXPATH
    cp $RENDIR/*.h $EXPATH

    rm -rf builddir
    mkdir -p builddir
    meson setup builddir -Dbuildtype=debugoptimized
    cd builddir
    ninja
}
{% if platform == "host" and dpdk == "mellanox"%}
#Build and link using mellanox's dpdk
export LD_LIBRARY_PATH=/opt/mellanox/dpdk/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
export PATH=/opt/mellanox/dpdk/bin:$PATH
export CPATH=/opt/mellanox/dpdk/include/dpdk:$CPATH
export C_INCLUDE_PATH=/opt/mellanox/dpdk/include/dpdk:$C_INCLUDE_PATH
export CPLUS_INCLUDE_PATH=/opt/mellanox/dpdk/include/dpdk:$CPLUS_INCLUDE_PATH
{% endif %}
kill_running_instances
startup_procedure
