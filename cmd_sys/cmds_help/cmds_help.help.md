# Popisy příkazů

Jeden `.md` soubor na příkaz. `cmd_help <jméno>` sáhne přesně sem a vypíše
odpovídající soubor, takže dokumentace příkazu leží vedle příkazu a ne
v samostatné příručce, která zastará.

Dva soubory nejsou o žádném konkrétním příkazu:

- `__not_documented__.md` - co se vypíše, když popis chybí
- `__not_implemented__.md` - co se vypíše, když příkaz zná jen jméno

Nový příkaz = nový `.md` se stejným jménem. Nic se neregistruje.
