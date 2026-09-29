use std::ffi::CStr;
use std::os::raw::c_char;
use std::ptr;

use crate::chunk::read_stored_chunk;
use crate::discovery::list_nodes;

use crate::reader::{
    copy_to_c_buffer,
};

use crate::array::{
    read_array_f32,
    read_array_f32_selection,
    read_array_f64,
};


/*
The functions in this file know nothing about icechunk.
These are wrappers that look like:

#[unsafe(no_mangle)]
pub extern "C" fn icechunk_read_array_f32(
    store_path: *const c_char,
    array_path: *const c_char,
    data: *mut *mut f32,
    count: *mut usize,
) -> i32 {
    // validate C pointers
    // convert strings
    // call reader
    // allocate C-compatible result
}
*/



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
pub extern "C" fn icechunk_read_array_f32_selection(
    store_path: *const c_char,
    array_path: *const c_char,
    start: *const usize,
    count: *const usize,
    ndim: usize,
    data: *mut *mut f32,
    nvalues: *mut usize,
) -> i32 {
    if store_path.is_null()
        || array_path.is_null()
        || start.is_null()
        || count.is_null()
        || data.is_null()
        || nvalues.is_null()
    {
        return -1;
    }

    if ndim == 0 {
        return -2;
    }

    let store_path =
        match unsafe { CStr::from_ptr(store_path) }.to_str() {
            Ok(s) => s,
            Err(_) => return -3,
        };

    let array_path =
        match unsafe { CStr::from_ptr(array_path) }.to_str() {
            Ok(s) => s,
            Err(_) => return -4,
        };

    let start = unsafe {
        std::slice::from_raw_parts(start, ndim)
    };

    let count = unsafe {
        std::slice::from_raw_parts(count, ndim)
    };

    let result = std::panic::catch_unwind(|| {
        let rt = match tokio::runtime::Runtime::new() {
            Ok(rt) => rt,
            Err(_) => return Err(-5),
        };

        rt.block_on(
            read_array_f32_selection(
                store_path,
                array_path,
                start,
                count,
            )
        )
    });

    let values = match result {
        Ok(Ok(values)) => values,
        Ok(Err(rc)) => return rc,
        Err(_) => return -6,
    };

    let n = values.len();

    let bytes = match n.checked_mul(
        std::mem::size_of::<f32>()
    ) {
        Some(bytes) => bytes,
        None => return -7,
    };

    let ptr_out = unsafe {
        libc::malloc(bytes) as *mut f32
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
        *nvalues = n;
    }

    0
}



#[unsafe(no_mangle)]
pub extern "C" fn icechunk_read_array_f64(
    store_path: *const c_char,
    array_path: *const c_char,
    data: *mut *mut f64,
    count: *mut usize,
) -> i32 {
    if store_path.is_null()
        || array_path.is_null()
        || data.is_null()
        || count.is_null()
    {
        return -1;
    }

    let store_path = match unsafe { CStr::from_ptr(store_path) }.to_str() {
        Ok(value) => value,
        Err(_) => return -2,
    };

    let array_path = match unsafe { CStr::from_ptr(array_path) }.to_str() {
        Ok(value) => value,
        Err(_) => return -3,
    };

    let runtime = match tokio::runtime::Runtime::new() {
        Ok(runtime) => runtime,
        Err(_) => return -4,
    };

    let values = match runtime.block_on(
        read_array_f64(store_path, array_path)
    ) {
        Ok(values) => values,
        Err(code) => return code,
    };

    let byte_len = values.len() * std::mem::size_of::<f64>();

    let buffer = unsafe {
        libc::malloc(byte_len) as *mut f64
    };

    if buffer.is_null() && byte_len != 0 {
        return -5;
    }

    unsafe {
        ptr::copy_nonoverlapping(
            values.as_ptr(),
            buffer,
            values.len(),
        );

        *data = buffer;
        *count = values.len();
    }

    0
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



/// Free a buffer returned by either read function.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn icechunk_free(data: *mut u8) {
    if !data.is_null() {
        unsafe {
            libc::free(data as *mut libc::c_void);
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


/*
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
*/
