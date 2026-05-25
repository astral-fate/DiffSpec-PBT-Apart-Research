# Path Sanitization

Given a user-supplied filesystem path string, return a sanitized path that has had all of the following stripped: parent-directory components (`..`), leading slashes (turning absolute paths into relative ones), and null bytes (`\x00`). The result must contain none of these three.
