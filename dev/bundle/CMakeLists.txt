cmake_minimum_required(VERSION 3.23 FATAL_ERROR)

project(geode-ijedi-bundle VERSION 0.0.1 LANGUAGES C CXX Fortran)

find_package(ecbuild 3.5 REQUIRED)
include(ecbuild_bundle)

ecbuild_bundle_initialize()

# ===============================================================================
# build just OOPS and IODA for inclusion in the GEODE container
# ===============================================================================
# ===============================================================================
# required repositories

# ===============================================================================
ecbuild_bundle( PROJECT jedicmake GIT    "https://github.com/jcsda/jedi-cmake.git"      UPDATE BRANCH develop RECURSIVE )
ecbuild_bundle( PROJECT oops      GIT    "https://github.com/JCSDA/oops.git"          UPDATE BRANCH develop )
ecbuild_bundle( PROJECT ioda      GIT    "https://github.com/JCSDA/ioda.git"          UPDATE BRANCH develop )

# ===============================================================================
# required repositories
# ===============================================================================
include(jedicmake/cmake/Functions/git_functions.cmake)

# ===============================================================================
ecbuild_bundle_finalize()
