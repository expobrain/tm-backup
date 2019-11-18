use std::path::PathBuf;

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
        let host;
        let path;

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

        match uri.find(':') {
            Some(n) => {
                host = uri[..n].to_string();
                path = PathBuf::from(uri[n + 1..].to_string());
            }
            None => panic!(format!("Not a valid SSH URI {}", src)),
        }

        Ok(SSHUri {
            original: src.to_string(),
            user,
            uri,
            host,
            path,
        })
    }

    pub fn join(&self, parts: &[&str]) -> Self {
        let path = parts.iter().fold(self.path.clone(), |acc, v| acc.join(v));

        SSHUri {
            original: self.original.clone(),
            user: self.user.clone(),
            uri: self.uri.clone(),
            host: self.host.clone(),
            path,
        }
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

    #[test]
    fn join() {
        let uri = SSHUri::from("user@host:/path/").unwrap();
        let result = uri.join(&["child1", "child2"]);

        let expected = SSHUri {
            original: "user@host:/path/".to_string(),
            user: Some("user".to_string()),
            uri: "host:/path/".to_string(),
            host: "host".to_string(),
            path: PathBuf::from("/path/child1/child2"),
        };

        assert_eq!(result, expected);
    }
}
