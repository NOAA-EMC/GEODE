#include <iostream>
#include <string>
#include <vector>

#include "ioda/Engines/Icechunk.h"
#include "ioda/Group.h"


int main(int argc, char** argv)
{
  if (argc != 3) {
    std::cerr << "Usage: " << argv[0]
              << " <store> <array-path>\n";
    return 1;
  }

  const std::string store = argv[1];
  const std::string array_path = argv[2];

  auto root =
      ioda::Engines::Icechunk::openFile(store);

  // Convert "/ObsValue/spectralRadiance"
  // into IODA group + variable.
  const auto slash = array_path.find_last_of('/');

  if (slash == std::string::npos || slash == 0) {
    std::cerr << "Invalid array path: "
              << array_path << "\n";
    return 1;
  }

  const std::string group_name =
      array_path.substr(1, slash - 1);

  const std::string variable_name =
      array_path.substr(slash + 1);

  auto group = root.open(group_name);
  auto variable = group.vars.open(variable_name);

  const auto dims = variable.getDimensions();

  std::cout
      << "Variable: " << array_path << "\n"
      << "rank: " << dims.dimensionality << "\n"
      << "elements: " << dims.numElements << "\n";

  std::vector<float> values;

  variable.read(values);

  std::cout
      << "read: " << values.size() << "\n";

  if (values.size() != dims.numElements) {
    std::cerr
        << "Read size does not match dimensions\n";
    return 1;
  }

  const std::size_t n = values.size();

  const std::size_t first =
      std::min<std::size_t>(10, n);

  for (std::size_t i = 0; i < first; ++i) {
    std::cout
        << "value[" << i << "] = "
        << values[i] << "\n";
  }

  if (n > 10) {
    std::cout
        << "value[last] = "
        << values.back() << "\n";

    for (std::size_t i = n - 5; i < n; ++i) {
      std::cout
          << "value[" << i << "] = "
          << values[i] << "\n";
    }
  }

  return 0;
}
