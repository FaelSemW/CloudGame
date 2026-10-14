# Assistente de instalação Bazzite

> **Atualização: o instalador público atual usa [sessões nativas sem VM](NATIVE-HOST.md).** O texto abaixo é histórico do instalador VM antigo. Use o guia nativo; não retome a cópia antiga para testar o novo modo.

A CLI pública executa `deploy/setup_host.py`, não interrompe mais só porque QEMU/libvirt/Tailscale estão ausentes. Ela verifica Bazzite por `/etc/os-release`, usa apenas pacotes Fedora fixos e `rpm-ostree install --idempotent --allow-inactive`, e não executa apt/dnf sobre o HOST imutável. O QEMU Flatpak do assistente Bazzite não substitui os serviços nativos exigidos por este backend.

1. Autorize a instalação quando o sistema pedir privilégios administrativos.
2. Em VM, use `--software`. Sem essa opção, se não houver GPU já dedicada a VFIO, o assistente oferece explicitamente o perfil de teste por CPU. Não desconecta a GPU usada pelo proprietário.
3. As dependências ausentes são instaladas automaticamente. Uma atualização pendente do sistema é preservada e pede reinício antes de continuar.
4. O assistente salva o progresso e oferece reiniciar. Após o reinício, abra **Cloud Game — continuar instalação** no menu de aplicativos. Não precisa copiar arquivos nem executar uma sequência de comandos. A retomada pede novamente autorização administrativa.
5. libvirt e Tailscale são ativados. Se a máquina já estiver autenticada, as preferências da tailnet são preservadas. Caso contrário, autorize pelo link mostrado pelo comando oficial Tailscale.
6. Se HTTPS ainda estiver desabilitado, abra o endereço do painel Tailscale mostrado, habilite MagicDNS/certificados HTTPS e pressione Enter. O assistente verifica a emissão do certificado e descarta os arquivos de teste. Não solicita senha, auth key ou token no terminal.
7. O provisionador prepara Sunshine/Steam/Xfce dentro da imagem isolada e verifica outro boot. O assistente verifica os serviços, diagnóstico privilegiado e o acesso HTTPS ao painel antes de indicar conclusão. Mostra o código de configuração de uso único localmente para criar o administrador.

O atalho apenas retoma a instalação; não é um terceiro aplicativo. O código copiado e o estado ficam em `/var/lib/cloud-game-installer`, pertencentes ao root, com estado em modo 0600 e lock contra duas execuções. Não são guardadas credenciais Steam nem links de autenticação no estado. Retomar usa a mesma versão persistida do instalador. Configurações existentes conflitantes são preservadas.

## Limites de recuperação

A retomada cobre a preparação, reinício por dependências, login/HTTPS e verificação final. Uma falha durante a escrita dos arquivos do HOST pode deixar instalação parcial: ela é preservada e bloqueia sobrescrita automática, exigindo diagnóstico. Um comprovante root registra a conclusão do instalador HOST e permite retomar a verificação após interrupção entre essa conclusão e a gravação do progresso.

O wizard não modifica configurações da BIOS, não inventa suporte a GPU passthrough e não ignora restrições de SELinux/firewall. Uma versão Bazzite sem rpm-ostree que precise de pacotes adicionais é recusada, sem tentar comandos incompatíveis. Layering pode exigir manutenção após atualizações do sistema. A implantação real no Bazzite será testada pelo proprietário; testes automatizados de fluxo não substituem essa validação.

## Referências verificadas

- [Pacotes em camada no Bazzite](https://docs.bazzite.gg/Installing_and_Managing_Software/rpm-ostree/)
- [Receita oficial de virtualização Bazzite](https://github.com/ublue-os/bazzite/blob/main/system_files/desktop/shared/usr/share/ublue-os/just/84-bazzite-virt.just)
- [Pacotes libvirt para sistemas RPM](https://www.libvirt.org/kbase/rpm-deployment.html)
- [Repositório Fedora oficial Tailscale, com verificação GPG](https://pkgs.tailscale.com/stable/fedora/tailscale.repo)
- [Autorização Tailscale](https://tailscale.com/docs/reference/tailscale-cli/up)
