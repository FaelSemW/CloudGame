# HOST nativo, sem máquina virtual

O instalador do código atual executa Sunshine e Steam no próprio kernel Linux do Bazzite. Não baixa imagem Ubuntu, não inicia QEMU/libvirt e não exige VFIO. Os arquivos do backend antigo permanecem para preservar o histórico; não são executados pelo assistente nativo. O pacote público ainda deve ser atualizado após a verificação de streaming deste backend.

## Isolamento e descarte

Cada reserva cria um desktop separado, com o usuário `cloud-game-player`, namespaces bubblewrap, rede própria e cgroup systemd. O desktop e os diretórios pessoais do proprietário não são compartilhados. O jogador não recebe sudo, barramento de sistema, dispositivos de entrada globais ou nós DRM que controlam o monitor físico. Somente render nodes da GPU são disponibilizados.

Home, autenticação dos launchers e runtime ficam em `/var/lib/cloudgame/native-volatile`, um mount tmpfs. Swap em disco é recusado. A limpeza revoga a rede, encerra o cgroup, verifica processos e remove somente o diretório da sessão identificada. Falhas mantêm o HOST bloqueado. Saves sincronizados com Steam Cloud não são apagados.

Namespaces compartilham o kernel do HOST: essa fronteira não equivale à de uma VM. Falta homologar isolamento no Bazzite com SELinux ativo e hardware real antes de disponibilizar a jogadores não confiáveis.

## Instalação e retomada

O assistente instala dependências ausentes por rpm-ostree, incluindo RPM oficial Sunshine fixado por versão e SHA-256. Preserva atualizações pendentes e salva progresso quando é necessário reiniciar. Não usa apt/dnf no Bazzite, não altera BIOS e não configura VFIO.

Tailscale requer autorização no navegador, MagicDNS e HTTPS. O painel permanece em loopback, publicado apenas por Tailscale Serve privado, sem Funnel.

O novo estado fica em `/var/lib/cloud-game-native-installer`. Após reiniciar, use **Cloud Game — continuar instalação**. Se o menu não o mostrar:

```sh
sudo python3 /var/lib/cloud-game-native-installer/source/deploy/setup_host.py
```

O instalador antigo em `/var/lib/cloud-game-installer` continua sendo a versão VM: não o use para retomar o modo nativo. Se ele estiver baixando Ubuntu, interrompa esse processo com Ctrl+C antes de iniciar o novo instalador. Não apague diretórios manualmente. Uma instalação antiga completa em `/opt/cloud-game` é preservada e bloqueia migração automática, exigindo revisão específica.

## Perfis e limites reais

- `--software`: Xvfb/Openbox e codificação por CPU, para testar mesmo dentro da VM Bazzite existente. Não cria uma VM adicional e não representa desempenho de jogos.
- Perfil padrão: Sway headless, Sunshine/wlr e render nodes da GPU. Captura/encoder dependem da GPU e do driver; precisam de validação em Bazzite físico. NVIDIA não está homologada.
- Teclado e mouse usam o fallback XTest do libvirtualhid oficial no X11/Xwayland privado. Aplicativos Wayland nativos não têm entrada garantida.
- **Gamepads desativados neste backend.** Expor `/dev/uinput` ou `/dev/uhid` ao jogador permitiria entrada fora do desktop privado. A ativação depende de um mecanismo de entrada separado e validado.
- A biblioteca persistente do administrador em `/var/lib/cloudgame/library` aparece somente para leitura em `/games`. Importação e uso transparente pela Steam ainda não estão implementados. Jogos que exigem escrita no diretório de instalação não estão homologados. Downloads na home temporária somem ao encerrar; não considere esse ponto uma biblioteca compartilhada completa.
- O tmpfs tem limite de 8 GiB e disputa RAM com o HOST. Steam pode precisar baixar seu runtime a cada sessão; otimização persistente segura pendente.

## Diagnóstico e evidências

```sh
sudo journalctl -u cloud-game -b --no-pager
sudo journalctl -u 'cg-native-*' -b --no-pager
```

Recupere pelo painel HOST. Não altere a reserva no SQLite nem remova seu arquivo manualmente: isso contornaria a verificação de descarte.

O workflow `native-host.yml` testa captura Sunshine, pareamento/decodificação Moonlight e descarte em Linux de CI, sem QEMU. Esse teste não substitui instalação Bazzite, Steam/jogos, entrada, GPU, Android ou rede Tailscale real.
