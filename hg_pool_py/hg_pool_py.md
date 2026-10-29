# hg_pool_py

Object pool, reference collections with filters, selection and sources of objects,
without Qt and without drawing. The interaction core that an application (a diagram
viewer, a table, ...) builds on: objects live in the pool and carry where they came
from; whoever shows, selects or loads them keeps a filtered collection.

Modelled on the CAD interaction layer (`hg_interact`: GObjectPool, GObject, Ref, RefCol,
UpdateLock), not a 1:1 port - hence its own name. Modes (when a click selects) are not
here; they are in `hg_interactive_applib`.

Help: [hg_pool_py.help.md](hg_pool_py.help.md)

AI Recipe: [hg_pool_py.recipe.md](hg_pool_py.recipe.md)
