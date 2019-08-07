extern crate libc;

#[no_mangle]
pub extern "C" fn rust_hello() {
    println!("Hello, world! (RUST)");
}

#[cfg(test)]
mod tests {
    #[test]
    fn it_works() {
        assert_eq!(2 + 2, 4);
    }
}
