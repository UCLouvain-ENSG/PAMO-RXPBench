
#
# Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES, ALL RIGHTS RESERVED.
#
# This software product is a proprietary product of NVIDIA CORPORATION &
# AFFILIATES (the "Company") and all right, title, and interest in and to the
# software product, including all associated intellectual property rights, are
# and shall remain exclusively with the Company.
#
# This software product is governed by the End User License Agreement
# provided with the software product.
#

project('DPDK_PORT_FORWARD', 'C', 'CPP',
        license: 'Proprietary',
        default_options: ['buildtype=release'],
        meson_version: '>= 0.61.2'
)
# Comment this line to restore warnings of experimental DOCA features
add_project_arguments([#'-lssl -lcrypto',
                        '-DALLOW_EXPERIMENTAL_API', 
                        '-DALLOW_INTERNAL_API',
                        # '-DFAKE_DPDK_DESC_IP_SRC',
                        # '-DFAKE_DPDK_DESC_IP_DST',
                        # '-DFAKE_DPDK_DESC_TIMESTAMP',
                        '-DFAKE_DPDK_DESC_SIZE',
                        # '-DFAKE_DPDK_DESC_PAYLOAD',
                        #'-DFAKE_DPDK_DESC_MAC_SRC',
                        #'-DFAKE_DPDK_DESC_MAC_DST',
                        ],
                        language: ['c', 'cpp'])

add_project_link_arguments(['-lm', '-lstdc++'], language : ['c','cpp'])
dependencies = []
hw_dependencies = []

# Library used by the main() function
dependencies += dependency('libbsd')
hw_dependencies += dependency('libbsd')

#dependencies += dependency('doca')
#hw_dependencies += dependency('doca')
# Basic dependencies
#dependencies += dependency('libdpdk-fork')
dependencies += dependency('libdpdk')
hw_dependencies += dependency('libdpdk')

dependencies += dependency('libhs')
hw_dependencies += dependency('libhs')

dependencies += dependency('libcrypto')
hw_dependencies += dependency('libcrypto')

dependencies += dependency('libssl')
hw_dependencies += dependency('libssl')

# Doca dependencies for the doca_flow solution

# Dependencies for HWS only
regex_test_src = [
        'rgx_stats.c',
        'helpers.c',
        'regex-test.c',
        'util-hs.c'
]
df_inc_dirs = []

incdir = include_directories('.')
executable('regex-test', regex_test_src,
        dependencies: dependencies,
        install: false,
        include_directories: [incdir])
