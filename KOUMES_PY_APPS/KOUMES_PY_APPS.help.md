# Viewers

HTML pages that draw the content. The app hands them the path to the file and
the `window.__chroma` bridge; the rest is up to the page.

| file | what it draws |
|---|---|
| `dirs.exe.html` | directory listing - main view of the middle panel |
| `md-viewer.exe.html` | markdown with physical line numbers |
| `redline.exe.html` | drawing over an image (boxes, lines) |
| `help.html` | this help and its kin |

## How a file picks its viewer

The search runs bottom-up, from the file's directory to the sandbox root: first
`.t2l/<name>.html`, then `<name>.html`. What to use for which extension is
declared by `config.t2l` in a `type: viewer_ext` record.

Adding your own viewer is therefore a matter of dropping an `.html` somewhere
above the file it applies to. Nothing gets recompiled.
