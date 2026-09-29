#include "ioda/Engines/Icechunk.h"
#include "ioda/Group.h"
#include "ioda/Variables/Variable.h"
#include "ioda/Variables/Selection.h"

#include <iostream>
#include <vector>

int main() {
    const std::string store =
        "data/cris_fsr_n20.icechunk";

    auto root =
        ioda::Engines::Icechunk::openFile(store);

    auto obsValue =
        root.open("ObsValue");

    auto radiance =
        obsValue.vars.open("spectralRadiance");

    // ------------------------------------------------------------
    // Selection
    // ------------------------------------------------------------

    const std::vector<ioda::Dimensions_t> start = {
        1000, 20
    };

    const std::vector<ioda::Dimensions_t> count = {
        100, 10
    };

    ioda::Selection selection;

    selection.select(
        ioda::Selection::SingleSelection(
            ioda::SelectionOperator::SET,
            start,
            count));

    // ------------------------------------------------------------
    // Read selected data
    // ------------------------------------------------------------

    std::vector<float> selected(
        count[0] * count[1]);

    try {

        radiance.read(
            gsl::make_span(
                selected.data(),
                selected.size()),
            selection,
            selection);

    } catch (const std::exception& e) {

        std::cerr
            << "selection read failed:\n"
            << e.what()
            << "\n";

        return 1;
    }

    // ------------------------------------------------------------
    // Results
    // ------------------------------------------------------------

    std::cout
        << "selection start:"
        << " " << start[0]
        << " " << start[1]
        << "\n";

    std::cout
        << "selection count:"
        << " " << count[0]
        << " " << count[1]
        << "\n";

    std::cout
        << "elements: "
        << selected.size()
        << "\n";

    std::cout
        << "first: "
        << selected.front()
        << "\n";

    std::cout
        << "last: "
        << selected.back()
        << "\n";

    return 0;
}
