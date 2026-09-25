#include <cstdio>
#include <cstdint>

extern "C" {
    int32_t icechunk_read_compressed_chunk(
        const char* store_path,
        const char* array_path,
        uint32_t chunk_index,
        uint8_t** data,
        size_t* len);

    int32_t icechunk_read_chunk_f32(
        const char* store_path,
        const char* array_path,
        uint32_t chunk_index,
        float** data,
        size_t* count);

	// this one is not correct:
	int32_t icechunk_read_array_f32(
		const char* store_path,
		const char* array_path,
		uint32_t num_chunks,
		float** data,
		size_t* count);

	int32_t icechunk_read_array_1d_f32(
		const char* store_path,
		const char* array_path,
		float** data,
		size_t* count);

    void icechunk_free(uint8_t* data);
}


int main()
{
	float* values = nullptr;
	size_t count = 0;

	const char* store_path = "../argo.icechunk";
	const char* array_path = "/ObsValue/salinity";

	int32_t rc = icechunk_read_array_1d_f32(
		store_path,
		array_path,
		&values,
		&count
	);

	std::printf("rc=%d count=%zu\n", rc, count);

	if (rc == 0) {
		for (size_t i = 0; i < 10 && i < count; ++i)
			std::printf("salinity[%zu] = %.6f\n",
						i, values[i]);

		if (count > 0) {
			std::printf("last salinity[%zu] = %.6f\n",
						count - 1, values[count - 1]);
		}

		icechunk_free(
			reinterpret_cast<uint8_t*>(values));
	}

	return rc;
}
