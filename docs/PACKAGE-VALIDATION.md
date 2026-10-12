# Validação do pacote — 12/10/2026

Artefato: `dist/cloud-game.pyz`, construído por `python3 tools/package.py`. Distribui apenas arquivos selecionados de HOST, cliente web, deploy, documentação e licenças. Não inclui bancos locais, senhas, checkouts de terceiros ou os esboços de integração nativa ainda não compilados.

Executado no Windows: 22 testes existentes de controle/API aprovados; 1 teste adicional verifica que o modo laboratório recusa operações privilegiadas; 14 testes Python aprovados, incluindo integridade do pacote e rejeição de caminhos fora do destino. Verificação de sintaxe Node e compilação sintática Python aprovadas. O comando `verify` do artefato gerado passou.

Não executado: instalação deste artefato no Bazzite, download/execução do Node Linux pela CLI, systemd, GPU, streaming, encerramento de processos reais e descarte real de VM. Os testes automatizados não substituem essas verificações. O modo laboratório não é evidência de streaming funcional.

Alterações desta entrega: `tools/package.py`, `tools/package_cli.py`, `deploy/runtime.py`, `deploy/install_host.py`, `host/backend.mjs`, `tests/test_package.py`, `tests/lab.test.mjs` e documentação PACKAGE. O download de runtime foi centralizado; o instalador de produção continua recusando substituição de instalações existentes.

Pendências para o pacote completo solicitado: concluir e compilar integrações nativas Android/desktop, empacotar dependências e fontes correspondentes de Moonlight, provisionar e homologar imagem Sunshine, validar instalação Bazzite e cumprir todos os critérios de ACCEPTANCE. Este artefato é um pacote de avaliação do controle, não uma release completa de cloud gaming.
