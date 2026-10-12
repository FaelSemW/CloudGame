# Open source e distribuição

Revisão inicial dos quatro repositórios oficiais, das licenças de topo, do NOTICE do Sunshine e do inventário de submódulos. Os textos foram preservados em `licenses/`; commits observados e URLs dos submódulos estão em `licenses/upstream-review.json`. Nenhum código-fonte de Sunshine ou Moonlight foi incorporado ao produto. Não foram compilados nem redistribuídos seus binários nesta entrega.

| Componente | Licença observada | Uso nesta versão |
|---|---|---|
| [Sunshine](https://github.com/LizardByte/Sunshine) | GNU GPL versão 3; preservar também NOTICE e cabeçalhos dos arquivos da versão distribuída | Processo externo dentro da VM, API de administração local, protocolo original para streaming |
| [Moonlight Qt](https://github.com/moonlight-stream/moonlight-qt) | GNU GPL versão 3 | Aplicativo externo Windows/Linux instalado pelo usuário |
| [Moonlight Android](https://github.com/moonlight-stream/moonlight-android) | GNU GPL versão 3, arquivo LICENSE.txt | Aplicativo externo Android instalado pelo usuário |
| [Moonlight common C](https://github.com/moonlight-stream/moonlight-common-c) | GNU GPL versão 3, arquivo LICENSE.txt | Não é linkado pelo cliente web; usado pelos clientes upstream |

A indicação acima descreve os textos de licença observados, sem presumir que todo arquivo/dependência é exclusivamente GPL-3.0-only ou GPL-3.0-or-later. Cabeçalhos específicos e exceções da versão efetivamente empacotada precisam ser preservados e auditados.

## Código novo

O código original deste repositório é oferecido sob GPL-3.0-or-later; o texto GPLv3 está em `LICENSE`. As licenças/avisos upstream mantêm seus próprios termos. Não revendicamos marcas Sunshine, Moonlight, Steam, Valve, Bazzite ou Tailscale. A interface não usa logos oficiais desses terceiros.

Node.js possui sua licença e avisos de componentes próprios (incluindo dependências incorporadas). O instalador baixa somente runtime oficial, verifica checksum e copia `LICENSE` e o nome/hash do arquivo para `/opt/cloud-game/runtime`. Não há dependências npm externas neste projeto. Bibliotecas Python usadas aqui são da biblioteca padrão. Na distribuição de uma imagem Linux completa, também existem obrigações de kernel, QEMU, libvirt, drivers, desktop, codecs e pacotes da distribuição.

## Obrigações para uma distribuição futura

1. Fixe versões/commits e inventarie **todas** as dependências efetivamente incluídas, transitivas, build tools e bibliotecas linkadas. Os submódulos upstream foram listados, mas não houve auditoria completa de dependências porque não se compila/distribui esses componentes aqui. **Isso é pendência impeditiva para um bundle de binários.**
2. Preserve arquivos LICENSE/COPYING/NOTICE, autores e avisos nos arquivos, documentação e instalador quando exigido. Se modificar código upstream, registre as alterações e datas exigidas.
3. Para distribuir binários ou trabalho derivado coberto pela GPL, disponibilize o código-fonte correspondente completo da **versão entregue**, incluindo modificações e scripts necessários à geração/instalação conforme os termos aplicáveis. Um link genérico para `master` ou apenas para o repositório upstream não substitui o código correspondente.
4. Escolha uma modalidade válida da seção 6 da GPLv3 para distribuição de código objeto; ao distribuir por download, prefira disponibilizar fontes correspondentes junto aos artefatos sem cobrança adicional. Não crie restrições de uso/redistribuição incompatíveis.
5. Se entregar um User Product no sentido da GPLv3, avalie e cumpra os requisitos de Installation Information quando aplicáveis. Não prometa que um EULA proprietário elimina essas obrigações.
6. Executar programas separados e comunicar-se por APIs evita copiar seu código para a interface, mas não é uma conclusão jurídica universal sobre derivação. Uma futura incorporação/linkagem de Moonlight common C ou adaptação dos clientes GPL precisa ser distribuída de forma compatível.
7. Não empacote jogos, Steam, codecs ou drivers proprietários sem direitos de distribuição. Biblioteca disponível no HOST não concede direito de uso do jogo ao jogador nem permissão para publicar seus arquivos. Steam Cloud e licenciamento continuam regidos pelos serviços/jogos.

## Avaliação de integração direta

`moonlight-common-c` resolve partes do protocolo/transporte/entrada; não é um player web pronto. Desktop precisa de integração com decoders, áudio, input e plataforma (o Moonlight Qt já faz isso). Android usa sua própria UI/MediaCodec/JNI e integração com o core C. Não há Android SDK/NDK, Java, Qt, compilador C/C++ ou hardware Android verificados no ambiente recebido.

Integrar nativamente exige manter forks por plataforma, pipeline de build, assinatura Android, auditoria de dependências e validação de desempenho. Nesta entrega foi implementado o caminho externo transparente: cliente próprio de controle + Moonlight oficial, pareado através de uma reserva autorizada. **Não é integração nativa, e nenhum vídeo é transmitido pelo navegador.**

O adaptador de API/markers foi escrito a partir da interface pública e da inspeção do upstream, sem copiar sua implementação. A consulta de referência incluiu Sunshine `v2025.924.154138` e master registrado em `upstream-review.json`; nenhum desses bins foi executado. Instale uma versão oficial atualizada, registre-a e homologue; não instale uma versão antiga apenas porque foi usada como referência de API.
