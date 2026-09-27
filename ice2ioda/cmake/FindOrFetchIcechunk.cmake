function(find_or_fetch_icechunk)

  set(options)
  set(oneValueArgs SOURCE_DIR GIT_REPOSITORY GIT_BRANCH)
  cmake_parse_arguments(ICE
    "${options}"
    "${oneValueArgs}"
    ""
    ${ARGN}
  )

  if(NOT ICE_SOURCE_DIR)
    message(FATAL_ERROR
      "find_or_fetch_icechunk: SOURCE_DIR is required")
  endif()

  # Use an existing checkout if present.
  if(EXISTS "${ICE_SOURCE_DIR}/icechunk/Cargo.toml")
    message(STATUS
      "Using existing Icechunk source: ${ICE_SOURCE_DIR}")

    set(ICECHUNK_SOURCE_DIR
        "${ICE_SOURCE_DIR}"
        PARENT_SCOPE)
    return()
  endif()

  # Otherwise clone it.
  message(STATUS
    "Icechunk source not found: ${ICE_SOURCE_DIR}")
  message(STATUS
    "Fetching Icechunk from ${ICE_GIT_REPOSITORY}")

  get_filename_component(parent_dir
    "${ICE_SOURCE_DIR}" DIRECTORY)

  file(MAKE_DIRECTORY "${parent_dir}")

  execute_process(
    COMMAND git clone
            --branch "${ICE_GIT_BRANCH}"
            "${ICE_GIT_REPOSITORY}"
            "${ICE_SOURCE_DIR}"
    RESULT_VARIABLE result
  )

  if(NOT result EQUAL 0)
    message(FATAL_ERROR
      "Failed to clone Icechunk")
  endif()

  if(NOT EXISTS "${ICE_SOURCE_DIR}/icechunk/Cargo.toml")
    message(FATAL_ERROR
      "Invalid Icechunk source tree: ${ICE_SOURCE_DIR}")
  endif()

  set(ICECHUNK_SOURCE_DIR
      "${ICE_SOURCE_DIR}"
      PARENT_SCOPE)

endfunction()
