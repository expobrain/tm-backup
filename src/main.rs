#[macro_use]
extern crate clap;

use clap::{App, Arg, SubCommand};
use log::{debug, error, info, warn};

const PREFIX: &str = "back-";

fn main() {
    simple_logger::init().unwrap();

    let matches = App::new("tm-backup")
        .version("0.1.0")
        .author("Daniele Esposti <daniele.esposti@gmail.com>")
        .about("")
        .arg(
            Arg::with_name("SOURCE")
                .help("Source path")
                .required(true)
                .index(1),
        )
        .arg(
            Arg::with_name("DEST")
                .help("Destination path")
                .required(true)
                .index(2),
        )
        .get_matches();

    // Same as above examples...
}
