#include "ioda/Engines/Icechunk.h"
#include "ioda/Group.h"
#include "ioda/Variables/Variable.h"

#include <iostream>
#include <vector>

int main() {
    const std::string store = "data/cris_fsr_n20.icechunk";

    auto root = ioda::Engines::Icechunk::openFile(store);

    auto obsValue = root.open("ObsValue");

	{
		std::cout << "spectralRadiance";
		std::cout << "\n";

		// read 2d float32
		auto radiance = obsValue.vars.open("spectralRadiance");
		const auto dims = radiance.getDimensions();

		std::cout << "shape:";
		for (const auto dim : dims.dimsCur) {
			std::cout << " " << dim;
		}
		std::cout << "\n";

		std::vector<float> data;

		radiance.read(data);

		std::cout << "elements: " << data.size() << "\n";
		std::cout << "first: " << data.front() << "\n";
		std::cout << "last: " << data.back() << "\n";
	}

	std::cout << "\n";

	{
		std::cout << "cloudCoverTotal";
		std::cout << "\n";

		// read 1d float32
		auto cloudCoverTotal = obsValue.vars.open("cloudCoverTotal");

		const auto dims = cloudCoverTotal.getDimensions();

		std::cout << "shape:";
		for (const auto dim : dims.dimsCur) {
			std::cout << " " << dim;
		}
		std::cout << "\n";

		std::vector<float> data;

		cloudCoverTotal.read(data);

		std::cout << "elements: " << data.size() << "\n";
		std::cout << "first: " << data.front() << "\n";
		std::cout << "last: " << data.back() << "\n";
	}

    return 0;
}
