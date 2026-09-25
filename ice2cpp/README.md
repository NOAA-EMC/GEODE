
This is a very crude proof of concept.
It builds FFI to access rust functionality of icechunk from C++.


Install rust

build the FFI with 
	cargo build

create icechunk store with a 1d array
edit test_ffi.cpp and set store_path and array_path

build the test_ffi demo with
	g++ -std=c++17 test_ffi.cpp     -Ltarget/debug     -licechunk_ffi     -Wl,-rpath,'$ORIGIN/target/debug'     -o test_ffi

run:
	./test_ffi
