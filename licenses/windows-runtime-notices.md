# Avisos dos runtimes Windows

`windows-runtime-notices.zip` preserva 719 arquivos originais de avisos,
licenças e metadados nas árvores `moonlight-qt`, `moonlight-qt-deps` e `qt`.
O instalador copia esse arquivo para sua pasta `licenses`; qualquer leitor
ZIP permite consultar os textos sem executar programas.

Origens:

- Moonlight Qt: `a57e947d7185fd01384f6973df4df59ae2968d01`, submódulos fixados.
- Moonlight Qt deps v19: `79621271459ebb945343f58d7acd6ad24d402c38`, submódulos recursivos fixados.
- Qt 6.12.0: arquivo oficial de fontes SHA-256 `98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165`.

Os textos foram coletados por `tools/source_bundle.py` e
`tools/qt_notices.py`. Incluem avisos de módulos e ferramentas presentes nos
fontes que podem não estar linkados ao executável. Não substituem os fontes
correspondentes nem a revisão final da distribuição. Consulte
`docs/WINDOWS-DEPENDENCIES.md` para o inventário das DLLs observadas.
