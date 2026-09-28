#include <iostream>
#include <string>
#include <vector>

#include "ioda/Engines/Icechunk.h"
#include "ioda/Group.h"

int main(int argc, char** argv)
{
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0]
              << " <argo.icechunk>\n";
    return 1;
  }

  const std::string store = argv[1];

  auto root =
      ioda::Engines::Icechunk::openFile(store);

  auto obsValue =
      root.open("ObsValue");

  if (!obsValue.vars.exists("salinity")) {
    std::cerr << "Missing ObsValue/salinity\n";
    return 1;
  }

  auto salinity =
      obsValue.vars.open("salinity");

  const auto dims =
      salinity.getDimensions();

  std::cout
      << "rank = "
      << dims.dimensionality
      << "\n";

  std::cout
      << "size = "
      << dims.numElements
      << "\n";

  if (dims.dimensionality != 1) {
    std::cerr << "Expected rank 1\n";
    return 1;
  }

  std::vector<float> values;
  salinity.read(values);

  std::cout
      << "read = "
      << values.size()
      << "\n";

  if (values.size() != dims.numElements) {
    std::cerr << "Read size does not match dimensions\n";
    return 1;
  }

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
