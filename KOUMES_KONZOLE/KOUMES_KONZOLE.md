# KOUMES_KONZOLE

The console form of koumes: a window in the terminal with AI agents on the left and
numbered panels on the right. Each panel runs anything: a file viewer, an editor, a
directory browser, a shell, an app.

**Why it exists.** Agents work in terminals and a person needs to see them together with
the files they work on. The console keeps both in one window and survives closing it,
because everything runs inside one tmux server. A person clicks, an agent calls
`clmon --something` from any shell, and both go the same way: one interface used by two,
as in the window version of koumes.

**The core stays small.** Layout, panels, agents and the menu are here. Views of things
are separate apps in `KOUMES_KONZOLE_APPS/`, so a new view does not touch the core.

Nothing about a machine is in the code. Where things are is in `config.t2l`, which programs
are used is in `apps.t2l`. Both are written when missing and neither is in git.

## Files

| file | what it is | what it does |
|---|---|---|
| `clmon` | program | the console: tmux layout, agents, panels, menu, commands |
| `clmon.tmux` | tmux configuration (`.conf`) | settings of the console's own tmux server |
| `apps` | module | database of apps and external programs, writes `apps.t2l` |
| `apps_viewer` | app | the list behind [apps], with what is installed |
| `config` | module | where things are on this machine, writes `config.t2l` |
| `config_view` | app | the app behind [config], assigns those places |
| `apps.t2l` | data, not in git | apps, tools and external viewers |
| `config.t2l` | data, not in git | places, koumes instances, the diagram viewer |

Help: [KOUMES_KONZOLE.help.md](KOUMES_KONZOLE.help.md)

AI Recipe: [KOUMES_KONZOLE.recipe.md](KOUMES_KONZOLE.recipe.md)
