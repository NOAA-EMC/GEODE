#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include "ioda/containers/FrameCols.h"

namespace py = pybind11;

py::dict make_frame(
    py::array_t<float, py::array::c_style | py::array::forcecast> latitude,
    py::array_t<float, py::array::c_style | py::array::forcecast> longitude,
    py::array_t<float, py::array::c_style | py::array::forcecast> brightness_temperature)
{
    auto lat = latitude.request();
    auto lon = longitude.request();
    auto bt  = brightness_temperature.request();

    if (lat.ndim != 1 || lon.ndim != 1) {
        throw std::runtime_error("latitude and longitude must be 1-D");
    }

    if (bt.ndim != 2) {
        throw std::runtime_error("brightness_temperature must be 2-D");
    }

    if (lat.shape[0] != lon.shape[0] ||
        lat.shape[0] != bt.shape[0]) {
        throw std::runtime_error("Location dimensions do not match");
    }

    const size_t nloc = lat.shape[0];
    const size_t nch  = bt.shape[1];

    osdf::FrameCols frame;

    frame.appendNewColumn(
        "MetaData/latitude",
        std::vector<float>(
            static_cast<float *>(lat.ptr),
            static_cast<float *>(lat.ptr) + nloc));

    frame.appendNewColumn(
        "MetaData/longitude",
        std::vector<float>(
            static_cast<float *>(lon.ptr),
            static_cast<float *>(lon.ptr) + nloc));

    const float *bt_data = static_cast<float *>(bt.ptr);

    for (size_t ch = 0; ch < nch; ++ch) {
        std::vector<float> values(nloc);

        for (size_t i = 0; i < nloc; ++i) {
            values[i] = bt_data[i * nch + ch];
        }

        frame.appendNewColumn(
            "ObsValue/brightnessTemperature_" + std::to_string(ch),
            values);
    }

    py::dict result;
    result["numRows"] = frame.numRows();
    result["numCols"] = frame.numCols();

    return result;
}

PYBIND11_MODULE(geode_osdf, m) {
    m.def(
        "make_frame",
        &make_frame,
        "Create an OSDF FrameCols from GEODE observation arrays");
}
