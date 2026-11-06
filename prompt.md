# Instruções para executar o trabalho de CDC com Debezium e PostgreSQL

Você vai ajudar **Lucas Bertol e Renato Marquioro** a implementar e apresentar o trabalho prático de **Projeto e Gerência de Banco de Dados — 2026/2**, do professor Sergio Mergen. O tema é **Captura de Mudanças de Dados em Tempo Real (CDC)**, Tema 10 do enunciado.

Leia todas as páginas de [trabalho final.pdf](trabalho%20final.pdf) e o [README.md](README.md) antes de começar. Em caso de divergência, siga o PDF para os requisitos acadêmicos. Use o README como referência para as escolhas técnicas já discutidas. Trate a interface web, o teste de pausa e a divisão de tempo abaixo como escolhas do projeto.

## Regra obrigatória de execução

1. Comece pela etapa 1. Execute **uma única etapa por vez**, inclusive quando a etapa for apenas de planejamento.
2. Ao concluir a etapa, revise seus critérios de saída e informe quais arquivos ou artefatos foram produzidos, quais verificações foram executadas, quais resultados foram observados e quais pendências restaram.
3. Termine a resposta com **“Posso avançar para a etapa N — [nome da etapa]?”** e espere uma autorização explícita em uma nova mensagem. Planejamento prévio, aprovação de uma etapa e ausência de resposta são insuficientes para iniciar etapas posteriores. Cada autorização libera apenas a próxima etapa.
4. Se o grupo pedir ajustes, permaneça na etapa atual, aplique as correções, repita as verificações e solicite autorização novamente. Se um critério de saída falhar, investigue dentro da etapa e reporte o bloqueio caso ele persista.
5. Ao encerrar a última etapa, entregue o resumo final e indique as ações administrativas que cabem ao grupo. Registre apenas resultados realmente observados.

## Etapa 1 — Validar o escopo e mapear o PDF

- Identifique as exigências do PDF por página e mapeie cada uma para uma etapa e uma evidência. Separe exigências do enunciado de decisões do grupo.
- Confirme o escopo de uma loja com uma tabela `public.produtos`, contendo `id` como chave primária, `nome` e `estoque`. A origem recebe as operações de escrita e o destino mantém uma cópia consultável.
- Defina a arquitetura local. Use Docker Compose com dois PostgreSQL, Kafka, Kafka Connect com o conector PostgreSQL do Debezium e o Debezium JDBC Sink. Use FastAPI com HTML, CSS e JavaScript para a tela de demonstração.
- Verifique as dependências disponíveis e proponha versões compatíveis com base na documentação oficial correspondente. Registre as versões exatas na configuração quando implementar.
- Registre que a dupla respeita o máximo de três integrantes. A exclusividade do tema na turma depende de confirmação. Um representante deve comunicar por e-mail ao professor (`mergen@inf.ufsm.br`) a formação e o tema escolhido. Se o grupo trocar para um tema fora dos sugeridos, registre a exigência de avaliação e concordância do professor.
- Registre que o professor reservou duas datas para apresentações, que a data de cada grupo será divulgada com antecedência e que a data comum de entrega ainda será confirmada no enunciado. Confira com o grupo se já houve divulgação.

**Critério de saída:** requisitos mapeados, escopo e arquitetura apresentados, pendências administrativas identificadas e nenhum serviço implementado nesta etapa.

## Etapa 2 — Preparar o ambiente e validar a captura

- Implemente o Compose e os scripts SQL de inicialização. Crie `public.produtos` em ambos os bancos, com colunas de tipos compatíveis e `id` como chave primária. Prepare os serviços para subir de forma reproduzível e aguardar a disponibilidade das dependências.
- Na origem, confirme `wal_level=logical`, acesso do usuário ao banco, `LOGIN`, `REPLICATION` e leitura da tabela para o snapshot. Crie previamente a publicação que inclui `public.produtos`. Configure o conector com `pgoutput`, o nome da publicação e um slot dedicado. Confira a publicação e o slot nas visões do PostgreSQL.
- Registre o conector de origem, confira o estado da tarefa e observe no tópico eventos reais de `INSERT`, `UPDATE` e `DELETE` executados com SQL. Distinga eventos de snapshot (`op=r`) de mudanças capturadas após a carga inicial.
- Registre comandos para subir e conferir o ambiente. Mantenha credenciais de demonstração restritas ao ambiente local.

**Critério de saída:** serviços acessíveis, pré-requisitos da origem conferidos e eventos reais `c`, `u` e `d` observados no tópico para a mesma chave.

## Etapa 3 — Sincronizar com o PostgreSQL de destino

- Configure o Debezium JDBC Sink para consumir o tópico e escrever na tabela previamente criada, com `schema.evolution=none`. Mapeie explicitamente a tabela conforme a versão escolhida. Explique no README a alternativa de criação automática com `schema.evolution=basic`.
- Valide na versão instalada `insert.mode=upsert`, `delete.enabled=true`, `primary.key.mode=record_key` e o mapeamento de `id`. Na exclusão, confira o evento `op=d`, a chave e o tombstone quando habilitado. Verifique o tratamento desses registros pelo sink e a remoção efetiva da linha.
- Execute cada operação separadamente e consulte o destino após cada uma. Pause apenas o sink pela API do Kafka Connect, confirme a pausa, insira outro produto na origem e observe o evento no tópico enquanto a linha ainda está ausente no destino. Retome o sink e confirme que a linha chega.

**Critério de saída:** inserção, atualização, exclusão e aplicação após a retomada comprovadas com SQL nos bancos, eventos do Kafka e estado do conector.

## Etapa 4 — Construir a interface web

- Crie uma página com três painéis. **Origem** mostra uma consulta real ao primeiro PostgreSQL e permite inserir, alterar estoque e excluir. **Eventos** mostra registros recebidos por um consumidor Kafka dedicado à interface, com chave, operação e opção de ver o JSON. **Destino** consulta o segundo PostgreSQL e exibe o estado do sink com ações de pausar e retomar via Kafka Connect.
- Use SQL parametrizado e valide as entradas. A aplicação escreve apenas na origem. O JDBC Sink é responsável por escrever no destino. Diferencie estados de carregamento, lista vazia e falha de conexão. Atualize os painéis periodicamente para que o atraso fique visível.
- Execute todo o roteiro pela interface e confirme os resultados diretamente nos dois bancos. Registre no README como acessar a página e operar o ambiente.

**Critério de saída:** página funcional no Compose, painéis ligados a dados reais e operações verificadas de ponta a ponta, inclusive pausa e retomada.

## Etapa 5 — Ensaiar e coletar evidências

- Parta de um ambiente limpo de demonstração e repita a subida conforme o README. Separe os comandos de verificação SQL na origem e no destino para mostrar a manipulação e a comunicação direta com PostgreSQL.
- Insira o produto `101` com estoque `10`, altere para `7` e exclua. A cada operação, mostre o mesmo `id` na origem, no evento e na verificação do destino. Para a exclusão, mostre a consulta que retorna zero linhas.
- Pause somente o sink, confirme a pausa e insira o produto `102`. Mostre origem e evento atualizados com a linha ainda ausente do destino. Retome o sink e mostre a linha no destino.
- Capture telas reais, legíveis e sem credenciais expostas. Guarde evidências para as três operações e para os estados antes e depois da retomada. Cronometre o roteiro e anote como recuperar o ambiente se um serviço falhar no ensaio.

**Critério de saída:** roteiro reproduzido em ambiente limpo, resultados registrados e capturas reais disponíveis para inserir nos slides.

## Etapa 6 — Criar e revisar os slides

Produza um deck editável em **PPTX** com os slides que o grupo vai apresentar. Use capturas produzidas na etapa anterior e referências à documentação oficial das versões usadas. Prepare notas de fala para os três eixos.

| Eixo | Responsável proposto | Tempo sugerido | Conteúdo |
| --- | --- | --- | --- |
| Conceitual | Lucas, eixo completo | 8 min | Contexto, problema da sincronização, CDC, WAL, vantagens e limitações. Compare com triggers e polling por timestamp, incluindo o caso de uma exclusão física. |
| Técnico | Renato, eixo completo | 4 min | Estudo de caso, diagrama da arquitetura, trechos essenciais da configuração e quatro pré-requisitos da origem. Explique também como o sink usa a chave para escrever no destino. |
| Demonstração | Renato, eixo completo | 8 min | Primeiro, slides com capturas reais da aplicação funcionando. Em seguida, execução ao vivo de inserção, atualização, exclusão e pausa/retomada, com evidência da integração direta com PostgreSQL. |

- Abra com título, disciplina, tema e nomes completos do grupo. Inclua slides para a teoria, comparação, arquitetura, configuração e evidências. Reserve uma tela legível para o teste assíncrono antes e depois da retomada.
- A fundamentação teórica vale **50%** e a demonstração prática ao vivo vale **50%**. Esses percentuais são pesos de avaliação. O tempo sugerido soma **20 minutos**, respeitando o limite aproximado de **20–25 minutos** indicado no PDF.
- Preserve a exigência de que cada aluno apresente pelo menos um eixo inteiro. Use o ensaio para revisar clareza, domínio teórico e organização. Ajuste o aprofundamento à complexidade do tema e ao tempo disponível, mantendo o fluxo de CDC compreensível.
- Renderize e revise todos os slides. Confira legibilidade em projeção, cortes, contraste, fidelidade das imagens e correspondência entre notas, comandos e o ambiente real. Mostre o deck ao grupo antes de iniciar a revisão final.

**Critério de saída:** PPTX revisado visualmente, capturas reais incluídas, notas preparadas e distribuição de conteúdo e tempo conferida.

## Etapa 7 — Revisar o trabalho e preparar a entrega

- Cruze novamente o resultado com todas as páginas do PDF. Revise os três eixos, a apresentação integral de pelo menos um eixo por integrante, as capturas antes da execução ao vivo e a comprovação de manipulação direta de dados em PostgreSQL.
- Confirme a duração em um ensaio completo e revise a correspondência entre o deck final e a demonstração. A avaliação considera o que foi realizado até a data de entrega, então inclua nos slides as evidências do que já está implementado.
- Entregue ao grupo o PPTX final, o link para o README e o roteiro de demonstração. A entrega exigida é a dos **mesmos slides que serão apresentados**, via **Moodle**, por **um integrante** na data comum definida pelo professor. Registre a data como pendente enquanto ela não estiver confirmada. Deixe o envio e a comunicação com o professor a cargo do grupo.

**Critério de saída:** arquivos finais identificados, requisitos e evidências conferidos e pendências de entrega explicitadas ao grupo.
