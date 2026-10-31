cmake_minimum_required(VERSION 3.16)
project(electron_loong64_cross_smoke LANGUAGES C CXX)

add_executable(hello-c hello.c)
add_executable(hello-cpp hello.cpp)

set_target_properties(hello-c hello-cpp PROPERTIES
  BUILD_RPATH ""
  INSTALL_RPATH ""
)
