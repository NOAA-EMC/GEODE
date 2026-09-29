use std::ffi::CStr;
use std::os::raw::c_char;
use std::path::Path as StdPath;
use std::ptr;
use std::sync::Arc;

use icechunk::format::{ByteRange, ChunkIndices, Path};
use icechunk::repository::VersionInfo;
use icechunk::Repository;


async fn read_stored_chunk(
    store_path: &str,
    array_path: &str,
    chunk_index: u32,
) -> Result<Vec<u8>, ()> {
    let storage = icechunk::new_local_filesystem_storage(
        StdPath::new(store_path),
    )
    .await
    .map_err(|e| {
        eprintln!("ERROR: new_local_filesystem_storage: {:?}", e);
    })?;

    let repo = Repository::open(
        None,
        Arc::clone(&storage),
        Default::default(),
    )
    .await
    .map_err(|e| {
        eprintln!("ERROR: Repository::open: {:?}", e);
    })?;

    let session = repo
        .readonly_session(
            &VersionInfo::BranchTipRef("main".to_string())
        )
        .await
        .map_err(|e| {
            eprintln!("ERROR: readonly_session: {:?}", e);
        })?;

    let path = Path::new(array_path)
        .map_err(|e| {
            eprintln!("ERROR: Path::new: {:?}", e);
        })?;

    let coords = ChunkIndices(vec![chunk_index]);

    let reader = session
        .get_chunk_reader(
            &path,
            &coords,
            &ByteRange::from_offset(0),
        )
        .await
        .map_err(|e| {
            eprintln!("ERROR: get_chunk_reader: {:?}", e);
        })?;

    match reader {
        Some(reader) => reader
            .await
            .map(|bytes| bytes.to_vec())
            .map_err(|e| {
                eprintln!("ERROR: chunk reader: {:?}", e);
            }),

        None => {
            eprintln!("ERROR: get_chunk_reader returned None");
            Err(())
        }
    }
}


/// Read the raw chunk exactly as stored by Icechunk.
///
/// Returns compressed bytes.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_read_compressed_chunk(
    store_path: *const c_char,
    array_path: *const c_char,
    chunk_index: u32,
    data: *mut *mut u8,
    len: *mut usize,
) -> i32 {
    if store_path.is_null()
        || array_path.is_null()
        || data.is_null()
        || len.is_null()
    {
        return -1;
    }

    let store_path = match unsafe {
        CStr::from_ptr(store_path)
    }.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let array_path = match unsafe {
        CStr::from_ptr(array_path)
    }.to_str() {
        Ok(s) => s,
        Err(_) => return -3,
    };

    let runtime = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(_) => return -4,
    };

    let bytes = match runtime.block_on(
        read_stored_chunk(
            store_path,
            array_path,
            chunk_index,
        )
    ) {
        Ok(bytes) => bytes,
        Err(_) => return -5,
    };

    copy_to_c_buffer(bytes, data, len)
}


/// Read one chunk and decode it into little-endian float32 values.
///
/// The returned buffer contains `float32` values, not compressed bytes.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_read_chunk_f32(
    store_path: *const c_char,
    array_path: *const c_char,
    chunk_index: u32,
    data: *mut *mut f32,
    count: *mut usize,
) -> i32 {
    if store_path.is_null()
        || array_path.is_null()
        || data.is_null()
        || count.is_null()
    {
        return -1;
    }

    let store_path = match unsafe {
        CStr::from_ptr(store_path)
    }.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let array_path = match unsafe {
        CStr::from_ptr(array_path)
    }.to_str() {
        Ok(s) => s,
        Err(_) => return -3,
    };

    let runtime = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(_) => return -4,
    };

    let compressed = match runtime.block_on(
        read_stored_chunk(
            store_path,
            array_path,
            chunk_index,
        )
    ) {
        Ok(bytes) => bytes,
        Err(_) => return -5,
    };

    let decoded = match zstd::decode_all(compressed.as_slice()) {
        Ok(bytes) => bytes,
        Err(e) => {
            eprintln!("ERROR: Zstd decompression: {:?}", e);
            return -6;
        }
    };

    if decoded.len() % 4 != 0 {
        eprintln!(
            "ERROR: decoded chunk size {} is not divisible by 4",
            decoded.len()
        );
        return -7;
    }

    let values: Vec<f32> = decoded
        .chunks_exact(4)
        .map(|b| {
            f32::from_le_bytes([
                b[0], b[1], b[2], b[3]
            ])
        })
        .collect();

    let n = values.len();

    let ptr_out = unsafe {
        libc::malloc(n * std::mem::size_of::<f32>())
            as *mut f32
    };

    if ptr_out.is_null() && n != 0 {
        return -8;
    }

    unsafe {
        ptr::copy_nonoverlapping(
            values.as_ptr(),
            ptr_out,
            n,
        );

        *data = ptr_out;
        *count = n;
    }

    0
}


async fn read_array_f32(
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

#[unsafe(no_mangle)]
pub extern "C" fn icechunk_read_array_f32(
    store_path: *const c_char,
    array_path: *const c_char,
    data: *mut *mut f32,
    count: *mut usize,
) -> i32 {
    if store_path.is_null()
        || array_path.is_null()
        || data.is_null()
        || count.is_null()
    {
        return -1;
    }

    let store_path =
        match unsafe { CStr::from_ptr(store_path) }.to_str() {
            Ok(s) => s,
            Err(_) => return -2,
        };

    let array_path =
        match unsafe { CStr::from_ptr(array_path) }.to_str() {
            Ok(s) => s,
            Err(_) => return -3,
        };

    let result = std::panic::catch_unwind(|| {
        let rt = match tokio::runtime::Runtime::new() {
            Ok(rt) => rt,
            Err(_) => return Err(-4),
        };

        rt.block_on(
            read_array_f32(
                store_path,
                array_path,
            )
        )
    });

    let values = match result {
        Ok(Ok(values)) => values,
        Ok(Err(rc)) => return rc,
        Err(_) => return -5,
    };

    let n = values.len();

    let bytes = match n.checked_mul(
        std::mem::size_of::<f32>()
    ) {
        Some(bytes) => bytes,
        None => return -6,
    };

    let ptr_out = unsafe {
        libc::malloc(bytes) as *mut f32
    };

    if ptr_out.is_null() && n != 0 {
        return -7;
    }

    unsafe {
        ptr::copy_nonoverlapping(
            values.as_ptr(),
            ptr_out,
            n,
        );

        *data = ptr_out;
        *count = n;
    }

    0
}


#[unsafe(no_mangle)]
pub extern "C" fn icechunk_get_array_1d_f32_size(
    store_path: *const libc::c_char,
    array_path: *const libc::c_char,
    count: *mut usize,
) -> i32 {
    if store_path.is_null() || array_path.is_null() || count.is_null() {
        return -1;
    }

    let store_path = match unsafe { CStr::from_ptr(store_path) }.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let array_path = match unsafe { CStr::from_ptr(array_path) }.to_str() {
        Ok(s) => s,
        Err(_) => return -3,
    };

    let rt = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(_) => return -4,
    };

    let result = rt.block_on(async {
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

        let shape = match node.node_data {
            icechunk::format::snapshot::NodeData::Array { shape, .. } => shape,
            _ => return Err(-15),
        };

        if shape.len() != 1 {
            return Err(-16);
        }

        let dim = shape.get(0).ok_or(-16)?;

        Ok::<usize, i32>(dim.array_length() as usize)
    });

    match result {
        Ok(n) => {
            unsafe {
                *count = n;
            }
            0
        }
        Err(rc) => rc,
    }
}


async fn read_array_1d_f32(
    store_path: &str,
    array_path: &str,
) -> Result<Vec<f32>, i32> {
    use std::path::Path as StdPath;
    use std::sync::Arc;

    use icechunk::format::ByteRange;
    use icechunk::format::Path;
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

    // Get the logical array shape.
    let node = session
        .get_array(&path)
        .await
        .map_err(|_| -14)?;

    let shape = match node.node_data {
        NodeData::Array { shape, .. } => shape,
        _ => return Err(-15),
    };

    // This POC deliberately supports only 1-D arrays.
    if shape.len() != 1 {
        return Err(-16);
    }

    let dim = shape.get(0).ok_or(-16)?;
    let array_len = dim.array_length() as usize;

    let mut output = vec![0.0f32; array_len];

    // Iterate over the actual chunks known to Icechunk.
    let chunks = session.array_chunk_iterator(&path).await;

    futures_util::pin_mut!(chunks);

    use futures_util::StreamExt;

    let mut chunk_size: Option<usize> = None;

    while let Some(chunk_result) = chunks.next().await {
        let chunk = chunk_result.map_err(|_| -17)?;

        let coord = chunk.coord;

        if coord.0.len() != 1 {
            return Err(-18);
        }

        let chunk_index = coord.0[0] as usize;

        let reader = session
            .get_chunk_reader(
                &path,
                &coord,
                &ByteRange::from_offset(0),
            )
            .await
            .map_err(|_| -19)?;

        let reader = match reader {
            Some(reader) => reader,
            None => continue,
        };

        let compressed = reader.await.map_err(|_| -20)?;

        let decoded = zstd::decode_all(compressed.as_ref())
            .map_err(|_| -21)?;

        if decoded.len() % std::mem::size_of::<f32>() != 0 {
            return Err(-22);
        }

        let stored_count =
            decoded.len() / std::mem::size_of::<f32>();

        if chunk_size.is_none() {
            chunk_size = Some(stored_count);
        }

        let stride = chunk_size.unwrap();

        let start = chunk_index
            .checked_mul(stride)
            .ok_or(-23)?;

        if start >= array_len {
            continue;
        }

        let copy_count = stored_count.min(array_len - start);

        for i in 0..copy_count {
            let offset = i * 4;

            let bytes = [
                decoded[offset],
                decoded[offset + 1],
                decoded[offset + 2],
                decoded[offset + 3],
            ];

            output[start + i] = f32::from_le_bytes(bytes);
        }
    }

    Ok(output)
}



async fn list_nodes(
    store_path: &str,
) -> Result<String, i32> {
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

    let nodes = session
        .list_nodes(&Path::root())
        .await
        .map_err(|_| -13)?;

    let mut output = String::new();

    for node_result in nodes {
        let node = node_result.map_err(|_| -14)?;

        match &node.node_data {
            icechunk::format::snapshot::NodeData::Group => {
                output.push_str(&format!(
                    "G|{}\n",
                    node.path
                ));
            }

            icechunk::format::snapshot::NodeData::Array {
                shape,
                ..
            } => {
                #[derive(serde::Deserialize)]
                struct ArrayDataType {
                    data_type: serde_json::Value,
                }

                // #[derive(serde::Deserialize)]
                // struct ArrayDataType {
                    // data_type: String,
                // }

                let meta: ArrayDataType =
                    serde_json::from_slice(&node.user_data)
                        .map_err(|_| -15)?;

                let dtype = match &meta.data_type {
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                };

                // output.push_str(&format!(
                    // "META|{}\n",
                    // String::from_utf8_lossy(&node.user_data)
                // ));

                // output.push_str(&format!(
                    // "  dtype={}\n",
                    // meta.data_type
                // ));

                output.push_str(&format!(
                    "A|{}|{}",
                    node.path,
                    dtype
                ));

                for dim in shape.iter() {
                    output.push_str(&format!(
                        "|{}",
                        dim.array_length()
                    ));
                }

                output.push('\n');
            }
        }
    }

    Ok(output)
}


#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_list_nodes(
    store_path: *const c_char,
    data: *mut *mut u8,
    len: *mut usize,
) -> i32 {
    if store_path.is_null()
        || data.is_null()
        || len.is_null()
    {
        return -1;
    }

    let store_path =
        match unsafe { CStr::from_ptr(store_path) }.to_str() {
            Ok(s) => s,
            Err(_) => return -2,
        };

    let rt = match tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(_) => return -3,
    };

    let result = rt.block_on(
        list_nodes(store_path)
    );

    let output = match result {
        Ok(output) => output,
        Err(rc) => return rc,
    };

    copy_to_c_buffer(
        output.into_bytes(),
        data,
        len,
    )
}


/// Copy a byte vector into a C-owned buffer.
fn copy_to_c_buffer(
    bytes: Vec<u8>,
    data: *mut *mut u8,
    len: *mut usize,
) -> i32 {
    let n = bytes.len();

    let ptr_out = unsafe {
        libc::malloc(n) as *mut u8
    };

    if ptr_out.is_null() && n != 0 {
        return -6;
    }

    unsafe {
        ptr::copy_nonoverlapping(
            bytes.as_ptr(),
            ptr_out,
            n,
        );

        *data = ptr_out;
        *len = n;
    }

    0
}


/// Free a buffer returned by either read function.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_free(data: *mut u8) {
    if !data.is_null() {
        unsafe {
            libc::free(data as *mut libc::c_void);
        }
    }
}
