# hg_interactive_applib - how to use it

For whoever builds an interactive application on it, and for a person or an agent who
drives such an application by its commands.

## Commands

Every application built on the module has these commands under its own prefix `<p>`
(the diagram viewer: `diag`). They come over the application's WebSocket, from its
toolbar and from the mouse - the same path for a human and an agent.

| command | what it does | reply |
|---|---|---|
| `<p>_xy x y [ctrl\|shift]` | a point into the active mode (a click); `ctrl` = add/remove from the selection, `shift` = a box by 2 points | |
| `<p>_reset` | one step back: a busy mode steps back, a mode on top ends, an idle one returns to the default | |
| `<p>_cmd_select` | mode select (the default) | |
| `<p>_cmd_pan` | moving the picture, on top of the active mode; 1st point grabs, 2nd ends | |
| `<p>_cmd_zoom` | zoom by a box (2 points), kept in the window's proportions | |
| `<p>_zoom_extent [kind]` | zoom so that all objects (of that kind) are in the window | `--EXTENT x1 y1 x2 y2` |
| `<p>_sel` | content of the selection | one `--ITEM` per object (and its data) |
| `<p>_save` | unsaved changes of the active source into its file | `--SAVED n --FILE path` |
| `<p>_state` | state of the application | `--FILE`, `--PORT`, `--STACK`, `--SOURCES`, `--SELECTED`, `--CHANGES` |
| `<p>_cross on [who] \| off` | a cross over the picture: an agent works on it, do not touch | `--CROSS on\|off` |
| `<p>_screenshot <png>` | snapshot of the active view | `--FILE` |
| `<p>_window <png>` | snapshot of the whole window | `--FILE --SIZE w h` |
| `<p>_help` | list of all commands of the application, its own ones too | `--CMD` lines |

Every reply also carries `--MODE <name>` (the active mode). An error comes as `--ERROR`.

```bash
echo 'diag_state' | websocat -n1 ws://127.0.0.1:<port>
```

The port: `<p>_state` tells it; an application starts on the first free port of its
range (the diagram viewer from 54335).

## Mouse

| | |
|---|---|
| click | `<p>_xy` into the active mode (select: selects the object under it) |
| ctrl+click | `<p>_xy ... ctrl` (select: adds or removes it) |
| shift+click, shift+click | the two corners of a box (select: adds what lies wholly inside) |
| shift + drag | the same box in one move |
| drag | the application decides (move, resize, pan) |
| right button | `<p>_reset` |
| wheel | zoom towards the mouse |

The floating panel in the view has the tabs **cmd** (mode buttons, hint and the active
mode's buttons), **files** (diagrams of the directory, a click selects, the next one
opens) and **log** (executed commands, errors red). Drag it by its title, resize it by
its edges.

## Building an application on it

1. Commands: subclass `CmdsInteractive(prefix)` and register your own commands next to
   the generic ones (`register(name, handler, description)`, as in `cmd_sys.Cmds`).
2. Root: subclass `InteractiveApp(prefix, default_mode, cmds, ws_default)`, keep one
   instance, add `drag_begin(x, y, view)`.
3. Modes: subclass `AppMode` (`name`, `hint`, `dialog`, `enter_point`, `enter_move`,
   `enter_reset`, `busy`, `snap`; `finish()` when a mode on top is done). Start a mode by
   a command made by `CmdsInteractive.mode(cls, once)`.
4. Objects: put them into the pool; each provides `hit(x, y, tol)` and `display(ents)`
   (appends entities: `EntityLine`, `EntityBox`, `EntityCircle`, `EntityText`,
   `EntityMark`, `EntityHandle`), optionally `describe(level)` and `hover(lines, cols)`.
5. View: subclass `InteractiveView` and set `APP`, `SOURCE`, `TOOLBAR`, `ICONS`,
   `SUFFIX` (and `GRID`, `DRAG_PX` when they differ).

Dynamics during a mode: `view.dyn_clear()`, `dyn_box(a, b)`, `dyn_dot(a)`, `dyn_add(ent)`.

How the module is built: `hg_interactive_applib.recipe.md`.
