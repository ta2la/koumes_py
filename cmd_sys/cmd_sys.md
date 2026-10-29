# cmd_sys

The command layer of koumes: a registry of named commands, a parser of command lines,
a log and a WebSocket connector. Without Qt, so it runs with or without a window.

**Why it exists.** A human and an agent use the same commands. The human calls them
from the UI, the agent sends them over a WebSocket; both go through one registry, are
logged the same way and get the same reply. Not two interfaces over one core - one
interface used by two.

Every application of koumes (the window, the console apps, the diagram viewer) builds
its commands on it: the shared `CMD_SYS()` registry, or its own group of commands
(`Cmds`) with its own port. Python port of the C++ `base2/cmd_sys`.

How to use it: `cmd_sys.help.md`.
