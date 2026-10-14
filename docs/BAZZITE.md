# Instalação e operação

Este procedimento é **candidato à homologação**, não foi executado neste ambiente Windows. GPU passthrough depende da placa, firmware, grupos IOMMU e possibilidade de reset. A V1 não está aprovada enquanto o roteiro ACCEPTANCE.md não passar.

## 1. HOST compatível

Requisitos implementados: Bazzite x86_64, libvirt/KVM do sistema, `virsh`, `qemu-img`, Python 3, nftables, Tailscale conectado, sudo, `restorecon` e `semanage`. A VM usa BIOS/q35 nesta versão; imagem UEFI não é suportada pelo gerador de domínio.

Use **Bazzite Portal → preparação de virtualização**, ou a receita `ujust setup-virtualization` disponibilizada pela sua imagem. Confira as opções existentes em `ujust --list` antes de executar. A disponibilidade e os nomes podem variar entre versões. Não use `apt`, `dnf install` ou um script de outra distribuição no HOST imutável. Se sua imagem não disponibilizar uma ferramenta, use o procedimento oficial da versão para layering via rpm-ostree/bootc e reinicie quando solicitado. O instalador recusa pré-requisitos ausentes; não modifica `/usr` nem desliga SELinux.

Separe uma GPU para o HOST e outra GPU, com sua função de áudio, para a VM. IOMMU deve estar habilitado no firmware; a GPU da VM deve estar ligada a `vfio-pci`. Todos os dispositivos do grupo IOMMU precisam ser GPU/áudio e estar listados na configuração. **ACS override, VFIO sem IOMMU e interrupções inseguras são recusados.** Uma GPU única compartilhada com o desktop do proprietário não é suportada. Pode ser necessário monitor físico ou adaptador HDMI na GPU da VM.

Swap em disco e zram com writeback são bloqueados. Zram é aceito somente quando o kernel informa `backing_dev=none`, mantendo os dados na memória. O tamanho inicial do tmpfs é 8 GiB; a VM com GPU usa 8 GiB de RAM além desse teto. Reserve memória para o Bazzite; 24–32 GiB totais é um ponto de partida, não garantia para todos os jogos. Ajuste o teto do mount e a RAM da VM conforme a carga, e valide OOM. Hibernação e dumps de RAM devem estar desativados por política do administrador: o código não consegue provar que firmware ou ferramentas de diagnóstico nunca gravarão memória.

## 2. Preparar a imagem de jogos, uma vez

O instalador agora cria automaticamente uma imagem limpa quando `/var/lib/cloudgame/base.qcow2` não existe. Baixa Ubuntu 24.04 e Sunshine oficial com SHA-256 fixados em `deploy/image-lock.json`, instala Xfce, áudio, Steam e o agente interno e configura o usuário sem privilégios. Depois inicia um overlay descartável para verificar a API real do Sunshine, grupos do jogador e ausência de compartilhamentos. Uma falha interrompe a instalação e preserva os registros. Essa verificação não comprova streaming, controle, desempenho ou GPU física.

Reserve pelo menos 16 GiB livres para a preparação inicial. O disco virtual tem capacidade de 128 GiB e alocação sob demanda; jogos exigem espaço adicional. A imagem automática usa drivers Mesa; a instalação automática com GPU NVIDIA permanece recusada por falta do driver proprietário nessa imagem.

Para testar dentro de uma VM sem GPU dedicada, selecione **Teste em VM / CPU** no instalador gráfico ou use `--software`. O jogador continua numa VM separada, sem pastas do proprietário. Renderização e codificação usam CPU; há perda expressiva de desempenho. KVM é usado quando disponível, com emulação QEMU como alternativa. Reserve pelo menos 8 GiB para o Bazzite de teste; isso não garante capacidade para jogos grandes.

O procedimento manual abaixo serve para preparar uma biblioteca ou drivers específicos. Não é mais necessário criar a imagem básica manualmente:

No virt-manager, crie uma VM Linux **limpa**, BIOS/q35, disco qcow2, desktop X11 (por exemplo, Xfce), QEMU Guest Agent e GPU dedicada. Esta VM é um componente interno do HOST, não um terceiro aplicativo do produto.

1. Crie `player`, UID 1000, home `/home/player`. Não dê sudo, wheel, docker, libvirt, disk, lxd, senha root ou permissões administrativas ao jogador. Elimine regras polkit de elevação automática. Configure autologin X11 para `player`, `DISPLAY=:0` e `XAUTHORITY=/home/player/.Xauthority`. Um display manager que use outro caminho exige ajuste na unidade.
2. Instale o Sunshine **nativo** oficial, `/usr/bin/sunshine`, driver de GPU, suporte de áudio e Steam por seus distribuidores oficiais. Não use uma compilação improvisada. Flatpak Sunshine não é compatível com esta unidade de serviço. Configure o acesso `uinput` conforme o Sunshine; isso ocorre dentro da VM, nunca no desktop do proprietário.
3. Copie esta pasta `deploy` para a VM e execute `sudo python3 prepare_guest.py`. O script instala configurações e helper interno e gera automaticamente uma credencial administrativa aleatória do Sunshine pela CLI oficial. Não baixa Steam/Sunshine. Essa credencial fica em arquivo root-only e não é senha Steam nem da plataforma.
4. Configure a NIC de MAC `52:54:00:77:00:02` com IPv4 estático `10.77.0.2/24`, gateway `10.77.0.1`, DNS `1.1.1.1`; desative IPv6. Não use DHCP. O hostname da VM não precisa ser o mesmo do HOST. O helper só gera essa NIC.
5. Desabilite qualquer outra inicialização automática do Sunshine e habilite `cloud-game-sunshine.service`. Há uma única instância, registrada no journal do sistema. A credencial já foi configurada no passo 3; não é necessário digitá-la no painel Sunshine. A porta administrativa `47990` deve continuar restrita à própria VM. O certificado local é usado pelo helper para validar TLS; nunca use `--insecure`.
6. Garanta que a aplicação `Desktop` existe; selecione a GPU/encoder apropriado no Sunshine e valide captura, áudio, teclado, mouse e gamepad dentro da VM de manutenção. A API `/api/apps` confirma preparação; as mensagens `CLIENT CONNECTED`/`CLIENT DISCONNECTED` do serviço confirmam conexões. Um upstream que altere esses marcadores exige revalidar o adaptador.
7. A imagem-base **nunca deve conter login Steam de proprietário ou jogador**. Importe somente arquivos de instalação de jogos autorizados e manifests selecionados para uma biblioteca na imagem. Faça login para testar jogos somente em um clone descartável. Não tente sanitizar uma imagem usada apagando `loginusers.vdf`: blocos livres, logs e snapshots podem guardar credenciais anteriores.
8. Prepare Steam, runtimes, Proton e a biblioteca antecipadamente, sem autenticação pessoal na imagem-base. Jogos que escrevem dentro da instalação terão essas escritas no overlay da sessão. Patches, shader caches e downloads grandes consomem o tmpfs e são perdidos; mantenha atualizações necessárias na imagem-base via manutenção. Nem todos os jogos suportam VM, anticheat, compartilhamento/licenciamento ou execução offline. Só autorize os jogos efetivamente testados e licenciados; posse de arquivos não concede licença ao jogador.
9. Remova todos os clientes pareados do Sunshine pela interface oficial antes de selar. Desligue a VM de manutenção e mantenha-a desligada durante sessões. Não deixe dispositivos físicos, pastas compartilhadas, SSH com chaves do proprietário ou discos pessoais na imagem.
10. Exporte/converta offline para um qcow2 independente, sem backing e sem snapshots. Instale em `/var/lib/cloudgame/base.qcow2`, proprietário root, modo `0444`. Use `restorecon` após a instalação. Registre versão da imagem, Sunshine, drivers e hashes antes da homologação. O helper recusa backing externo, snapshots e permissões graváveis.

Os jogos persistentes ficam **dentro da imagem-base**, protegidos por backing somente leitura. A V1 não monta diretamente uma biblioteca pessoal do HOST. Modificações de filesystem, perfis, credenciais Steam digitadas durante uma sessão e saves locais ficam no overlay descartável da VM inteira. Saves enviados à nuvem permanecem sujeitos ao Steam/jogo e não podem ser apagados pelo HOST.

## 3. Instalar o HOST

Antes de instalar, conecte o HOST ao Tailscale e habilite MagicDNS e HTTPS para a tailnet. Verifique que a sub-rede `10.77.0.0/24` não conflita com uma rede existente. O instalador cria a bridge `cgbr0` e habilita encaminhamento IPv4; não altera interfaces físicas.

Pela pasta do projeto, execute o lançador gráfico:

```sh
python3 deploy/install-gui.py
```

Alternativa única para instalação sem Zenity:

```sh
pkexec /usr/bin/python3 deploy/install_host.py
```

O instalador copia o código para `/opt/cloud-game`, cria o usuário de serviço, unidades systemd, tmpfs e regra sudo para **um único helper fixo**. Baixa Node 22 LTS x86_64 de nodejs.org, confere SHA-256 contra o manifesto HTTPS oficial e preserva a licença e a procedência. Nada é instalado no `/usr` imutável. Instalações existentes são recusadas para preservar configuração/dados; falhas intermediárias exigem revisão administrativa, sem rollback destrutivo automático.

O instalador escreve `/etc/cloud-game/vm.json` com o perfil escolhido, memória/CPUs e, no perfil físico, a única GPU compatível já dedicada ao VFIO. Nenhum driver do desktop do proprietário é desvinculado automaticamente. `templateReviewed: true` é gravado após a verificação automática da imagem; não substitui homologação de segurança ou streaming. O arquivo é root-only, não editável remotamente pelo cliente.

O instalador ativa HTTPS privado com o comando abaixo. Configuração Serve/Funnel preexistente é preservada e impede instalação automática para evitar sobrescrevê-la:

```sh
sudo tailscale serve --bg http://127.0.0.1:8787
```

Não use Funnel. O serviço escuta somente em `127.0.0.1:8787`. `/etc/cloud-game/host.env` contém `CG_ORIGIN=https://nome.tailnet.ts.net` e `CG_STREAM_HOST=100.x.y.z`. A origem deve ser exatamente a URL usada pelo navegador. HTTP loopback é apenas para desenvolvimento.

Obtenha o código de instalação local com `sudo journalctl -u cloud-game -b`, abra a URL HTTPS privada e crie o administrador. O código perde validade após a primeira conta. Use **Verificar e recuperar HOST** no painel; configuração incompleta mantém o PC bloqueado. Cadastre cada jogador com senha/código longo e o IPv4 Tailscale do dispositivo que executará Moonlight. Nesta versão cada conta corresponde a um dispositivo de streaming; outro dispositivo precisa de outra conta.

## 4. Firewall e conectividade

O helper gera sua própria tabela `inet cloud_game`, sem `flush ruleset`. Ela bloqueia IPv6 da bridge, pacotes com IP de origem inesperado, acesso da VM a redes privadas e novas conexões da VM ao HOST. Autoriza saída pública para Steam e jogos. Durante a reserva, faz DNAT **somente do IP Tailscale autorizado** para a VM, nas portas TCP `47984,47989,48010` e UDP `47998,47999,48000,48002,48010`. A porta administrativa `47990` nunca é encaminhada.

**Pendente obrigatório de integração:** firewalld e as regras instaladas pelo Tailscale podem recusar encaminhamento em outras chains. `accept` na nossa chain não anula um `drop` posterior. Não desative firewalld para contornar. Autorize estritamente o encaminhamento tailscale0 → cgbr0 e o retorno/egresso necessário na política da versão instalada; valide os testes de rede antes de liberar usuários. A instalação não afirma que essa política já foi homologada no seu Bazzite.

Na tailnet, remova a permissão padrão irrestrita quando aplicável e use ACLs/grants que permitam aos jogadores alcançar apenas esse HOST em HTTPS e nas portas de streaming acima. Permita administração só às identidades desejadas. Isso é uma dependência de configuração da tailnet, não da senha da plataforma. Não abra portas no roteador. Não habilite subnet routes do HOST para a LAN do proprietário.

Tailscale usa coordenação externa e pode usar relay DERP. Não exige uma VM de processamento paga, mas os termos/limites do plano devem ser verificados antes de uso comercial. Alternativas são Headscale autogerido ou WireGuard; **não foram integradas aqui**. WireGuard exigiria adaptar a validação do peer, interface e procedimento TLS; não é uma opção selecionável implementada.

## 5. Cliente

Os clientes nativos CloudGame Android e Windows/Linux incorporam Moonlight no mesmo aplicativo. Seus builds de desenvolvimento estão no GitHub Actions; ainda não há release pública homologada. O `.deb` disponível é para Ubuntu 24.04 amd64, não para instalar no HOST Bazzite. Tailscale precisa estar conectado no dispositivo do jogador.

No aplicativo CloudGame, informe a origem HTTPS privada do HOST e entre com a senha da **plataforma**. Inicie a sessão e aguarde **Pronto para conectar**; depois use **Jogar / Reconectar**. O aplicativo inicia o pareamento nativo e envia o PIN para autorização pelo HOST automaticamente. O player só abre após a conclusão do pareamento e da autorização. Apenas uma tentativa efetiva de pareamento é admitida por sessão; falhas podem exigir encerrar e criar outra sessão.

Como alternativa manual para diagnóstico, a interface web de controle ainda mostra instruções para um [Moonlight oficial externo](https://moonlight-stream.org/). Essa alternativa não é o fluxo dos aplicativos nativos nem transmite vídeo pelo navegador.

Login Steam acontece na interface oficial da Steam **dentro da VM**. Fechar/desconectar Moonlight abre uma janela de até 120 segundos para reconexão à mesma sessão. Sem primeiro streaming, a reserva expira em 10 minutos. Limite total de 4 horas. Encerrar no Cloud Game descarta o ambiente; sair da conta Cloud Game, sozinho, não encerra streaming.

## 6. Recuperação, atualização e diagnóstico

Falha de limpeza mantém reserva e erro persistidos. No painel, consulte diagnóstico/registros e use recuperação; ela tenta revogar rede, destruir os domínios `cg-<UUID>` conhecidos, verificar processos e excluir somente `disk.qcow2` dentro dos diretórios UUID do volume autorizado. Qualquer nome, tipo de arquivo ou processo inesperado bloqueia a liberação. Não apague o banco para contornar bloqueio.

O boot/restart do HOST realiza recuperação antes de aceitar reservas. Um watchdog systemd independente, a cada ~30 segundos, limpa ao detectar serviço HOST parado ou prazo absoluto vencido. A falha do watchdog aparece no journal e deve ser investigada. O watchdog e o helper compartilham lock; não executam duas limpezas simultâneas.

Para manutenção: encerre a sessão, pare `cloud-game.service`, confirme ausência de VM e de processos QEMU da sessão, faça backup **consistente** do SQLite (API `.backup` da ferramenta sqlite3 ou serviço parado com WAL tratado) e preserve a imagem-base. Atualize arquivos revisados em `/opt/cloud-game`; nunca substitua imagem-base com uma VM ativa. Registre versões e repita ACCEPTANCE.md após Sunshine, kernel, Bazzite, drivers, libvirt ou Tailscale atualizados. Não desative SELinux; examine AVCs e crie política mínima quando necessária.

Recuperação de senha do único administrador: exige acesso local root. Ainda não há fluxo dedicado seguro de reset no painel; não crie um segundo admin via SQL sem procedimento auditado. Jogadores podem ter senhas alteradas/desativação feita no painel, encerrando sua sessão e revogando tokens.

## Referências oficiais revisadas

- [Bazzite: FAQ e restrições de plataforma](https://docs.bazzite.gg/General/FAQ/)
- [Bazzite: comparação e virtualização](https://docs.bazzite.gg/General/SteamOS_Comparison/)
- [Sunshine: configuração](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2configuration.html)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)

As referências fundamentam a integração; não substituem teste da combinação exata de hardware/software.

### Associação ao firewalld e conflitos de rede

O serviço de rede identifica sua bridge com o alias `cloud-game-managed-v1` e recusa uma `cgbr0` de outra origem, assim como rotas que sobreponham `10.77.0.0/24`. Em instalação antiga, uma bridge sem esse alias exige revisão administrativa de propriedade; o instalador não a toma automaticamente.

Quando firewalld está ativo, a configuração exige a zona `libvirt` e associa somente `cgbr0` a ela, em runtime e permanentemente. Confere conflitos nas duas configurações antes de escrever. Não executa reload global nem modifica a zona de `tailscale0`. As regras restritivas CloudGame são instaladas antes de ativar a bridge; portas administrativas do guest continuam bloqueadas. Configurações personalizadas, como políticas adicionais ou StrictForwardPorts, podem impedir tráfego e exigem homologação; o script não as desativa.

Referências: [rede e firewalld no libvirt](https://libvirt.org/firewall.html), [comandos de zonas firewalld](https://firewalld.org/documentation/man-pages/firewall-cmd.html). O teste CI de nftables usa namespaces sem firewalld e não comprova essa convivência no Bazzite.

### Assistente guiado (atualização)

O bootstrap público agora prepara automaticamente os pacotes nativos ausentes via rpm-ostree, ativa virtualização/Tailscale e guia a autorização de rede e HTTPS. A preparação manual descrita acima permanece como referência técnica, não como requisito para executar a CLI. Consulte [SETUP.md](SETUP.md) para reinício, retomada pelo menu e limites de recuperação.
