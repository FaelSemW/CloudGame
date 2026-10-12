# Homologação obrigatória em Bazzite e clientes

Todos os itens desta página estão **pendentes em hardware real**. Registre data, versões, GPU/driver, imagem-base, dispositivos, resultado e evidências. Não marque um teste como aprovado com base apenas nos testes unitários Windows.

| Teste | Procedimento | Evidência exigida |
|---|---|---|
| Instalação/boot | Execute instalador na imagem Bazzite escolhida; reinicie | `systemctl status` do HOST, mount, bridge e watchdog; SELinux enforcing; diagnóstico completo |
| Prerequisitos | Remova temporariamente um pré-requisito em laboratório ou configure GPU incorreta | HOST bloqueado, erro compreensível, nenhuma VM criada |
| Reserva | Envie pedidos de duas contas/dispositivos simultaneamente | Exatamente um domínio QEMU e um dono; outro recebe conflito/ocupado |
| Sunshine | Inicie sessão com imagem preparada | Agent responde, API local autentica, captura/encoder funciona; nenhuma porta 47990 pública |
| Android | Pelo Android real em outra rede, autentique, reserve, pareie e abra Desktop | Vídeo real de jogo, áudio, controles; versão/dispositivo e gravação do resultado |
| Windows/Linux | Repita com Moonlight Qt em ambas as plataformas pretendidas | Mesmo fluxo real; teclado, mouse, gamepad e decoder confirmados |
| Rede privada | Teste da LAN, internet pública e outro IP Tailscale | Painel fora da tailnet inacessível; portas de streaming somente para peer reservado |
| Firewall | Inspecione nftables/firewalld/Tailscale e tente rede do guest | Sem acesso novo ao HOST, owner LAN, outros peers ou IPv6; Steam público funciona |
| Dados do proprietário | Crie arquivo sentinela pessoal no HOST; procure via guest | Nenhum share, disco ou caminho pessoal visível; sentinela intacta após sessão |
| Biblioteca | Altere arquivo de jogo dentro do guest | Hash correspondente na imagem-base não muda; clone posterior recupera original |
| Credenciais | Faça login de teste Steam só em clone; encerre e inicie outra sessão | Perfil/login local não persiste; jamais copie credenciais em logs de evidência |
| Processos filhos | Deixe processo e filho executando e encerre pelo painel | VM/QEMU ausentes, overlay ausente, nenhum processo do guest sobrevivente |
| Desconexão | Saia do Moonlight e reconecte em menos de 120 s | Mesmo UUID; nenhuma VM duplicada; estado confirmado pelo Sunshine |
| Desconexão expirada | Não reconecte por mais de 120 s | Descarte e retorno a disponível somente após verificação |
| Sem primeira conexão | Reserve e não abra Moonlight por 10 min | Descarte automático, sem dependência de aba aberta |
| Dois streams | Tente abrir segundo stream usando certificado copiado em laboratório | Encerramento por detecção de múltiplas conexões; medir janela e aprovar política |
| Pareamento revogado | Reutilize cliente de uma sessão anterior sem novo PIN | Sem acesso até novo pareamento; conta/IP de outro usuário não consegue parear |
| Falha de limpeza | Provoque recusa de `virsh destroy`/arquivo inesperado no tmpfs em laboratório | Estado bloqueado persistente; reserva seguinte recusada; recuperação não apaga arquivo inesperado |
| Caminhos e symlinks | Insira symlink/entrada inesperada na área de sessão em laboratório | Limpeza bloqueada; destino fora do escopo intacto |
| Serviço parado | Pare abruptamente o processo HOST durante streaming | Watchdog limpa em aproximadamente 30–35 s quando não estiver aguardando lock; reinício recupera antes de liberar |
| Reinício da máquina | Reinicie durante streaming | tmpfs anterior ausente; nenhum par/credencial da sessão; novo HOST só libera após recuperar |
| GPU reset | Faça vários ciclos rápidos de iniciar/encerrar | GPU reutilizável e isolamento mantido; erro mantém bloqueio quando detectado |
| Memória/disco | Esgote quota tmpfs em sessão de teste | Não afeta imagem-base/arquivos pessoais; retorno seguro ou bloqueio, sem disponibilidade falsa |
| Senha/revogação | Desative conta/troque senha com sessão ativa | Sessão encerrada, tokens antigos recusados, conta desativada não entra |
| Atualização Bazzite | Atualize/reinicie em laboratório | `/opt`, `/etc`, `/var` preservados, serviço funcional; nenhum relaxamento de segurança |

## Evidências locais já disponíveis

- `npm test`: 22 testes de controle/API, com SQLite real; backend Linux substituído **somente nos testes**.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: 11 testes de políticas/geração de comandos, sem KVM/nft reais.
- `npm run check` e `py_compile`: análise sintática, não execução Linux.
- Navegador local: tela de primeira configuração revisada, layouts desktop e estreito sem overflow horizontal.

Não use estes resultados como homologação de streaming, desempenho, isolamento de GPU, instalador Bazzite ou segurança do kernel.
