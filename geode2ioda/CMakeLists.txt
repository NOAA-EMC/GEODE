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


find_package(Python3 3.13 REQUIRED COMPONENTS
    Interpreter
    Development.Embed
)

message(STATUS "Python3_EXECUTABLE = ${Python3_EXECUTABLE}")
message(STATUS "Python3_VERSION = ${Python3_VERSION}")
message(STATUS "Python3_INCLUDE_DIRS = ${Python3_INCLUDE_DIRS}")
message(STATUS "Python3_LIBRARIES = ${Python3_LIBRARIES}")


add_executable(test_geode_reader
    test_geode_reader.cpp
    GeodeReader.cpp
)

target_include_directories(test_geode_reader PRIVATE
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/ioda/include
    /contrib/spack-stack/spack-stack-1.9.2/envs/ue-oneapi-2024.2.1/install/oneapi/2024.2.1/eckit-1.28.3-dbuuyib/include
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/oops-install/include
)

target_link_directories(test_geode_reader PRIVATE
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/lib
    /scratch3/NCEPDEV/da/Edward.Givelberg/i2i/oops-install/lib64
)

target_link_libraries(test_geode_reader PRIVATE
    pybind11::embed
    Python3::Python
    ioda
    oops
)

set_target_properties(test_geode_reader PROPERTIES
    BUILD_RPATH
    "/scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/lib"
)
