#include <iostream>
#include <string>
#include <vector>

#include "ioda/Engines/Icechunk.h"
#include "ioda/Group.h"


int main(int argc, char** argv)
{
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0]
              << " <cris_fsr_n20.icechunk>\n";
    return 1;
  }

  const std::string store = argv[1];

  auto root =
      ioda::Engines::Icechunk::openFile(store);

  if (!root.exists("MetaData")) {
    std::cerr << "Missing MetaData group\n";
    return 1;
  }

  if (!root.exists("ObsValue")) {
    std::cerr << "Missing ObsValue group\n";
    return 1;
  }

  auto metaData = root.open("MetaData");
  auto obsValue = root.open("ObsValue");

  const auto metadata_variables =
      metaData.vars.list();

  const auto obs_variables =
      obsValue.vars.list();

  std::cout << "MetaData variables:\n";
  for (const auto& name : metadata_variables) {
    std::cout << "  " << name << "\n";
  }

  std::cout << "ObsValue variables:\n";
  for (const auto& name : obs_variables) {
    std::cout << "  " << name << "\n";
  }

  if (!metaData.vars.exists("sensorChannelNumber")) {
    std::cerr << "Missing MetaData/sensorChannelNumber\n";
    return 1;
  }

  if (!obsValue.vars.exists("spectralRadiance")) {
    std::cerr << "Missing ObsValue/spectralRadiance\n";
    return 1;
  }

  auto sensorChannelNumber =
      metaData.vars.open("sensorChannelNumber");

  auto spectralRadiance =
      obsValue.vars.open("spectralRadiance");

  const auto channel_dims =
      sensorChannelNumber.getDimensions();

  const auto radiance_dims =
      spectralRadiance.getDimensions();

  std::cout
      << "sensorChannelNumber rank = "
      << channel_dims.dimensionality << "\n";

  std::cout
      << "sensorChannelNumber elements = "
      << channel_dims.numElements << "\n";

  std::cout
      << "spectralRadiance rank = "
      << radiance_dims.dimensionality << "\n";

  std::cout
      << "spectralRadiance elements = "
      << radiance_dims.numElements << "\n";

  if (channel_dims.dimensionality != 2) {
    std::cerr
        << "Expected sensorChannelNumber to be rank 2\n";
    return 1;
  }

  if (radiance_dims.dimensionality != 2) {
    std::cerr
        << "Expected spectralRadiance to be rank 2\n";
    return 1;
  }

  return 0;
}
