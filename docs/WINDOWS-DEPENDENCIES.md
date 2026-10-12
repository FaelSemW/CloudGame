# Dependências do desktop Windows

Inventário do artefato `cloud-game-windows-build-internal` da execução
[38226584427](https://github.com/FaelSemW/CloudGame/actions/runs/38226584427).
Esta lista descreve arquivos observados, não certifica a distribuição final.

| Arquivos/componentes | Fonte e licença observada |
|---|---|
| `Moonlight.exe`, core C, ENet, NanoRS, parser H.264, mDNS | Moonlight Qt e submódulos fixados pelo montador; GPLv3 e licenças específicas preservadas nos fontes |
| `Qt6*.dll`, plugins e QML | Qt 6.12.0; GPL/LGPL e licenças de componentes terceiros por módulo |
| `avcodec-63`, `avformat-63`, `avutil-61`, `swscale-10` | FFmpeg no submódulo do bundle v19; licença predominante LGPL-2.1-or-later, condicionada às opções de compilação |
| `dav1d.dll`, `opus.dll` | Avisos BSD preservados nos arquivos COPYING dos respectivos submódulos |
| `SDL2.dll`, `SDL3.dll`, `SDL2_ttf.dll` | SDL, sdl2-compat, SDL_ttf: licença zlib; FreeType/HarfBuzz e outros componentes têm avisos próprios |
| `libssl-3-x64.dll`, `libcrypto-3-x64.dll` | OpenSSL, Apache-2.0 e avisos de componentes terceiros |
| `libplacebo-374.dll` | libplacebo, texto LGPL-2.1 e dependências específicas |
| `discord-rpc.dll` | Discord RPC, MIT |
| `AntiHooking.dll` | Código Moonlight e Detours; Detours inclui aviso MIT da Microsoft |
| `msvcp*`, `vcruntime*`, `concrt140.dll`, `vccorlib140.dll` | Runtime Microsoft Visual C++; conferir lista REDIST e termos do toolchain usado antes da distribuição pública |

Os binários de dependências vêm do release oficial `moonlight-qt-deps` v19.
Seu repositório de fontes foi obtido no commit
`79621271459ebb945343f58d7acd6ad24d402c38`, com submódulos recursivos.
Os scripts de compilação e patches desse repositório acompanham o arquivo de
fontes gerado por `tools/source_bundle.py`.

O fonte oficial Qt usado para preservar avisos é
`qt-everywhere-src-6.12.0.tar.xz`, 443394020 bytes, SHA-256
`98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165`.
O hash foi conferido contra o servidor oficial e contra o arquivo baixado.
`tools/qt_notices.py` preservou 609 arquivos originais de avisos/licenças.
Isso inclui módulos que podem não estar no aplicativo; não se deve inferir
que todos os módulos Qt estão sendo distribuídos.

Antes da release pública: comparar o inventário da compilação final, preservar
os avisos no instalador, fornecer os fontes correspondentes junto aos downloads
e concluir a conferência dos runtimes Microsoft e das opções reais das DLLs.
Não há licença comercial Qt nem certificado de assinatura Windows configurado.

Referências: [licenciamento Qt](https://doc.qt.io/qt-6/licensing.html),
[fontes oficiais Qt](https://download.qt.io/official_releases/qt/6.12/6.12.0/single/),
[fontes das dependências Moonlight v19](https://github.com/moonlight-stream/moonlight-qt-deps/tree/v19).
