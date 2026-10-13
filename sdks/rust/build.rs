// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Generates the client from openapi.yaml with progenitor.
//!
//! progenitor reads OpenAPI 3.0 and this spec says 3.1, so the document is
//! rewritten first (see `down_convert`). The rewrite happens in memory; the
//! file the crate keeps is a byte for byte copy of docs/openapi.yaml, which CI
//! checks.

use std::{env, fs, path::Path};

use serde_json::Value;

fn main() {
    let src = "openapi.yaml";
    println!("cargo:rerun-if-changed={src}");
    println!("cargo:rerun-if-changed=build.rs");

    let text = fs::read_to_string(src).expect("read openapi.yaml");
    let mut doc: Value = serde_yaml::from_str(&text).expect("parse openapi.yaml");
    down_convert(&mut doc);
    let spec = serde_json::from_value(doc).expect("the converted spec is not OpenAPI 3.0");

    let mut settings = progenitor::GenerationSettings::default();
    settings
        .with_interface(progenitor::InterfaceStyle::Builder)
        .with_inner_type(quote::quote!(crate::State));
    let mut generator = progenitor::Generator::new(&settings);
    let tokens = generator
        .generate_tokens(&spec)
        .expect("progenitor could not generate the client");
    let ast = syn::parse2(tokens).expect("generated code does not parse");
    let content = prettyplease::unparse(&ast);

    let out = Path::new(&env::var("OUT_DIR").expect("OUT_DIR")).join("codegen.rs");
    fs::write(out, content).expect("write codegen.rs");
}

/// Turns the 3.1 document into one progenitor accepts.
///
/// 1. The version string becomes 3.0.3, because progenitor refuses anything
///    else. The spec only uses 3.1 in one place: `type: [X, "null"]`, which
///    becomes `type: X` with `nullable: true`.
/// 2. Error responses are dropped from every operation. progenitor allows one
///    response type per operation and the spec has several error shapes. The
///    status is still reported: the generated call returns
///    `Error::UnexpectedResponse`, and the retry layer in src/transport.rs has
///    parsed the `{"detail", "code"}` body by then (see `ApiError`).
/// 3. Operations that take `multipart/form-data` are dropped, because
///    progenitor cannot send it. `Client::ingestion_upload_csv` in src/lib.rs
///    covers the one that exists.
fn down_convert(doc: &mut Value) {
    doc["openapi"] = Value::from("3.0.3");
    nullable_types(doc);

    let Some(paths) = doc.get_mut("paths").and_then(Value::as_object_mut) else {
        return;
    };
    for item in paths.values_mut() {
        let Some(item) = item.as_object_mut() else {
            continue;
        };
        item.retain(|_, op| !takes_multipart(op));
        for op in item.values_mut() {
            if let Some(responses) = op.get_mut("responses").and_then(Value::as_object_mut) {
                responses.retain(|status, _| status.starts_with('2'));
            }
        }
    }
    paths.retain(|_, item| {
        item.as_object().is_some_and(|map| {
            map.keys().any(|key| {
                matches!(
                    key.as_str(),
                    "get" | "put" | "post" | "delete" | "patch" | "head" | "options"
                )
            })
        })
    });
}

fn takes_multipart(op: &Value) -> bool {
    op.pointer("/requestBody/content")
        .and_then(Value::as_object)
        .is_some_and(|content| content.contains_key("multipart/form-data"))
}

fn nullable_types(node: &mut Value) {
    match node {
        Value::Object(map) => {
            if let Some(Value::Array(types)) = map.get("type") {
                let names: Vec<Value> = types
                    .iter()
                    .filter(|t| t.as_str() != Some("null"))
                    .cloned()
                    .collect();
                let had_null = names.len() != types.len();
                if names.len() == 1 {
                    map.insert("type".to_string(), names[0].clone());
                } else {
                    map.remove("type");
                }
                if had_null {
                    map.insert("nullable".to_string(), Value::Bool(true));
                }
            }
            for child in map.values_mut() {
                nullable_types(child);
            }
        }
        Value::Array(items) => {
            for child in items {
                nullable_types(child);
            }
        }
        _ => {}
    }
}
