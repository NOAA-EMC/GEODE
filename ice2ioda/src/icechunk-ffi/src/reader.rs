use std::ffi::CStr;
use std::ptr;

use std::path::Path as StdPath;
use std::sync::Arc;

use icechunk::format::{Path};
use icechunk::repository::VersionInfo;
use icechunk::Repository;


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


/// Copy a byte vector into a C-owned buffer.
pub(crate) fn copy_to_c_buffer(
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

