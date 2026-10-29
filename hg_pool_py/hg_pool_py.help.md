# hg_pool_py - how to use it

For whoever builds an application on the pool: objects, collections, selection and
sources.

## Commands

None. The module has no commands of its own; the commands that use it (selection,
saving, state) are in `hg_interactive_applib` (`<p>_sel`, `<p>_save`, `<p>_state`).

## Objects

```python
from hg_pool_py import POOL, PoolObj

class Node(PoolObj):
    kind = "node"
    Z = 10                       # picked before objects with a lower Z

    def hit(self, x, y, tol):    # from its own data
        ...

    def display(self, lst, plain=False):   # what draws it (for a scene)
        ...

with POOL.lock():                # changes resolved once, after the lock
    n = Node(source="/path/of/source", key=3, oid="server", st={"xy": (10, 20)})
    n.st["xy"] = (30, 40)
    n.modified()
```

An object registers itself in the pool when created and leaves it with `destroy()`.
Its identity is `(source, key)`.

## Collections

```python
from hg_pool_py import POOL, RefCol, FilterSource

col = RefCol(FilterSource("/path/of/source"))   # its objects, kept in sync by the pool
col.listeners.append(redraw)                     # called when it changed
POOL.add_refcol(col)
col.objs()                                       # what is in it now
POOL.remove_refcol(col)
```

A drawing collection subclasses `RefCol` and returns its own `Ref` from `make_ref`;
`Ref.repaint()` is called for every changed object it holds.

## Selection

`SELSET` is the selection of the whole application.

| call | what it does |
|---|---|
| `SELSET.click(obj)` | a click: on a selected object its next level (up to `obj.SEL_MAX`, then none), on another only that one, on nothing (`None`) clears |
| `SELSET.toggle(obj)` | ctrl+click: adds or removes it, the rest stays |
| `SELSET.set(obj, Sel.SEL)` | sets a level |
| `SELSET.clear()` | nothing selected |
| `SELSET.items()` | the selected objects |
| `SELSET.level(obj)` | its level: `Sel.NONE`, `Sel.SEL`, `Sel.HANDLES` |
| `SELSET.selected_key(source)` | key of the first selected object of a source, 0 when none |

## Sources

```python
from hg_pool_py import SOURCES, SourceFile

class DiagFile(SourceFile):
    def _load(self):                     # create objects, return {key: object}
        ...
    def _write(self, pending):           # {key: {attr: value}} into the file
        self.write_text(...)
    def _apply(self, obj, attrs):        # an unsaved change back after a reload
        ...

src = DiagFile("/path/of/file")
SOURCES.open(src)                        # for now opening one closes the previous
src.load()
src.stage({3: {"xy": "30 40"}})          # an unsaved change; src.changes counts them
src.save()
src.reload()                             # after a change on disk; its own writes do not count
src.listeners.append(lambda s, what: ...)   # what: "changed" | "saved"
```

How the module is built: `hg_pool_py.recipe.md`.
