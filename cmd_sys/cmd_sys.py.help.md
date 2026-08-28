# cmd_sys.py

Registr příkazů a jejich vykonávání.

- `add(jméno, funkce, category=…)` - registrace; víc než to není potřeba
- `execute(řádek, …)` - provedení teď hned
- `execute_thread_safe(…)` - zařazení do fronty pro vlákno s oknem; odsud
  volají tlačítka a WS most

**Proč ta fronta.** Qt smí se svými widgety mluvit jen z hlavního vlákna, ale
příkaz může přijít odkudkoli - ze socketu, ze stdin, z kliknutí. Vše se tedy
odloží a hlavní vlákno si to vybere.
