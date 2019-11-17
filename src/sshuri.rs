use std::path::{Path, PathBuf};

#[derive(Eq, PartialEq, Debug)]
pub struct SSHUri {
    original: String,
    user: Option<String>,
    uri: String,
    host: String,
    path: PathBuf,
}

impl SSHUri {
    pub fn from(src: &str) -> Result<Self, String> {
        let user;
        let uri;

        match src.find('@') {
            Some(n) => {
                user = Some(src[..n].to_string());
                uri = src[n + 1..].to_string();
            }
            _ => {
                user = None;
                uri = src.to_string()
            }
        }

        let host = uri[..uri.find(":").unwrap()].to_string();
        let path = PathBuf::from(uri[uri.find(":").unwrap() + 1..].to_string());

        Ok(SSHUri {
            original: src.to_string(),
            user,
            uri,
            host,
            path,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_uri() {
        let result = SSHUri::from("user@host:/path/");

        let expected = Ok(SSHUri {
            original: "user@host:/path/".to_string(),
            user: Some("user".to_string()),
            uri: "host:/path/".to_string(),
            host: "host".to_string(),
            path: PathBuf::from("/path"),
        });

        assert_eq!(result, expected);
    }
}
