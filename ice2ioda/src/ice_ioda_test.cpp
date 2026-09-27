#include <iostream>
#include <vector>
#include <string>

#include "ioda/Group.h"
#include "ioda/Engines/Icechunk.h"

int main(int argc, char** argv)
{
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0] << " <icechunk-store>\n";
    return 1;
  }

  const std::string store = argv[1];

  auto root =
      ioda::Engines::Icechunk::openFile(store);

  auto obsValue =
      root.open("ObsValue");

  auto salinity =
      obsValue.vars.open("salinity");

  std::cout
      << "rank = "
      << salinity.getDimensions().dimensionality
      << "\n";

  std::cout
      << "size = "
      << salinity.getDimensions().numElements
      << "\n";

  std::vector<float> values;

  salinity.read(values);

  std::cout
      << "read = "
      << values.size()
      << "\n";

  for (size_t i = 0; i < 10; ++i) {
    std::cout
        << "salinity[" << i << "] = "
        << values[i]
        << "\n";
  }

  std::cout
      << "last = "
      << values.back()
      << "\n";

  return 0;
}
