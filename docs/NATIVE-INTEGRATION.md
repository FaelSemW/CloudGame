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

Pendências concretas: Qt/MSVC e ambiente Linux para compilar desktop; provisionamento automático da imagem Sunshine e dependências do HOST; assinatura e pacotes finais; testes reais Android/desktop e Bazzite/GPU; publicação autenticada no GitHub (o push anterior foi recusado por ausência de credenciais). Não há release completa disponível.
