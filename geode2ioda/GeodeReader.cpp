#include "GeodeReader.hpp"

#include <pybind11/embed.h>
#include <pybind11/numpy.h>

#include "ioda/containers/FrameCols.h"

namespace py = pybind11;

namespace geode {

std::unique_ptr<osdf::IFrame>
Reader::read(const Query& query) {
    py::gil_scoped_acquire gil;

    py::module_ icechunk = py::module_::import("icechunk");
    py::module_ xarray = py::module_::import("xarray");

    py::object storage =
        icechunk.attr("local_filesystem_storage")(query.store);

    py::object repo =
        icechunk.attr("Repository").attr("open")(storage);

    py::object session =
        repo.attr("readonly_session")("main");

    py::object datatree =
        xarray.attr("open_datatree")(
            session.attr("store"),
            py::arg("engine") = "zarr",
            py::arg("consolidated") = false);

    py::object meta =
        datatree.attr("__getitem__")("/MetaData").attr("ds");

    py::object obs =
        datatree.attr("__getitem__")("/ObsValue").attr("ds");

	py::object latitude_obj =
		meta.attr("__getitem__")("latitude").attr("values");

	py::object longitude_obj =
		meta.attr("__getitem__")("longitude").attr("values");

	py::object bt_obj =
		obs.attr("__getitem__")("brightnessTemperature").attr("values");

	py::array_t<float> latitude =
		latitude_obj.cast<py::array_t<float>>();

	py::array_t<float> longitude =
		longitude_obj.cast<py::array_t<float>>();

	py::array_t<float> bt =
		bt_obj.cast<py::array_t<float>>();

    auto lat = latitude.request();
    auto lon = longitude.request();
    auto bt_info = bt.request();

    if (lat.ndim != 1 || lon.ndim != 1) {
        throw std::runtime_error(
            "latitude and longitude must be 1-D");
    }

    if (bt_info.ndim != 2) {
        throw std::runtime_error(
            "brightnessTemperature must be 2-D");
    }

    if (lat.shape[0] != lon.shape[0] ||
        lat.shape[0] != bt_info.shape[0]) {
        throw std::runtime_error(
            "Location dimensions do not match");
    }

    const size_t nloc = lat.shape[0];
    const size_t nch = bt_info.shape[1];

    auto frame = std::make_unique<osdf::FrameCols>();

    frame->appendNewColumn(
        "MetaData/latitude",
        std::vector<float>(
            static_cast<float*>(lat.ptr),
            static_cast<float*>(lat.ptr) + nloc));

    frame->appendNewColumn(
        "MetaData/longitude",
        std::vector<float>(
            static_cast<float*>(lon.ptr),
            static_cast<float*>(lon.ptr) + nloc));

    const float* bt_data =
        static_cast<float*>(bt_info.ptr);

    for (size_t ch = 0; ch < nch; ++ch) {
        std::vector<float> values(nloc);

        for (size_t i = 0; i < nloc; ++i) {
            values[i] = bt_data[i * nch + ch];
        }

        frame->appendNewColumn(
            "ObsValue/brightnessTemperature_" +
                std::to_string(ch),
            values);
    }

    return frame;
}

}  // namespace geode
