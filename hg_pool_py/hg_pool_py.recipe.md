# hg_pool_py - recipe

A description precise enough to write the module again, in any language, and get the
same module: its parts, files, classes, functions, interfaces and the decisions behind
them. File names are given without an extension.

## What it is

The object pool of an interactive application: every object lives in one pool and
carries its identity; collections with filters refer to objects (a selection, a
source's objects, a drawn scene); changes are resolved under a lock. No Qt, no drawing,
standard library only (it will move to its own repo). Modelled on the CAD interaction
layer (GObjectPool, GObject, Ref, RefCol, UpdateLock), not a 1:1 port.

## Decisions

- **Identity of an object is `(source, key)`.** `source` is the id of its source (a
  normalized file path, a database id, ...), `key` its id inside the source (record order
  in a t2l file, a row id, ...). The object never points to a document object.
- **The pool owns objects; collections only refer.** A collection keeps `Ref`s chosen by
  its `Filter`; the pool keeps membership in sync. Nobody else adds or removes refs.
- **Selection is a pool collection**: the object keeps a numeric flag `sel`, the
  selection is a collection filtered on it. When a click selects (modes) is not here.
- **No drawing here.** `Ref` is membership only. A drawing collection (a scene) lives in
  another module: it subclasses `RefCol`, makes its own `Ref` subclass in `make_ref` and
  keeps what it draws there. `PoolObj.display(lst)` is the contract for it; the pool
  never calls it.
- **Changes under a lock.** Every change of an object calls `modified()`; under
  `POOL.lock()` the pool resolves them after the outermost lock is released. Without a
  lock each change is resolved at once. An application runs each command under one lock.
- **A source does not own its objects.** They live in the pool and carry the source id;
  the source knows them through its own collection.
- **One class per file**, the file named after the class in snake_case; a singleton
  instance lives in the file of its class. Users import from the package, never from
  its files.
- English, no machine paths (public repo).

## Files

### `__init__`

Exports `POOL`, `Pool`, `PoolObj`, `Ref`, `Filter`, `FilterSource`, `RefCol`, `Sel`,
`FilterSelection`, `SELSET`, `RefColSelection`, `Source`, `SourceFile`, `SOURCES`,
`Sources`.

### `pool_obj` - **`PoolObj(source, key, oid="", st=None)`**

An object in the pool: identity and a selection flag, not graphics.
- class fields: `kind = ""` (what it is, e.g. "node"), `Z = 0` (pick priority, higher
  first), `SEL_MAX = 1` (how many selection levels it has);
- fields: `source`, `key`, `id` (= `oid`, readable id), `st` (its data, a dict; a new one
  when none is given), `sel = 0`, `refs` (the refs of the collections holding it);
- the constructor registers it: `POOL.register(self)`;
- `modified()`: `POOL.changed(self)` - resolved once the lock is released;
- `set_sel(level)`: when different, store it and `modified()`;
- `display(lst, plain=False)`: contract for drawing collections - append what draws the
  object (`plain` = without selection marks); base does nothing;
- `hit(x, y, tol) -> bool`: does the point hit the object, from its own data; base false;
- `destroy()`: remove every ref from its collection, `POOL.unregister(self)`.

### `ref` - **`Ref(obj, parent)`**

Membership of one object in one collection. Fields `obj`, `parent`; the constructor
appends itself to `obj.refs`. `repaint()`: the object changed - base only sets
`parent.dirty = true`.

### `filter` - **`Filter`**

`pass_(obj) -> bool` (the trailing underscore because `pass` is a keyword): base passes
everything.

### `filter_source` - **`FilterSource(source)`** (a `Filter`)

Field `source`; passes objects with `obj.source == source`.

### `ref_col` - **`RefCol(flt=None)`**

A collection of refs with a filter; membership is kept by the pool.
- fields: `filter` (the given one or a plain `Filter`), `refs`, `dirty = false`,
  `listeners` (functions called by `refresh_display`);
- `make_ref(obj)`: the ref kind of this collection - base `Ref(obj, self)`; a scene
  returns one that keeps its drawing;
- `objs()`: the objects of its refs;
- `ref_of(obj)`: the ref of `obj` whose parent is this collection, or none;
- `initialize()`: `sync` every object of the pool, `dirty = true`;
- `sync(obj)`: passes the filter and has no ref -> append `make_ref(obj)`, dirty; does not
  pass and has a ref -> `remove(ref)`;
- `remove(ref)`: out of `refs` and out of `ref.obj.refs`, dirty;
- `refresh_display()`: call every listener (over a copy); a listener raising a runtime
  error (a dead Qt widget behind it) is dropped.

### `pool` - **`Pool`** and the singleton **`POOL`**

All objects, all collections, the changed ones, the lock.
- fields: `objs`, `refcols`, `_changed` (objects waiting), `_lock` (depth);
- `add_refcol(rc)`: append, `rc.initialize()`, resolve;
- `remove_refcol(rc)`: out of `refcols`, remove all its refs;
- `register(obj)`: append to `objs`, `changed(obj)`;
- `unregister(obj)`: out of `objs` and out of `_changed`;
- `changed(obj)`: append to `_changed` once; with no lock held resolve at once;
- `lock()`: a context: depth +1, on exit -1, at 0 resolve (also after an exception);
- resolve (`_solve`): take the changed list (and start a new one); for each object still
  in the pool: `sync` it in every collection, then `repaint()` each of its refs; then
  every dirty collection gets `dirty = false` and `refresh_display()`.

### `sel` - **`Sel`** (an integer enum)

The meaning of `PoolObj.sel`: `NONE = 0`, `SEL = 1`, `HANDLES = 2` (selected with
handles shown).

### `filter_selection` - **`FilterSelection`** (a `Filter`)

Passes objects with `sel != NONE`.

### `ref_col_selection` - **`RefColSelection`** (a `RefCol`) and the singleton **`SELSET`**

The selection: a collection with `FilterSelection`. `SELSET` is created here and
registered with `POOL.add_refcol`.
- `items()`: the selected objects;
- `level(obj)`: its `Sel` (`NONE` for none);
- `click(obj)` (under the lock): none -> clear all; a selected object -> its next level,
  past `obj.SEL_MAX` back to `NONE`; an unselected one -> clear all, then it gets `SEL`;
- `toggle(obj)` (ctrl+click, under the lock): none -> nothing; selected -> `NONE`, else
  `SEL`; the rest stays;
- `set(obj, level)` (under the lock);
- `clear()` (under the lock): every selected object to `NONE`;
- `selected_key(source)`: key of the first selected object of that source, 0 when none.

### `source` - **`Source(sid)`**

A source of pool objects: id, its collection, unsaved changes. Loading and writing are
a subclass's.
- fields: `id`, `refcol = RefCol(FilterSource(sid))`, `error` (cannot be read, none),
  `_pending` (unsaved changes `{key: {attr: value}}`), `changes = 0` (count, each staged
  change +1), `listeners` (functions `f(source, what)`, what = "changed" | "saved");
- `objs()`: the objects of its collection sorted by `Z`;
- `item(key)`: its object with that key, or none;
- `load()` (under the lock): `unload()`, then `_load()`; returns `{key: object}` (they
  reach the collection after the lock);
- `unload()` (under the lock): `destroy()` every object of its collection;
- `reload() -> bool`: when `_outdated()` is false return false; else under the lock
  `load()` and give every pending change back to the new object with that key
  (`_apply`); true;
- `stage(changes)`: merge `{key: {attr: value}}` into `_pending`, `changes += 1`,
  notify "changed";
- `save()`: with pending changes `_write(pending)`; `_saved()`; clear pending, `changes = 0`,
  notify "saved";
- for a subclass: `_load() -> {key: object}` (base `{}`), `_write(pending)`,
  `_apply(obj, attrs)`, `_saved()` (hook, e.g. a preview), `_outdated()` (base true).

### `source_file` - **`SourceFile(path)`** (a `Source`)

A source in a file: id = the real (normalized) path.
- field `_last_written` (the content it wrote itself); property `path` (= id);
- `read()`: the whole file as text (utf-8), none when it cannot be read;
- `write_text(new)`: atomic - write `path + ".tmp"`, then replace; remember the content;
- `_outdated()`: the file can be read and differs from what it wrote itself - its own
  write is not a reason to reload.

### `sources` - **`Sources`** and the singleton **`SOURCES`**

The open sources; one is active (new objects go there).
- fields `items`, `active`;
- `open(src)`: for now only one open - close all others first; append, make it active,
  `POOL.add_refcol(src.refcol)`;
- `find(sid)`: the open source with that id, or none;
- `close(src)`: `unload()`, `POOL.remove_refcol(src.refcol)`, out of `items`; when it was
  active, the last remaining one becomes active (or none).

## Order of creation

`POOL` exists before anything else; `SELSET` is created and registered when the package
is imported; `SOURCES` is empty until an application opens a source. Import order inside
the package follows the dependencies: `pool` <- `pool_obj`, `ref`, `filter` <-
`filter_source`, `ref_col` <- `sel`, `filter_selection`, `ref_col_selection` <- `source`
<- `source_file`, `sources`.
