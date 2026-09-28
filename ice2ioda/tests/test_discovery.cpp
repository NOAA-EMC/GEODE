#include <cstdint>
#include <iostream>
#include <string>

extern "C" {
int32_t icechunk_list_nodes(
    const char* store_path,
    uint8_t** data,
    size_t* len);

void icechunk_free(uint8_t* data);
}

int main(int argc, char** argv)
{
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0]
              << " <icechunk-store>\n";
    return 1;
  }

  const std::string store = argv[1];

  uint8_t* data = nullptr;
  size_t len = 0;

  const int32_t rc =
      icechunk_list_nodes(
          store.c_str(),
          &data,
          &len);

  if (rc != 0) {
    std::cerr << "icechunk_list_nodes failed: "
              << rc << "\n";
    return 1;
  }

  std::cout << "Discovered nodes:\n";
  std::cout.write(
      reinterpret_cast<const char*>(data),
      len);
  std::cout << "\n";

  icechunk_free(data);

  return 0;
}
