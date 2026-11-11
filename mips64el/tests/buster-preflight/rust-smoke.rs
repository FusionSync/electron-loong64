use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
fn main() {
    let counter = Arc::new(AtomicU64::new(0));
    let worker = Arc::clone(&counter);
    std::thread::spawn(move || {
        let values: Vec<u64> = (1..=1000).collect();
        worker.store(values.iter().sum(), Ordering::SeqCst);
    }).join().expect("thread join");
    assert_eq!(counter.load(Ordering::SeqCst), 500_500);
    let text = String::from("Electron MIPS64EL Rust std: 中文");
    assert!(text.is_char_boundary(text.len()));
    let path = std::env::temp_dir().join(format!("electron-mips64el-rust-smoke-{}", std::process::id()));
    std::fs::write(&path, text.as_bytes()).expect("file write");
    assert_eq!(std::fs::read_to_string(&path).expect("file read"), text);
    std::fs::remove_file(&path).expect("file remove");
    println!("{}; heap, threads, AtomicU64, UTF-8, and file I/O passed", text);
}
