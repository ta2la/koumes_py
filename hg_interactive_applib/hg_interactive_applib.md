# hg_interactive_applib

An interactive application over the object pool (`hg_pool_py`): modes on a
stack (selecting into the pool selection), mouse input turned into commands and the commands every interactive
application has (`<prefix>_xy`, `_reset`, `_cmd_select`, `_cmd_pan`, `_sel`, `_save`,
`_state`, `_cross`, `_screenshot`, `_window`). A concrete application (the diagram
viewer) adds its objects, a few modes and a few commands. The view part is Qt: entities
and their canvas, the scene (a pool collection that is drawn), the view widget with its
canvas and the floating panel (cmd / files / log).

Modelled on the CAD interaction layer (`hg_interact`: Cmd, CmdQueue, Scene, WidgetInteract; entities as in `hg_display`) with
MicroStation logic, not a 1:1 port. A module next to `cmd_sys` and `hg_pool_py`.

Help: [hg_interactive_applib.help.md](hg_interactive_applib.help.md)

AI Recipe: [hg_interactive_applib.recipe.md](hg_interactive_applib.recipe.md)
