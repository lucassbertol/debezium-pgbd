# Captura de mudanças com Debezium e PostgreSQL

- **Grupo:** Lucas Bertol e Renato Marquioro
- **Disciplina:** Projeto e Gerência de Banco de Dados — 2026/2
- **Tema 10:** Captura de Mudanças de Dados em Tempo Real (Change Data Capture — CDC)
- **Tecnologias:** PostgreSQL 17, Debezium 3.4 (conector PostgreSQL e JDBC Sink), Apache Kafka 4.1 com Kafka Connect, Docker Compose e uma interface FastAPI.
- **Status:** Captura, sincronização e interface local funcionando, com ensaio registrado em `evidencias/etapa-5`. Falta o ensaio cronometrado com a fala do grupo.

## Proposta

Demonstrar como o Debezium captura, pelo WAL e sem triggers, as inserções, atualizações e exclusões confirmadas em um banco PostgreSQL e como essas mudanças são publicadas no Kafka e aplicadas de forma assíncrona, em quase tempo real, em outro PostgreSQL.

O estudo de caso é o catálogo de uma loja. O banco de origem recebe as alterações de estoque e cadastro. O banco de destino mantém uma cópia do catálogo para consultas. A demonstração usa uma única tabela, `public.produtos`, com `id` como chave primária e os campos `nome` e `estoque`. Para cada alteração, a demonstração mostra o comando SQL na origem, o evento gerado no Kafka (com o tempo entre o commit e a captura) e o efeito da operação no destino.

## Arquitetura

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

O ambiente roda localmente com Docker Compose. O `psql` consulta os dois bancos, e a interface web (ou o consumidor de console do Kafka) exibe os eventos.

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

Os quatro pontos abaixo são conferidos por `scripts/validar-captura.sh` e explicados no slide 11:

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

Com o Docker em execução e o Docker Compose **2.24.4 ou posterior**, rode o inicializador na raiz do projeto.

**Linux**

```bash
./iniciar-web.sh
```

**Windows (PowerShell, com Docker Desktop em modo de contêineres Linux)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar-web.ps1
```

Abra a [demonstração](http://127.0.0.1:18000/) quando o inicializador indicar que está pronta. **Este é o ambiente usado na apresentação.** Ele registra os dois conectores e confere que os bancos e o painel de eventos começam vazios. Cada execução apaga os volumes **do projeto descartável `debezium-pgbd-demo-vazia`**, incluindo produtos e eventos de demonstrações anteriores. O projeto normal usa a porta `8000` e seus dados ficam separados. Execute um inicializador por vez.

Para abrir as duas sessões SQL da demonstração, use `psql-origem.cmd` e `psql-destino.cmd` no Windows (duplo clique) ou `./psql.sh origem` e `./psql.sh destino` no Linux. Eles equivalem aos comandos abaixo. A API do Kafka Connect dessa instância fica em `http://127.0.0.1:18083/`; no Windows PowerShell, chame-a com `curl.exe`, não com `curl`.

```bash
docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml exec origem psql -U postgres -d catalogo
docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml exec destino psql -U postgres -d catalogo
```

Para parar a instância, execute `docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml down`.

1. Em **Origem**, informe ID, nome e estoque e use **Inserir produto**. As linhas de cada banco aparecem nos painéis **Origem** e **Destino**, atualizadas a cada 0,3 s. Abra **Consultar banco** para usar **Editar** ou **Excluir** na linha do produto.
2. Em **Eventos**, confira a chave, a operação e o tempo de captura (`ts_ms − source.ts_ms`, do commit na origem ao processamento pelo Debezium) e abra **Ver JSON** para inspecionar o registro completo. O painel usa o consumidor Kafka dedicado `catalogo-interface` e mantém em memória os 40 eventos mais recentes recebidos.
3. Em **Destino**, compare a linha com a origem. Use **Pausar sink**, espere **Pausado** e insira outro produto. Confira o evento no Kafka e a ausência da linha no destino. Use **Retomar sink** e verifique que a linha aparece. O backend consulta esse banco em transações somente leitura.

A interface mostra duas medidas de tempo para cada mudança:

- **Captura** (painel Eventos): `ts_ms − source.ts_ms`, do commit na origem até o processamento pelo Debezium.
- **Tempo até o destino** (painel Destino): do commit na origem (`source.ts_ms`) até uma consulta ao PostgreSQL de destino confirmar o estado esperado. A interface consulta o destino a cada 0,3 s, então o valor é um limite superior com essa resolução. Ele é sempre maior que o tempo de captura e, com o sink pausado, inclui o tempo de pausa.

As duas medidas usam o relógio da máquina, compartilhado pelos contêineres e pelo navegador. Se os valores parecerem estranhos no Windows (por exemplo, depois de o computador hibernar), reinicie o Docker Desktop para ressincronizar o relógio da máquina virtual. Alterações feitas pelo `psql` também entram nas medições.

O painel **Eventos** mostra o estado do conector de captura do Debezium, que acompanha o WAL e publica no Kafka, e identifica o último evento observado. O painel **Destino** mostra separadamente o estado do Debezium JDBC Sink, responsável por ler o tópico e aplicar as mudanças no segundo PostgreSQL.

Use **Consultar banco** em **Origem** ou **Destino** para abrir o resultado do `SELECT` completo de `public.produtos` no PostgreSQL escolhido. A janela da origem permite editar e excluir produtos, e a do destino é somente leitura. Use **Atualizar visualização** para consultar novamente e **SQL executado** para inspecionar a instrução. Com o sink pausado, o produto `102` aparece na tabela da origem e só passa a aparecer no destino após a retomada.

### Regenerar as evidências e os slides

Com o ambiente recém-criado pelo inicializador e Python com Playwright, `python-pptx` e Pillow (`pip install playwright python-pptx pillow` e `python -m playwright install chromium`):

```bash
python scripts/gerar-evidencias.py
python scripts/atualizar-slides.py
```

O primeiro script refaz os cinco passos da demonstração pela interface e pelo `psql`, grava as sete capturas em `evidencias/etapa-5` e o registro `verificacao.txt` com o tempo de cada passo, os eventos do Kafka e as consultas nos dois bancos. Se algo falhar, ele preserva o registro anterior e grava `falha-ensaio.png` e `verificacao-falha.txt`. O segundo substitui as capturas nos slides 14 a 19 do deck final. `scripts/validar-cronometro.py` testa a interface com dados simulados, sem Docker.

Para usar o ambiente normal, execute `docker compose up -d --build --wait` e registre os conectores com os comandos das seções anteriores. A [interface do ambiente normal](http://127.0.0.1:8000/) reutiliza seus volumes.

O modo `schema.evolution=basic` permite ao JDBC Sink criar a tabela de destino com base no esquema dos eventos e adicionar colunas ausentes. **Na demonstração, o SQL de inicialização cria `public.produtos` e o sink usa `schema.evolution=none`**. A configuração mapeia `catalogo.public.produtos` para a tabela `produtos` no esquema JDBC `public` e usa o campo `id` da chave do evento para aplicar upserts e exclusões.

As versões das imagens estão fixadas no `compose.yaml` (a do Kafka Connect também pelo digest). `insert.mode=upsert`, `delete.enabled=true`, `primary.key.mode=record_key` e o mapeamento de `id` foram validados na versão instalada pelos scripts de verificação e pelo ensaio.

Na exclusão, o conector de origem emite o evento `op=d` com a chave do produto e, em seguida, o *tombstone*, com a mesma chave e valor nulo, que permite a compactação do tópico. O ensaio confirmou os dois eventos e a remoção da linha no destino.

## Fundamentação teórica

- **Problema.** Manter uma cópia consultável do catálogo à medida que a origem muda, sem depender de uma nova cópia completa a cada alteração.
- **Conceitos.** Explicar CDC baseado em log, o papel do WAL, a decodificação lógica e a diferença entre confirmar uma transação na origem, publicar seu evento e aplicar a mudança no destino. Diferenciar também a carga inicial por *snapshot* (eventos de leitura `op=r`) do fluxo contínuo de alterações.
- **Vantagens.** A captura aproveita o log do banco e mantém o código que altera o catálogo separado do processo de sincronização. O tópico permite observar as mudanças e consumir os eventos em outro ritmo.
- **Limitações.** O destino pode ficar temporariamente defasado (quase tempo real, não tempo real estrito). A entrega é *pelo menos uma vez*: após falhas, eventos podem ser reprocessados, por isso o sink usa a chave primária e `upsert`, que é idempotente. Se o conector de origem parar de avançar, o slot retém WAL e aumenta o uso de disco (`max_slot_wal_keep_size` limita esse risco). A solução também tem mais serviços para operar.

### Garantias e cuidados

| Aspecto | O que significa no catálogo |
| --- | --- |
| **Entrega pelo menos uma vez** | Após uma falha, o conector pode reenviar eventos a partir do último offset salvo. O upsert pela chave torna a repetição inofensiva. |
| **Ordem por chave** | O Kafka garante ordem dentro de uma partição, e o Debezium usa a chave primária como chave da mensagem. Os eventos de um mesmo produto chegam em ordem. |
| **Eventos por linha** | Uma transação que altera três produtos gera três eventos. O destino pode mostrar parte da transação por um instante. |
| **REPLICA IDENTITY** | No padrão (`DEFAULT`), o campo `before` vem nulo no `UPDATE` e só com a chave no `DELETE`. Com `REPLICA IDENTITY FULL`, traz a linha antiga inteira. |
| **Mudanças de esquema** | A replicação lógica não transporta DDL. Um `ALTER TABLE` precisa ser aplicado também no destino; com `schema.evolution=none`, o sink pode falhar. |

### Comparação com triggers e polling por timestamp

O catálogo de destino precisa refletir inserções, atualizações e exclusões da origem. As três abordagens diferem na forma de detectar essas mudanças e no trabalho necessário para entregá-las ao destino.

| Abordagem | Como funciona | O que exige ou limita |
| --- | --- | --- |
| **Triggers no PostgreSQL** | Uma trigger pode registrar cada `INSERT`, `UPDATE` e `DELETE` em uma tabela de eventos, na mesma transação que altera o catálogo. | Exige instalar e manter as triggers nas tabelas monitoradas. O registro do evento acrescenta trabalho à transação de origem, e outro processo precisa encaminhá-lo ao destino. |
| **Polling por timestamp** | Um processo consulta periodicamente a tabela pelo campo `updated_at` para buscar linhas inseridas ou atualizadas desde a última leitura. | Exige manter o timestamp atualizado e executar consultas periódicas. Mudanças sucessivas na mesma linha entre consultas podem aparecer apenas como seu estado mais recente. Uma exclusão física faz a linha desaparecer da consulta, então é preciso registrar a remoção separadamente ou usar exclusão lógica. |
| **Replicação lógica nativa** | O PostgreSQL de destino assina uma publicação da origem (`CREATE SUBSCRIPTION`) e aplica as mudanças lidas do WAL. | Não usa triggers nem serviços extras e aplica cada transação inteira. Só entrega para outro PostgreSQL, atende um destino por assinatura e não guarda o histórico de mudanças para reprocessamento. |
| **Debezium com CDC baseado no WAL** | O conector lê as alterações confirmadas no log do PostgreSQL e publica eventos de inserção, atualização e exclusão. | Dispensa triggers de captura e consultas periódicas à tabela. Exige configurar a replicação lógica e monitorar o avanço do slot, pois atrasos na leitura podem aumentar a retenção de WAL. |

Se o estoque passar de **10 para 7 e depois para 4**, em duas transações confirmadas entre consultas, o polling pode enxergar apenas **4**. Se o produto for excluído fisicamente no mesmo intervalo, a consulta por `updated_at` não retorna essa exclusão. O Debezium pode capturar as duas atualizações e a exclusão como eventos separados. Isso permite que o grupo demonstre tanto o estado final do catálogo quanto as operações que levaram a ele.

**Por que Debezium, se origem e destino são PostgreSQL?** Para uma cópia simples entre dois PostgreSQL, a replicação lógica nativa é a opção mais simples. O Debezium compensa quando o destino é de outro tipo (busca, cache, data lake, outro SGBD), quando vários sistemas consomem as mesmas mudanças ou quando é preciso reler o histórico no tópico. Na demonstração já há dois consumidores do mesmo tópico: o JDBC Sink e o painel de eventos da interface. O destino PostgreSQL foi escolhido para que a verificação seja feita com SQL nos dois lados, como o enunciado exige.

## Demonstração ao vivo

Antes da apresentação, subir o ambiente com o inicializador, verificar os dois conectores e deixar abertas a interface e as duas sessões SQL (origem e destino). O [roteiro](evidencias/etapa-5/roteiro.md) traz o checklist e os comandos de recuperação. Executar cada passo separadamente e consultar o destino pelo mesmo `id` antes de seguir.

| Passo | Ação na origem | Evento esperado | Verificação no destino |
| --- | --- | --- | --- |
| 1. Inserção | Cadastrar o produto `101` com estoque `10`. | `op=c`, com a chave `101`. | O produto aparece com estoque `10`. |
| 2. Atualização | Executar `UPDATE public.produtos SET estoque = 7 WHERE id = 101;` no `psql` da origem. | `op=u`, com o novo estoque. | O mesmo produto aparece com estoque `7`. |
| 3. Exclusão | Abrir **Consultar banco** na origem e excluir o produto `101`. | `op=d`, com a chave `101`. | A consulta pelo `id` retorna zero linhas. |
| 4. Sincronização assíncrona | Pausar somente o sink, confirmar a pausa e cadastrar o produto `102`. | `op=c` aparece no tópico com o sink pausado. | O produto está na origem e ainda não aparece no destino. Depois de retomar o sink, ele aparece. |

Os resultados da tabela são os critérios de sucesso da demonstração. Durante o ensaio, registrar capturas que mostrem o SQL executado, os eventos e as consultas no destino. Para o teste de pausa, guardar uma captura antes da retomada e outra depois.

## Apresentação e entrega

A avaliação divide o trabalho em **fundamentação teórica (50%)** e **demonstração prática ao vivo (50%)**. O roteiro abaixo separa a apresentação nos três eixos exigidos e soma 21 minutos, dentro do limite de 20–25 minutos do enunciado.

- [Slides finais em PPTX](apresentacao/CDC-com-Debezium-e-PostgreSQL-final.pptx)
- [Roteiro de demonstração, consultas SQL e recuperação](evidencias/etapa-5/roteiro.md)

| Eixo | Responsável proposto | Tempo | Conteúdo |
| --- | --- | --- | --- |
| Conceitual (slides 1–8) | Lucas | 8:45 | Problema, conceitos, WAL, alternativas (triggers, polling, replicação nativa), vantagens, limitações e garantias. |
| Técnico (slides 9–13) | Renato | 4:00 | Estudo de caso, diagrama do fluxo, tópico como log, quatro pré-requisitos da origem e configuração do sink. |
| Demonstração (slides 14–20) | Renato | 7:15 | Primeiro as capturas da interface e das consultas, depois a execução ao vivo e a verificação nos dois bancos. |
| Conclusão e referências (slides 21–22) | Lucas | 1:00 | Por que usamos Debezium e quando uma cópia nativa é suficiente. |

Cada integrante apresenta pelo menos um eixo completo. Para a entrega, o grupo deve:

- A dupla respeita o limite de três integrantes. O grupo confirmou a exclusividade do Tema 10 na turma e o envio da composição e do tema ao professor (`mergen@inf.ufsm.br`).
- Cronometrar o ensaio completo com a fala de Lucas e Renato e as transições para a demonstração (tabela no final do [roteiro](evidencias/etapa-5/roteiro.md)). O tempo da sequência técnica automatizada fica registrado em `evidencias/etapa-5/verificacao.txt`.
- Incluir nos slides as capturas da solução funcionando, pois a avaliação considera o que foi realizado até a data de entrega.
- Entregar pelo Moodle os mesmos slides que serão apresentados. Basta um envio por grupo, na data comum a confirmar. A data da apresentação de cada grupo será divulgada com antecedência.

## Referências

- [Enunciado do trabalho](trabalho%20final.pdf)
- [Documentação do conector Debezium para PostgreSQL 3.4](https://debezium.io/documentation/reference/3.4/connectors/postgresql.html)
- [PostgreSQL 17 — Decodificação lógica](https://www.postgresql.org/docs/17/logicaldecoding-explanation.html)
- [PostgreSQL 17 — Replicação lógica](https://www.postgresql.org/docs/17/logical-replication.html)
- [Apache Kafka 4.1 — Introdução](https://kafka.apache.org/41/getting-started/introduction/)
- [Documentação do Debezium JDBC Sink 3.4](https://debezium.io/documentation/reference/3.4/connectors/jdbc.html)
