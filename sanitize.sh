build_dir="sanitizedbuild"
rm -rf $build_dir
mkdir $build_dir
meson setup $build_dir -Dbuildtype=debug -Dc_args="-fanalyzer -fsanitize=address -fno-omit-frame-pointer -static-libasan" -Dc_link_args="-fsanitize=address"
cppcheck_includes="-I/opt/mellanox/dpdk/include/dpdk -I/opt/mellanox/dpdk/include/dpdk/../aarch64-linux-gnu/dpdk -I/opt/mellanox/dpdk/include/dpdk -I/usr/include/libnl3"
cppcheck_checks="warning,performance"
cppcheck_flist="regex-test.c helpers.c"
cppcheck --enable=$cppcheck_checks --force --language=c $cppcheck_includes $cppcheck_flist
cd $build_dir
ninja
#TODO Add a linting step
sudo ./regex-test -l 0,1,2,3 -a 0000:03:00.0,class=eth:regex,representor=[0,65535] --log-level=info -- --rgx_rules_path ../data/rgxdb.rof2 --hs_enabled 0 --rgx_enabled 0 & sleep 3
sudo pkill regex-test
sleep 1
stty echo  