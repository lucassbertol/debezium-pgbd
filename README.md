# Captura de mudanças com Debezium e PostgreSQL

- **Grupo:** Lucas Bertol e Renato Marquioro
- **Disciplina:** Projeto e Gerência de Banco de Dados — 2026/2
- **Tema 10:** Captura de Mudanças de Dados em Tempo Real (Change Data Capture — CDC)
- **Status:** Captura, sincronização e interface local disponíveis. Slides e roteiro de demonstração preparados para a revisão final do grupo.

## Proposta

Demonstrar como o Debezium captura inserções, atualizações e exclusões confirmadas em um banco PostgreSQL e como essas mudanças são aplicadas de forma assíncrona em outro PostgreSQL.

O estudo de caso é o catálogo de uma loja. O banco de origem recebe as alterações de estoque e cadastro. O banco de destino mantém uma cópia do catálogo para consultas. A demonstração usa uma única tabela, `public.produtos`, com `id` como chave primária e os campos `nome` e `estoque`. Para cada alteração, o grupo vai mostrar o comando SQL na origem, o evento gerado e o efeito da operação no destino.

## Arquitetura proposta

```text
PostgreSQL de origem
    ↓ alterações confirmadas no WAL, decodificadas com pgoutput
Conector PostgreSQL do Debezium (Kafka Connect)
    ↓ eventos de mudança
Tópico Kafka
    ↓ consumo assíncrono
Debezium JDBC Sink (Kafka Connect)
    ↓ operações SQL
PostgreSQL de destino
```

1. **PostgreSQL de origem.** Os comandos `INSERT`, `UPDATE` e `DELETE` modificam o catálogo. O PostgreSQL registra as alterações no *Write-Ahead Log* (WAL). A replicação lógica usa `wal_level=logical`, uma publicação que inclui `public.produtos` e um slot de replicação que acompanha o avanço da leitura.
2. **Conector de origem.** O Debezium usa o plugin `pgoutput` para receber mudanças confirmadas e publicá-las no Kafka. A captura ocorre sem triggers na tabela e sem consultas periódicas ao catálogo.
3. **Kafka.** O tópico separa a captura da aplicação e permite inspecionar a chave e o tipo de cada evento. O evento pode estar disponível no tópico enquanto o destino ainda apresenta o estado anterior.
4. **Conector de destino.** O Debezium JDBC Sink consome os eventos e grava no segundo PostgreSQL. A configuração proposta usa a chave do evento (`primary.key.mode=record_key`), gravações em modo `upsert` (`insert.mode=upsert`) e exclusões habilitadas (`delete.enabled=true`). O `id` identifica a linha a inserir, atualizar ou remover.

O ambiente será executado localmente com Docker Compose. O `psql` servirá para consultar os dois bancos e um consumidor de console do Kafka exibirá os eventos durante a apresentação.

### Subir e conferir a captura na origem

Execute os comandos na raiz do repositório com Docker Compose, acesso ao daemon Docker, `curl` e Python 3.

```bash
docker compose up -d --wait
docker compose ps
curl --fail --silent --show-error -X PUT \
  -H 'Content-Type: application/json' --data-binary @connect/origem.json \
  http://127.0.0.1:8083/connectors/produtos-origem/config
curl --fail --silent --show-error \
  http://127.0.0.1:8083/connectors/produtos-origem/status | python3 -m json.tool
```

Quando o conector e a tarefa estiverem em `RUNNING`, execute `bash scripts/validar-captura.sh`. O script confere WAL lógico, permissões, publicação e slot ativo. Em seguida, insere um produto de teste, altera o estoque de 10 para 7, exclui o produto e verifica os eventos `c`, `u` e `d` para a mesma chave. Eventos `r` são leituras do snapshot inicial e ficam fora dessa verificação.

Para inspecionar diretamente as tabelas e os eventos, use:

```bash
docker compose exec origem psql -U postgres -d catalogo -c 'TABLE public.produtos'
docker compose exec destino psql -U postgres -d catalogo -c 'TABLE public.produtos'
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic catalogo.public.produtos \
  --from-beginning --property print.key=true
```

As credenciais são exclusivas da demonstração local. PostgreSQL e Kafka ficam na rede interna do Compose. A API do Connect é publicada em `127.0.0.1:8083`. Para parar o ambiente preservando os volumes, execute `docker compose down`.

### Pré-requisitos do PostgreSQL de origem

Reservar um slide do eixo técnico para explicar estes quatro pontos e conferi-los no ambiente antes do ensaio:

| Pré-requisito | O que mostrar e conferir |
| --- | --- |
| **WAL lógico** | Executar `SHOW wal_level;` e confirmar que o resultado é `logical`. |
| **Permissões** | Usar um usuário de conexão com `LOGIN` e `REPLICATION`, acesso ao banco e permissão de leitura na tabela para o snapshot inicial. |
| **Publicação** | Criar previamente uma publicação que inclua `public.produtos`. Conferir a tabela em `pg_publication_tables` e usar o mesmo nome na configuração do conector. |
| **Slot de replicação** | Configurar um nome de slot para o conector. Depois de iniciá-lo, conferir em `pg_replication_slots` se o slot pertence ao banco de origem, usa `pgoutput` e está ativo durante a captura. |

### Registrar e verificar o JDBC Sink

Com a origem em execução, registre o sink e confira seu estado:

```bash
curl --fail --silent --show-error -X PUT \
  -H 'Content-Type: application/json' --data-binary @connect/destino.json \
  http://127.0.0.1:8083/connectors/produtos-destino/config
curl --fail --silent --show-error \
  http://127.0.0.1:8083/connectors/produtos-destino/status | python3 -m json.tool
bash scripts/validar-sincronizacao.sh
```

O teste usa chaves negativas para os produtos de verificação. Confere os dois bancos após cada operação, inspeciona o evento de exclusão e o tombstone e comprova que o evento de inserção chega ao Kafka durante a pausa do sink. Depois da retomada, confirma a chegada da linha ao destino e remove o produto de teste.

### Operar pela interface web

Execute `docker compose up -d --build --wait` e registre os conectores de origem e destino com os comandos das seções anteriores. Abra [CDC em operação](http://127.0.0.1:8000/). A interface é servida localmente pelo FastAPI e atualiza os painéis a cada segundo.

1. Em **Origem**, informe ID, nome e estoque e use **Inserir produto**. Use **Editar** para alterar o estoque e **Excluir** para remover a linha da origem.
2. Em **Eventos**, confira a chave e a operação e abra **Ver JSON** para inspecionar o registro completo. O painel usa o consumidor Kafka dedicado `catalogo-interface` e mantém em memória os 40 eventos mais recentes recebidos.
3. Em **Destino**, compare a linha com a origem. Use **Pausar sink**, espere **Pausado** e insira outro produto. Confira o evento no Kafka e a ausência da linha no destino. Use **Retomar sink** e verifique que a linha aparece. O backend consulta esse banco em transações somente leitura.

O modo `schema.evolution=basic` permite ao JDBC Sink criar a tabela de destino com base no esquema dos eventos e adicionar colunas ausentes. **Na demonstração, o SQL de inicialização cria `public.produtos` e o sink usa `schema.evolution=none`**. A configuração mapeia `catalogo.public.produtos` para a tabela `produtos` no esquema JDBC `public` e usa o campo `id` da chave do evento para aplicar upserts e exclusões.

Antes da apresentação, fixar as versões das imagens usadas no Docker Compose, consultar a documentação da versão escolhida do Debezium e validar `insert.mode=upsert`, `delete.enabled=true`, `primary.key.mode=record_key` e o mapeamento de `id`. Os nomes e os comportamentos das propriedades podem variar entre versões. Confirmar que as tarefas dos conectores estão em execução e que cada operação produz o resultado esperado no destino.

No teste de exclusão, inspecionar o evento `op=d` com a chave do produto e, se habilitado no conector de origem, o *tombstone* que vem depois, com a mesma chave e valor nulo. Conferir se os registros esperados chegam ao sink com a chave preservada e se a consulta pelo `id` retorna zero linhas no destino. O JDBC Sink pode processar um evento de exclusão ou um tombstone, conforme a configuração e a versão usadas.

## Fundamentação teórica

- **Problema.** Manter uma cópia consultável do catálogo à medida que a origem muda, sem depender de uma nova cópia completa a cada alteração.
- **Conceitos.** Explicar CDC baseado em log, o papel do WAL, a decodificação lógica e a diferença entre confirmar uma transação na origem, publicar seu evento e aplicar a mudança no destino. Diferenciar também a carga inicial por *snapshot* (eventos de leitura `op=r`) do fluxo contínuo de alterações.
- **Vantagens.** A captura aproveita o log do banco e mantém o código que altera o catálogo separado do processo de sincronização. O tópico permite observar as mudanças e consumir os eventos em outro ritmo.
- **Limitações.** O destino pode ficar temporariamente defasado. Eventos podem ser reprocessados, por isso o sink usa a chave primária e `upsert` para que a reaplicação de uma gravação produza o mesmo estado. Se o conector de origem parar de avançar, o slot pode reter WAL e aumentar o uso de disco.

### Comparação com triggers e polling por timestamp

O catálogo de destino precisa refletir inserções, atualizações e exclusões da origem. As três abordagens diferem na forma de detectar essas mudanças e no trabalho necessário para entregá-las ao destino.

| Abordagem | Como funciona | O que exige ou limita |
| --- | --- | --- |
| **Triggers no PostgreSQL** | Uma trigger pode registrar cada `INSERT`, `UPDATE` e `DELETE` em uma tabela de eventos, na mesma transação que altera o catálogo. | Exige instalar e manter as triggers nas tabelas monitoradas. O registro do evento acrescenta trabalho à transação de origem, e outro processo precisa encaminhá-lo ao destino. |
| **Polling por timestamp** | Um processo consulta periodicamente a tabela pelo campo `updated_at` para buscar linhas inseridas ou atualizadas desde a última leitura. | Exige manter o timestamp atualizado e executar consultas periódicas. Mudanças sucessivas na mesma linha entre consultas podem aparecer apenas como seu estado mais recente. Uma exclusão física faz a linha desaparecer da consulta, então é preciso registrar a remoção separadamente ou usar exclusão lógica. |
| **Debezium com CDC baseado no WAL** | O conector lê as alterações confirmadas no log do PostgreSQL e publica eventos de inserção, atualização e exclusão. | Dispensa triggers de captura e consultas periódicas à tabela. Exige configurar a replicação lógica e monitorar o avanço do slot, pois atrasos na leitura podem aumentar a retenção de WAL. |

Se o estoque passar de **10 para 7 e depois para 4**, em duas transações confirmadas entre consultas, o polling pode enxergar apenas **4**. Se o produto for excluído fisicamente no mesmo intervalo, a consulta por `updated_at` não retorna essa exclusão. O Debezium pode capturar as duas atualizações e a exclusão como eventos separados. Isso permite que o grupo demonstre tanto o estado final do catálogo quanto as operações que levaram a ele.

## Demonstração ao vivo

Antes da apresentação, preparar os serviços, verificar os dois conectores e deixar abertas três sessões: SQL na origem, eventos do tópico e SQL no destino. Executar cada passo separadamente e consultar o destino pelo mesmo `id` antes de seguir.

| Passo | Ação na origem | Evento esperado | Verificação no destino |
| --- | --- | --- | --- |
| 1. Inserção | Cadastrar o produto `101` com estoque `10`. | `op=c`, com a chave `101`. | O produto aparece com estoque `10`. |
| 2. Atualização | Executar `UPDATE public.produtos SET estoque = 7 WHERE id = 101;` no `psql` da origem. | `op=u`, com o novo estoque. | O mesmo produto aparece com estoque `7`. |
| 3. Exclusão | Excluir o produto `101`. | `op=d`, com a chave `101`. | A consulta pelo `id` retorna zero linhas. |
| 4. Sincronização assíncrona | Pausar somente o sink, confirmar a pausa e cadastrar o produto `102`. | `op=c` aparece no tópico com o sink pausado. | O produto está na origem e ainda não aparece no destino. Depois de retomar o sink, ele aparece. |

Os resultados da tabela são os critérios de sucesso da demonstração. Durante o ensaio, registrar capturas que mostrem o SQL executado, os eventos e as consultas no destino. Para o teste de pausa, guardar uma captura antes da retomada e outra depois.

## Apresentação e entrega

A avaliação divide o trabalho em **fundamentação teórica (50%)** e **demonstração prática ao vivo (50%)**. O roteiro abaixo separa a apresentação nos três eixos exigidos e reserva aproximadamente 20 minutos dentro do limite indicado no enunciado.

- [Slides finais em PPTX](apresentacao/CDC-com-Debezium-e-PostgreSQL-alinhado.pptx)
- [Roteiro de demonstração, consultas SQL e recuperação](evidencias/etapa-5/roteiro.md)

| Eixo | Responsável proposto | Tempo | Conteúdo |
| --- | --- | --- | --- |
| Conceitual | Lucas | 8 min | Problema, conceitos, vantagens e limitações do CDC. |
| Técnico | Renato | 4 min | Estudo de caso, diagrama do fluxo, quatro pré-requisitos do PostgreSQL de origem e configuração da tabela e do sink no destino. |
| Demonstração | Renato | 8 min | Primeiro as capturas de tela nos slides, depois a execução ao vivo e a verificação nos dois bancos. |

Cada integrante apresenta pelo menos um eixo completo. Para a entrega, o grupo deve:

- A dupla respeita o limite de três integrantes. O grupo confirmou a exclusividade do Tema 10 na turma e o envio da composição e do tema ao professor (`mergen@inf.ufsm.br`).
- Cronometrar o ensaio completo com a fala de Lucas e Renato e as transições para a demonstração. O roteiro reserva 20 minutos. No ensaio automatizado, a sequência técnica levou 12,5 segundos, incluindo interações, comandos SQL e capturas.
- Incluir nos slides as capturas da solução funcionando, pois a avaliação considera o que foi realizado até a data de entrega.
- Entregar pelo Moodle os mesmos slides que serão apresentados. Basta um envio por grupo, na data comum a confirmar. A data da apresentação de cada grupo será divulgada com antecedência.

## Referências

- [Enunciado do trabalho](trabalho%20final.pdf)
- [Documentação do conector Debezium para PostgreSQL](https://debezium.io/documentation/reference/connectors/postgresql.html)
- [Documentação do Debezium JDBC Sink 3.4](https://debezium.io/documentation/reference/3.4/connectors/jdbc.html)
