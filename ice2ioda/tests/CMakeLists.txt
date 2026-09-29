set(TEST_INCLUDE_DIRS
  "${IODA_SOURCE_DIR}/src/engines/ioda/include"
  "${IODA_SOURCE_DIR}/src/engines/ioda/src"
  "${IODA_BUILD_DIR}/include"
)

set(TEST_LINK_DIRS
  "${IODA_BUILD_DIR}/lib"
  "${CMAKE_SOURCE_DIR}/src/icechunk-ffi/target/release"
)

function(add_icechunk_test TARGET SOURCE)
  add_executable(${TARGET} ${SOURCE})

  target_include_directories(${TARGET} PRIVATE
    ${TEST_INCLUDE_DIRS}
  )

  target_link_directories(${TARGET} PRIVATE
    ${TEST_LINK_DIRS}
  )

  target_link_libraries(${TARGET} PRIVATE
    ioda_engines
    icechunk_ffi
    ${ECKIT_LIBRARY}
  )

  add_dependencies(${TARGET} icechunk_ffi)

  set_target_properties(${TARGET} PROPERTIES
    BUILD_RPATH
      "${IODA_BUILD_DIR}/lib;${CMAKE_SOURCE_DIR}/src/icechunk-ffi/target/release"
  )
endfunction()

add_icechunk_test(test_discovery test_discovery.cpp)
add_icechunk_test(test_argo test_argo.cpp)

add_icechunk_test(test_cris_open test_cris_open.cpp)
add_icechunk_test(test_read_f32 test_read_f32.cpp)
add_icechunk_test(test_read_f64 test_read_f64.cpp)
# add_icechunk_test(test_read_i32 test_read_i32.cpp)

add_icechunk_test(test_ioda_read test_ioda_read.cpp)
