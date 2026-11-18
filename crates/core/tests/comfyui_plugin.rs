use std::collections::BTreeMap;
use std::path::Path;

use colab_playground_core::plugins::{
    PluginOrigin, PluginStore, resolve_endpoints, resolve_inputs,
};

#[test]
fn comfyui_video_plugin_installs_and_resolves() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../plugins/comfyui-video");
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path().join("data");
    let mut store = PluginStore::load(
        Some(&data.join("plugins")),
        Some(&data.join("plugins.json")),
    )
    .unwrap();
    let preview = store
        .inspect_folder(
            &root,
            &data.join("staging"),
            PluginOrigin::Folder {
                path: root.display().to_string(),
            },
        )
        .unwrap();
    assert_eq!(preview.manifest.id, "comfyui-video");
    store.install(&preview).unwrap();

    let reloaded = PluginStore::load(
        Some(&data.join("plugins")),
        Some(&data.join("plugins.json")),
    )
    .unwrap();
    assert!(reloaded.load_errors.is_empty(), "{:?}", reloaded.load_errors);
    let loaded = reloaded.get("comfyui-video").unwrap();
    let inputs = resolve_inputs(&loaded.manifest, &BTreeMap::new()).unwrap();
    let eps = resolve_endpoints(&loaded.manifest, &inputs.values).unwrap();
    assert_eq!(eps.len(), 1);
    assert_eq!(eps[0].remote_port, 8188);
    assert_eq!(eps[0].health.as_deref(), Some("/system_stats"));
}
