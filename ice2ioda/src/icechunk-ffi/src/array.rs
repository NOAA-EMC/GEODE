// use std::ffi::CStr;
// use std::ptr;

use std::path::Path as StdPath;
use std::sync::Arc;

use icechunk::format::{ByteRange, Path};
use icechunk::repository::VersionInfo;
use icechunk::Repository;


pub(crate) async fn read_array_f32(
    store_path: &str,
    array_path: &str,
) -> Result<Vec<f32>, i32> {
    use futures_util::StreamExt;
    use icechunk::format::snapshot::NodeData;

    let storage = icechunk::new_local_filesystem_storage(
        StdPath::new(store_path)
    )
    .await
    .map_err(|_| -10)?;

    let repo = Repository::open(
        None,
        Arc::clone(&storage),
        Default::default(),
    )
    .await
    .map_err(|_| -11)?;

    let session = repo
        .readonly_session(
            &VersionInfo::BranchTipRef("main".to_string())
        )
        .await
        .map_err(|_| -12)?;

    let path = Path::new(array_path)
        .map_err(|_| -13)?;

    let node = session
        .get_array(&path)
        .await
        .map_err(|_| -14)?;

    let shape: Vec<usize> = match node.node_data {
        NodeData::Array { shape, .. } => {
            shape
                .iter()
                .map(|d| d.array_length() as usize)
                .collect()
        }
        _ => return Err(-15),
    };

    if shape.is_empty() {
        return Err(-16);
    }

    /*
     * Get the Zarr chunk shape from the array metadata.
     *
     * Icechunk stores this in the node user data.
     */
    let metadata: serde_json::Value =
        serde_json::from_slice(&node.user_data)
            .map_err(|_| -17)?;

    let chunk_shape = metadata
        .get("chunk_grid")
        .and_then(|v| v.get("configuration"))
        .and_then(|v| v.get("chunk_shape"))
        .and_then(|v| v.as_array())
        .ok_or(-18)?;

    let chunk_shape: Vec<usize> = chunk_shape
        .iter()
        .map(|v| v.as_u64().ok_or(-19).map(|n| n as usize))
        .collect::<Result<_, _>>()?;

    if chunk_shape.len() != shape.len() {
        return Err(-20);
    }

    /*
     * Compute the total number of logical elements.
     */
    let total_elements = shape.iter().try_fold(
        1usize,
        |a, &b| a.checked_mul(b).ok_or(-21),
    )?;

    let mut output = vec![0.0f32; total_elements];

    /*
     * Row-major strides for the logical array.
     *
     * For shape [N, M]:
     *
     *   strides = [M, 1]
     */
    let mut strides = vec![1usize; shape.len()];

    for i in (0..shape.len() - 1).rev() {
        strides[i] = strides[i + 1]
            .checked_mul(shape[i + 1])
            .ok_or(-22)?;
    }

    let chunks = session.array_chunk_iterator(&path).await;

    futures_util::pin_mut!(chunks);

    while let Some(chunk_result) = chunks.next().await {
        let chunk = chunk_result.map_err(|_| -23)?;

        let coord = &chunk.coord.0;

        if coord.len() != shape.len() {
            return Err(-24);
        }

        /*
         * Starting logical index of this chunk.
         */
        let mut start = Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            start.push(
                (coord[d] as usize)
                    .checked_mul(chunk_shape[d])
                    .ok_or(-25)?
            );
        }

        let reader = session
            .get_chunk_reader(
                &path,
                &chunk.coord,
                &ByteRange::from_offset(0),
            )
            .await
            .map_err(|_| -26)?;

        let reader = match reader {
            Some(reader) => reader,
            None => continue,
        };

        let compressed = reader.await.map_err(|_| -27)?;

        let decoded = zstd::decode_all(compressed.as_ref())
            .map_err(|_| -28)?;

        if decoded.len() % std::mem::size_of::<f32>() != 0 {
            return Err(-29);
        }

        let chunk_elements =
            decoded.len() / std::mem::size_of::<f32>();

        /*
         * Determine the actual extent of this chunk.
         *
         * Normally this is chunk_shape, except at an
         * array boundary.
         */
        let mut actual_shape = Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            if start[d] >= shape[d] {
                return Err(-30);
            }

            actual_shape.push(
                chunk_shape[d].min(shape[d] - start[d])
            );
        }

        let expected_elements =
            actual_shape.iter().try_fold(
                1usize,
                |a, &b| a.checked_mul(b).ok_or(-31),
            )?;

        if chunk_elements < expected_elements {
            return Err(-32);
        }

        /*
         * Copy the chunk into the logical output array.
         *
         * Iterate over every element of the chunk using
         * row-major coordinates.
         */
        for linear in 0..expected_elements {
            let mut remainder = linear;
            let mut output_index = 0usize;

            for d in (0..shape.len()).rev() {
                let local = remainder % actual_shape[d];
                remainder /= actual_shape[d];

                let global = start[d] + local;

                output_index +=
                    global * strides[d];
            }

            let byte_offset =
                linear * std::mem::size_of::<f32>();

            let value = f32::from_le_bytes([
                decoded[byte_offset],
                decoded[byte_offset + 1],
                decoded[byte_offset + 2],
                decoded[byte_offset + 3],
            ]);

            output[output_index] = value;
        }
    }

    Ok(output)
}


pub(crate) async fn read_array_f32_selection(
    store_path: &str,
    array_path: &str,
    selection_start: &[usize],
    selection_count: &[usize],
) -> Result<Vec<f32>, i32> {
    use futures_util::StreamExt;
    use icechunk::format::snapshot::NodeData;

    /*
     * ------------------------------------------------------------
     * Open Icechunk
     * ------------------------------------------------------------
     */

    let storage = icechunk::new_local_filesystem_storage(
        StdPath::new(store_path)
    )
    .await
    .map_err(|_| -40)?;

    let repo = Repository::open(
        None,
        Arc::clone(&storage),
        Default::default(),
    )
    .await
    .map_err(|_| -41)?;

    let session = repo
        .readonly_session(
            &VersionInfo::BranchTipRef("main".to_string())
        )
        .await
        .map_err(|_| -42)?;

    let path = Path::new(array_path)
        .map_err(|_| -43)?;

    let node = session
        .get_array(&path)
        .await
        .map_err(|_| -44)?;

    /*
     * ------------------------------------------------------------
     * Get array shape
     * ------------------------------------------------------------
     */

    let shape: Vec<usize> = match node.node_data {
        NodeData::Array { shape, .. } => {
            shape
                .iter()
                .map(|d| d.array_length() as usize)
                .collect()
        }
        _ => return Err(-45),
    };

    if shape.is_empty() {
        return Err(-46);
    }

    /*
     * ------------------------------------------------------------
     * Validate selection
     * ------------------------------------------------------------
     */

    if selection_start.len() != shape.len()
        || selection_count.len() != shape.len()
    {
        return Err(-47);
    }

    for d in 0..shape.len() {
        let end = selection_start[d]
            .checked_add(selection_count[d])
            .ok_or(-48)?;

        if end > shape[d] {
            return Err(-49);
        }
    }

    /*
     * ------------------------------------------------------------
     * Get Zarr chunk shape
     * ------------------------------------------------------------
     */

    let metadata: serde_json::Value =
        serde_json::from_slice(&node.user_data)
            .map_err(|_| -50)?;

    let chunk_shape = metadata
        .get("chunk_grid")
        .and_then(|v| v.get("configuration"))
        .and_then(|v| v.get("chunk_shape"))
        .and_then(|v| v.as_array())
        .ok_or(-51)?;

    let chunk_shape: Vec<usize> = chunk_shape
        .iter()
        .map(|v| {
            v.as_u64()
                .ok_or(-52)
                .map(|n| n as usize)
        })
        .collect::<Result<_, _>>()?;

    if chunk_shape.len() != shape.len() {
        return Err(-53);
    }

    /*
     * ------------------------------------------------------------
     * Number of requested output elements
     * ------------------------------------------------------------
     */

    let selected_elements =
        selection_count.iter().try_fold(
            1usize,
            |a, &b| a.checked_mul(b).ok_or(-54),
        )?;

    let mut output =
        vec![0.0f32; selected_elements];

    /*
     * ------------------------------------------------------------
     * Row-major strides for the SELECTED output.
     *
     * For selection [100, 10]:
     *
     *   output strides = [10, 1]
     * ------------------------------------------------------------
     */

    let mut output_strides =
        vec![1usize; shape.len()];

    for i in (0..shape.len() - 1).rev() {
        output_strides[i] =
            output_strides[i + 1]
                .checked_mul(selection_count[i + 1])
                .ok_or(-55)?;
    }

    /*
     * ------------------------------------------------------------
     * Iterate through Icechunk chunks.
     * ------------------------------------------------------------
     */

    let chunks =
        session.array_chunk_iterator(&path).await;

    futures_util::pin_mut!(chunks);

    while let Some(chunk_result) = chunks.next().await {
        let chunk = chunk_result.map_err(|_| -56)?;

        let coord = &chunk.coord.0;

        if coord.len() != shape.len() {
            return Err(-57);
        }

        /*
         * Logical starting position of this chunk.
         */

        let mut chunk_start =
            Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            chunk_start.push(
                (coord[d] as usize)
                    .checked_mul(chunk_shape[d])
                    .ok_or(-58)?
            );
        }

        /*
         * Actual chunk extent.  Edge chunks may be smaller.
         */

        let mut chunk_end =
            Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            if chunk_start[d] >= shape[d] {
                return Err(-59);
            }

            let end =
                chunk_start[d]
                    .checked_add(chunk_shape[d])
                    .ok_or(-60)?;

            chunk_end.push(
                end.min(shape[d])
            );
        }

        /*
         * --------------------------------------------------------
         * Determine whether this chunk intersects the selection.
         *
         * chunk:     [chunk_start, chunk_end)
         * selection: [selection_start, selection_end)
         * --------------------------------------------------------
         */

        let mut selection_end =
            Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            selection_end.push(
                selection_start[d]
                    .checked_add(selection_count[d])
                    .ok_or(-61)?
            );
        }

        let mut intersects = true;

        for d in 0..shape.len() {
            if chunk_end[d] <= selection_start[d]
                || chunk_start[d] >= selection_end[d]
            {
                intersects = false;
                break;
            }
        }

        /*
         * This is the critical optimization:
         *
         * DO NOT read/decompress chunks that cannot contribute
         * to the requested selection.
         */

        if !intersects {
            continue;
        }

        /*
         * --------------------------------------------------------
         * Compute intersection.
         * --------------------------------------------------------
         */

        let mut intersection_start =
            Vec::with_capacity(shape.len());

        let mut intersection_end =
            Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            intersection_start.push(
                chunk_start[d]
                    .max(selection_start[d])
            );

            intersection_end.push(
                chunk_end[d]
                    .min(selection_end[d])
            );
        }

        /*
         * --------------------------------------------------------
         * NOW read the chunk.
         * --------------------------------------------------------
         */

        let reader = session
            .get_chunk_reader(
                &path,
                &chunk.coord,
                &ByteRange::from_offset(0),
            )
            .await
            .map_err(|_| -62)?;

        let reader = match reader {
            Some(reader) => reader,
            None => continue,
        };

        let compressed =
            reader.await.map_err(|_| -63)?;

        let decoded =
            zstd::decode_all(compressed.as_ref())
                .map_err(|_| -64)?;

        if decoded.len()
            % std::mem::size_of::<f32>() != 0
        {
            return Err(-65);
        }

        let chunk_elements =
            decoded.len()
                / std::mem::size_of::<f32>();

        /*
         * Actual chunk shape.
         */

        let actual_shape =
            chunk_end
                .iter()
                .zip(chunk_start.iter())
                .map(|(end, start)| end - start)
                .collect::<Vec<_>>();

        let expected_elements =
            actual_shape.iter().try_fold(
                1usize,
                |a, &b| a.checked_mul(b).ok_or(-66),
            )?;

        if chunk_elements < expected_elements {
            return Err(-67);
        }

        /*
         * --------------------------------------------------------
         * Copy the intersection from this chunk into output.
         * --------------------------------------------------------
         *
         * Both arrays are row-major.
         * --------------------------------------------------------
         */

        /*
         * Chunk strides.
         */

        let mut chunk_strides =
            vec![1usize; shape.len()];

        for i in (0..shape.len() - 1).rev() {
            chunk_strides[i] =
                chunk_strides[i + 1]
                    .checked_mul(actual_shape[i + 1])
                    .ok_or(-68)?;
        }

        /*
         * Iterate over the intersection.
         */

        let mut intersection_size =
            Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            intersection_size.push(
                intersection_end[d]
                    - intersection_start[d]
            );
        }

        let intersection_elements =
            intersection_size.iter().try_fold(
                1usize,
                |a, &b| a.checked_mul(b).ok_or(-69),
            )?;

        for linear in 0..intersection_elements {

            /*
             * Convert linear intersection index into
             * multidimensional coordinates.
             */

            let mut remainder = linear;

            let mut global_index =
                vec![0usize; shape.len()];

            for d in (0..shape.len()).rev() {
                let local =
                    remainder
                        % intersection_size[d];

                remainder /=
                    intersection_size[d];

                global_index[d] =
                    intersection_start[d]
                        + local;
            }

            /*
             * Convert global coordinate to chunk-local
             * coordinate.
             */

            let mut chunk_offset = 0usize;

            for d in 0..shape.len() {
                let local =
                    global_index[d]
                        - chunk_start[d];

                chunk_offset +=
                    local * chunk_strides[d];
            }

            /*
             * Convert global coordinate to selection-local
             * coordinate.
             */

            let mut output_offset = 0usize;

            for d in 0..shape.len() {
                let local =
                    global_index[d]
                        - selection_start[d];

                output_offset +=
                    local * output_strides[d];
            }

            /*
             * Decode f32.
             */

            let byte_offset =
                chunk_offset
                    * std::mem::size_of::<f32>();

            let value =
                f32::from_le_bytes([
                    decoded[byte_offset],
                    decoded[byte_offset + 1],
                    decoded[byte_offset + 2],
                    decoded[byte_offset + 3],
                ]);

            output[output_offset] = value;
        }
    }

    Ok(output)
}


pub(crate) async fn read_array_f64(
    store_path: &str,
    array_path: &str,
) -> Result<Vec<f64>, i32> {
    use futures_util::StreamExt;
    use icechunk::format::snapshot::NodeData;

    let storage = icechunk::new_local_filesystem_storage(
        StdPath::new(store_path)
    )
    .await
    .map_err(|_| -10)?;

    let repo = Repository::open(
        None,
        Arc::clone(&storage),
        Default::default(),
    )
    .await
    .map_err(|_| -11)?;

    let session = repo
        .readonly_session(
            &VersionInfo::BranchTipRef("main".to_string())
        )
        .await
        .map_err(|_| -12)?;

    let path = Path::new(array_path)
        .map_err(|_| -13)?;

    let node = session
        .get_array(&path)
        .await
        .map_err(|_| -14)?;

    let shape: Vec<usize> = match node.node_data {
        NodeData::Array { shape, .. } => {
            shape
                .iter()
                .map(|d| d.array_length() as usize)
                .collect()
        }
        _ => return Err(-15),
    };

    if shape.is_empty() {
        return Err(-16);
    }

    /*
     * Get the Zarr chunk shape from the array metadata.
     *
     * Icechunk stores this in the node user data.
     */
    let metadata: serde_json::Value =
        serde_json::from_slice(&node.user_data)
            .map_err(|_| -17)?;

    let chunk_shape = metadata
        .get("chunk_grid")
        .and_then(|v| v.get("configuration"))
        .and_then(|v| v.get("chunk_shape"))
        .and_then(|v| v.as_array())
        .ok_or(-18)?;

    let chunk_shape: Vec<usize> = chunk_shape
        .iter()
        .map(|v| v.as_u64().ok_or(-19).map(|n| n as usize))
        .collect::<Result<_, _>>()?;

    if chunk_shape.len() != shape.len() {
        return Err(-20);
    }

    /*
     * Compute the total number of logical elements.
     */
    let total_elements = shape.iter().try_fold(
        1usize,
        |a, &b| a.checked_mul(b).ok_or(-21),
    )?;

    let mut output = vec![0.0f64; total_elements];

    /*
     * Row-major strides for the logical array.
     *
     * For shape [N, M]:
     *
     *   strides = [M, 1]
     */
    let mut strides = vec![1usize; shape.len()];

    for i in (0..shape.len() - 1).rev() {
        strides[i] = strides[i + 1]
            .checked_mul(shape[i + 1])
            .ok_or(-22)?;
    }

    let chunks = session.array_chunk_iterator(&path).await;

    futures_util::pin_mut!(chunks);

    while let Some(chunk_result) = chunks.next().await {
        let chunk = chunk_result.map_err(|_| -23)?;

        let coord = &chunk.coord.0;

        if coord.len() != shape.len() {
            return Err(-24);
        }

        /*
         * Starting logical index of this chunk.
         */
        let mut start = Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            start.push(
                (coord[d] as usize)
                    .checked_mul(chunk_shape[d])
                    .ok_or(-25)?
            );
        }

        let reader = session
            .get_chunk_reader(
                &path,
                &chunk.coord,
                &ByteRange::from_offset(0),
            )
            .await
            .map_err(|_| -26)?;

        let reader = match reader {
            Some(reader) => reader,
            None => continue,
        };

        let compressed = reader.await.map_err(|_| -27)?;

        let decoded = zstd::decode_all(compressed.as_ref())
            .map_err(|_| -28)?;

        if decoded.len() % std::mem::size_of::<f64>() != 0 {
            return Err(-29);
        }

        let chunk_elements =
            decoded.len() / std::mem::size_of::<f64>();

        /*
         * Determine the actual extent of this chunk.
         *
         * Normally this is chunk_shape, except at an
         * array boundary.
         */
        let mut actual_shape = Vec::with_capacity(shape.len());

        for d in 0..shape.len() {
            if start[d] >= shape[d] {
                return Err(-30);
            }

            actual_shape.push(
                chunk_shape[d].min(shape[d] - start[d])
            );
        }

        let expected_elements =
            actual_shape.iter().try_fold(
                1usize,
                |a, &b| a.checked_mul(b).ok_or(-31),
            )?;

        if chunk_elements < expected_elements {
            return Err(-32);
        }

        /*
         * Copy the chunk into the logical output array.
         *
         * Iterate over every element of the chunk using
         * row-major coordinates.
         */
        for linear in 0..expected_elements {
            let mut remainder = linear;
            let mut output_index = 0usize;

            for d in (0..shape.len()).rev() {
                let local = remainder % actual_shape[d];
                remainder /= actual_shape[d];

                let global = start[d] + local;

                output_index +=
                    global * strides[d];
            }

            let byte_offset =
                linear * std::mem::size_of::<f64>();

            let value = f64::from_le_bytes([
                decoded[byte_offset],
                decoded[byte_offset + 1],
                decoded[byte_offset + 2],
                decoded[byte_offset + 3],
                decoded[byte_offset + 4],
                decoded[byte_offset + 5],
                decoded[byte_offset + 6],
                decoded[byte_offset + 7],
            ]);

            output[output_index] = value;
        }
    }

    Ok(output)
}
