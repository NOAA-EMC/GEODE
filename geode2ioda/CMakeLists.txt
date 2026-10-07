cmake_minimum_required(VERSION 3.20)
project(geode_osdf LANGUAGES CXX)

find_package(Python3 3.13 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(geode_osdf pybind_osdf.cpp)

target_include_directories(geode_osdf PRIVATE
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/ioda/include
    /contrib/spack-stack/spack-stack-1.9.2/envs/ue-oneapi-2024.2.1/install/oneapi/2024.2.1/eckit-1.28.3-dbuuyib/include
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/oops-install/include
)

target_link_directories(geode_osdf PRIVATE
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/lib
)

target_link_libraries(geode_osdf PRIVATE ioda)

set_target_properties(geode_osdf PROPERTIES
    BUILD_RPATH
    "/scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/lib"
)
