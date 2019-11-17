#[macro_use]
extern crate clap;

use log::{warn, info, error, debug};
use clap::{App, Arg};
use std::path::Path;

mod sshuri;

type SSHUri = String;

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

    let source = Path::new(matches.value_of("SOURCE").unwrap());
    let dest: SSHUri = matches.value_of("DEST").unwrap().to_string();

    info!("{}",source.display());
    info!("{}",dest);
}
