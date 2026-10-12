# Clientes integrados — desenvolvimento

O código da interface CloudGame é montado dentro dos projetos oficiais Moonlight por `tools/native_sources.py`. Não inicia executáveis Moonlight externos: desktop usa `CliPair::Launcher`, `CliStartStream::Launcher` e `Session` no mesmo processo Qt; Android usa `NvHTTP`, `PairingManager` e `Game` no mesmo APK, incluindo JNI/decoder/controles existentes.

```sh
python3 tools/native_sources.py all --sync
```

Os commits estão fixados no script. Submódulos seguem os pins de cada projeto, incluindo versões distintas de moonlight-common-c quando exigidas pelo upstream. O montador recusa versões inesperadas e preserva alterações manuais que não correspondam ao overlay anterior. Não usa `git reset --hard`. As licenças originais continuam nos checkouts.

O APK usa o identificador `io.github.faelsemw.cloudgame`; autenticação da plataforma via HTTPS com cookies só em memória, sem coletar dados Steam. A reconexão conserva o certificado público do Sunshine associado à origem e UUID da sessão. Backup e transferência das identidades locais são excluídos. O HOST consulta o pedido pendente do Sunshine e aprova seu identificador junto com o PIN, aguardando a conclusão criptográfica. Múltiplos pedidos pendentes bloqueiam o pareamento.

GitHub Actions tem builds Android, Linux e Windows separados. **Um workflow definido não é um build executado.** Os artefatos são internos até a verificação de licenças transitivas, empacotamento de bibliotecas/fontes correspondentes, assinatura de release e homologação de streaming. Android debug é apenas para desenvolvimento; não é a release final.

O HOST ainda requer a imagem Sunshine preparada conforme BAZZITE.md. O provisionamento dessa imagem e o instalador completo não estão concluídos. Os scripts atuais de download não substituem esses componentes. Não distribuir o pacote de controle como produto completo.

No Windows de desenvolvimento, o JDK e as ferramentas Android ficam em `.toolchains` (ignorada pelo Git). Não são componentes redistribuídos com o aplicativo. A montagem não remove licenças de dependências nem muda suas versões para forçar compatibilidade.

## Evidências locais de 12/10/2026

`assembleNonRootDebug` completou com sucesso, incluindo os quatro ABIs (arm64-v8a, armeabi-v7a, x86, x86_64). `aapt2` confirmou o identificador `io.github.faelsemw.cloudgame.debug`, versão `0.1.0-dev` e launcher `com.limelight.cloudgame.CloudGameActivity`. Foram verificadas a presença das classes de controle e `Game` nos arquivos DEX e bibliotecas ELF `libmoonlight-core.so` no APK. `apksigner verify` confirmou assinatura debug; não há chave de produção ou publicação deste APK. Hash e tamanho estão em `android-build-evidence.json`.

A primeira compilação falhou porque o NDK recusa caminhos com espaços. `tools/build-android.ps1` resolve isso criando um alias temporário `subst` apenas quando necessário, escolhendo uma letra livre e removendo o alias ao terminar. Limita a compilação a dois workers e 1,5 GiB de heap Java.

23 testes Node e 19 testes Python passaram. Incluem concorrência, bloqueio de limpeza e contrato de pareamento Sunshine por identificador. Não equivalem à homologação Linux. O provisionador guest agora gera a credencial Sunshine pela CLI oficial e configura permissões de entrada dentro da VM, mas essas alterações não foram executadas em Linux.

## Evidências de desktop no GitHub Actions

[Execução 38226584427](https://github.com/FaelSemW/CloudGame/actions/runs/38226584427): Android, Windows e Linux concluídos com sucesso. Windows foi compilado com MSVC e Qt 6.12.0 e empacotado com Inno Setup. Linux foi compilado no Ubuntu 24.04 e empacotado como `.deb`, com dependências da distribuição; esse pacote não é um instalador para Bazzite. A execução com Xvfb abriu a interface real CloudGame e salvou captura e logs nos artefatos. O aviso de ausência de decoder por hardware é esperado nesse runner sem GPU.

A revisão do log encontrou bindings QML acessando o controlador durante seu encerramento. A ordem de destruição C++ foi corrigida para manter o controlador vivo até a destruição da engine QML; o teste agora rejeita também `TypeError`. A execução citada acima antecede essa correção; seu novo resultado deve ser consultado na execução do commit correspondente.

O push autenticado para GitHub funciona. Os instaladores estão em artefatos de Actions, ainda sem release pública completa. `tools/source_bundle.py` prepara fontes rastreados, submódulos fixados, overlays aplicados e avisos de licença, excluindo dados locais e diretórios de build não rastreados. O SDK Qt e suas dependências redistribuídas exigem fontes/avisos adicionais; gerar esse arquivo não constitui uma auditoria completa.

## Revisão verificada: 56ab70d

A [execução 38270190388](https://github.com/FaelSemW/CloudGame/actions/runs/38270190388) concluiu os três jobs com sucesso. Linux passou na inicialização e no encerramento sem erros de binding QML. Windows compilou, gerou o instalador, instalou em diretório temporário do runner, iniciou o executável por dez segundos e desinstalou; os logs não indicaram os erros QML monitorados. Android gerou o APK debug com os fontes correspondentes. Isso não verifica transmissão, entrada ou desempenho remoto.

Os 719 avisos originais de desktop foram posteriormente preservados em `licenses/windows-runtime-notices.zip` (commit 6560d9f), para inclusão nas próximas compilações do instalador; o artefato da execução acima antecede essa inclusão. Os fontes Qt oficiais tiveram SHA-256 conferido. O arquivo local de fontes Windows/dependências da revisão 533f2a7 contém 63224 arquivos, SHA-256 `41291291b9f9309854734b6c3f0e740b805d3cd46f28037b1e06a44b0072e218`; ele corresponde à revisão anterior, não deve ser usado como fonte correspondente do binário 56ab70d.

Pendências concretas: provisionamento automático da imagem Sunshine e dependências do HOST; revisão final e publicação dos fontes/avisos dos runtimes redistribuídos junto aos binários correspondentes; assinatura de produção Android; testes reais Android/desktop e Bazzite/GPU. Não há release completa disponível e os scripts que consultam releases não estão prontos para uso público.
