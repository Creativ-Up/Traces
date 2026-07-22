#[path = "../src/print.rs"]
mod print;

fn main() -> anyhow::Result<()> {
    let path = std::env::args().nth(1).expect("usage: test_print <image.png>");
    print::LocalPrinter::print_bit_image(&path)
}
