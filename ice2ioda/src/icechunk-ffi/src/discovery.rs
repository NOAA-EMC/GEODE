// use std::ffi::CStr;
// use std::ptr;

use std::path::Path as StdPath;
use std::sync::Arc;

use icechunk::format::{Path};
// use icechunk::format::{ByteRange, ChunkIndices, Path};
use icechunk::repository::VersionInfo;
use icechunk::Repository;


pub(crate) async fn list_nodes(
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
