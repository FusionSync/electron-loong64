#![no_std]
#[no_mangle]
pub static mut X: usize = 0;
#[no_mangle]
pub unsafe extern "C" fn store(v: usize) {
    X = v;
}
