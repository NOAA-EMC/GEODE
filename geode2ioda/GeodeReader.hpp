#pragma once

#include <memory>
#include <string>

namespace osdf {
class IFrame;
}

namespace geode {

struct Query {
    std::string store;
};

class Reader {
public:
    Reader() = default;

    std::unique_ptr<osdf::IFrame> read(const Query& query);
};

}  // namespace geode
