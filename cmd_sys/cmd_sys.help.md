# cmd_sys - příkazová vrstva

Jádro toho, proč koumes umí obsloužit člověka i agenta stejně. Registr příkazů,
parser argumentů, log a WebSocket most. **Na Qt nezávisí** - běží i v režimu
bez okna.

| soubor | co dělá |
|---|---|
| `cmd_sys.py` | registr a dispatch; sem se příkazy přidávají |
| `cmd_arg_col_parser.py` | rozebrání řádku na argumenty (i uvozovky) |
| `ws_server_lite.py` | WS server, přes který příkazy chodí ven i dovnitř |
| `log_guard.py` | zápis do `config/cmdlog.txt` |
| `cmds_help/` | popisy jednotlivých příkazů |

## Tvar příkazu

```
<jméno> <argumenty…> --VÝSTUP hodnoty
```

Vstup je to, co jste poslali; od prvního `--` dál si příkaz dopsal, jak to
dopadlo. Log si toho drží obojí, takže je z něj zpětně vidět nejen co se chtělo,
ale i co z toho vyšlo.
