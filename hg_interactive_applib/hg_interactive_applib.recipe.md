# hg_interactive_applib - recipe

A description precise enough to write the module again, in any language, and get the
same module: its parts, files, classes, functions, interfaces and the decisions behind
them. File names are given without an extension.

## What it is

The layer of an interactive application over the object pool (`hg_pool_py`): modes on a
stack, mouse input turned into commands, the commands every interactive application has,
and a Qt view that draws the pool's objects. A concrete application (the diagram viewer)
adds its objects, a few modes and a few commands.

Depends on `cmd_sys` (the `Cmds` base: commands with a prefix, log, WebSocket) and on
`hg_pool_py` (`POOL`, `SELSET`, `SOURCES`, `Sel`, `Ref`, `RefCol`). Modelled on the CAD
interaction layer (`hg_interact`: Cmd, CmdQueue, Scene, WidgetInteract; entities as in
`hg_display`) with MicroStation logic, not a 1:1 port.

Split into two halves:
- **without Qt:** the modes, the commands and the root - the logic, usable and testable
  without a window;
- **Qt:** entities, scene, panel, view - drawing and the widget.

## Decisions

- **Not cmd_sys.** cmd_sys parses and dispatches commands; modes, points and views are an
  interaction layer on top of it.
- **Everything is a command.** A mode is started by a command; input into a mode comes
  only as `<prefix>_xy x y [mods]` (mods: `ctrl`, `shift`), reset as `<prefix>_reset`.
  A human and an agent use the same path; it is logged and broadcast.
- **Only points and reset are commands.** Mouse movement (dynamics) goes into the active
  mode directly, not logged, not broadcast.
- **The view is an argument** of every call into a mode (like CAD `enterPoint(pt, view)`);
  the stack and the modes keep no view.
- **A mode counts its steps by collected points** (like CAD `points_`); a click accepts.
- **Selection lives in the pool** (`SELSET`); here only the modes change it.
- **An object only turns itself into entities** (`display`); the view draws entities and
  knows nothing about the objects' data. Entities know nothing about the object.
- **The pool knows nothing about drawing**: the scene makes its own refs that hold entities.
- **The commands keep no state**; they reach the application root through `app`.
- **One root per application** (its secondary singleton, application scope only).
- **Commands run under `POOL.lock`** (the lock of the `Cmds` base).
- English, no machine paths (public repo).

## Files

**One class per file**, the file named after the class in snake_case (`AppMode_select` ->
`app_mode_select`, `RefColScene` -> `ref_col_scene`). Module-level helpers and constants
live in the file of the class they belong to (named below). The groups below are only
for reading; they are not files.

### `__init__`

Exports every class of the module, and `box_ratio`, `C_BG`, `C_SEL`, `C_DYN`,
`make_pen`, `on_layer`, `on_screen`, `ents_bound`, `paint_ents`. Users import from the
package, never from its files.

### Modes and their stack (no Qt): `app_mode`, `app_mode_stack`, `app_mode_select`, `app_mode_pan`, `app_mode_zoom`

Constant `C_MARK = #e2d2f3` (in `app_mode_select`): background of a content line that has its own object.

**`AppMode`** - base of a mode.
- class fields: `name = "void"`, `snap = True` (points into the mode snap to the grid);
- fields: `queue` (set by the stack), `once` (pushed on top);
- `hint() -> text` (HTML allowed), default `""`;
- `dialog() -> [(label, command)]` - buttons of the mode, default none;
- `enter_point(x, y, view)`, `enter_move(x, y, view)`, `enter_reset(view)` - default nothing;
- `busy() -> bool` - in progress? (reset then steps back instead of ending), default false;
- `finish()` - a mode pushed on top is done: `queue.remove(self)`.

**`AppModeStack(default_mode)`** - like CAD CmdQueue; `default_mode` is a class.
- fields: `default_mode`, `stack` (the active mode is the last), `mods` (set of modifiers
  of the last point), `listeners` (functions called after every change);
- the constructor adds `default_mode()`;
- `active()` - the last on the stack;
- `add(mode, once=False, view=None)`: sets `mode.queue`, `mode.once`; once=false replaces
  the stack - when a view is given, every mode on it gets `enter_reset(view)` first;
  once=true pushes on top; then `changed()`;
- `remove(mode)`: removes it only when the stack has more than one mode; `changed()`;
- `point(x, y, view, mods=())`: `mods` becomes the set; `active().enter_point`; `changed()`;
- `move(x, y, view)`: `active().enter_move` (no `changed`);
- `reset(view)`: the active mode is `once` or `busy` -> its `enter_reset`; else when it
  is not an instance of the default class -> `add(default_mode(), view=view)`; else its
  `enter_reset`; then `changed()`;
- `changed()`: calls every listener (over a copy of the list).

**`AppMode_select`** - default mode, `name = "select"`.
- fields: `corner` (1st point of the box, none), `under` (id of the object under the
  mouse), `under_text` (its content), `room = (6, 40)` (lines, columns that fit the panel);
- `hint()`: with a corner "shift+click the other corner (right button = back)", else
  "click selects, ctrl+click adds/removes, shift: rectangle by 2 points, drag moves the
  selected". Then the name and content: when exactly one object is selected it wins over
  the mouse (its `id` and `hover(lines, cols)` if it has `hover`), else `under` and
  `under_text`. A name adds `<br><b>name</b>`; content as a list `[(line, marked)]` puts
  marked lines in a span with background `C_MARK`, a string is escaped; content goes into
  `<pre style="font-size:9pt">`;
- `enter_point`: with `shift` in `queue.mods` - no corner: remember it and end; with a
  corner: under `POOL.lock` every object of `view.objs_in(corner, point)` with selection
  `NONE` gets `SELSET.set(obj, Sel.SEL)` (additive), then `enter_reset`. Without shift:
  `enter_reset`, `hit = view.pick(x, y)`, with `ctrl` `SELSET.toggle(hit)`, else
  `SELSET.click(hit)`;
- `enter_move`: with a corner `view.dyn_clear()` and `view.dyn_box(corner, view.snap(x, y))`;
  `room = view.hover_room()`; with exactly one selected end here; else pick the object
  under the mouse, and when its id differs from `under`, store id and its `hover(room)`
  and call `view.refresh_bar()`;
- `enter_reset`: a corner is dropped together with the dynamics;
- `busy()`: a corner exists.

**`AppMode_pan`** - `name = "pan"`, `snap = False`; field `grab`.
- `hint()` "drag the picture";
- `enter_point`: no grab -> remember it; else `finish()`;
- `enter_move`: with a grab `view.pan_by(x - grab.x, y - grab.y)` (the scene point under
  the mouse returns to the grabbed place);
- `enter_reset`: `finish()`.

**`box_ratio(a, b, ratio) -> (x1, y1, x2, y2)`** (in `app_mode_zoom`) - box from corner `a` towards `b`,
widened to `ratio` = width/height (as CAD `Cmd_zoomBox::newDisplay_`): `dx, dy = b - a`,
each at least 1e-9 in size (sign kept); if `ratio > |dx/dy|` then `dx = sign(dx)*|dy*ratio|`
else `dy = sign(dy)*|dx/ratio|`; result `(a.x, a.y, a.x+dx, a.y+dy)`.

**`AppMode_zoom`** - `name = "zoom"`, `snap = False`; field `corner`.
- `hint()` "enter first point of box" / "enter second point of box";
- `enter_point`: no corner -> remember; else `box_ratio(corner, point, view.ratio())`,
  drop the corner, `view.dyn_clear()`, `view.zoom_to(box)`, `finish()`;
- `enter_move`: with a corner the box by `box_ratio` as dynamics (`dyn_clear`, `dyn_box`)
  and `view.dyn_dot(corner)`;
- `enter_reset`: a corner -> drop it with the dynamics; none -> `finish()`;
- `busy()`: a corner exists.

### The commands every interactive application has (no Qt): `cmds_interactive`

**`CmdsInteractive(prefix)`** - derives from `cmd_sys.Cmds(prefix, POOL.lock)`; field
`app` (the root, set by `InteractiveApp`). Registers, with these descriptions:

| command | handler |
|---|---|
| `<p>_xy x y [ctrl\|shift]` | no view or < 2 args -> error "no view or coordinates"; else `app.queue.point(float x, float y, app.view, rest)`; a value or runtime error becomes the error text |
| `<p>_reset` | no view -> error; else `app.queue.reset(app.view)` |
| `<p>_cmd_select` | `app.queue.add(AppMode_select(), once=False, view=app.view)` |
| `<p>_cmd_pan` | the same with `AppMode_pan`, once=true |
| `<p>_cmd_zoom` | the same with `AppMode_zoom`, once=true |
| `<p>_zoom_extent [kind]` | no view -> error; `r = view.extent(kind)`; empty -> error "nothing there"; `view.zoom_to(r)`; reply `"x1 y1 x2 y2"` as `EXTENT` |
| `<p>_sel` | for each selected item: its `describe(level name)` if it has it, else one `ITEM` "key kind level id" |
| `<p>_save` | no active source (`SOURCES.active`) -> error; `n = changes`, `save()`; reply `SAVED n`, `FILE id` |
| `<p>_state` | `FILE` active source id (or empty), `PORT` (WebSocket port or 0), `STACK` mode names, `SOURCES` count; with a source also `SELECTED` (`SELSET.selected_key(id)`) and `CHANGES` |
| `<p>_cross on [who] \| off` | no arg -> error; every view `set_cross(who or "KOUMES")` for on, `""` for off; reply `CROSS on/off` |
| `<p>_screenshot <png>` | `app.view.grab()` saved; reply `FILE` |
| `<p>_window <png>` | grab of the view's whole window, scaled to the window size when the device pixel ratio is not 1; reply `FILE`, `SIZE "w h"` |

- `mode(cls, once=False)` - returns the handler of a command that starts a mode;
- an application subclasses it and registers its own commands next to these.

### The root (no Qt): `interactive_app`

**`InteractiveApp(prefix, default_mode, cmds, ws_default=0)`**
- fields: `prefix`, `queue = AppModeStack(default_mode)`, `cmds` (and `cmds.app = self`),
  `ws_default`, `views` (a weak set: whose bar and log to refresh), `view` (the active
  view, where input goes);
- wiring: `queue.listeners += changed`; `cmds.changed = changed`; `cmds.mode` returns the
  active mode's name (it goes into every reply as `MODE`);
- `active_view()`;
- `execute(line, view=None)`: a given view becomes the active one; `cmds.run(line)` -
  from code the same as from an agent (logged, broadcast, under the lock);
- `start_ws(port=0)`: `cmds.start_ws(port, ws_default)` - the port exactly, or the first
  free one from `ws_default` (the application gives its range: the diagram viewer 54335);
- `drain()`: `cmds.drain()` - WebSocket lines run on the main thread;
- `point(x, y, view, mods=())`: when the active mode has `snap`, `(x, y) = view.snap(x, y)`;
  then `execute("<p>_xy %g %g[ mod...]", view)`;
- `move(x, y, view)`: the view becomes active; `queue.move` (dynamics, not a command);
- `reset(view)`: `execute("<p>_reset", view)`;
- `changed()`: `refresh_bar()` of every view; a view whose widget is already gone
  (runtime error) is dropped, and if it was the active one, `view` becomes none;
- the application adds `drag_begin(x, y, view)` (called by the view when a drag starts:
  move, resize or pan - its own decision).

### Drawn elements (Qt): `entity`, `canvas`, `entity_line`, `entity_box`, `entity_circle`, `entity_text`, `entity_mark`, `entity_handle`

Constants (in `entity`, with `make_pen`, `on_layer`, `on_screen`): `C_SEL = #c2407e` (selection), `C_BG = #ffffff` (background, inside of an empty
circle); `LINE_STYLES`: `solid`, `dash`, `dot`.

- **`Canvas(painter, scale)`** - where entities draw: a painter already in scene
  coordinates, and the scale (pixels per unit);
- **`make_pen(color, width, style="solid")`** - pen with the line style (unknown = solid);
- **`Entity`** - fields `layer = 0`, `px = false` (line width in screen pixels);
  `draw(canvas)` abstract, `bound() -> rect` (default empty);
- **`on_layer(layer, ents)`** - sets `layer` of all, returns them;
- **`on_screen(ents)`** - sets `px` and a cosmetic pen (width independent of the scale);
  used for dynamics and selection;
- **`EntityLine(p1, p2, color, width, style)`** - a line; bound = normalized rect p1-p2;
- **`EntityBox(rect, color, width, fill=None, style, radius=0)`** - a rounded rectangle,
  outline and optional fill; bound = rect;
- **`EntityCircle(center, r, color, width, fill=None)`** - with fill: filled, no outline;
  without: outline of `width` (cosmetic when `px`), inside `C_BG`; bound = square around;
- **`EntityText(doc, at)`** - formatted text document drawn with its top left at `at`;
  bound = `at` + document size;
- **`EntityMark(at, d, items, color, width)`** - a mark in screen pixels around `at`, x
  axis along the unit vector `d`, y across; items `("item_line", (x1, y1, x2, y2, w))` and
  `("item_circle", (x, y, r, fill))`; a point maps to `at + (x*ux - y*uy, x*uy + y*ux) / scale`;
  `px = true`; bound = the point;
- **`EntityHandle(at)`** - a handle: square of `PX = 7` screen pixels, outline `C_SEL`
  1 px, inside `C_BG`; bound = the point.

### A collection that is drawn (Qt): `ref_scene`, `ref_col_scene`

- **`RefScene(obj, parent)`** (a `Ref`) - holds the object's entities `ents`;
  `repaint()`: `ents = []`, `obj.display(ents)`, `parent.dirty = true`;
- **`RefColScene`** (a `RefCol`) - `make_ref(obj)` makes a `RefScene`;
  `entities()` = entities of all refs sorted by `layer` (stable sort, higher on top);
  `ordered()` = objects sorted by `obj.Z` (the pick order);
- **`paint_ents(painter, ents, scale)`** (in `ref_col_scene`, with `ents_bound`) - draws them through one `Canvas`;
- **`ents_bound(ents)`** - union of their bounds.

### Floating window inside the view (Qt): `flow_layout`, `float_panel`

- **`FlowLayout(parent=None, spacing=3)`** - items flow left to right and wrap like words;
  zero margins; height for width; minimum size = the largest item; placing goes by size
  hints and wraps when an item would cross the right edge (and the line is not empty).
- **`FloatPanel(parent)`** - a frame with a title strip and tabs:
  - constants `SIZE = (300, 250)`, `MARGIN = 8`, `EDGE = 5`, `MIN = (120, 80)`;
  - look: background `#f7f8fa`, border `#9aa4ae`; title " ⠿", 14 px high, background
    `#dde2e8`, text `#55606b`, 9 px, move cursor; tabs in document mode; margins `EDGE`
    (the edge belongs to the window, for resizing);
  - `add_tab(widget, name)` - the tab in a scroll area (vertical scroll only);
  - dragging the title moves the panel (and stays inside the view);
  - edges and corners resize it: a corner catches `2*EDGE`, a side only `EDGE`; the cursor
    follows the edge under the mouse; never smaller than `MIN`, never outside the parent;
    resizing by the left or top edge also counts as moved;
  - `keep_inside()`: never larger than the view minus `2*MARGIN` (at least 80); until the
    user resized it, it keeps `SIZE`; until the user moved it, it sits top right
    (`MARGIN` from the edges); always clamped into the view; raised on top.

### The Qt view (Qt): `diag_canvas`, `interactive_view`

Constant `C_DYN = #2b7bd9` (dynamics, in `interactive_view`).

**`DiagCanvas(view)`** - the drawing surface.
- fields `scale = 1`, `off = (0, 0)`: screen = scene * scale + off; mouse tracking on;
- `to_scene(p)`;
- paint: fill `C_BG`, antialiasing, transform, then `paint_ents` of
  `scene.entities() + view.err + view.dyn` (dynamics on top); with `view.cross` a red
  semi-transparent cross (6 px) over the whole widget and the text
  "pracuje agent - <who>" (bold, 16 pt) above the middle;
- `fit(rect, max_scale=1)`: scale = min(width/rect.w, height/rect.h, max_scale), the
  rect's centre to the widget's centre;
- `ensure_visible(rect, margin=40)`: shifts so the rect is at least `margin` px inside;
- wheel: zoom by 1.15 per step towards the mouse (the scene point under it stays);
- `pan_by(dx, dy)`: shift by scene units.

**`InteractiveView(path, parent=None)`** - a widget; the application subclasses it and
supplies the class fields:
- `APP` (the root), `SOURCE` (file source class with `THUMB` (w, h) and `THUMB_DIR`),
  `TOOLBAR` (tuples `(tip, command, icon, mode)`; mode none = a button without a state,
  after which the count of unsaved changes is shown), `ICONS` (icon directory with
  `dir.png` and `thumb_generic.png`), `SUFFIX` (file suffix of the application),
  `GRID = 10`, `DRAG_PX = 4`;
- signals `selected(record_no)`, `opened(path)`;
- construction: `path` = real path = source id, `SOURCES.open(SOURCE(path))`; fields `dyn`,
  `err`, `cross`; the canvas with this view as its event filter; the floating panel with
  tabs **cmd** (toolbar buttons in a `FlowLayout`, icons 22 px, tooltip "tip (command)",
  checkable when they have a mode, a click executes the command; under them the hint
  label, a separator and the mode's dialog buttons in a `FlowLayout`), **files** and
  **log** (monospace 9 px); cmd is the current tab; registers in `APP.views`, becomes
  `APP.view`; `ws_port = APP.start_ws()`; a timer every 30 ms calls `APP.drain`; the scene
  `RefColScene`, its listener redraws the canvas; `SELSET` listener `sel_changed`;
  `POOL.add_refcol(scene)` and remove on destruction; load the source, show its error,
  fit on first show, `refresh_bar()`;
- **files tab**: the path as links (each part switches the browsed directory), a 📂 button
  opening it in the file manager; icon list of directories (no hidden ones) and then the
  application's files (name without the suffix, tooltip the full name, icon from
  `THUMB_DIR/<name>.png`, else `thumb_generic.png`); tiles are rounded frames of half the
  thumb size with the picture fitted inside; a click into a directory enters it, the first
  click on a file selects it, the next click on the selected one runs `<p>_open "path"`;
  refreshed when the tab becomes current; `browse(dir)`, `refresh_files()`, `saved()`
  (refresh when the files tab is current);
- `open_file(path)`: reset the active mode (it may hold vanishing objects), clear dynamics,
  open and load the new source, fit, `refresh_bar()`, emit `opened`;
- `select(record_no)`: quietly (no `selected` signal) clear the selection, select the
  object of this source with that key and make it visible;
- `reload()`: the file changed on disk - keep the selected key, reset the active mode,
  reload the source, show its error, select again;
- `pick(x, y, kind=None)`: objects from the top (`scene.ordered()` reversed), the first
  of the kind with `obj.hit(x, y, tol)`, `tol = 5 px / scale`;
- `sel_changed()`: unless quiet, emit `selected` with the selected key of this source;
- `snap(x, y)`: round to `GRID`;
- `hover_room()`: (lines, columns) of text that fit the panel under the hint label:
  `max(3, (panel h - label top - 60) // 13)`, `max(20, (panel w - 20) // 6)`;
- `refresh_bar()`: rebuild the dialog buttons from `active().dialog()`, refresh the log,
  check the toolbar button of the bottom mode of the stack, hint `<b>name</b>: hint`, the
  label "N changes";
- log tab: the `cmds.log` lines, errors in `#c0392b`, scrolled to the end, rebuilt only
  when the log grew;
- `pan_by`, `ratio()` (canvas width / height), `extent(kind=None)` (union of the entity
  bounds of the refs, of that kind), `zoom_to((x1, y1, x2, y2))` (fit without a scale
  limit), `set_cross(who)`;
- dynamics: `dyn_clear()`, `dyn_add(ent)` (through `on_screen`), `dyn_box(a, b)` (dashed
  box `C_DYN` 1.4), `dyn_dot(a)` (filled circle r 3 `C_DYN`), `dyn_rect(rect)`;
  `objs_in(a, b)` = objects whose whole drawing lies inside the box;
- mouse (event filter on the canvas; no drag and drop events): left press remembers the
  point and ctrl / shift; right press = `APP.reset`; movement past `DRAG_PX` starts a drag -
  with shift the press point goes as `point(..., ("shift",))`, else `APP.drag_begin`;
  every movement goes to `APP.move`; left release = `APP.point` of the release point (drag)
  or the press point (click), mods `shift`, or `ctrl` only for a click;
- first fit: the whole extent plus 40 on each side, not above 1:1, once the widget has a
  real size (on show and resize, which also keep the panel inside).

## Interfaces an application supplies

- **An object in the pool:** `id`, `key`, `kind`, `source`, `Z` (pick order),
  `sel` (selection level), `hit(x, y, tol) -> bool`, `display(ents)` (appends its
  entities), `SEL_MAX`; optional `describe(level) -> [(value, name)]` for `<p>_sel` and
  `hover(lines, cols) -> text | [(line, marked)]` for the hint.
- **A source** (`SOURCE`): constructor `(path)`, `id`, `load()`, `reload() -> bool`,
  `save()`, `changes`, `error`, `THUMB`, `THUMB_DIR`.
- **A view for the modes:** `snap`, `pick`, `pan_by`, `ratio`, `zoom_to`, `objs_in`,
  `hover_room`, `refresh_bar`, `dyn_clear`, `dyn_box`, `dyn_dot`, `set_cross`, `grab`,
  `window`.
- **The root:** `drag_begin(x, y, view)`.

## Name

The directory is `hg_interactive_applib` since 2026-10-29, before `hg_interactive_app`;
the module docstrings still use the old name.
