#include <iostream>
#include <string>
#include <cstdlib>

extern "C" {

int32_t icechunk_read_array_f64(
    const char* store_path,
    const char* array_path,
    double** data,
    size_t* count);

}


int main(int argc, char** argv)
{
  if (argc != 3) {
    std::cerr << "Usage: " << argv[0]
              << " <store> <array-path>\n";
    return 1;
  }

  const std::string store = argv[1];
  const std::string array_path = argv[2];

  double* data = nullptr;
  size_t count = 0;

  const int32_t rc =
      icechunk_read_array_f64(
          store.c_str(),
          array_path.c_str(),
          &data,
          &count);

  if (rc != 0) {
    std::cerr
        << "icechunk_read_array_f64 failed: "
        << rc << "\n";
    return 1;
  }

  std::cout
      << "Variable: " << array_path << "\n"
      << "elements: " << count << "\n";

  const std::size_t first =
      std::min<std::size_t>(10, count);

  for (std::size_t i = 0; i < first; ++i) {
    std::cout
        << "value[" << i << "] = "
        << data[i] << "\n";
  }

  if (count > 10) {
    std::cout
        << "value[last] = "
        << data[count - 1] << "\n";

    for (std::size_t i = count - 5; i < count; ++i) {
      std::cout
          << "value[" << i << "] = "
          << data[i] << "\n";
    }
  }

  std::free(data);

  return 0;
}
