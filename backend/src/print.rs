use std::io::Write;

use anyhow::{Context, Result};
use escpos::{
    driver::NativeUsbDriver,
    printer::Printer,
    utils::{BitImageOption, BitImageSize, DebugMode, Protocol},
};

const VENDOR_ID: u16 = 0x04b8;
const PRODUCT_ID: u16 = 0x0e28;

pub struct LocalPrinter;

impl LocalPrinter {
    pub fn print_bit_image(path: &str) -> Result<()> {
        let driver = NativeUsbDriver::open(VENDOR_ID, PRODUCT_ID).unwrap();
        let mut printer = Printer::new(driver, Protocol::default(), None);
        printer
            .debug_mode(Some(DebugMode::Hex))
            .init()?
            .bit_image_option(
                path,
                BitImageOption::new(Some(576), None, BitImageSize::Normal)?,
            )?
            .feed()?
            .print_cut()?;
        Ok(())
    }

    pub fn print_bit_image_bytes(bytes: &[u8]) -> Result<()> {
        let mut file = tempfile::Builder::new()
            .suffix(".png")
            .tempfile()
            .context("while creating temporary file")?;
        file.write_all(bytes)
            .context("while writing image to temporary file")?;
        let path = file
            .path()
            .to_str()
            .context("temporary file path is not valid UTF-8")?;
        Self::print_bit_image(path)
    }
}
