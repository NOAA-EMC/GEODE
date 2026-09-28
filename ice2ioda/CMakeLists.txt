cmake_minimum_required(VERSION 3.20)

project(ice2ioda LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

list(APPEND CMAKE_MODULE_PATH
  "${CMAKE_SOURCE_DIR}/cmake")


# External dependencies

include(FindOrFetchIcechunk)

set(ICECHUNK_SOURCE_DIR
    "${CMAKE_BINARY_DIR}/_deps/icechunk-src"
    CACHE PATH
    "Icechunk source directory")

find_or_fetch_icechunk(
  SOURCE_DIR "${ICECHUNK_SOURCE_DIR}"
  GIT_REPOSITORY "https://github.com/earth-mover/icechunk.git"
  GIT_BRANCH "main"
)

set(ICECHUNK_FFI_DIR
    "${CMAKE_SOURCE_DIR}/src/icechunk-ffi"
    CACHE PATH "Icechunk FFI source directory")

set(ICECHUNK_LINK
    "${CMAKE_SOURCE_DIR}/src/icechunk-src")

if(NOT EXISTS "${ICECHUNK_LINK}")
  execute_process(
    COMMAND ${CMAKE_COMMAND} -E create_symlink
            "${ICECHUNK_SOURCE_DIR}"
            "${ICECHUNK_LINK}"
  )
endif()


set(IODA_SOURCE_DIR "" CACHE PATH "Path to IODA source tree")
set(IODA_BUILD_DIR "" CACHE PATH "Path to IODA build tree")

if(NOT IODA_SOURCE_DIR)
  message(FATAL_ERROR "Set IODA_SOURCE_DIR")
endif()

if(NOT IODA_BUILD_DIR)
  message(FATAL_ERROR "Set IODA_BUILD_DIR")
endif()


find_library(ECKIT_LIBRARY
  NAMES eckit
  REQUIRED
)

message(STATUS "Found eckit: ${ECKIT_LIBRARY}")

# message("CMAKE_CURRENT_SOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}")

# ----------------------------------------------------------------------
# Rust Icechunk FFI
# ----------------------------------------------------------------------

add_custom_target(build_icechunk_ffi
  COMMAND cargo build --release
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/src/icechunk-ffi"
)

add_library(icechunk_ffi SHARED IMPORTED GLOBAL)

set_target_properties(icechunk_ffi PROPERTIES
  IMPORTED_LOCATION
    "${CMAKE_CURRENT_SOURCE_DIR}/src/icechunk-ffi/target/release/libicechunk_ffi.so"
)

add_dependencies(icechunk_ffi build_icechunk_ffi)

add_subdirectory(tests)
