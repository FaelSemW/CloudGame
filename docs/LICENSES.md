# Open source e distribuição

Revisão das licenças de topo dos quatro repositórios oficiais, do NOTICE do Sunshine e do inventário de submódulos. Os textos foram preservados em `licenses/`; o inventário inicial está em `licenses/upstream-review.json` e os commits usados nos clientes estão fixados em `tools/native_sources.py`. Android e desktop agora incorporam Moonlight e foram compilados. A revisão transitiva e os fontes completos dos runtimes redistribuídos ainda precisam ser concluídos antes de uma release binária pública.

| Componente | Licença observada | Uso nesta versão |
|---|---|---|
| [Sunshine](https://github.com/LizardByte/Sunshine) | GNU GPL versão 3; preservar também NOTICE e cabeçalhos dos arquivos da versão distribuída | Processo externo dentro da VM, API de administração local, protocolo original para streaming |
| [Moonlight Qt](https://github.com/moonlight-stream/moonlight-qt) | GNU GPL versão 3 | Código incorporado no cliente Windows/Linux, com overlay CloudGame |
| [Moonlight Android](https://github.com/moonlight-stream/moonlight-android) | GNU GPL versão 3, arquivo LICENSE.txt | Código incorporado no mesmo APK CloudGame |
| [Moonlight common C](https://github.com/moonlight-stream/moonlight-common-c) | GNU GPL versão 3, arquivo LICENSE.txt | Linkado pelos clientes nativos nas versões dos respectivos submódulos |

A indicação acima descreve os textos de licença observados, sem presumir que todo arquivo/dependência é exclusivamente GPL-3.0-only ou GPL-3.0-or-later. Cabeçalhos específicos e exceções da versão efetivamente empacotada precisam ser preservados e auditados.

## Código novo

O código original deste repositório é oferecido sob GPL-3.0-or-later; o texto GPLv3 está em `LICENSE`. As licenças/avisos upstream mantêm seus próprios termos. Não revendicamos marcas Sunshine, Moonlight, Steam, Valve, Bazzite ou Tailscale. A interface não usa logos oficiais desses terceiros.

Node.js possui sua licença e avisos de componentes próprios (incluindo dependências incorporadas). O instalador baixa somente runtime oficial, verifica checksum e copia `LICENSE` e o nome/hash do arquivo para `/opt/cloud-game/runtime`. Não há dependências npm externas neste projeto. Bibliotecas Python usadas aqui são da biblioteca padrão. Na distribuição de uma imagem Linux completa, também existem obrigações de kernel, QEMU, libvirt, drivers, desktop, codecs e pacotes da distribuição.

## Obrigações para uma distribuição futura

1. Fixe versões/commits e inventarie **todas** as dependências efetivamente incluídas, transitivas, build tools e bibliotecas linkadas. Os clientes têm commits fixos e foram compilados; a auditoria completa de dependências ainda está pendente. **Isso impede tratar os artefatos de desenvolvimento como uma release pronta para distribuição.**
2. Preserve arquivos LICENSE/COPYING/NOTICE, autores e avisos nos arquivos, documentação e instalador quando exigido. Se modificar código upstream, registre as alterações e datas exigidas.
3. Para distribuir binários ou trabalho derivado coberto pela GPL, disponibilize o código-fonte correspondente completo da **versão entregue**, incluindo modificações e scripts necessários à geração/instalação conforme os termos aplicáveis. Um link genérico para `master` ou apenas para o repositório upstream não substitui o código correspondente.
4. Escolha uma modalidade válida da seção 6 da GPLv3 para distribuição de código objeto; ao distribuir por download, prefira disponibilizar fontes correspondentes junto aos artefatos sem cobrança adicional. Não crie restrições de uso/redistribuição incompatíveis.
5. Se entregar um User Product no sentido da GPLv3, avalie e cumpra os requisitos de Installation Information quando aplicáveis. Não prometa que um EULA proprietário elimina essas obrigações.
6. Executar programas separados e comunicar-se por APIs evita copiar seu código para a interface, mas não é uma conclusão jurídica universal sobre derivação. Uma futura incorporação/linkagem de Moonlight common C ou adaptação dos clientes GPL precisa ser distribuída de forma compatível.
7. Não empacote jogos, Steam, codecs ou drivers proprietários sem direitos de distribuição. Biblioteca disponível no HOST não concede direito de uso do jogo ao jogador nem permissão para publicar seus arquivos. Steam Cloud e licenciamento continuam regidos pelos serviços/jogos.

## Avaliação de integração direta

`moonlight-common-c` resolve partes do protocolo/transporte/entrada; não é um player web pronto. Desktop precisa de integração com decoders, áudio, input e plataforma (o Moonlight Qt já faz isso). Android usa sua própria UI/MediaCodec/JNI e integração com o core C. O SDK/NDK/JDK foram instalados para compilação Android local; Qt/MSVC e Qt/Linux foram usados no GitHub Actions. Não houve teste de streaming em hardware.

Os overlays montam a interface CloudGame dentro dos clientes nativos. O desktop chama as classes de pareamento e sessão no mesmo processo; Android inicia `Game` no mesmo APK. A interface web antiga continua como alternativa de controle manual; não transmite vídeo. A assinatura Android atual é de debug, não de produção.

`tools/source_bundle.py` arquiva somente fontes rastreados, submódulos fixados e overlays verificados, preservando modos executáveis e avisos. Um manifesto registra hashes e commits. O script exclui arquivos locais não rastreados e recusa submódulos divergentes. Para Windows, `moonlight-qt-deps` v19 está fixado no commit `79621271459ebb945343f58d7acd6ad24d402c38`; o SDK Qt 6.12.0 é um componente adicional. Seus fontes, licenças e componentes terceiros devem acompanhar a distribuição conforme a [documentação oficial do Qt](https://doc.qt.io/qt-6/licensing.html). O `.deb` Ubuntu usa bibliotecas do sistema, sem empacotar o SDK Qt.

O adaptador de API/markers foi escrito a partir da interface pública e da inspeção do upstream, sem copiar sua implementação. A consulta de referência incluiu Sunshine `v2025.924.154138` e master registrado em `upstream-review.json`; essas referências antigas não são a versão instalada. O provisionador atual fixa Sunshine `v2026.914.233613` e seu SHA-256 em `deploy/image-lock.json`; essa versão foi executada com vídeo real no CI 38347361268. O pacote é baixado da release oficial durante a instalação, não redistribuído como uma imagem de VM nossa.
