use std::path::Path as StdPath;
use std::sync::Arc;

use icechunk::format::{ByteRange, ChunkIndices, Path};
use icechunk::repository::VersionInfo;
use icechunk::Repository;


pub(crate) async fn read_stored_chunk(
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
