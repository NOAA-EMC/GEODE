#include <pybind11/embed.h>

#include <iostream>

#include "GeodeReader.hpp"
#include "ioda/containers/FrameCols.h"


namespace py = pybind11;

int main() {
    py::scoped_interpreter guard{};

    geode::Reader reader;

    geode::Query query;
    query.store =
        "/scratch3/NCEPDEV/da/Edward.Givelberg/"
        "GEODE/ice2ioda/data/atms_n20.icechunk";

    auto frame = reader.read(query);

    std::cout << "OSDF rows: " << frame->numRows() << "\n";
    std::cout << "OSDF cols: " << frame->numCols() << "\n";

    if (frame->numRows() != 3110399) {
        return 1;
    }

    if (frame->numCols() != 24) {
        return 1;
    }

    std::cout << "PASS\n";
    return 0;
}
