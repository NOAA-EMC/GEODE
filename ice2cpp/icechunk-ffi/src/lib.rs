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


#[unsafe(no_mangle)]
pub extern "C" fn icechunk_read_array_1d_f32(
    store_path: *const libc::c_char,
    array_path: *const libc::c_char,
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

    let store_path = match unsafe { std::ffi::CStr::from_ptr(store_path) }.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let array_path = match unsafe { std::ffi::CStr::from_ptr(array_path) }.to_str() {
        Ok(s) => s,
        Err(_) => return -3,
    };

    let result = std::panic::catch_unwind(|| {
        let rt = match tokio::runtime::Runtime::new() {
            Ok(rt) => rt,
            Err(_) => return Err(-4),
        };

        rt.block_on(read_array_1d_f32(store_path, array_path))
    });

    match result {
        Ok(Ok(values)) => {
            let n = values.len();

            let bytes = n
                .checked_mul(std::mem::size_of::<f32>())
                .ok_or(())
                .unwrap_or(0);

            let ptr = unsafe { libc::malloc(bytes) } as *mut f32;

            if ptr.is_null() && n != 0 {
                return -5;
            }

            unsafe {
                std::ptr::copy_nonoverlapping(values.as_ptr(), ptr, n);
                *data = ptr;
                *count = n;
            }

            0
        }

        Ok(Err(rc)) => rc,

        Err(_) => -6,
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



/// The function below is first draft, incorrect:
/// Read an entire float32 array by reading and decoding each chunk.
///
/// `num_chunks` is currently supplied by the caller.
/// The returned buffer contains all array values in logical order.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_read_array_f32(
    store_path: *const c_char,
    array_path: *const c_char,
    num_chunks: u32,
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

    let values = match runtime.block_on(async {
        let mut all_values: Vec<f32> = Vec::new();

        for chunk_index in 0..num_chunks {
            eprintln!("reading chunk {}", chunk_index);

            let compressed = read_stored_chunk(
                store_path,
                array_path,
                chunk_index,
            )
            .await?;

            let decoded = zstd::decode_all(compressed.as_slice())
                .map_err(|e| {
                    eprintln!(
                        "ERROR: Zstd decompression for chunk {}: {:?}",
                        chunk_index, e
                    );
                })?;

            if decoded.len() % 4 != 0 {
                eprintln!(
                    "ERROR: decoded chunk {} has {} bytes, \
                     not divisible by 4",
                    chunk_index,
                    decoded.len()
                );
                return Err(());
            }

            let chunk_values: Vec<f32> = decoded
                .chunks_exact(4)
                .map(|b| {
                    f32::from_le_bytes([
                        b[0], b[1], b[2], b[3]
                    ])
                })
                .collect();

            eprintln!(
                "chunk {}: {} values",
                chunk_index,
                chunk_values.len()
            );

            all_values.extend_from_slice(&chunk_values);
        }

        Ok::<Vec<f32>, ()>(all_values)
    }) {
        Ok(values) => values,
        Err(_) => return -5,
    };

    let n = values.len();

    let ptr_out = unsafe {
        libc::malloc(n * std::mem::size_of::<f32>())
            as *mut f32
    };

    if ptr_out.is_null() && n != 0 {
        return -6;
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
