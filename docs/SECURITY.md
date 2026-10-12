# Fronteiras e limites de segurança

## Ameaça considerada

Jogador autenticado pode executar programas dentro do desktop remoto e criar arquivos/processos arbitrários na VM. Portanto separar apenas `$HOME`, usar um container com os dispositivos do proprietário ou executar Sunshine na sessão gráfica do proprietário não satisfaz o isolamento pretendido.

A fronteira escolhida é KVM + IOMMU, sem mounts do HOST e sem discos físicos do proprietário. Requer GPU dedicada e sistema atualizado; não promete resistência a falhas de hypervisor/driver nem a ataques físicos. O jogador não deve ter administrador no guest, mas a arquitetura também não confia no guest para decidir quais arquivos do HOST apagar.

## Controles implementados

| Área | Controle |
|---|---|
| Conta | scrypt com salt aleatório; senha/código com pelo menos 12 caracteres; sem senha Steam na API |
| Sessão web | token aleatório de 256 bits, hash no SQLite, cookie HttpOnly/SameSite=Strict/Secure em HTTPS, validade 12 h, logout e revogação |
| Login | até 8 falhas por origem/socket e por nome de conta, janela de 15 min persistida no SQLite |
| Requisição | JSON limitado a 8 KiB, validação de campos, origem exata para mutações, sem CORS aberto, CSP e proteção de framing |
| Exclusividade | compare-and-set SQL de estado, trava de operação no serviço e flock no helper root |
| Autorização | sessão só pode ser encerrada pelo dono ou admin; pareamento só pelo dono; estado público autenticado não revela sessão de outro usuário |
| VM | domínio transient UUID, um disco overlay, uma NIC dedicada, GPU/áudio VFIO, sem compartilhamento de pastas ou console de rede |
| Rede | HTTPS privado via Serve; origem exata configurada; IP do dispositivo definido pelo admin; porta Sunshine 47990 ausente do DNAT |
| Descarte | tráfego da bridge fechado antes de destruir VM; ausência de domínios/QEMU confirmada; só arquivo disk.qcow2 autorizado; falha preserva bloqueio |
| Reinício | recupera antes de liberar reservas; watchdog root tem prazo de 4 h independente do cliente |

Os códigos individuais são senhas longas administradas por usuário, **não OTP** de seis dígitos. O PIN Moonlight de quatro dígitos só funciona dentro de uma reserva autenticada e não é credencial da plataforma. O pareamento é marcado antes de chamar Sunshine, para falha/restart não permitir adicionar outro cliente. A imagem-base precisa estar sem pares anteriores.

## Dados e biblioteca

Imagem-base somente leitura contém OS, launchers, runtimes e jogos autorizados. O overlay da VM inteira recebe homes, saves, caches, alterações na biblioteca, credenciais e processos da sessão. Não há persistência de saves locais entre sessões. Saves na nuvem podem permanecer ou ser sincronizados mesmo após limpeza; não há promessa de apagá-los.

Tmpfs é usado para evitar manter overlay em disco; o diagnóstico recusa swap. O descarte é **lógico**, não apagamento forense da RAM, SSD, dumps, hibernação ou sistemas externos. O administrador deve impedir hibernação/crash dumps e não capturar a memória da VM. Backups só devem conter imagem-base limpa e banco de controle, nunca RAM/overlay de uma sessão.

## Confiança administrativa e limitações

- Root do HOST, kernel, libvirt, firmware, IOMMU e imagem-base são confiáveis. Um proprietário malicioso tem controle do hypervisor e pode observar a VM; a plataforma não promete esconder credenciais do operador físico do HOST.
- O helper verifica classes PCI/grupos/driver, mas não certifica segurança do firmware, reset correto da GPU, uso de memória da placa ou ausência de bugs de passthrough. Homologação específica de GPU é indispensável.
- `templateReviewed` é uma declaração administrativa, não um detector de credenciais. Não é possível provar automaticamente que uma imagem nunca teve dados pessoais. Ela deve ser criada limpa e testada em clones descartáveis.
- API de controle e streaming compartilham a rede privada, mas usam canais e credenciais distintos. IP Tailscale autorizado é vínculo por dispositivo, não prova adicional de identidade humana. Um dispositivo já comprometido pode compartilhar sua conexão/certificado.
- Apenas um pareamento é aceito por sessão; mais de uma conexão reportada pelo Sunshine provoca encerramento pelo monitor. O adaptador não altera o protocolo para impedir criptograficamente que um dispositivo comprometido duplique seu certificado antes da detecção.
- O monitor de conexão depende de mensagens do journal da invocação corrente do Sunshine; não é telemetria assinada nem comprovação de que quadros foram decodificados pelo cliente. Mudanças no formato, rotação/rate-limit de logs ou comprometimento do guest precisam ser avaliados. Não usar `serverinfo.currentgame` como prova: ele pode continuar ocupado sem cliente conectado.
- O status de controle atualiza a cada 2 s, o monitor Linux a cada 5 s, e o diagnóstico ocioso a cada 30 s. Há latência de observação; não é telemetria instantânea. Sem resposta do HOST, o cliente mostra estado desconhecido, nunca disponibilidade presumida.
- O bloqueio por socket atrás do Tailscale Serve pode agrupar usuários em 127.0.0.1. Isso é conservador e pode causar negação de login temporária entre usuários; não confiamos em X-Forwarded-For fornecido pelo cliente.
- SQLite `node:sqlite` ainda emite aviso experimental no runtime validado. Esquema inicial criado idempotentemente; não há framework de migração ou backup automático implementado.
- Logs/auditoria e registros de usuários ficam no banco local. Não registramos senhas, tokens, PINs ou chamadas Steam. A retenção automática da auditoria ainda não existe; monitore espaço em disco.
- Administração remota não edita comandos, XML, caminhos, GPU ou imagem-base. Esses campos ficam em configuração root-only. O serviço Node não roda como root, mas sua permissão de invocar o helper é sensível e precisa ser auditada.
- Scripts de instalação não têm rollback transacional e não sobrescrevem uma instalação existente. A configuração completa ainda demanda conhecimento de virtualização; o requisito de instalação simples universal permanece pendente.

## Testes obrigatórios antes de liberar jogadores

Veja ACCEPTANCE.md. Especialmente: acesso da VM ao HOST/LAN, novos pares fora da reserva, duas conexões, symlinks, VM órfã, falha de libvirt, queda do serviço, reboot, retorno de GPU, firewalld, SELinux, OOM e ausência de credenciais no próximo clone. Testes de unidade com subprocessos substituídos não aprovam essas fronteiras.
